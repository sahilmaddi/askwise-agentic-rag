"""HTTP API. Run with: uvicorn app.main:app --reload"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import telemetry
from app.config import Settings
from app.ingestion.extract import UnsupportedFileError, supported_extensions
from app.service import DocumentNotFoundError, RagService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("askwise")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)


def create_app(settings: Settings | None = None, service: RagService | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service or RagService(settings)
        if settings.seed_samples:
            added = app.state.service.seed_samples()
            log.info("Seeded %d sample documents", added)
        log.info("Ready: %s", app.state.service.info())
        yield

    # Docs live under /api so they work through the same proxy as the API itself.
    app = FastAPI(title="Askwise API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs",
                  redoc_url=None, openapi_url="/api/openapi.json",
                  description="Agentic RAG over your documents, with citations for every answer.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                       allow_headers=["*"])
    app.state.telemetry = telemetry.setup(app)

    def rag(request: Request) -> RagService:
        return request.app.state.service

    @app.exception_handler(ValueError)
    async def bad_request(_: Request, exc: ValueError):
        status = 415 if isinstance(exc, UnsupportedFileError) else 400
        return JSONResponse({"detail": str(exc)}, status_code=status)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/info")
    def info(request: Request):
        return {**rag(request).info(), "telemetry": request.app.state.telemetry,
                "acceptedFiles": sorted(supported_extensions(settings))}

    @app.get("/api/documents")
    def documents(request: Request):
        return [d.to_dict() for d in rag(request).documents()]

    @app.post("/api/documents", status_code=201)
    def upload(request: Request, files: list[UploadFile] = File(...)):
        results = []
        for upload_file in files:
            data = upload_file.file.read()
            record, created = rag(request).ingest(upload_file.filename or "document.txt", data)
            results.append({**record.to_dict(), "duplicate": not created})
        return results

    @app.delete("/api/documents/{document_id}", status_code=204)
    def delete(request: Request, document_id: str):
        try:
            rag(request).delete(document_id)
        except DocumentNotFoundError:
            raise HTTPException(404, "Document not found") from None

    @app.post("/api/ask")
    def ask(request: Request, body: AskRequest):
        return rag(request).ask(body.question, body.top_k)

    @app.post("/api/ask/stream")
    def ask_stream(request: Request, body: AskRequest):
        """Server-sent events: `step` as each agent step finishes, `token` as the answer is written, then `done`."""
        events = rag(request).ask_events(body.question, body.top_k)

        def stream():
            try:
                for event in events:
                    yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:  # the response has started, so report the failure as an event
                log.exception("Answer failed")
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


app = create_app()
