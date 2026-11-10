"""The agentic RAG loop (a corrective-RAG graph):

    route ──small talk──▶ reply
      │ ──no documents──▶ reply
      ▼
    retrieve ◀───────────────┐
      ▼                      │
    grade ──none relevant──▶ rewrite (at most MAX_REWRITES times)
      │ ──still nothing────▶ "couldn't find it" (never guesses)
      ▼
    generate (streamed, cites [n]) ▶ cite ▶ check groundedness ▶ done

Each node is timed and traced, and reported to the caller as it happens so the UI can show the agent's work.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from time import perf_counter

from app import telemetry
from app.agent.brains import CITATION, NOT_FOUND, Brain
from app.models import Answer, Citation, ScoredChunk, Step
from app.retrieval.hybrid import HybridRetriever

SMALL_TALK = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|thx|good (morning|afternoon|evening)|who are you\??)[\s!.?]*$",
    re.IGNORECASE,
)
GREETING = (
    "Hi! I answer questions using the documents in your library, with a citation for every fact. "
    "What would you like to know?"
)
EMPTY_LIBRARY = "Your library is empty. Upload a document (PDF, Word, Markdown or text) and ask me about it."


@dataclass
class AgentState:
    question: str
    query: str
    steps: list[Step] = field(default_factory=list)
    hits: list[ScoredChunk] = field(default_factory=list)
    relevant: list[ScoredChunk] = field(default_factory=list)
    rewrites: int = 0


class RagAgent:
    def __init__(self, retriever: HybridRetriever, brain: Brain, has_documents: Callable[[], bool],
                 top_k: int = 5, max_rewrites: int = 1):
        self.retriever, self.brain, self.has_documents = retriever, brain, has_documents
        self.top_k, self.max_rewrites = top_k, max_rewrites

    def run(self, question: str, top_k: int | None = None) -> Iterator[dict]:
        """Yields {"type": "step"}, {"type": "token"} and finally {"type": "done", "answer": {...}} events."""
        k = top_k or self.top_k
        state = AgentState(question=question.strip(), query=question.strip())
        started = perf_counter()
        with telemetry.span("agent.run", question_length=len(state.question), top_k=k):
            route, event = self._node(state, "route", lambda: self._route(state))
            yield event
            if route != "retrieve":
                text = GREETING if route == "small_talk" else EMPTY_LIBRARY
                yield {"type": "token", "text": text}
                yield self._done(state, Answer(state.question, text, steps=state.steps), started)
                return

            while True:
                _, event = self._node(state, "retrieve", lambda: self._retrieve(state, k))
                yield event
                _, event = self._node(state, "grade", lambda: self._grade(state))
                yield event
                if state.relevant or state.rewrites >= self.max_rewrites or not state.hits:
                    break
                _, event = self._node(state, "rewrite", lambda: self._rewrite(state))
                yield event

            if not state.relevant:
                yield {"type": "token", "text": NOT_FOUND}
                answer = Answer(state.question, NOT_FOUND, steps=state.steps, search_query=self._query(state))
                yield self._done(state, answer, started)
                return

            passages = [
                {"number": i, "source": h.chunk.source, "page": h.chunk.page, "text": h.chunk.text}
                for i, h in enumerate(state.relevant, start=1)
            ]
            parts: list[str] = []
            start = perf_counter()
            with telemetry.span("agent.generate", model=self.brain.name, passages=len(passages)):
                for token in self.brain.answer(state.question, passages, self._query(state)):
                    parts.append(token)
                    yield {"type": "token", "text": token}
            text = "".join(parts).strip()
            yield self._record(state, "generate", f"Wrote the answer with {self.brain.name} from "
                                                  f"{len(passages)} passage{'s' if len(passages) != 1 else ''}", start)

            citations, event = self._node(state, "cite", lambda: self._cite(text, state.relevant))
            yield event
            grounded = True
            if text != NOT_FOUND:
                cited = [p for p in passages if p["number"] in {c.number for c in citations}] or passages
                grounded, event = self._node(state, "check", lambda: self._check(text, cited))
                yield event
            answer = Answer(state.question, text, citations, state.steps, grounded, self._query(state))
            yield self._done(state, answer, started)

    # --- nodes: each returns (result, human-readable detail) ---

    def _route(self, state: AgentState) -> tuple[str, str]:
        if SMALL_TALK.match(state.question):
            return "small_talk", "Small talk, so no search is needed"
        if not self.has_documents():
            return "empty", "The library has no documents yet"
        return "retrieve", "Question needs the documents: searching"

    def _retrieve(self, state: AgentState, k: int) -> tuple[None, str]:
        state.hits = self.retriever.retrieve(state.query, k)
        return None, f"Found {len(state.hits)} passages for “{state.query}” (vector + keyword search, fused with RRF)"

    def _grade(self, state: AgentState) -> tuple[None, str]:
        passages = [{"number": i, "text": h.chunk.text} for i, h in enumerate(state.hits, start=1)]
        keep = set(self.brain.grade(state.question, passages, self._query(state))) if passages else set()
        state.relevant = [h for i, h in enumerate(state.hits, start=1) if i in keep]
        return None, f"{len(state.relevant)} of {len(state.hits)} passages are relevant"

    def _rewrite(self, state: AgentState) -> tuple[None, str]:
        state.rewrites += 1
        state.query = self.brain.rewrite(state.question)
        telemetry.rewrites.add(1)
        return None, f"Nothing relevant, so the search was rewritten as “{state.query}”"

    @staticmethod
    def _cite(text: str, relevant: list[ScoredChunk]) -> tuple[list[Citation], str]:
        used = sorted({int(n) for n in CITATION.findall(text) if 1 <= int(n) <= len(relevant)})
        citations = [
            Citation(n, relevant[n - 1].chunk.document_id, relevant[n - 1].chunk.source, relevant[n - 1].chunk.page,
                     relevant[n - 1].chunk.text, relevant[n - 1].score)
            for n in used
        ]
        return citations, f"Cited {len(citations)} of {len(relevant)} passages"

    def _check(self, text: str, cited: list[dict]) -> tuple[bool, str]:
        grounded = self.brain.check(text, cited)
        return grounded, ("Every statement is supported by the cited passages" if grounded
                          else "Some statements may not be supported by the passages")

    # --- plumbing ---

    def _node(self, state: AgentState, name: str, fn):
        start = perf_counter()
        with telemetry.span(f"agent.{name}"):
            result, detail = fn()
        return result, self._record(state, name, detail, start)

    @staticmethod
    def _record(state: AgentState, name: str, detail: str, start: float) -> dict:
        ms = round((perf_counter() - start) * 1000, 1)
        step = Step(name, detail, ms)
        state.steps.append(step)
        telemetry.step_latency.record(ms, {"step": name})
        return {"type": "step", "step": asdict(step)}

    @staticmethod
    def _query(state: AgentState) -> str | None:
        return state.query if state.query != state.question else None

    @staticmethod
    def _done(state: AgentState, answer: Answer, started: float) -> dict:
        telemetry.questions.add(1, {"outcome": "answered" if answer.citations else "no_answer"})
        telemetry.question_latency.record((perf_counter() - started) * 1000)
        return {"type": "done", "answer": answer.to_dict()}
