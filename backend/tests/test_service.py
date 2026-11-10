import pytest

from app.ingestion.extract import UnsupportedFileError
from app.service import DocumentNotFoundError, RagService


def test_ingest_lists_and_deletes_documents(service):
    docs = service.documents()
    assert len(docs) == 3
    handbook = next(d for d in docs if d.filename == "northwind-employee-handbook.md")
    assert handbook.chunks > 1 and handbook.extractor == "text"

    service.delete(handbook.id)
    assert len(service.documents()) == 2
    assert all(c["source"] != handbook.filename for c in service.ask("annual leave days")["citations"])
    with pytest.raises(DocumentNotFoundError):
        service.delete(handbook.id)


def test_duplicate_uploads_are_detected(service):
    content = b"# Parking\n\nVisitors park in bay C and register at reception."
    record, created = service.ingest("parking.md", content)
    again, created_again = service.ingest("parking-copy.md", content)
    assert created and not created_again and again.id == record.id


def test_rejects_unsupported_and_empty_files(service):
    with pytest.raises(UnsupportedFileError):
        service.ingest("virus.exe", b"MZ...")
    with pytest.raises(ValueError):
        service.ingest("empty.txt", b"")


def test_a_scanned_pdf_without_ocr_is_rejected_clearly(service):
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(UnsupportedFileError, match="No text"):
        service.ingest("scan.pdf", buffer.getvalue())


def test_index_survives_a_restart(settings, service):
    restarted = RagService(settings)
    assert len(restarted.documents()) == 3
    assert "24 days" in restarted.ask("annual leave days per year")["answer"]
    assert restarted.store.count() == restarted.registry.chunk_count()


def test_switching_embedding_model_rebuilds_the_index(settings, service):
    from dataclasses import replace

    from app.embeddings import HashingEmbedder

    rebuilt = RagService(replace(settings), embedder=HashingEmbedder(dimensions=256))
    assert rebuilt.store.count() == rebuilt.registry.chunk_count()
    assert "9,000" in rebuilt.ask("hotel limit per night in metro cities")["answer"]
