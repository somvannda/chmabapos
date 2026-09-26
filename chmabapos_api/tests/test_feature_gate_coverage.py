"""Guard: every paid capability in the catalog must have an enforcement gate.

A capability that is advertised as paid (i.e. not Free, not marketing-only) but
is never passed to ``require_plan_feature`` can be toggled by a platform admin
with no effect — exactly the ``roles_permissions`` gap that shipped ungated.
This static check fails when such a capability is added without a gate.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.features import FEATURE_CATALOG, MARKETING_ONLY

# Capabilities that ship on every plan, so they intentionally need no gate.
ALWAYS_AVAILABLE = {"khqr_payments"}

V1_SOURCE = Path(__file__).resolve().parents[1] / "app" / "api" / "v1.py"


def test_every_paid_capability_has_an_enforcement_gate() -> None:
    source = V1_SOURCE.read_text(encoding="utf-8")
    gated = set(re.findall(r'require_plan_feature\([^;]*?"([a-z_]+)"\s*\)', source))
    expected = set(FEATURE_CATALOG) - MARKETING_ONLY - ALWAYS_AVAILABLE
    missing = sorted(expected - gated)
    assert not missing, f"capabilities with no require_plan_feature gate: {missing}"


def test_always_available_capabilities_exist_in_the_catalog() -> None:
    assert ALWAYS_AVAILABLE <= set(FEATURE_CATALOG)
