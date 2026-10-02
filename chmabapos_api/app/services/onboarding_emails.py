"""The content of the automated onboarding email sequence.

This is the single source of truth for the messages a stalled merchant
receives. Two things read it:

* the automated drip (``app.services.mailing.default_drip_config``) turns each
  entry into a sequenced step, and
* the reference-data seed (``scripts/seed.py``) mirrors each entry as an
  editable ``EmailTemplate`` so an operator can review, tweak and manually send
  the same copy from the admin Mailing tool.

Kept dependency-free (no imports from ``models``/``schemas``/``config``) so it
is cheap and safe to import from the seed script. Bodies use ``{{base}}`` as a
placeholder for the storefront URL, plus the normal ``{{name}}`` /
``{{store}}`` merge tokens resolved per recipient at send time.
"""
from __future__ import annotations

from typing import Final

# Replaced with the storefront URL (``settings.frontend_url``) when a message
# is rendered. It is not a per-recipient merge token.
BASE_TOKEN: Final[str] = "{{base}}"

# Ordered exactly as the drip should read. ``audience`` must match a key in
# ``app.services.mailing.AUDIENCES``.
ONBOARDING_EMAILS: Final[tuple[dict[str, object], ...]] = (
    {
        "id": "unverified-day1",
        "day_offset": 1,
        "audience": "unverified",
        "name": "Onboarding 01 - Confirm your email (day 1)",
        "subject": "{{name}}, your Chmaba account is one click away",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>You started signing up for Chmaba but we could not confirm your email yet. "
            "Open Chmaba, sign in, and tap <strong>Resend</strong> to get a fresh confirmation code.</p>"
            '<p><a href="' + BASE_TOKEN + '">Confirm my email</a></p>'
        ),
    },
    {
        "id": "unverified-day3",
        "day_offset": 3,
        "audience": "unverified",
        "name": "Onboarding 02 - Confirm your email (day 3)",
        "subject": "Still want to give Chmaba a try, {{name}}?",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>Your store is still waiting for you. Confirming your email takes a few seconds "
            "and there is no cost to start.</p>"
            '<p><a href="' + BASE_TOKEN + '">Open Chmaba</a></p>'
        ),
    },
    {
        "id": "workspace-day1",
        "day_offset": 1,
        "audience": "no_workspace",
        "name": "Onboarding 03 - Finish setting up (day 1)",
        "subject": "{{name}}, finish setting up your Chmaba store",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>You created your Chmaba account but have not set up a store yet. It takes about two minutes.</p>"
            '<p><a href="' + BASE_TOKEN + '">Finish setting up</a></p>'
        ),
    },
    {
        "id": "workspace-day3",
        "day_offset": 3,
        "audience": "no_workspace",
        "name": "Onboarding 04 - Getting started help (day 3)",
        "subject": "Need a hand getting started, {{name}}?",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>Still with us? Setting up takes a couple of minutes and there is no cost to start.</p>"
            '<p><a href="' + BASE_TOKEN + '">Set up your store</a></p>'
        ),
    },
    {
        "id": "workspace-day7",
        "day_offset": 7,
        "audience": "no_workspace",
        "name": "Onboarding 05 - Store still waiting (day 7)",
        "subject": "{{name}}, your store is still waiting",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>Your Chmaba account is ready whenever you are. Come back and start selling.</p>"
            '<p><a href="' + BASE_TOKEN + '">Open Chmaba</a></p>'
        ),
    },
    {
        "id": "product-day2",
        "day_offset": 2,
        "audience": "no_product",
        "name": "Onboarding 06 - Add your first item (day 2)",
        "subject": "Your Chmaba store is ready, {{name}} - add your first item",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>Your store is set up. We added a few sample items so you can try a sale right away, "
            "but they are only placeholders. Add one real product and your catalogue is yours.</p>"
            '<p><a href="' + BASE_TOKEN + '">Add my first product</a></p>'
        ),
    },
    {
        "id": "product-day5",
        "day_offset": 5,
        "audience": "no_product",
        "name": "Onboarding 07 - One item is all it takes (day 5)",
        "subject": "One item is all it takes, {{name}}",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>Add a single product - name, price, done - and you can ring up a real sale today.</p>"
            '<p><a href="' + BASE_TOKEN + '">Add a product</a></p>'
        ),
    },
    {
        "id": "sale-day2",
        "day_offset": 2,
        "audience": "no_sales",
        "name": "Onboarding 08 - Ring your first sale (day 2)",
        "subject": "{{name}}, ring up your first sale in 30 seconds",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>You have products in your store - now let us make a sale. It takes about 30 seconds, "
            "and you can take cash or KHQR. You are on the Free plan, so there is no card and no pressure.</p>"
            '<p><a href="' + BASE_TOKEN + '">Make a sale</a></p>'
        ),
    },
    {
        "id": "sale-day6",
        "day_offset": 6,
        "audience": "no_sales",
        "name": "Onboarding 09 - Fastest way to see it work (day 6)",
        "subject": "The fastest way to see Chmaba work, {{name}}",
        "body_html": (
            "<p>Hi {{name}},</p>"
            "<p>The best way to judge Chmaba is to sell one thing with it. Ring a sale, print or skip "
            "the receipt, and see how your day looks afterwards.</p>"
            '<p><a href="' + BASE_TOKEN + '">Open the register</a></p>'
        ),
    },
)
