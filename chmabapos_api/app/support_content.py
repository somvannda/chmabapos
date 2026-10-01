"""Help corpus served to the in-app help center and used to ground the assistant.

This module is the single source of truth for in-app help content. The web help
center reads it through ``GET /support/articles`` and ``GET /support/starter-prompts``;
the support assistant (``app/services/support.py``) retrieves from the same data.

Keep articles short and task-oriented: one job per article, imperative title,
concrete steps. Content is filtered by the company's ``vertical`` and the
caller's role, and ranked by ``order`` within a section.
"""
from __future__ import annotations

from typing import Any, Final

ALL_VERTICALS: Final[tuple[str, ...]] = (
    "coffee",
    "restaurant",
    "mart",
    "electronics",
    "shop",
    "general",
)

ALL_ROLES: Final[tuple[str, ...]] = ("owner", "manager", "inventory_manager", "cashier")

# Sections group related guides in the help center. Each article carries the
# verticals and roles it applies to so the UI (and retrieval) can filter.
SUPPORT_SECTIONS: Final[list[dict[str, Any]]] = [
    {
        "id": "getting-started",
        "title": "Getting started",
        "blurb": "Set up your store and ring up your first sale.",
        "articles": [
            {
                "id": "getting-started.first-sale",
                "title": "Ring up your first sale",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Point of sale from the sidebar.",
                    "Tap the products your customer is buying to add them to the cart.",
                    "Choose a payment method - cash or KHQR.",
                    "For cash, enter the amount received; the change is calculated for you.",
                    "Tap Charge to complete the sale and print the receipt.",
                ],
                "tip": "If your store requires an open shift, open one from Overview before your first sale.",
            },
            {
                "id": "getting-started.add-products",
                "title": "Add your products",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Go to Products and tap Add product.",
                    "Enter a name, price and, if you have one, a barcode.",
                    "Optionally set a cost price so margin reports work.",
                    "Set stock on hand, or leave inventory tracking off for made-to-order items.",
                    "Save. The product now appears on the Point of sale screen.",
                ],
                "tip": "Group products into Categories so the POS grid stays quick to scan.",
            },
        ],
    },
    {
        "id": "inventory",
        "title": "Inventory",
        "blurb": "Keep stock counts accurate.",
        "articles": [
            {
                "id": "inventory.restock",
                "title": "Receive stock into a store",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Inventory and find the product.",
                    "Choose Restock and enter the quantity received.",
                    "Add a reason such as Delivery or Stock count.",
                    "Save. On-hand stock updates immediately for every register in this store.",
                ],
            },
            {
                "id": "inventory.low-stock",
                "title": "Watch for low stock",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Set a reorder point on each product you track.",
                    "Overview shows a Low stock items count when any product drops below it.",
                    "Open Inventory and filter to low items to restock before you run out.",
                ],
            },
        ],
    },
    {
        "id": "electronics",
        "title": "Serials & warranty",
        "blurb": "For electronics stores that track individual units.",
        "articles": [
            {
                "id": "electronics.serials",
                "title": "Add serial numbers and IMEI",
                "verticals": ["electronics"],
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Turn on Track serials when creating or editing a product.",
                    "Open the product and use Add serials to enter each unit's serial number.",
                    "Record the IMEI and cost price per unit for accurate resale and warranty.",
                    "At checkout, pick the exact unit being sold so its warranty clock starts.",
                ],
                "tip": "Serial numbers must be unique across your company, so a unit can never be sold twice.",
            },
            {
                "id": "electronics.warranty",
                "title": "Track warranty and used grades",
                "verticals": ["electronics"],
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "On a serial, set the supplier warranty and the customer warranty separately.",
                    "The customer warranty only starts when the unit is actually sold.",
                    "For used or refurbished units, record a condition grade and battery health.",
                    "Grade history is kept, so a re-graded unit never loses its earlier assessment.",
                ],
            },
        ],
    },
    {
        "id": "team-billing",
        "title": "Team, billing & settings",
        "blurb": "Manage people, your plan and preferences.",
        "articles": [
            {
                "id": "team.invite",
                "title": "Invite a team member",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Team access and choose Invite.",
                    "Enter their email and pick a role - manager, inventory manager or cashier.",
                    "Choose which stores they can work in.",
                    "They receive an email and join once they accept.",
                ],
            },
            {
                "id": "billing.change-plan",
                "title": "Change your plan",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Billing & plans.",
                    "Compare the plans and their included features.",
                    "Choose a plan and complete payment to unlock it.",
                    "Downgrading pauses extra stores or members instead of deleting them.",
                ],
            },
        ],
    },
]

# Starter questions shown when the help center / assistant opens, tailored to
# the merchant's business type. These are data, not model output.
STARTER_PROMPTS: Final[dict[str, list[str]]] = {
    "coffee": [
        "How do I set up my menu and categories?",
        "How do I open and close a shift?",
        "How do I ring up a coffee sale?",
    ],
    "restaurant": [
        "How do I set up a food menu?",
        "How do I handle split payments?",
        "How do I open and close a shift?",
    ],
    "mart": [
        "How do I add products with barcodes?",
        "How do I restock low items?",
        "How do I read today's sales?",
    ],
    "electronics": [
        "How do I add serial numbers and IMEI?",
        "How do I track warranty on a sale?",
        "How do I grade a used phone?",
    ],
    "shop": [
        "How do I add my products?",
        "How do I receive stock?",
        "How do I read my sales report?",
    ],
    "general": [
        "How do I ring up a sale?",
        "How do I add products?",
        "How do I receive stock?",
    ],
}


def _article_matches(article: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        [article.get("title", ""), *article.get("steps", []), article.get("tip") or ""]
    ).lower()
    return needle in haystack


def articles_for(
    *,
    vertical: str | None = None,
    role: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Return sections whose articles match the caller's vertical, role and query.

    Sections with no remaining articles are dropped. Each returned section keeps
    its order; articles keep their authored order.
    """
    sections: list[dict[str, Any]] = []
    for section in SUPPORT_SECTIONS:
        rows: list[dict[str, Any]] = []
        for article in section["articles"]:
            if vertical and vertical not in article["verticals"]:
                continue
            if role and role not in article["roles"]:
                continue
            if not _article_matches(article, query):
                continue
            rows.append(article)
        if rows:
            sections.append(
                {
                    "id": section["id"],
                    "title": section["title"],
                    "blurb": section["blurb"],
                    "articles": rows,
                }
            )
    return sections


def starter_prompts_for(*, vertical: str | None = None, role: str | None = None) -> list[str]:
    """Return starter questions for a vertical, falling back to general.

    Cashiers are shown only the operational prompts; owners/managers see all.
    """
    prompts = list(STARTER_PROMPTS.get(vertical or "", STARTER_PROMPTS["general"]))
    if role == "cashier":
        prompts = [prompt for prompt in prompts if "sales" in prompt.lower() or "sale" in prompt.lower() or "shift" in prompt.lower()]
        if not prompts:
            prompts = list(STARTER_PROMPTS["general"])
    return prompts
