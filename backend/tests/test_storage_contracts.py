import asyncio

import pytest

from app.repositories import invoices as invoice_repository
from app.services import uploads
from app.storage.config import configured_storage_backend, get_storage_backend
from app.storage.contracts import InvoiceMetadataStore, UploadedDocumentStore


def test_storage_backend_defaults_to_local(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)

    assert configured_storage_backend() == "local"
    selected_repository, selected_documents = get_storage_backend()
    assert selected_repository is invoice_repository
    assert isinstance(selected_repository, InvoiceMetadataStore)
    assert isinstance(selected_documents, UploadedDocumentStore)


def test_storage_backend_can_be_explicitly_set_to_local():
    assert configured_storage_backend("local") == "local"


def test_unsupported_storage_backend_is_rejected():
    with pytest.raises(ValueError, match="only 'local'"):
        configured_storage_backend("vercel_blob")


def test_local_document_store_saves_finds_and_deletes(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    store = uploads.LocalUploadedDocumentStore()

    async def chunks():
        yield b"%PDF-1.7\n"
        yield b"synthetic test bytes"

    upload_id = "a" * 32
    size = asyncio.run(store.save_upload(upload_id, ".pdf", chunks()))
    found = store.find_upload(upload_id)

    assert size == len(b"%PDF-1.7\nsynthetic test bytes")
    assert found == (tmp_path / f"{upload_id}.pdf", ".pdf")
    assert found[0].read_bytes() == b"%PDF-1.7\nsynthetic test bytes"

    store.delete_upload(upload_id)
    assert store.find_upload(upload_id) is None


def test_local_document_store_does_not_accept_unsafe_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    store = uploads.LocalUploadedDocumentStore()

    assert store.find_upload("../private") is None
    store.delete_upload("../private")
    assert list(tmp_path.iterdir()) == []
