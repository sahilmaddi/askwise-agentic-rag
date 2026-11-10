"""Splits page text into overlapping chunks small enough to embed and to quote.

`recursive` follows the same idea as LangChain's RecursiveCharacterTextSplitter: split on the coarsest boundary
that exists (paragraph, line, sentence, word) and only fall back to finer ones for pieces that are still too long.
`sentence` never cuts a sentence in half; it uses spaCy's sentencizer when spaCy is installed.
"""
from __future__ import annotations

from collections.abc import Callable

from app.text import sentences as regex_sentences

SEPARATORS = ("\n\n", "\n", ". ", " ", "")


def recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    _check(chunk_size, overlap)
    return _merge(_pieces(text, SEPARATORS, chunk_size), chunk_size, overlap)


def sentence_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    _check(chunk_size, overlap)
    pieces: list[str] = []
    for sentence in _sentence_splitter()(text):
        # A single sentence longer than a chunk is still cut, on word boundaries.
        if len(sentence) > chunk_size:
            pieces.extend(_pieces(sentence + " ", SEPARATORS[3:], chunk_size))
        else:
            pieces.append(sentence + " ")
    return _merge(pieces, chunk_size, overlap)


def splitter(name: str) -> Callable[[str, int, int], list[str]]:
    if name == "sentence":
        return sentence_split
    if name == "recursive":
        return recursive_split
    raise ValueError(f"Unknown chunker '{name}'. Use 'recursive' or 'sentence'.")


def _check(chunk_size: int, overlap: int) -> None:
    if chunk_size < 50:
        raise ValueError("chunk_size must be at least 50 characters")
    if not 0 <= overlap < chunk_size:
        raise ValueError("chunk_overlap must be between 0 and chunk_size")


def _pieces(text: str, separators: tuple[str, ...], size: int) -> list[str]:
    separator = next(s for s in separators if s == "" or s in text)
    finer = separators[separators.index(separator) + 1:]
    parts = list(text) if separator == "" else text.split(separator)
    pieces: list[str] = []
    for i, part in enumerate(parts):
        piece = part + separator if separator and i < len(parts) - 1 else part
        if not piece:
            continue
        if len(piece) <= size or not finer:
            pieces.append(piece)
        else:
            pieces.extend(_pieces(piece, finer, size))
    return pieces


def _merge(pieces: list[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    window: list[str] = []
    length = 0
    for piece in pieces:
        if window and length + len(piece) > size:
            chunks.append("".join(window).strip())
            # Keep the tail of the previous chunk (up to `overlap` characters) as context for the next one.
            while window and (length > overlap or length + len(piece) > size):
                length -= len(window.pop(0))
        window.append(piece)
        length += len(piece)
    if window:
        chunks.append("".join(window).strip())
    return [chunk for chunk in chunks if chunk]


def _sentence_splitter() -> Callable[[str], list[str]]:
    try:
        import spacy

        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        return lambda text: [s.text.strip() for s in nlp(text).sents if s.text.strip()]
    except ImportError:
        return regex_sentences
