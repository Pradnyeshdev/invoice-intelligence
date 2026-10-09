"""Select the configured storage implementation.

SQLite and filesystem storage are the only supported implementation here.
"""

import os


LOCAL_STORAGE = "local"


def configured_storage_backend(value: str | None = None) -> str:
    """Return the explicitly configured backend, defaulting to local storage."""
    backend = (
        value if value is not None else os.getenv("STORAGE_BACKEND", LOCAL_STORAGE)
    ).strip().lower()
    if backend != LOCAL_STORAGE:
        raise ValueError("STORAGE_BACKEND currently supports only 'local'.")
    return backend


def get_storage_backend():
    """Return the local SQLite and filesystem implementations."""
    configured_storage_backend()

    # Lazy imports avoid coupling the contracts/configuration module to app services.
    from app.repositories import invoices
    from app.services.uploads import LocalUploadedDocumentStore

    return invoices, LocalUploadedDocumentStore()
