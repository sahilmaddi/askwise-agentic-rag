"""Chat model providers, all through LangChain's common chat interface.

ollama   open models served locally by Ollama (default meta llama3.2)
openai   OpenAI
azure    Azure OpenAI (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_API_VERSION)
mistral  Mistral AI
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from app.config import Settings


class ChatModel(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]], **parameters) -> str: ...

    def stream(self, messages: list[dict[str, str]], **parameters) -> Iterator[str]: ...


class LangChainChatModel:
    def __init__(self, model, name: str):
        self._model = model
        self.name = name

    @staticmethod
    def _convert(messages: list[dict[str, str]]) -> list[tuple[str, str]]:
        roles = {"system": "system", "user": "human", "assistant": "ai"}
        return [(roles[m["role"]], m["content"]) for m in messages]

    def _bound(self, parameters: dict):
        allowed = {k: v for k, v in parameters.items() if k in {"temperature", "max_tokens"}}
        return self._model.bind(**allowed) if allowed else self._model

    def complete(self, messages: list[dict[str, str]], **parameters) -> str:
        return str(self._bound(parameters).invoke(self._convert(messages)).content)

    def stream(self, messages: list[dict[str, str]], **parameters) -> Iterator[str]:
        for part in self._bound(parameters).stream(self._convert(messages)):
            if part.content:
                yield str(part.content)


def build_chat_model(settings: Settings) -> ChatModel | None:
    """None means the offline extractive mode: no language model at all."""
    provider, model = settings.llm_provider, settings.llm_model
    if provider == "extractive":
        return None
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = model or "llama3.2:1b"
        return LangChainChatModel(ChatOllama(model=model, base_url=settings.ollama_base_url), f"ollama/{model}")
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = model or "gpt-4o-mini"
        return LangChainChatModel(ChatOpenAI(model=model), f"openai/{model}")
    if provider == "azure":
        from langchain_openai import AzureChatOpenAI

        model = model or "gpt-4o-mini"
        return LangChainChatModel(AzureChatOpenAI(azure_deployment=model), f"azure/{model}")
    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        model = model or "mistral-small-latest"
        return LangChainChatModel(ChatMistralAI(model=model), f"mistral/{model}")
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'")
