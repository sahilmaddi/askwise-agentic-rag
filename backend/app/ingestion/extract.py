"""Turns an uploaded file into text, page by page.

- Plain text and Markdown are decoded directly.
- PDFs with a text layer are read with pypdf.
- Everything else (Word, PowerPoint, HTML, scanned PDFs...) goes to Apache Tika when TIKA_URL is set.
- Azure AI Document Intelligence (OCR + layout) takes over when its endpoint and key are configured.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import PurePath

from app.config import Settings

TEXT_TYPES = {".txt", ".md", ".markdown", ".csv", ".json", ".log"}
TIKA_TYPES = {".docx", ".doc", ".pptx", ".xlsx", ".html", ".htm", ".rtf", ".odt", ".epub", ".eml"}


class UnsupportedFileError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedDocument:
    pages: list[tuple[int | None, str]]
    extractor: str

    @property
    def text_length(self) -> int:
        return sum(len(text) for _, text in self.pages)


def supported_extensions(settings: Settings) -> set[str]:
    extensions = TEXT_TYPES | {".pdf"}
    if settings.tika_url or settings.azure_docintel_endpoint:
        extensions |= TIKA_TYPES | {".png", ".jpg", ".jpeg", ".tiff"}
    return extensions


def extract(filename: str, data: bytes, settings: Settings) -> ExtractedDocument:
    extension = PurePath(filename).suffix.lower()
    if extension not in supported_extensions(settings):
        raise UnsupportedFileError(
            f"'{extension or filename}' files are not supported here. "
            f"Supported: {', '.join(sorted(supported_extensions(settings)))}"
        )
    if settings.azure_docintel_endpoint and settings.azure_docintel_key and extension not in TEXT_TYPES:
        return _azure_document_intelligence(data, settings)
    if extension in TEXT_TYPES:
        return ExtractedDocument([(None, _decode(data))], "text")
    if extension == ".pdf":
        document = _pdf(data)
        # A PDF with no text layer is a scan: hand it to Tika (which can run OCR) if available.
        if document.text_length > 20 or not settings.tika_url:
            return document
    return _tika(data, settings.tika_url)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedFileError("Could not decode the file as text")


def _pdf(data: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[tuple[int | None, str]] = [
        (number, page.extract_text() or "") for number, page in enumerate(reader.pages, start=1)
    ]
    return ExtractedDocument(pages, "pypdf")


def _tika(data: bytes, tika_url: str) -> ExtractedDocument:
    import httpx

    response = httpx.put(
        f"{tika_url.rstrip('/')}/tika",
        content=data,
        headers={"Accept": "text/plain", "X-Tika-OCRLanguage": "eng"},
        timeout=120,
    )
    response.raise_for_status()
    return ExtractedDocument([(None, response.text)], "tika")


def _azure_document_intelligence(data: bytes, settings: Settings) -> ExtractedDocument:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    credential = AzureKeyCredential(settings.azure_docintel_key)
    client = DocumentIntelligenceClient(settings.azure_docintel_endpoint, credential)
    result = client.begin_analyze_document("prebuilt-layout", body=data).result()
    pages: list[tuple[int | None, str]] = [
        (page.page_number, "\n".join(line.content for line in (page.lines or [])))
        for page in (result.pages or [])
    ]
    return ExtractedDocument(pages, "azure-document-intelligence")
