from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payments.base import PaymentProvider
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.platform_config import load_payment_settings


async def payment_provider_for(db: AsyncSession) -> PaymentProvider:
    """Build the ChmabaPay provider from admin-managed settings (env fallback)."""
    cfg = await load_payment_settings(db)
    return ChmabaPayClient(
        mode=cfg.get("chamabapay_mode") or None,
        api_url=cfg.get("chamabapay_api_url") or None,
        api_key=cfg.get("chamabapay_api_key") or None,
    )
