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
always map to the same URL. ``MediaAsset`` rows catalogue these files so the UI
can browse and reuse them; because every upload becomes a catalogued asset, a
file that is no longer attached to a product is still a reusable library item
rather than an orphan.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MediaAsset


def _media_root() -> Path:
    return Path(settings.media_root)


def content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def store_image(content: bytes, suffix: str, company_id: UUID) -> str:
    """Persist ``content`` for ``company_id`` and return its public URL.

    Idempotent: if a file with the same digest already exists it is reused, not
    rewritten.
    """
    digest = content_digest(content)
    relative = Path("companies") / str(company_id) / digest[:2] / f"{digest}{suffix}"
    target = _media_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    return f"{settings.media_url_prefix}/{relative.as_posix()}"


async def upsert_media_asset(
    db: AsyncSession,
    *,
    company_id: UUID,
    created_by: UUID | None,
    content: bytes,
    suffix: str,
    filename: str | None,
    content_type: str | None,
) -> MediaAsset:
    """Catalogue an uploaded image, reusing the row for identical bytes.

    Flushes so the caller can reference ``asset.id`` in the same transaction.
    """
    digest = content_digest(content)
    existing = (await db.execute(select(MediaAsset).where(MediaAsset.company_id == company_id, MediaAsset.sha256 == digest))).scalar_one_or_none()
    if existing:
        return existing
    url = store_image(content, suffix, company_id)
    asset = MediaAsset(company_id=company_id, sha256=digest, url=url, content_type=content_type, byte_size=len(content), original_filename=filename, created_by=created_by)
    db.add(asset)
    await db.flush()
    return asset


def delete_by_url(url: str) -> None:
    """Best-effort removal of a stored file, refusing to escape the media root."""
    prefix = f"{settings.media_url_prefix}/"
    if not url.startswith(prefix):
        return
    relative = url[len(prefix):]
    root = _media_root().resolve()
    target = (root / relative).resolve()
    if target != root and root in target.parents and target.is_file():
        target.unlink()


def store_platform_image(content: bytes, suffix: str) -> str:
    """Persist a platform-level image (mailing assets) and return its URL.

    Unlike ``store_image`` this is not tenant-scoped: mailing images are
    authored by platform admins and embedded in email, so they live under a
    single ``platform/mailing`` tree and are content-addressed like everything
    else.
    """
    digest = content_digest(content)
    relative = Path("platform") / "mailing" / digest[:2] / f"{digest}{suffix}"
    target = _media_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    return f"{settings.media_url_prefix}/{relative.as_posix()}"
