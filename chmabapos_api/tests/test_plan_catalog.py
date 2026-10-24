"""The plan editor renders the capability catalog the API gates on.

Before this endpoint the admin editor carried its own hardcoded list, so a new
gate could be missing from the editor (and the editor could offer a key the API
rejects). These tests pin the response to `FEATURE_CATALOG`.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.features import FEATURE_CATALOG
from app.main import app


@pytest.mark.asyncio
async def test_feature_catalog_endpoint_is_the_backend_catalog() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/plans/features")
    assert response.status_code == 200
    body = response.json()
    assert [row["key"] for row in body] == list(FEATURE_CATALOG)
    assert all(row["label"] for row in body)
