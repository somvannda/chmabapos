from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_ROOT / "scripts" / "reconcile_serial_stock.py"


async def _setup_store(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = f"reconcile-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Reconcile Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Reconcile Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    body = setup.json()
    return {**headers, "X-Store-ID": body["store"]["id"]}, body["store"]["id"], body["company"]["id"]


@pytest.mark.asyncio
async def test_reconcile_script_rewrites_a_drifted_balance() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id, company_id = await _setup_store(client)

        product = await client.post("/api/v1/products", headers=headers, json={"name": "Drift Laptop", "sku": f"DR-{uuid.uuid4().hex[:8]}", "price": "100.00", "track_serials": True})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        variants = await client.put(f"/api/v1/products/{product_id}/variants", headers=headers, json={"variants": [{"sku": f"DR-A-{uuid.uuid4().hex[:6]}", "name": "128GB"}]})
        assert variants.status_code == 200, variants.text
        variant_id = variants.json()["variants"][0]["id"]

        serials = [f"DR-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        received = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=headers, json={"quantity": 3, "variant_id": variant_id, "serial_numbers": serials})
        assert received.status_code == 200, received.text

        # Simulate the legacy drift the script exists to repair.
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE variant_inventory_balances SET on_hand = 9 WHERE store_id = :store_id AND variant_id = :variant_id"),
                {"store_id": store_id, "variant_id": variant_id},
            )
            await db.commit()

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--company-id", str(company_id), "--apply"],
            cwd=BACKEND_ROOT,
            env={**os.environ},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert "balance 9.000 -> 3" in result.stdout, result.stdout

        async with SessionLocal() as db:
            balance = (await db.execute(text("SELECT on_hand FROM variant_inventory_balances WHERE store_id = :store_id AND variant_id = :variant_id"), {"store_id": store_id, "variant_id": variant_id})).scalar_one()
            movement = (await db.execute(text("SELECT quantity FROM stock_movements WHERE reason = 'serial_reconciliation' AND store_id = :store_id AND variant_id = :variant_id"), {"store_id": store_id, "variant_id": variant_id})).scalar_one()
        assert float(balance) == 3.0
        assert float(movement) == -6.0

        inventory = await client.get("/api/v1/inventory", headers=headers)
        row = next(item for item in inventory.json() if item["product_id"] == product_id)
        assert next(item for item in row["variants"] if item["variant_id"] == variant_id)["on_hand"] == 3
