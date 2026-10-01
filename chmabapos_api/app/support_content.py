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
    language: str = "en",
) -> list[dict[str, Any]]:
    """Return sections whose articles match the caller's vertical, role and query.

    Sections with no remaining articles are dropped. Each returned section keeps
    its order; articles keep their authored order. ``language`` selects the
    localized copy of the text.
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
    return _localize_sections(sections, language)


def starter_prompts_for(*, vertical: str | None = None, role: str | None = None, language: str = "en") -> list[str]:
    """Return starter questions for a vertical, falling back to general.

    Cashiers are shown only the operational prompts; owners/managers see all. The
    cashier filter is computed on the English list so it works for every language.
    """
    key = vertical or ""
    english = list(STARTER_PROMPTS.get(key, STARTER_PROMPTS["general"]))
    localized = list(STARTER_PROMPTS_KM.get(key, STARTER_PROMPTS_KM["general"])) if language == "km" else english
    if role == "cashier":
        keep = [index for index, prompt in enumerate(english) if "sale" in prompt.lower() or "shift" in prompt.lower()]
        if keep:
            localized = [localized[index] for index in keep]
        else:
            localized = list(STARTER_PROMPTS_KM["general"] if language == "km" else STARTER_PROMPTS["general"])
    return localized


# Khmer translations, keyed by section id and article id. English stays the base
# so a missing translation falls back to English rather than breaking the page.
# Reviewing/refining this copy is expected; it is a first pass.
KH_TRANSLATIONS: Final[dict[str, dict[str, Any]]] = {
    "getting-started": {"title": "ចាប់ផ្តើម", "blurb": "ដំឡើងហាងរបស់អ្នក និងចុះលក់លើកដំបូង។"},
    "getting-started.first-sale": {
        "title": "ចុះលក់លើកដំបូង",
        "steps": [
            "បើក ចំណុចលក់ ពីរបារចំហៀង។",
            "ចុចលើទំនិញដែលអតិថិជនទិញ ដើម្បីបញ្ចូលទៅកន្ត្រក។",
            "ជ្រើសរើសវិធីទូទាត់ — សាច់ប្រាក់ ឬ KHQR។",
            "សម្រាប់សាច់ប្រាក់ បញ្ចូលចំនួនទទួលបាន ហើយប្រព័ន្ធនឹងគណនាប្រាក់អាប់។",
            "ចុច គិតប្រាក់ ដើម្បីបញ្ចប់ការលក់ និងបោះពុម្ពវិក្កយបត្រ។",
        ],
        "tip": "ប្រសិនបើហាងរបស់អ្នកតម្រូវឲ្យបើកវេន សូមបើកវេនពី ផ្ទាំងសង្ខេប មុនពេលលក់ដំបូង។",
    },
    "getting-started.add-products": {
        "title": "បន្ថែមទំនិញ",
        "steps": [
            "ទៅកាន់ ទំនិញ ហើយចុច បន្ថែមទំនិញ។",
            "បញ្ចូលឈ្មោះ តម្លៃ និងបាកូដ ប្រសិនបើមាន។",
            "អាចកំណត់តម្លៃដើម ដើម្បីឲ្យរបាយការណ៍ចំណេញដំណើរការ។",
            "កំណត់ស្តុកដែលមាន ឬបិទការតាមដានស្តុកសម្រាប់ទំនិញធ្វើតាមការបញ្ជាទិញ។",
            "រក្សាទុក។ ទំនិញនឹងបង្ហាញនៅផ្ទាំង ចំណុចលក់។",
        ],
        "tip": "ដាក់ទំនិញជា ប្រភេទ ដើម្បីឲ្យផ្ទាំងលក់ងាយស្រួលស្វែងរក។",
    },
    "inventory": {"title": "ស្តុក", "blurb": "រក្សាចំនួនស្តុកឲ្យត្រឹមត្រូវ។"},
    "inventory.restock": {
        "title": "ទទួលស្តុកចូលហាង",
        "steps": [
            "បើក ស្តុក ហើយរកទំនិញ។",
            "ជ្រើស បន្ថែមស្តុក ហើយបញ្ចូលចំនួនទទួលបាន។",
            "បន្ថែមមូលហេតុ ដូចជា ការដឹកជញ្ជូន ឬ ការរាប់ស្តុក។",
            "រក្សាទុក។ ស្តុកនឹងធ្វើបច្ចុប្បន្នភាពភ្លាមៗសម្រាប់គ្រប់ម៉ាស៊ីនគិតលុយក្នុងហាងនេះ។",
        ],
    },
    "inventory.low-stock": {
        "title": "តាមដានស្តុកជិតអស់",
        "steps": [
            "កំណត់ចំណុចបញ្ជាទិញឡើងវិញសម្រាប់ទំនិញនីមួយៗដែលអ្នកតាមដាន។",
            "ផ្ទាំងសង្ខេប បង្ហាញចំនួនទំនិញជិតអស់ នៅពេលទំនិញណាមួយធ្លាក់ក្រោមកម្រិតនោះ។",
            "បើក ស្តុក ហើយចម្រាញ់តែទំនិញជិតអស់ ដើម្បីបន្ថែមស្តុកមុនពេលអស់។",
        ],
    },
    "electronics": {"title": "សេរៀល និងការធានា", "blurb": "សម្រាប់ហាងអេឡិចត្រូនិចដែលតាមដានឧបករណ៍នីមួយៗ។"},
    "electronics.serials": {
        "title": "បន្ថែមលេខសេរៀល និង IMEI",
        "steps": [
            "បើក តាមដានសេរៀល ពេលបង្កើត ឬកែទំនិញ។",
            "បើកទំនិញ ហើយចុច បន្ថែមសេរៀល ដើម្បីបញ្ចូលលេខសេរៀលនីមួយៗ។",
            "កត់ត្រា IMEI និងតម្លៃដើមក្នុងមួយឯកតា សម្រាប់ការលក់បន្ត និងការធានា។",
            "ពេលគិតលុយ សូមជ្រើសឯកតាជាក់លាក់ដែលលក់ ដើម្បីចាប់ផ្តើមការធានា។",
        ],
        "tip": "លេខសេរៀលត្រូវតែមានតែមួយគត់ក្នុងក្រុមហ៊ុន ដូច្នេះឯកតាមួយមិនអាចលក់ពីរដងបានទេ។",
    },
    "electronics.warranty": {
        "title": "តាមដានការធានា និងស្ថានភាពឧបករណ៍ប្រើរួច",
        "steps": [
            "នៅលើសេរៀល កំណត់ការធានាពីអ្នកផ្គត់ផ្គង់ និងការធានាឲ្យអតិថិជនដោយឡែកពីគ្នា។",
            "ការធានាឲ្យអតិថិជនចាប់ផ្តើម នៅពេលឯកតាត្រូវលក់ជាក់ស្តែង។",
            "សម្រាប់ឧបករណ៍ប្រើរួច កត់ត្រាលំដាប់ស្ថានភាព និងសុខភាពថ្ម។",
            "ប្រវត្តិលំដាប់ស្ថានភាពត្រូវបានរក្សាទុក ដូច្នេះការវាយតម្លៃចាស់មិនបាត់បង់ទេ។",
        ],
    },
    "team-billing": {"title": "ក្រុម វិក្កយបត្រ និងការកំណត់", "blurb": "គ្រប់គ្រងសមាជិក គម្រោង និងចំណូលចិត្ត។"},
    "team.invite": {
        "title": "អញ្ជើញសមាជិកក្រុម",
        "steps": [
            "បើក ការចូលប្រើក្រុម ហើយជ្រើស អញ្ជើញ។",
            "បញ្ចូលអ៊ីមែល និងជ្រើសតួនាទី — អ្នកគ្រប់គ្រង អ្នកគ្រប់គ្រងស្តុក ឬអ្នកគិតលុយ។",
            "ជ្រើសហាងដែលពួកគេអាចធ្វើការបាន។",
            "ពួកគេនឹងទទួលអ៊ីមែល ហើយចូលរួមនៅពេលទទួលយក។",
        ],
    },
    "billing.change-plan": {
        "title": "ប្តូរគម្រោង",
        "steps": [
            "បើក វិក្កយបត្រ និងគម្រោង។",
            "ប្រៀបធៀបគម្រោង និងលក្ខណៈពិសេសដែលរួមបញ្ចូល។",
            "ជ្រើសគម្រោង ហើយបង់ប្រាក់ដើម្បីបើកដំណើរការ។",
            "ការបញ្ចុះគម្រោង បញ្ឈប់ហាង ឬសមាជិកលើសតែប៉ុណ្ណោះ មិនលុបចោលទេ។",
        ],
    },
}

STARTER_PROMPTS_KM: Final[dict[str, list[str]]] = {
    "coffee": ["តើខ្ញុំកំណត់ម៉ឺនុយ និងប្រភេទដូចម្តេច?", "តើខ្ញុំបើក និងបិទវេនដូចម្តេច?", "តើខ្ញុំគិតលុយកាហ្វេដូចម្តេច?"],
    "restaurant": ["តើខ្ញុំកំណត់ម៉ឺនុយអាហារដូចម្តេច?", "តើខ្ញុំដោះស្រាយការបង់ប្រាក់បែងចែកដូចម្តេច?", "តើខ្ញុំបើក និងបិទវេនដូចម្តេច?"],
    "mart": ["តើខ្ញុំបន្ថែមទំនិញជាមួយបាកូដដូចម្តេច?", "តើខ្ញុំបន្ថែមស្តុកទំនិញជិតអស់ដូចម្តេច?", "តើខ្ញុំមើលការលក់ថ្ងៃនេះដូចម្តេច?"],
    "electronics": ["តើខ្ញុំបន្ថែមលេខសេរៀល និង IMEI ដូចម្តេច?", "តើខ្ញុំតាមដានការធានានៅពេលលក់ដូចម្តេច?", "តើខ្ញុំវាយតម្លៃទូរស័ព្ទប្រើរួចដូចម្តេច?"],
    "shop": ["តើខ្ញុំបន្ថែមទំនិញដូចម្តេច?", "តើខ្ញុំទទួលស្តុកដូចម្តេច?", "តើខ្ញុំមើលរបាយការណ៍លក់ដូចម្តេច?"],
    "general": ["តើខ្ញុំគិតលុយដូចម្តេច?", "តើខ្ញុំបន្ថែមទំនិញដូចម្តេច?", "តើខ្ញុំទទួលស្តុកដូចម្តេច?"],
}


def _localize_sections(sections: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    """Return sections with Khmer copy substituted when ``language == 'km'``.

    Missing translations fall back to the English base, so partial coverage is
    always renderable.
    """
    if language != "km":
        return sections
    localized: list[dict[str, Any]] = []
    for section in sections:
        section_km = KH_TRANSLATIONS.get(section["id"], {})
        articles = []
        for article in section["articles"]:
            article_km = KH_TRANSLATIONS.get(article["id"], {})
            articles.append(
                {
                    **article,
                    "title": article_km.get("title", article["title"]),
                    "steps": article_km.get("steps", article["steps"]),
                    "tip": article_km.get("tip", article.get("tip")),
                }
            )
        localized.append(
            {
                "id": section["id"],
                "title": section_km.get("title", section["title"]),
                "blurb": section_km.get("blurb", section["blurb"]),
                "articles": articles,
            }
        )
    return localized
