"""The event contract for first-party product telemetry.

One registry, two producers. The browser/SDK may only send names in
``CLIENT_EVENTS``; the API may only emit names in ``SERVER_EVENTS``. A name that
is not registered is dropped by the collector (never stored), which is what
stops the table turning into a pile of unknown ``button_click`` rows that nobody
can query.

The registry is intentionally small. Add an event because a question needs it,
not because a control exists. ``version`` is bumped when the meaning or the
property set changes, so an old client cannot silently corrupt a new report.

See ``docs/activation-intelligence-requirements.md`` for the funnel these events
serve.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSpec:
    """One accepted event name and the properties it may carry."""

    version: int = 1
    props: tuple[str, ...] = ()
    sample: float = 1.0
    description: str = ""


# --------------------------------------------------------------------------
# Client-emitted (untrusted, explanatory). None of these are funnel counts.
# --------------------------------------------------------------------------
CLIENT_EVENTS: dict[str, EventSpec] = {
    # Session and navigation
    "session.started": EventSpec(props=("entry_route", "referrer_host"), sample=1.0),
    "session.heartbeat": EventSpec(props=("route_key", "visible", "funnel_step"), sample=1.0),
    "session.ended": EventSpec(props=("exit_route", "duration_ms", "reason"), sample=1.0),
    "page.viewed": EventSpec(props=("route_key", "title_key"), sample=1.0),
    "page.left": EventSpec(props=("route_key", "dwell_ms", "scroll_pct"), sample=1.0),
    # Interaction
    "ui.click": EventSpec(props=("element_key", "role", "label_key", "route_key"), sample=1.0),
    "ui.rage_click": EventSpec(props=("element_key", "route_key", "clicks"), sample=1.0),
    "ui.dead_click": EventSpec(props=("element_key", "route_key"), sample=1.0),
    "ui.form_field_focused": EventSpec(props=("form", "field"), sample=1.0),
    "ui.form_field_completed": EventSpec(props=("form", "field", "duration_ms"), sample=1.0),
    "ui.form_validation_failed": EventSpec(props=("form", "field", "rule"), sample=1.0),
    "ui.form_abandoned": EventSpec(props=("form", "last_field", "filled_fields"), sample=1.0),
    # Errors and performance
    "error.client": EventSpec(props=("error_key", "route_key", "boundary"), sample=1.0),
    "error.network": EventSpec(props=("endpoint_key", "status", "error_code", "retry"), sample=1.0),
    "perf.route": EventSpec(props=("route_key", "ttfb_ms", "dcl_ms", "lcp_ms"), sample=0.5),
    # Signup and verification
    "auth.signup_started": EventSpec(props=("mode",), sample=1.0),
    "auth.signup_submitted": EventSpec(props=("mode", "turnstile"), sample=1.0),
    "auth.signup_failed": EventSpec(props=("reason",), sample=1.0),
    "auth.verify_submitted": EventSpec(props=("method", "device_switch"), sample=1.0),
    "auth.verify_failed": EventSpec(props=("reason",), sample=1.0),
    "auth.verify_resent": EventSpec(props=(), sample=1.0),
    "auth.login_submitted": EventSpec(props=("method",), sample=1.0),
    "auth.login_failed": EventSpec(props=("reason",), sample=1.0),
    # Setup wizard
    "onboarding.step_viewed": EventSpec(props=("step", "step_key"), sample=1.0),
    "onboarding.step_completed": EventSpec(props=("step", "step_key", "duration_ms", "back_count"), sample=1.0),
    "onboarding.step_back": EventSpec(props=("from_step", "to_step"), sample=1.0),
    "onboarding.abandoned": EventSpec(props=("step", "step_key", "dwell_ms", "last_field"), sample=1.0),
    "onboarding.plan_viewed": EventSpec(props=("plan_code", "recommended"), sample=1.0),
    "onboarding.plan_selected": EventSpec(props=("plan_code", "recommended"), sample=1.0),
    "onboarding.submit_failed": EventSpec(props=("status", "detail_key"), sample=1.0),
    "onboarding.abandon_survey": EventSpec(props=("step_key", "answer"), sample=1.0),
    # Product entry
    "product.create_opened": EventSpec(props=("entry",), sample=1.0),
    "product.create_field_edited": EventSpec(props=("field", "has_value"), sample=1.0),
    "product.create_failed": EventSpec(props=("field", "rule"), sample=1.0),
    "product.created": EventSpec(props=("entry", "duration_ms", "fields_filled"), sample=1.0),
    "product.import_started": EventSpec(props=("rows",), sample=1.0),
    "product.import_failed": EventSpec(props=("rows", "reason"), sample=1.0),
    # Payments / KHQR
    "payments.khqr_section_opened": EventSpec(props=("scope",), sample=1.0),
    "payments.khqr_link_pasted": EventSpec(props=("length_bucket",), sample=1.0),
    "payments.khqr_verify_failed": EventSpec(props=("reason",), sample=1.0),
    "payments.khqr_verified": EventSpec(props=("scope",), sample=1.0),
    "payments.khqr_test_scan": EventSpec(props=("result",), sample=1.0),
    # Guided setup coach
    "coach.shown": EventSpec(props=("step_id", "completed", "total"), sample=1.0),
    "coach.show_me": EventSpec(props=("step_id", "target_found"), sample=1.0),
    "coach.dismissed": EventSpec(props=("step_id", "completed"), sample=1.0),
    "coach.completed": EventSpec(props=("days_since_signup",), sample=1.0),
    # Selling
    "sale.cart_started": EventSpec(props=("entry",), sample=1.0),
    "sale.checkout_opened": EventSpec(props=("items", "total_bucket", "currency"), sample=1.0),
    "sale.payment_method_selected": EventSpec(props=("method",), sample=1.0),
    "sale.checkout_failed": EventSpec(props=("reason", "method"), sample=1.0),
    "sale.completed": EventSpec(props=("payment_method", "items"), sample=1.0),
    "shift.open_clicked": EventSpec(props=(), sample=1.0),
    "shift.opened": EventSpec(props=("opening_float_bucket",), sample=1.0),
    # Help and support
    "help.article_opened": EventSpec(props=("article_id", "from"), sample=1.0),
    "support.chat_opened": EventSpec(props=("from_route", "funnel_step"), sample=1.0),
    "support.message_sent": EventSpec(props=("intent",), sample=1.0),
    # Storefront (shopper)
    "storefront.order_started": EventSpec(props=("items",), sample=1.0),
    "storefront.order_submitted": EventSpec(props=("items", "payment_method"), sample=1.0),
    # QR and invitations
    "qr.downloaded": EventSpec(props=("scope", "format"), sample=1.0),
    "qr.shared": EventSpec(props=("scope",), sample=1.0),
    "invite.link_clicked": EventSpec(props=("role",), sample=1.0),
    "invite.accepted": EventSpec(props=("role",), sample=1.0),
    # Billing
    "billing.checkout_opened": EventSpec(props=("plan_code", "cycle"), sample=1.0),
}


# --------------------------------------------------------------------------
# Server-emitted (authoritative). These are the only rows the funnel counts.
# --------------------------------------------------------------------------
SERVER_EVENTS: dict[str, EventSpec] = {
    "user.registered": EventSpec(props=("method",)),
    "user.email_verified": EventSpec(props=("method",)),
    "user.logged_in": EventSpec(props=("method",)),
    "workspace.created": EventSpec(props=("vertical", "plan_code", "billing_cycle", "country", "currency")),
    "workspace.first_loaded": EventSpec(props=("vertical",)),
    "plan.selected": EventSpec(props=("plan_code", "billing_cycle", "recommended")),
    "product.created": EventSpec(props=("track_inventory", "opening_stock")),
    "inventory.opening_set": EventSpec(props=("unit",)),
    "shift.opened": EventSpec(props=("opening_float_present",)),
    "order.paid": EventSpec(props=("payment_method", "currency", "items", "total_bucket")),
    "order.refunded": EventSpec(props=("reason", "currency")),
    "payment.link_verified": EventSpec(props=("scope",)),
    "invite.accepted": EventSpec(props=("role",)),
    "storefront.order_received": EventSpec(props=("items", "currency")),
    "billing.payment_created": EventSpec(props=("plan_code", "cycle")),
    "billing.payment_succeeded": EventSpec(props=("plan_code", "cycle")),
    "billing.payment_failed": EventSpec(props=("plan_code", "reason")),
    "billing.plan_activated": EventSpec(props=("plan_code", "cycle")),
    "drip.email_sent": EventSpec(props=("step_id", "audience")),
    "drip.link_clicked": EventSpec(props=("step_id", "url_key")),
}


def client_event(name: str) -> EventSpec | None:
    """The spec if the client may send this name, else ``None``."""
    return CLIENT_EVENTS.get(name)


def server_event(name: str) -> EventSpec | None:
    """The spec if the API may emit this name, else ``None``."""
    return SERVER_EVENTS.get(name)


def all_event_names() -> frozenset[str]:
    """Every registered name, for documentation and drift tests."""
    return frozenset(CLIENT_EVENTS) | frozenset(SERVER_EVENTS)
