from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.cutluy import CutLuyClient
from app.services.payments.base import PaymentProvider
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.payments.cutluy import CutLuyProvider
from app.services.platform_config import load_payment_settings


def _resolve_name(cfg: dict[str, str | None]) -> str:
    return (cfg.get("payments_provider") or settings.payments_provider or "cutluy").strip().lower()


async def payment_provider_for(db: AsyncSession) -> PaymentProvider:
    """Build the active payment provider from admin-managed settings (env fallback).

    Defaults to CutLuy so introducing this abstraction does not change behaviour;
    flip ``PAYMENTS_PROVIDER=chamabapay`` per the migration plan.
    """
    cfg = await load_payment_settings(db)
    if _resolve_name(cfg) == "chamabapay":
        return ChmabaPayClient(
            mode=cfg.get("chamabapay_mode") or None,
            api_url=cfg.get("chamabapay_api_url") or None,
            api_key=cfg.get("chamabapay_api_key") or None,
        )
    return CutLuyProvider(
        CutLuyClient(
            mode=cfg.get("cutluy_mode") or None,
            api_url=cfg.get("cutluy_api_url") or None,
            api_key=cfg.get("cutluy_api_key") or None,
        )
    )
