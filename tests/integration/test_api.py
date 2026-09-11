"""Integration tests for HTTP API."""

from __future__ import annotations

from app.core.exceptions import ProviderError
from app.main import create_app
from app.repositories.memory_repository import MemoryReviewRepository
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "codeassistai"


def test_create_and_get_review(client: TestClient) -> None:
    create = client.post(
        "/api/v1/reviews",
        json={
            "code": "def divide(a, b):\n    return a / b\n",
            "language": "python",
            "file_name": "math_utils.py",
            "review_types": ["logic", "readability", "security", "performance", "testing"],
            "severity_threshold": "low",
            "include_summary": True,
        },
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "completed"
    assert body["summary"] is not None
    assert isinstance(body["findings"], list)
    assert body["metadata"]["provider"] == "mock"

    review_id = body["review_id"]
    fetched = client.get(f"/api/v1/reviews/{review_id}")
    assert fetched.status_code == 200
    assert fetched.json()["review_id"] == review_id


def test_feedback_submission(client: TestClient) -> None:
    create = client.post(
        "/api/v1/reviews",
        json={"code": "def divide(a, b):\n    return a / b\n", "language": "python"},
    )
    review = create.json()
    finding_id = review["findings"][0]["finding_id"] if review["findings"] else None
    feedback = client.post(
        f"/api/v1/reviews/{review['review_id']}/feedback",
        json={
            "finding_id": finding_id,
            "feedback_type": "useful",
            "comment": "Correctly identified missing validation.",
        },
    )
    assert feedback.status_code == 201
    assert feedback.json()["feedback_type"] == "useful"


def test_invalid_language(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reviews",
        json={"code": "print(1)", "language": "brainfuck"},
    )
    assert response.status_code == 422


def test_empty_code(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reviews",
        json={"code": "   ", "language": "python"},
    )
    assert response.status_code == 422


def test_oversized_code(settings, mock_provider, repository) -> None:
    application = create_app()
    application.state.settings = settings
    application.state.provider = mock_provider
    application.state.repository = repository
    # settings fixture max_code_length is 1000
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/reviews",
            json={"code": "x" * 1001, "language": "python"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_missing_review(client: TestClient) -> None:
    response = client.get("/api/v1/reviews/review-does-not-exist")
    assert response.status_code == 404


class BoomProvider:
    name = "boom"
    model_name = "boom-model"

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        raise ProviderError("simulated provider failure")


def test_provider_failure() -> None:
    application = create_app()
    application.state.provider = BoomProvider()
    application.state.repository = MemoryReviewRepository()
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/reviews",
            json={"code": "print(1)", "language": "python"},
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"


class BadJsonProvider:
    name = "badjson"
    model_name = "badjson-model"

    def generate_review(self, code: str, language: str, prompt: str) -> str:
        return "<<<not-json>>>"


def test_malformed_model_response() -> None:
    application = create_app()
    application.state.provider = BadJsonProvider()
    application.state.repository = MemoryReviewRepository()
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/reviews",
            json={"code": "print(1)", "language": "python"},
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "parse_error"


def test_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
