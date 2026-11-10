"""Wires the pipeline together: extract ▶ chunk ▶ embed ▶ index (vector + keyword) ▶ agent."""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import uuid
from collections.abc import Iterator
from pathlib import Path

from app import telemetry
from app.agent.brains import Brain, ExtractiveBrain, LLMBrain
from app.agent.graph import RagAgent
from app.config import Settings
from app.embeddings import Embedder, build_embedder
from app.ingestion.chunking import splitter
from app.ingestion.extract import UnsupportedFileError, extract
from app.llm import build_chat_model
from app.models import Chunk, DocumentRecord
from app.registry import Registry, now_iso
from app.retrieval.bm25 import BM25Index
from app.retrieval.hybrid import HybridRetriever
from app.vectorstores.base import VectorStore
from app.vectorstores.factory import build_vector_store

log = logging.getLogger(__name__)
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class DocumentNotFoundError(LookupError):
    pass


class RagService:
    def __init__(self, settings: Settings, embedder: Embedder | None = None, store: VectorStore | None = None,
                 brain: Brain | None = None, registry: Registry | None = None):
        self.settings = settings
        self.embedder = embedder or build_embedder(settings)
        self.store = store or build_vector_store(settings, self.embedder.name)
        self.registry = registry or Registry(settings.data_dir / "askwise.db")
        if brain is None:
            model = build_chat_model(settings)
            brain = LLMBrain(model) if model else ExtractiveBrain()
        self.brain = brain
        self.split = splitter(settings.chunker)
        self.keywords = BM25Index()
        chunks = self.registry.chunks()
        self.keywords.add([(c.id, c.text) for c in chunks])
        if chunks and self.store.count() != len(chunks):
            # The vector index is missing or was built with another model: rebuild it from the stored chunks.
            log.info("Re-embedding %d chunks into %s/%s", len(chunks), self.store.name, self.embedder.name)
            self._index_vectors(chunks)
        retriever = HybridRetriever(self.embedder, self.store, self.keywords, self.registry)
        self.agent = RagAgent(retriever, self.brain, lambda: len(self.keywords) > 0, settings.top_k,
                              settings.max_rewrites)

    def ingest(self, filename: str, data: bytes) -> tuple[DocumentRecord, bool]:
        """Returns the document and whether it was newly added (False when identical content already exists)."""
        if not data:
            raise ValueError("The file is empty")
        if len(data) > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"Files are limited to {self.settings.max_upload_mb} MB")
        digest = hashlib.sha256(data).hexdigest()
        existing = self.registry.find_by_hash(digest)
        if existing:
            return existing, False
        with telemetry.span("ingest", filename=filename, bytes=len(data)):
            with telemetry.span("ingest.extract"):
                extracted = extract(filename, data, self.settings)
            document_id = uuid.uuid4().hex[:12]
            with telemetry.span("ingest.chunk", chunker=self.settings.chunker):
                chunks = [
                    Chunk(f"{document_id}-{i}", document_id, filename, i, text, page)
                    for i, (page, text) in enumerate(
                        (page, piece)
                        for page, page_text in extracted.pages
                        for piece in self.split(page_text, self.settings.chunk_size, self.settings.chunk_overlap)
                    )
                ]
            if not chunks:
                raise UnsupportedFileError("No text could be extracted from this file")
            record = DocumentRecord(
                document_id, filename, mimetypes.guess_type(filename)[0] or "application/octet-stream", len(data),
                len(extracted.pages), len(chunks), extracted.extractor, now_iso(),
            )
            self._index_vectors(chunks)
            self.keywords.add([(c.id, c.text) for c in chunks])
            self.registry.add(record, digest, chunks)
            telemetry.ingested_chunks.add(len(chunks), {"extractor": extracted.extractor})
        return record, True

    def delete(self, document_id: str) -> None:
        ids = self.registry.delete(document_id)
        if not ids:
            raise DocumentNotFoundError(document_id)
        self.store.delete(ids)
        self.keywords.delete(ids)

    def documents(self) -> list[DocumentRecord]:
        return self.registry.documents()

    def ask_events(self, question: str, top_k: int | None = None) -> Iterator[dict]:
        if not question.strip():
            raise ValueError("Ask a question")
        return self.agent.run(question, top_k)

    def ask(self, question: str, top_k: int | None = None) -> dict:
        """Runs the agent to completion and returns the answer (see models.Answer) as a dict."""
        for event in self.ask_events(question, top_k):
            if event["type"] == "done":
                return event["answer"]
        raise RuntimeError("The agent finished without an answer")

    def info(self) -> dict:
        return {
            "llm": self.brain.name,
            "embeddings": self.embedder.name,
            "vectorStore": self.store.name,
            "chunker": self.settings.chunker,
            "chunkSize": self.settings.chunk_size,
            "extractors": ["text", "pypdf"]
            + (["tika"] if self.settings.tika_url else [])
            + (["azure-document-intelligence"] if self.settings.azure_docintel_endpoint else []),
            "documents": len(self.registry.documents()),
            "chunks": self.registry.chunk_count(),
        }

    def seed_samples(self) -> int:
        added = 0
        for path in sorted(SAMPLES.glob("*.md")):
            _, new = self.ingest(path.name, path.read_bytes())
            added += new
        return added

    def _index_vectors(self, chunks: list[Chunk]) -> None:
        with telemetry.span("ingest.embed", model=self.embedder.name, chunks=len(chunks)):
            for start in range(0, len(chunks), 64):
                batch = chunks[start:start + 64]
                self.store.add([c.id for c in batch], self.embedder.embed_documents([c.text for c in batch]))
