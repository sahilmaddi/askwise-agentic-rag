"""The agent's decisions (is this passage relevant? how should I search again? what is the answer? is it
supported?) come from a "brain". LLMBrain asks a chat model using the .prompty prompts; ExtractiveBrain makes the
same decisions with simple text heuristics so the whole pipeline runs, and is testable, without any model."""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Protocol

from app import prompts
from app.llm import ChatModel
from app.text import sentences, terms

CITATION = re.compile(r"\[(\d+)\]")
NOT_FOUND = "I couldn't find that in your documents."


class Brain(Protocol):
    name: str

    def grade(self, question: str, passages: list[dict], search_query: str | None = None) -> list[int]: ...

    def rewrite(self, question: str) -> str: ...

    def answer(self, question: str, passages: list[dict], search_query: str | None = None) -> Iterator[str]: ...

    def check(self, answer: str, passages: list[dict]) -> bool: ...


def _json_field(reply: str, field: str):
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0)).get(field)
    except (json.JSONDecodeError, AttributeError):
        return None


class LLMBrain:
    def __init__(self, model: ChatModel):
        self.model = model
        self.name = model.name

    def _ask(self, prompt_name: str, **inputs) -> str:
        prompt = prompts.load(prompt_name)
        return self.model.complete(prompt.render(**inputs), **prompt.parameters)

    def grade(self, question: str, passages: list[dict], search_query: str | None = None) -> list[int]:
        # The model judges against the user's own words; a rewritten query is only a search aid.
        numbers = _json_field(self._ask("grade", question=question, passages=passages), "relevant")
        valid = {p["number"] for p in passages}
        if not isinstance(numbers, list):
            return sorted(valid)  # an unreadable verdict should not throw good passages away
        return [n for n in numbers if isinstance(n, int) and n in valid]

    def rewrite(self, question: str) -> str:
        query = self._ask("rewrite", question=question).strip().strip("\"'").splitlines()
        return (query[0].strip() if query else "")[:200] or question

    def answer(self, question: str, passages: list[dict], search_query: str | None = None) -> Iterator[str]:
        prompt = prompts.load("answer")
        yield from self.model.stream(prompt.render(question=question, passages=passages), **prompt.parameters)

    def check(self, answer: str, passages: list[dict]) -> bool:
        verdict = _json_field(self._ask("check", answer=answer, passages=passages), "grounded")
        return verdict is not False


SYNONYMS = {
    "vacation": "annual leave", "holiday": "leave", "pto": "paid leave", "wfh": "remote work",
    "home": "remote", "laptop": "equipment device", "trip": "travel", "flight": "travel",
    "hotel": "accommodation", "money": "reimbursement expense", "sick": "sick leave", "boss": "manager",
    "password": "credentials authentication", "salary": "pay", "dog": "pets", "parental": "maternity paternity",
}


class ExtractiveBrain:
    """No language model: answers by quoting the sentences that best match the question."""

    name = "extractive"

    @staticmethod
    def _wanted(question: str, search_query: str | None) -> set[str]:
        # Without a model there is no understanding of synonyms, so the rewritten query's words count too.
        return set(terms(question)) | set(terms(search_query or ""))

    def grade(self, question: str, passages: list[dict], search_query: str | None = None) -> list[int]:
        wanted = self._wanted(question, search_query)
        if not wanted:
            return []
        relevant = []
        for p in passages:
            shared = wanted & set(terms(p["text"]))
            if len(shared) >= min(2, len(wanted)) or len(shared) / len(wanted) >= 0.5:
                relevant.append(p["number"])
        return relevant

    def rewrite(self, question: str) -> str:
        words = terms(question)
        extra = [SYNONYMS[w] for w in words if w in SYNONYMS]
        return " ".join(words + extra) or question

    def answer(self, question: str, passages: list[dict], search_query: str | None = None) -> Iterator[str]:
        wanted = self._wanted(question, search_query)
        candidates = []
        for p in passages:
            for position, sentence in enumerate(sentences(p["text"])):
                if sentence.startswith("#") or len(sentence) < 15:
                    continue  # headings and fragments are not answers
                overlap = len(wanted & set(terms(sentence)))
                if overlap:
                    candidates.append((overlap, p["number"], position, sentence.lstrip("*- ").rstrip()))
        if not candidates:
            yield NOT_FOUND
            return
        best = max(c[0] for c in candidates)
        chosen = sorted((c for c in candidates if c[0] >= max(1, 0.75 * best)), key=lambda c: (-c[0], c[1], c[2]))[:3]
        chosen.sort(key=lambda c: (c[1], c[2]))  # back into reading order
        for i, (_, number, _, sentence) in enumerate(chosen):
            yield ("" if i == 0 else " ") + f"{sentence} [{number}]"

    def check(self, answer: str, passages: list[dict]) -> bool:
        valid = {p["number"] for p in passages}
        cited = [int(n) for n in CITATION.findall(answer)]
        return bool(cited) and all(n in valid for n in cited)
