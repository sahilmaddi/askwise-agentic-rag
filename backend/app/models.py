from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    source: str
    index: int
    text: str
    page: int | None = None


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    filename: str
    content_type: str
    size_bytes: int
    pages: int
    chunks: int
    extractor: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Citation:
    number: int
    document_id: str
    source: str
    page: int | None
    text: str
    score: float


@dataclass(frozen=True)
class Step:
    name: str
    detail: str
    ms: float


@dataclass
class Answer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    grounded: bool = True
    search_query: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
