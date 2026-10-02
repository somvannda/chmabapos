"""The content of the automated onboarding email sequence.

This is the single source of truth for the messages a stalled merchant
receives. Two things read it:

* the automated drip (``app.services.mailing.default_drip_config``) turns each
  entry into a sequenced step, and
* the reference-data seed (``scripts/seed.py``) mirrors each entry as an
  editable ``EmailTemplate`` so an operator can review, tweak and manually send
  the same copy from the admin Mailing tool.

Bodies are rendered through the shared branded layout in
``app.services.email_layout``. Kept dependency-light (no imports from
``models``/``schemas``/``config``) so it is safe to import from the seed script
and the migration.
"""
from __future__ import annotations

from typing import Final

from app.services.email_layout import marketing_email

# Replaced with the storefront URL (``settings.frontend_url``) when a message
# is rendered. It is not a per-recipient merge token.
BASE_TOKEN: Final[str] = "{{base}}"


def _email(
    *,
    id: str,
    day_offset: int,
    audience: str,
    name: str,
    subject: str,
    heading: str,
    preview: str,
    paragraphs: tuple[str, ...],
    cta_label: str,
    cta_href: str = BASE_TOKEN,
    footnote: str | None = None,
) -> dict[str, object]:
    return {
        "id": id,
        "day_offset": day_offset,
        "audience": audience,
        "name": name,
        "subject": subject,
        "body_html": marketing_email(
            heading=heading,
            preview=preview,
            paragraphs=paragraphs,
            cta_label=cta_label,
            cta_href=cta_href,
            footnote=footnote,
        ),
    }


# Ordered exactly as the drip should read. ``audience`` must match a key in
# ``app.services.mailing.AUDIENCES``.
ONBOARDING_EMAILS: Final[tuple[dict[str, object], ...]] = (
    _email(
        id="unverified-day1",
        day_offset=1,
        audience="unverified",
        name="Onboarding 01 - Confirm your email (day 1)",
        subject="Confirm your email to start selling on Chmaba",
        heading="Let's confirm your email",
        preview="One quick tap and your Chmaba store is ready.",
        paragraphs=(
            "Hi {{name}},",
            "You started setting up Chmaba, but your email isn't confirmed yet. Confirm it and you can have your store ready to sell in about two minutes.",
        ),
        cta_label="Confirm my email",
        footnote="If the button doesn't work, sign in at Chmaba and tap <strong>Resend</strong> to get a fresh code.",
    ),
    _email(
        id="unverified-day3",
        day_offset=3,
        audience="unverified",
        name="Onboarding 02 - Confirm your email (day 3)",
        subject="Your Chmaba store is still waiting, {{name}}",
        heading="Still want to give Chmaba a try?",
        preview="Confirm your email and pick up right where you left off.",
        paragraphs=(
            "Hi {{name}},",
            "Your account is ready whenever you are. Confirming your email takes a few seconds, and starting is free — no card, no commitment.",
        ),
        cta_label="Open Chmaba",
    ),
    _email(
        id="workspace-day1",
        day_offset=1,
        audience="no_workspace",
        name="Onboarding 03 - Finish setting up (day 1)",
        subject="Finish setting up your Chmaba store, {{name}}",
        heading="Two minutes to your first sale",
        preview="Add a store name and you're ready to start selling.",
        paragraphs=(
            "Hi {{name}},",
            "You created your Chmaba account but haven't set up a store yet. Give your store a name and we'll have you ringing up sales — free to start.",
        ),
        cta_label="Finish setting up",
    ),
    _email(
        id="workspace-day3",
        day_offset=3,
        audience="no_workspace",
        name="Onboarding 04 - Getting started help (day 3)",
        subject="Need a hand getting started, {{name}}?",
        heading="We'll walk you through it",
        preview="Set up your store in a couple of minutes.",
        paragraphs=(
            "Hi {{name}},",
            "Setting up your Chmaba store takes a couple of minutes. If anything is unclear, just reply to this email — a real person will help you get going.",
        ),
        cta_label="Set up your store",
    ),
    _email(
        id="workspace-day7",
        day_offset=7,
        audience="no_workspace",
        name="Onboarding 05 - Store still waiting (day 7)",
        subject="Your store is still waiting, {{name}}",
        heading="Ready when you are",
        preview="Your Chmaba store is a couple of minutes away.",
        paragraphs=(
            "Hi {{name}},",
            "Your Chmaba account is ready. Set up your store and start taking sales today — there's no cost to begin, and you can change everything later.",
        ),
        cta_label="Open Chmaba",
    ),
    _email(
        id="product-day2",
        day_offset=2,
        audience="no_product",
        name="Onboarding 06 - Add your first item (day 2)",
        subject="Add your first item to Chmaba, {{name}}",
        heading="Your store is ready for its first item",
        preview="Add one real product and make it yours.",
        paragraphs=(
            "Hi {{name}},",
            "We added a few sample items so you can try the register right away — but they're only placeholders. Add one real product and your catalogue is yours.",
            "Name, price, done. That's all it takes.",
        ),
        cta_label="Add my first product",
    ),
    _email(
        id="product-day5",
        day_offset=5,
        audience="no_product",
        name="Onboarding 07 - One item is all it takes (day 5)",
        subject="One item is all it takes, {{name}}",
        heading="Add one item, make one sale",
        preview="A single product is all you need to start.",
        paragraphs=(
            "Hi {{name}},",
            "Add a single product and you can ring up a real sale today. Watching your own item go through the register is the quickest way to know Chmaba fits your shop.",
        ),
        cta_label="Add a product",
    ),
    _email(
        id="sale-day2",
        day_offset=2,
        audience="no_sales",
        name="Onboarding 08 - Ring your first sale (day 2)",
        subject="Ring up your first sale, {{name}}",
        heading="Your first sale is 30 seconds away",
        preview="Take cash or KHQR and see Chmaba in action.",
        paragraphs=(
            "Hi {{name}},",
            "You have products in your store — now let's make a sale. Take cash or KHQR, and print or skip the receipt.",
            "You're on the <strong>Free plan</strong>: no card, no pressure.",
        ),
        cta_label="Make a sale",
    ),
    _email(
        id="sale-day6",
        day_offset=6,
        audience="no_sales",
        name="Onboarding 09 - Fastest way to see it work (day 6)",
        subject="The fastest way to see Chmaba work, {{name}}",
        heading="See it in one sale",
        preview="Ring a sale and watch your day come together.",
        paragraphs=(
            "Hi {{name}},",
            "The best way to judge Chmaba is to sell one thing with it. Ring a sale and watch your day come together in your reports.",
        ),
        cta_label="Open the register",
    ),
)
