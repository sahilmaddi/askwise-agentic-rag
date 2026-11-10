"""Loads .prompty files: YAML front matter (name, model parameters, sample inputs) followed by a Jinja2 chat
template with `system:` / `user:` / `assistant:` role markers. Keeping prompts as files lets them be reviewed,
versioned and tried out in the Prompty VS Code extension without touching Python."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

_ROLE = re.compile(r"^(system|user|assistant):\s*$", re.MULTILINE)
_ENV = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, autoescape=False)


@dataclass(frozen=True)
class Prompty:
    name: str
    parameters: dict
    sample: dict
    template: str

    def render(self, **inputs) -> list[dict[str, str]]:
        text = _ENV.from_string(self.template).render(**inputs)
        parts = _ROLE.split(text)
        messages = [
            {"role": role, "content": content.strip()}
            for role, content in zip(parts[1::2], parts[2::2], strict=True)
            if content.strip()
        ]
        if not messages:
            raise ValueError(f"Prompt '{self.name}' rendered no messages")
        return messages


def parse(source: str) -> Prompty:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", source, re.DOTALL)
    if not match:
        raise ValueError("A .prompty file starts with YAML front matter between --- lines")
    meta = yaml.safe_load(match.group(1)) or {}
    return Prompty(
        name=meta.get("name", "prompt"),
        parameters=(meta.get("model") or {}).get("parameters") or {},
        sample=meta.get("sample") or {},
        template=match.group(2),
    )


@cache
def load(name: str) -> Prompty:
    return parse((Path(__file__).parent / f"{name}.prompty").read_text(encoding="utf-8"))
