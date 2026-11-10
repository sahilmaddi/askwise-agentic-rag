"""HTTP tests. They need FastAPI and httpx (installed from requirements-dev.txt)."""
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def client(settings):
    from dataclasses import replace

    with TestClient(create_app(replace(settings, seed_samples=True))) as test_client:
        yield test_client


def test_info_and_documents(client):
    info = client.get("/api/info").json()
    assert info["llm"] == "extractive" and info["documents"] == 3
    assert len(client.get("/api/documents").json()) == 3


def test_upload_ask_and_delete(client):
    files = [("files", ("pets.md", b"# Pets\n\nDogs are welcome in the Pune office on Fridays.", "text/markdown"))]
    created = client.post("/api/documents", files=files)
    assert created.status_code == 201 and created.json()[0]["duplicate"] is False
    assert client.post("/api/documents", files=files).json()[0]["duplicate"] is True

    answer = client.post("/api/ask", json={"question": "Are dogs welcome in the Pune office?"}).json()
    assert "Fridays" in answer["answer"] and answer["citations"][0]["source"] == "pets.md"

    assert client.delete(f"/api/documents/{created.json()[0]['id']}").status_code == 204
    assert client.delete(f"/api/documents/{created.json()[0]['id']}").status_code == 404


def test_streaming_answer_sends_steps_tokens_and_done(client):
    with client.stream("POST", "/api/ask/stream", json={"question": "How long is the notice period?"}) as response:
        body = "".join(response.iter_text())
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "step" and events[-1]["type"] == "done"
    assert "60 days" in events[-1]["answer"]["answer"]


def test_validation_errors(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "   "}).status_code == 400
    bad = client.post("/api/documents", files=[("files", ("a.exe", b"MZ", "application/octet-stream"))])
    assert bad.status_code == 415
