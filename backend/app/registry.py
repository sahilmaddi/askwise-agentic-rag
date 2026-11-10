"""SQLite record of documents and their chunks: the source of truth for chunk text and citations."""
from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.models import Chunk, DocumentRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
    pages INTEGER NOT NULL, chunks INTEGER NOT NULL, extractor TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL, page INTEGER, text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
"""


class Registry:
    def __init__(self, path: Path | str):
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def find_by_hash(self, sha256: str) -> DocumentRecord | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
        return _document(row) if row else None

    def add(self, record: DocumentRecord, sha256: str, chunks: list[Chunk]) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record.id, record.filename, record.content_type, record.size_bytes, record.pages, record.chunks,
                 record.extractor, sha256, record.created_at),
            )
            self._db.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?)",
                [(c.id, c.document_id, c.index, c.page, c.text) for c in chunks],
            )

    def delete(self, document_id: str) -> list[str]:
        """Removes a document and returns the ids of its chunks, or [] if it did not exist."""
        with self._lock, self._db:
            ids = [r["id"] for r in self._db.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))]
            deleted = self._db.execute("DELETE FROM documents WHERE id = ?", (document_id,)).rowcount
        return ids if deleted else []

    def documents(self) -> list[DocumentRecord]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [_document(r) for r in rows]

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return _document(row) if row else None

    def chunks(self, ids: list[str] | None = None) -> list[Chunk]:
        query = ("SELECT c.*, d.filename FROM chunks c JOIN documents d ON d.id = c.document_id")
        with self._lock:
            if ids is None:
                rows = self._db.execute(query + " ORDER BY d.created_at, c.idx").fetchall()
            else:
                rows = []
                for start in range(0, len(ids), 500):
                    batch = ids[start:start + 500]
                    marks = ",".join("?" * len(batch))
                    rows += self._db.execute(f"{query} WHERE c.id IN ({marks})", batch).fetchall()
        return [Chunk(r["id"], r["document_id"], r["filename"], r["idx"], r["text"], r["page"]) for r in rows]

    def chunk_count(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _document(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(row["id"], row["filename"], row["content_type"], row["size_bytes"], row["pages"],
                          row["chunks"], row["extractor"], row["created_at"])
