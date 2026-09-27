"""Content-addressed media storage, scoped per company.

An upload is stored under its SHA-256 digest inside the owning company's
directory::

    <media_root>/companies/<company_id>/<sha[:2]>/<sha><ext>

Two consequences fall out of this shape:

* **Dedup** — identical bytes within one company always resolve to the same
  path and URL, so re-uploading the same picture costs nothing extra.
* **Tenant isolation** — a file physically lives under exactly one company, so
  one tenant's media can never be read from another tenant's path.

The URL written to the database is derived from the digest, so the same bytes
always map to the same URL.

Orphan cleanup is intentionally deferred: a file may be referenced by more than
one product or variant, so removing it safely needs reference counting (see the
media library work). Until then, replacing an image leaves its old file on disk.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from app.config import settings


def _media_root() -> Path:
    return Path(settings.media_root)


def store_image(content: bytes, suffix: str, company_id: UUID) -> str:
    """Persist ``content`` for ``company_id`` and return its public URL.

    Idempotent: if a file with the same digest already exists it is reused, not
    rewritten.
    """
    digest = hashlib.sha256(content).hexdigest()
    relative = Path("companies") / str(company_id) / digest[:2] / f"{digest}{suffix}"
    target = _media_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    return f"{settings.media_url_prefix}/{relative.as_posix()}"
