import pytest

from app.main import configured_cors_origins


def test_cors_defaults_to_local_frontend_origins() -> None:
    assert configured_cors_origins(None) == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_uses_configured_origins_and_removes_duplicates() -> None:
    assert configured_cors_origins(
        "https://invoice.example, http://localhost:5173/, https://invoice.example"
    ) == ["https://invoice.example", "http://localhost:5173"]


def test_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(ValueError, match="explicit origins"):
        configured_cors_origins("*")
