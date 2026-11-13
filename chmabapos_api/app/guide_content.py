"""Seed corpus for the public User Guides library.

The User Guides library is the public, long-form counterpart to the in-app help
center (``app/support_content.py``). It is written for a merchant who has not
signed up yet and walks them from planning a coffee shop to closing the till on
day one. Unlike the help center, a guide is a page of its own: it has a category,
a reading order, long-form sections, checklists and SEO metadata.

This module is the *seed*. Platform admins edit the database copy through
``/admin/guides``; the rows here are inserted by the migration that creates the
tables. Keep the structure data-only (no imports from ``models`` or
``schemas``) so it stays safe to import from a migration.

Layout of one guide:
    slug, title, summary, group_title, level, estimated_minutes, intro,
    learning_points, requirements, sections, takeaways, seo_title,
    seo_description, is_featured, position

Layout of one section:
    heading, body (list of paragraphs), steps (list of strings), tip (optional)
"""
from __future__ import annotations

from typing import Any, Final

GUIDE_CATEGORIES: Final[list[dict[str, Any]]] = [
    {
        "slug": "coffee-shop",
        "name": "Coffee shop",
        "description": "Open, stock and run a coffee counter - from the first menu item to the last shift close.",
        "icon": "Coffee",
        "accent": "#b46b3e",
        "position": 1,
    },
    {
        "slug": "restaurant",
        "name": "Restaurant",
        "description": "Plan the menu and floor, take dine-in orders, run the kitchen and close the day.",
        "icon": "UtensilsCrossed",
        "accent": "#4b6b57",
        "position": 2,
    },
    {
        "slug": "mart",
        "name": "Mart / grocery",
        "description": "Build a scannable catalogue, receive deliveries and keep perishable stock honest.",
        "icon": "ShoppingCart",
        "accent": "#2f6f8f",
        "position": 3,
    },
    {
        "slug": "electronics",
        "name": "Electronics store",
        "description": "Track every serial and IMEI, start warranty at the sale and record service on the unit.",
        "icon": "Smartphone",
        "accent": "#5a5fa8",
        "position": 4,
    },
]

GUIDES: Final[list[dict[str, Any]]] = [
    {
        "category": "coffee-shop",
        "slug": "plan-your-coffee-shop",
        "title": "Plan your coffee shop before you touch the register",
        "summary": "Decide the menu, prices, payment flow and counter setup first, so building the workspace is one calm pass instead of three.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": True,
        "position": 1,
        "seo_title": "How to plan a coffee shop before opening | Chmaba guides",
        "seo_description": "A practical pre-launch checklist for coffee shops: menu structure, drink pricing, payment methods, receipt setup and the details to prepare before using your POS.",
        "intro": [
            "The register is the last thing you set up, not the first. A coffee shop runs on a small number of repeatable decisions: what you sell, what it costs, how customers pay and who opens the door in the morning.",
            "Spend an hour on these decisions now and the setup steps that follow become quick data entry rather than a redesign in the middle of service.",
        ],
        "learning_points": [
            "Choose a menu structure you can actually run every day",
            "Set drink prices from cost and a target margin",
            "Pick the payment and receipt flow before your first customer",
            "List the details you need before creating the workspace",
        ],
        "requirements": [
            "Your planned menu with prices",
            "A rough cost per drink (beans, milk, cup, pastry)",
            "Your business and store names",
            "Your ABA PayWay link if you will accept KHQR",
        ],
        "sections": [
            {
                "heading": "Start with a menu you can run every day",
                "body": [
                    "A coffee counter gets fast when the menu is small enough for a new barista to learn in one shift. Aim for four to six groups and roughly 15 to 30 sellable items: espresso and hot coffee, iced coffee, tea and matcha, bakery, and a small extras group.",
                    "Keep the number of decisions per drink low. Size is a choice. Milk and sugar are choices. Everything else - extra shot, syrup, whipped cream - should be an add-on with a clear price.",
                    "Write the menu the way the customer says it: 'Iced Latte' and 'Hot Latte' are easier to find on a busy POS grid than one 'Latte' product with a hidden temperature question. You can still group them under one category.",
                ],
                "steps": [
                    "List every drink you plan to sell and the price for each size.",
                    "Group the list into four to six categories a customer would recognise.",
                    "Mark your best sellers - these go first on the register grid.",
                    "Cut anything you cannot make consistently during a rush.",
                ],
                "tip": "A short menu with clear sizes and modifiers is easier to train and easier to report on than a long menu with exceptions.",
            },
            {
                "heading": "Price from cost, not from the shop next door",
                "body": [
                    "Start with the cost of one cup: the coffee dose, milk, cup, lid, sleeve and any garnish. Add the pastry cost separately if it is sold as a set. A useful target for a coffee shop is a ingredient cost around 25 to 35 percent of the selling price - the exact number depends on your rent and labour, so confirm it with your accountant.",
                    "If a 16oz latte costs you $1.10 in ingredients and you sell it for $4.00, your ingredient margin is 72.5 percent. That is the number to protect when you run a promotion.",
                    "Round prices to a number your staff can read back quickly. In a dual-currency counter, keep the USD price as the source of truth and let the enabled exchange rate handle riel.",
                ],
                "steps": [
                    "Write the ingredient cost for each drink size.",
                    "Divide the selling price by the cost to see your multiple, or subtract cost from price to see gross profit.",
                    "Set a minimum margin below which a discount needs a manager.",
                    "Record the cost price on every product in Chmaba so the margin report is real.",
                ],
                "tip": "Update cost prices when your bean or milk supplier changes. A margin report is only as honest as the costs behind it.",
            },
            {
                "heading": "Choose how customers will pay",
                "body": [
                    "Decide the payment mix now because it changes what you configure. Chmaba supports cash, KHQR through an ABA PayWay link, and split payments that mix the two on one sale. You can add more currencies later, but the primary currency should match how you price the menu.",
                    "If you take KHQR, ask your bank for the PayWay link before launch day. A tested link means the QR appears at checkout and the screen confirms payment without a manual step.",
                ],
                "steps": [
                    "Decide whether the counter takes cash, KHQR, or both.",
                    "Get the ABA PayWay link and confirm it is active.",
                    "Decide whether a shift must be open before a sale.",
                    "Decide who may give discounts and refunds.",
                ],
            },
            {
                "heading": "Prepare the details you will type in",
                "body": [
                    "Setup goes quickly when the information is already written down. Gather the names, numbers and files before you open the signup page.",
                ],
                "steps": [
                    "Business name, store name and store address.",
                    "Primary currency and any second currency you accept.",
                    "Tax rate and whether menu prices include tax - confirm this with your accountant.",
                    "Receipt logo, receipt footer and order-number prefix.",
                    "The first team members and the role each one needs.",
                    "Your menu with a price and a cost for every item.",
                ],
                "tip": "You do not need a perfect brand kit to launch. A clean logo, an address and a receipt that prints correctly are enough for day one.",
            },
        ],
        "takeaways": [
            "Build the menu around repeatable drinks, not a long list of exceptions.",
            "Price from ingredient cost and protect a margin you can name.",
            "Choose cash, KHQR or both before setup so payment configuration is a single step.",
            "Gather names, tax details and menu costs before creating the workspace.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "create-your-workspace",
        "title": "Create your workspace and first store",
        "summary": "Sign up, choose the coffee shop business type and create the store your team will sell from.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 2,
        "seo_title": "Create your Chmaba workspace for a coffee shop | Chmaba guides",
        "seo_description": "Step-by-step: create a coffee shop workspace, choose the right business type, set currency and tax, and add your first store in Chmaba.",
        "intro": [
            "A Chmaba workspace holds your company, your stores, your team and your books. Creating it takes a few minutes; choosing the coffee shop business type gives you a head start with the right categories and feature defaults.",
        ],
        "learning_points": [
            "Create and verify your Chmaba account",
            "Choose the coffee shop business type during onboarding",
            "Set the primary currency and tax details for your store",
            "Confirm the seeded categories and sample products",
        ],
        "requirements": [
            "An email address you check regularly",
            "Your business name and first store name",
            "Your country, primary currency and tax rate",
        ],
        "sections": [
            {
                "heading": "Create your account",
                "body": [
                    "Open chmaba.com and choose Start free. Enter your name, email and a strong password, then create the account.",
                    "Chmaba sends a six-digit confirmation code to your email. Enter it on the confirmation screen. If it does not arrive, use Resend code; check the spam folder before trying a different address.",
                ],
                "steps": [
                    "Choose Start free on the Chmaba home page.",
                    "Enter your full name, email and password.",
                    "Open the email and enter the six-digit code.",
                    "If you signed in with Google, finish the same onboarding instead of entering a code.",
                ],
                "tip": "Use an email the business will keep. It becomes the owner sign-in and receives billing and security notices.",
            },
            {
                "heading": "Answer the onboarding questions",
                "body": [
                    "Onboarding asks for the company name, the first store name, the country and the currency. Then it asks what kind of business you run. Choose 'Cafe / coffee shop'.",
                    "The business type is not cosmetic. It seeds useful starting categories and turns on the feature packs a coffee counter usually needs: variants for sizes, modifiers for milk and sugar, and delivery. You can change individual feature packs later without changing the business type.",
                ],
                "steps": [
                    "Enter the company name as it should appear on reports.",
                    "Enter the store name customers and staff will recognise.",
                    "Choose your country and primary currency.",
                    "Choose Cafe / coffee shop as the business type.",
                    "Pick the plan you want to start on; the free plan is enough for a first store.",
                ],
                "tip": "The company is the umbrella; the store is the physical counter. You can add more stores later without recreating the company.",
            },
            {
                "heading": "Check your starting data",
                "body": [
                    "A new coffee workspace starts with Coffee, Tea, Bakery and Cold drinks categories and a few sample products, so the register is never an empty screen. Treat these as a starting point, not a menu.",
                    "Rename the categories to match the words on your menu, and replace or edit the sample products in the next guide. If you are not ready to sell, leave the samples until you have added your real items.",
                ],
                "steps": [
                    "Open Products and review the seeded categories.",
                    "Rename a category if your menu uses a different word.",
                    "Open the store settings and confirm the address and receipt details.",
                    "Invite the people who will work the counter once the menu is ready.",
                ],
            },
            {
                "heading": "Set currency, tax and receipt basics",
                "body": [
                    "Open Settings before the first sale. Confirm the primary currency, enable KHR if you accept riel, and add the exchange rate you use at the counter. Then set the tax rate that applies to your sales and choose whether displayed prices include it.",
                    "These choices affect totals, receipts and reports, so decide them before training anyone. Changing them later is possible but confusing during service.",
                ],
                "steps": [
                    "Open Settings and choose Currencies to confirm the primary currency.",
                    "Enable a second currency only if you actually accept it.",
                    "Set the exchange rate you will use at the counter.",
                    "Open Store settings and enter the address and tax rate.",
                    "Open Receipts and add your logo, footer and order prefix.",
                ],
                "tip": "If you are unsure about tax, set the rate your accountant confirms and keep a note of the decision. Do not guess a rate on launch day.",
            },
        ],
        "takeaways": [
            "Verify the account before onboarding so the workspace belongs to a real sign-in.",
            "Choose Cafe / coffee shop to seed the right categories and feature packs.",
            "Confirm currency and tax before the first sale, not after.",
            "The seeded categories and products are a starting point you should rename and replace.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "build-your-coffee-menu",
        "title": "Build a coffee menu that is fast to ring up",
        "summary": "Turn your paper menu into categories and products the register can find in a second.",
        "group_title": "Set up your menu",
        "level": "beginner",
        "estimated_minutes": 15,
        "is_featured": False,
        "position": 3,
        "seo_title": "Build a coffee shop menu in your POS | Chmaba guides",
        "seo_description": "How to structure coffee shop categories and products in Chmaba so the register stays fast, stock stays honest and reports are useful.",
        "intro": [
            "The register should mirror the way your barista thinks during a rush: category first, then the drink, then the choices. Build the menu in that order and a new team member can take an order on their first shift.",
        ],
        "learning_points": [
            "Structure categories around how customers order",
            "Add products with a price and a cost price",
            "Use product names that survive a busy counter",
            "Decide which items need stock tracking",
        ],
        "requirements": [
            "Your final drink list with prices",
            "Ingredient costs per drink",
            "A photo for any item you want to show on the POS grid",
        ],
        "sections": [
            {
                "heading": "Group the menu the way the counter works",
                "body": [
                    "Four to six categories is plenty for most coffee shops. A useful starting structure is Hot coffee, Iced coffee, Tea and matcha, Bakery, and Extras. If your menu separates blended drinks or food, add one category for that rather than burying them in Coffee.",
                    "Avoid categories named after suppliers or internal prep areas. The category is a signpost for a cashier, not a stockroom label.",
                ],
                "steps": [
                    "Open Categories and choose Add category.",
                    "Name each category in the words your staff use at the counter.",
                    "Keep the order stable; the POS grid follows it, so put best sellers high.",
                    "Move on to products once the category list reads like the menu board.",
                ],
                "tip": "If a category has more than about 24 items, split it. A long scroll costs more time than an extra tab.",
            },
            {
                "heading": "Add each drink as a product",
                "body": [
                    "Open Products and choose Add product. Enter the name, category, selling price and cost price. The cost price is what makes the margin report truthful; it is not shown to customers.",
                    "Use a SKU that means something to you, such as COF-001 for a coffee and ICED-004 for an iced drink. If you scan packaged goods, add the barcode as well.",
                ],
                "steps": [
                    "Open Products and choose Add product.",
                    "Enter the name exactly as the customer says it.",
                    "Choose the category and enter the selling price.",
                    "Enter the cost price for one serving.",
                    "Add a SKU and, for packaged goods, a barcode.",
                    "Save and confirm the item appears on the POS grid.",
                ],
                "tip": "Use 'Iced Latte' and 'Hot Latte' as separate products. One ambiguous 'Latte' with a hidden option is a common source of wrong drinks.",
            },
            {
                "heading": "Decide what you actually count",
                "body": [
                    "A made-to-order latte is not a stock item; it is a recipe. Track the things you physically count: bags of beans, cartons of milk, cups and lids, pastries, bottled drinks, retail bags. Leave made-to-order drinks untracked so the register never blocks a sale because a recipe has no stock balance.",
                    "For tracked items, set a reorder point that reflects how often you order. A reorder point of one day of sales is too late for a weekly delivery; use the lead time plus a safety buffer.",
                ],
                "steps": [
                    "Turn on Track inventory only for items you physically count.",
                    "Set the opening stock for those items.",
                    "Set a reorder point based on supplier lead time.",
                    "Leave drinks and other made-to-order items untracked.",
                ],
                "tip": "If you want ingredient-level control later, track milk and beans as separate products and adjust them at stock count; do not try to deduct every gram on every sale in the first week.",
            },
            {
                "heading": "Make the grid easy to scan",
                "body": [
                    "Images and consistent names shorten the time it takes to find a product. Put the best sellers in the first positions and use the same capitalisation everywhere.",
                    "If an item runs out, hide it or mark it unavailable rather than leaving a button that records a sale you cannot make. Stock tracking does this automatically for tracked items; for untracked drinks, use the product's active setting.",
                ],
                "steps": [
                    "Add a clear photo to your top ten products.",
                    "Put best sellers first in each category.",
                    "Hide or deactivate seasonal items instead of deleting them.",
                    "Walk the grid once as if you were taking an order; move anything you struggled to find.",
                ],
            },
        ],
        "takeaways": [
            "Four to six categories keep the register fast.",
            "Separate hot and iced drinks into distinct products.",
            "Track countable goods, not made-to-order drinks.",
            "Use cost prices and consistent names so reports and training stay clear.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "sizes-milk-and-extras",
        "title": "Sizes, milk and extras: variants vs modifiers",
        "summary": "Set up sizes as variants and milk, sugar and extras as modifiers so the register asks the right question at the right time.",
        "group_title": "Set up your menu",
        "level": "intermediate",
        "estimated_minutes": 15,
        "is_featured": False,
        "position": 4,
        "seo_title": "Coffee sizes, milk options and modifiers in a POS | Chmaba guides",
        "seo_description": "Use variants for size and modifiers for milk, sugar and extras in Chmaba. Avoid the combinatorial mess that makes coffee ordering slow.",
        "intro": [
            "Sizes and milk look like the same kind of choice, but they behave differently. A size changes the product you are selling and often its cost. Milk, sugar and extras change the drink without changing what it is. Model them differently and the register stays short.",
        ],
        "learning_points": [
            "Use variants for size and cost differences",
            "Use modifier groups for milk, sugar and extras",
            "Avoid creating a product for every possible combination",
            "Make required choices obvious to the cashier",
        ],
        "requirements": [
            "Your size names and the price for each size",
            "Your milk options and any upcharge",
            "Your sugar levels and extras with prices",
        ],
        "sections": [
            {
                "heading": "Sizes belong in variants",
                "body": [
                    "A 12oz latte and a 16oz latte have different prices and different ingredient costs. In Chmaba, variants give each size its own SKU, price, cost and stock behaviour, and the register shows each size as its own tile.",
                    "Do not create a separate parent product for each size. That multiplies your menu and makes reports harder to read. One drink, three variants is the clean model.",
                ],
                "steps": [
                    "Open Products and find the drink.",
                    "Choose Manage variants on the product row.",
                    "Add one variant per size with its own name, SKU, price and cost.",
                    "Set stock per variant only if you track the drink itself.",
                    "Save and check that each size appears as its own tile on the register.",
                ],
                "tip": "A product with variants uses each variant's SKU, so the parent SKU becomes a reference rather than a sellable code.",
            },
            {
                "heading": "Milk, sugar and extras belong in modifiers",
                "body": [
                    "In Chmaba a product can have one modifier group attached to it. Use that group for the choice that matters most for the drink - Milk for a latte, Sugar level for a tea - and give every option its price difference.",
                    "If you also sell extras, add them as options in the same group and allow more than one selection, or keep them as separate product tiles. One short group per product is easier to train than a long list of every possible add-on.",
                ],
                "steps": [
                    "Open Products and choose Modifier groups.",
                    "Create a group such as Milk and add Whole, Oat, Soy and Almond.",
                    "Set a price difference only where the supplier charges you more.",
                    "Mark the group required if the barista must make a choice.",
                    "Open the product, choose the modifier group in Edit product, and save.",
                    "Test the prompt on the register before service.",
                ],
                "tip": "Keep the group small and specific. A milk group with four options is usable; one group holding every syrup, milk and extra is not.",
            },
            {
                "heading": "Avoid the combination trap",
                "body": [
                    "If you create a variant for every size and every milk, a three-size, four-milk menu becomes twelve variants per drink and hundreds across the menu. That is hard to price, hard to count and hard to train.",
                    "The rule is simple: if it changes what the product is and what it costs to make, make it a variant. If it is a preference added to the same drink, make it a modifier.",
                ],
                "steps": [
                    "List every option you offer.",
                    "Mark options that change the base recipe and cost as variants.",
                    "Mark preference and add-on options as modifiers.",
                    "Rebuild any product that currently has a variant for milk.",
                ],
            },
            {
                "heading": "Test the order the way a customer speaks",
                "body": [
                    "A customer says 'a large iced latte with oat milk'. That should be one size tile tap plus one milk choice. If it takes more than that, simplify the setup.",
                ],
                "steps": [
                    "Tap the Iced Latte - 16 oz tile on the register.",
                    "Tick Oat milk in the options and choose Add item.",
                    "Check the cart line shows the size and the milk option.",
                    "Print a test receipt and read it back as a barista.",
                ],
                "tip": "A receipt that prints '16 oz / Oat milk' under the drink is a production ticket, not just a price slip.",
            },
        ],
        "takeaways": [
            "Size is a variant; milk, sugar and extras are modifiers.",
            "Give each size its own price and cost so margins are accurate.",
            "A product has one modifier group: use it for the choice that matters most.",
            "Test the full order flow and read the printed ticket.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "price-for-margin",
        "title": "Price your drinks for a real margin",
        "summary": "Use cost price, recipe costing and the margin report to see which drinks actually make money.",
        "group_title": "Set up your menu",
        "level": "intermediate",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 5,
        "seo_title": "Coffee shop drink costing and margin report | Chmaba guides",
        "seo_description": "Set cost prices, read the margin report and protect coffee shop profits with a simple recipe-costing routine in Chmaba.",
        "intro": [
            "Revenue is not profit. A busy counter can still lose money if the drinks are priced below their ingredient cost or if discounts eat the difference. Chmaba gives every product a cost price so the margin report can show the truth.",
        ],
        "learning_points": [
            "Record a cost price for every drink and variant",
            "Read the margin report without an accounting degree",
            "Set a discount floor that protects the till",
            "Know when to reprice after a supplier change",
        ],
        "requirements": [
            "Ingredient cost per drink",
            "Current selling prices",
            "Access to Reports as an owner or manager",
        ],
        "sections": [
            {
                "heading": "Cost one drink properly",
                "body": [
                    "A latte cost is not just the beans. Add the coffee dose, the milk volume, the cup, lid and sleeve, and any garnish. For a bakery item, use the supplier cost or your own batch cost per piece.",
                    "If a 16oz latte uses 18g of beans at $0.03 per gram, 220ml of milk at $0.0015 per ml, and $0.18 of cup and lid, the ingredient cost is about $1.05. Add a small waste allowance if your team pours off shots regularly.",
                ],
                "steps": [
                    "Weigh or measure one serving of each ingredient.",
                    "Multiply by your supplier cost per unit.",
                    "Add packaging and a waste allowance.",
                    "Round to a practical cost figure and record it on the product or variant.",
                ],
                "tip": "Variants have their own cost, so a 20oz drink should not inherit the 12oz cost. Set both.",
            },
            {
                "heading": "Read the margin report",
                "body": [
                    "Open Reports and choose the Margin report. It compares what you sold with the cost price recorded on each product. The result is a gross-margin view, not a full profit-and-loss statement: rent, wages and utilities are not in it.",
                    "Look for drinks that sell well but contribute little, and drinks with a healthy margin that nobody orders. The first is a pricing conversation; the second is a menu or staff-training conversation.",
                ],
                "steps": [
                    "Open Reports and choose a period such as Last 7 days.",
                    "Open the Margin report.",
                    "Sort by contribution, not only by quantity.",
                    "Write down the three products to reprice and the three to promote.",
                ],
            },
            {
                "heading": "Set a discount floor",
                "body": [
                    "A discount is a transfer from your margin to the customer. Decide the maximum percentage a cashier may give without approval and configure the approval policy so larger discounts pause for a manager.",
                    "Do the arithmetic before a promotion: if a drink has a 65 percent gross margin, a 20 percent discount still leaves money; a 50 percent discount may leave almost none after packaging and waste.",
                ],
                "steps": [
                    "Decide the maximum cashier discount.",
                    "Turn on the approval requirement for larger discounts.",
                    "Brief the team on which promotions are allowed and when.",
                    "Review discount totals in Reports after the first week.",
                ],
                "tip": "A discount that is not recorded is worse than no discount: it hides the cost and trains the team to improvise.",
            },
            {
                "heading": "Reprice when costs move",
                "body": [
                    "Milk, beans and packaging change price. When a supplier invoice changes, update the cost price on the affected products and variants the same week. Otherwise the margin report slowly drifts away from reality.",
                    "You do not need to reprice the menu every time; you need to know when the margin has moved enough to justify it.",
                ],
                "steps": [
                    "Keep supplier invoices in one place.",
                    "When a cost changes, update the product cost price.",
                    "Re-read the margin report for the affected category.",
                    "Reprice only the drinks whose margin has fallen below your floor.",
                ],
            },
        ],
        "takeaways": [
            "Cost the whole serving, including packaging and waste.",
            "The margin report is a decision tool, not a full P&L.",
            "Protect a discount floor with an approval rule.",
            "Update costs when suppliers change and reprice selectively.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "payments-receipts-and-display",
        "title": "Connect payments, receipts and the customer screen",
        "summary": "Set up KHQR, receipt printing and the customer display so checkout is one smooth motion.",
        "group_title": "Set up your menu",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 6,
        "seo_title": "Set up KHQR, receipts and a customer display | Chmaba guides",
        "seo_description": "Connect an ABA PayWay KHQR link, configure receipt printing and open the customer display in Chmaba.",
        "intro": [
            "Checkout has three visible parts: taking the money, printing the proof and showing the customer what they are paying. Configure each one before the first real sale and the counter stays calm at the busiest moment.",
        ],
        "learning_points": [
            "Connect and verify an ABA PayWay link for KHQR",
            "Turn on the right POS preferences",
            "Customise and test the receipt",
            "Open the customer display on a second screen",
        ],
        "requirements": [
            "An active ABA PayWay link from your bank",
            "A receipt printer connected to the register",
            "A second monitor if you want a customer display",
        ],
        "sections": [
            {
                "heading": "Connect KHQR through ABA PayWay",
                "body": [
                    "Open Settings and choose Bank & KHQR. Paste the PayWay link for the company, or for one store if the store has its own merchant account. Save the link and choose Test connection.",
                    "Once the link is verified, KHQR appears as a payment method at checkout. A store-level link overrides the company link for that store, which is useful when each branch settles to a different account.",
                ],
                "steps": [
                    "Open Settings and choose Bank & KHQR.",
                    "Paste the ABA PayWay link.",
                    "Choose Save link.",
                    "Choose Test connection and confirm it succeeds.",
                    "Open the register and check that KHQR is available at checkout.",
                ],
                "tip": "KHQR confirmation needs an internet connection. Keep a cash fallback for the moment the connection drops.",
            },
            {
                "heading": "Set the POS preferences once",
                "body": [
                    "Open Settings and choose POS preferences. Decide whether a shift must be open before selling, whether discounts and tips are allowed, whether the sale sound plays and whether receipts auto-print.",
                    "The shift setting is a control, not a formality. If it is on and no shift is open, the register will not charge a sale. Choose it deliberately and train the opening routine.",
                ],
                "steps": [
                    "Choose whether an open shift is required.",
                    "Turn discounts and tips on or off for the counter.",
                    "Turn on auto-print if you always print a receipt.",
                    "Save and make a test sale.",
                ],
            },
            {
                "heading": "Make the receipt useful",
                "body": [
                    "Open Settings and choose Receipts. Set the order prefix, paper size and language, then choose and edit the template. Add your logo, address, phone number and a short footer such as a thank-you line or Wi-Fi password.",
                    "Use the preview at true paper size, then print a test. Check that the drink name, size, modifiers and total are readable and that the receipt cuts cleanly.",
                ],
                "steps": [
                    "Set the order prefix and paper size.",
                    "Add the store address and phone number.",
                    "Add a logo and a short footer.",
                    "Choose the blocks you need and remove the rest.",
                    "Print a test receipt and read it as a customer would.",
                ],
                "tip": "For printing with no browser dialog, launch the POS with kiosk printing or use QZ Tray. Auto-print alone still opens the normal print dialog in a regular browser tab.",
            },
            {
                "heading": "Open the customer display",
                "body": [
                    "A second screen lets the customer see the cart and the KHQR code. In Settings, open Customer display and turn it on. On the register, choose Open customer display; a new window opens and follows the sale.",
                    "Move that window to the customer-facing monitor. The display only shows live data while a register is open on the same computer; opened on its own it shows 'Waiting for the register'.",
                ],
                "steps": [
                    "Open Settings and choose Customer display.",
                    "Turn on Enable the customer display.",
                    "On the register, choose Open customer display.",
                    "Drag the window to the customer-facing monitor.",
                    "Add an item and confirm the display updates.",
                ],
            },
        ],
        "takeaways": [
            "Verify the PayWay link before launch, not during the first KHQR sale.",
            "Choose the shift policy deliberately and train the opening routine.",
            "A tested receipt is part of checkout, not an afterthought.",
            "The customer display needs a register open on the same computer.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "ring-up-your-first-sale",
        "title": "Ring up your first coffee sale",
        "summary": "A complete walkthrough from opening the shift to handing over the receipt - cash, KHQR and a mixed payment.",
        "group_title": "Sell every day",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": True,
        "position": 7,
        "seo_title": "How to ring up a coffee shop sale in Chmaba | Chmaba guides",
        "seo_description": "Walk through a real coffee order in Chmaba: open a shift, choose order type, add drinks and modifiers, take cash or KHQR and print the receipt.",
        "intro": [
            "This is the full counter loop with a realistic order: a large iced latte with oat milk, a small hot americano and a croissant. Follow it once with a test sale before the shop opens.",
        ],
        "learning_points": [
            "Open a shift and choose the order type",
            "Add drinks and choose size and modifiers",
            "Take cash, KHQR or a split payment",
            "Finish the sale and hand over a receipt",
        ],
        "requirements": [
            "At least one product with variants and modifiers",
            "A payment method configured (cash or KHQR)",
            "A receipt printer or the customer display if you use one",
        ],
        "sections": [
            {
                "heading": "Open the register",
                "body": [
                    "Open Point of sale. If your settings require a shift, choose Open shift and enter the opening cash float. Every sale after that belongs to the shift, which is what makes the end-of-day cash count meaningful.",
                    "Set the order type before adding items: Takeaway for the queue at the bar, Dine-in if the customer is staying, Delivery if the order goes out. The choice is saved on the order and appears in reports.",
                ],
                "steps": [
                    "Open Point of sale.",
                    "Choose Open shift and enter the cash float.",
                    "Choose Takeaway, Dine-in or Delivery.",
                    "Confirm the cart is empty or clear it before starting.",
                ],
                "tip": "If the charge button seems blocked, check whether a shift is required and not yet open.",
            },
            {
                "heading": "Add the drinks",
                "body": [
                    "The register shows each size as its own tile. Tap the tile for the size the customer wants; if the drink has a modifier group, its options open next.",
                    "Add the second drink and the croissant the same way. Read the cart back to the customer before you charge; correcting a drink is easier now than after payment.",
                ],
                "steps": [
                    "Tap Iced Latte - 16 oz.",
                    "Tick Oat milk in the options and choose Add item.",
                    "Tap Hot Latte - 12 oz.",
                    "Tap Butter Croissant.",
                    "Read the cart back and confirm the total.",
                ],
                "tip": "The cart line should show the modifiers. If it does not, the receipt will not tell the barista what to make.",
            },
            {
                "heading": "Take the payment",
                "body": [
                    "Choose Charge to open the payment screen. For cash, enter the amount received and confirm the change. For KHQR, choose KHQR and show the code to the customer, then wait for the confirmation on screen.",
                    "For a split payment, add the first tender, then the second, until the remaining balance is zero. Cash plus KHQR on one sale is supported and is common when a customer wants to use up cash.",
                ],
                "steps": [
                    "Choose Charge.",
                    "For cash, enter the amount received and check the change.",
                    "For KHQR, show the QR and wait for confirmation.",
                    "For a split, add each tender until the balance is zero.",
                    "Complete the sale and print or email the receipt.",
                ],
                "tip": "If the KHQR confirmation is slow, do not re-enter the sale. Wait for the state to settle, or use the order in Orders to check its payment status.",
            },
            {
                "heading": "Finish and hand over",
                "body": [
                    "When the sale completes, the receipt prints if auto-print is on. Hand it over, or use Orders to reprint or email a copy. The order is now in the day's totals and in the shift.",
                    "Keep the test receipt and compare it with the cart. If a modifier is missing or the size is wrong, fix the product setup before the next customer.",
                ],
                "steps": [
                    "Confirm the receipt printed or the customer display shows the total.",
                    "Hand the receipt to the customer.",
                    "Open Orders to confirm the sale is listed as paid.",
                    "Void the test sale with a refund if it was not a real sale.",
                ],
            },
        ],
        "takeaways": [
            "Open the shift before the first sale so cash reconciles later.",
            "Set the order type before adding items.",
            "Read the cart and modifiers back before charging.",
            "Cash, KHQR and split payments all follow the same charge screen.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "holds-splits-and-refunds",
        "title": "Holds, split payments and refunds",
        "summary": "Handle the queue without losing an order, and correct a sale without breaking the day's totals.",
        "group_title": "Sell every day",
        "level": "intermediate",
        "estimated_minutes": 10,
        "is_featured": False,
        "position": 8,
        "seo_title": "Hold orders, split payments and refunds in a coffee shop | Chmaba guides",
        "seo_description": "Park an order, take a mixed payment and refund a coffee sale correctly in Chmaba.",
        "intro": [
            "A busy counter produces interruptions: a customer steps aside to find a wallet, a group wants to pay separately, a drink comes back because the milk was wrong. Each has a clean path in the register.",
        ],
        "learning_points": [
            "Park an order with Hold and resume it later",
            "Take a payment in two parts without losing the total",
            "Refund all or part of a sale",
            "Know when a refund needs manager approval",
        ],
        "requirements": [
            "A completed test sale to practise on",
            "A manager account if approval rules are on",
        ],
        "sections": [
            {
                "heading": "Hold an order instead of deleting it",
                "body": [
                    "With items in the cart, choose Hold and add a label such as the customer's name or 'table 4'. The cart clears so you can serve the next customer, and the order waits under Held.",
                    "When the customer is ready, open Held, find the order and resume it. The items return to the cart. Discard only when the customer has left; it removes the parked order for good.",
                ],
                "steps": [
                    "Add the items to the cart.",
                    "Choose Hold and enter a recognisable label.",
                    "Serve the next customer.",
                    "Open Held, choose the order and resume it.",
                    "Charge as usual.",
                ],
                "tip": "If the cart already has items when you resume, choose whether to replace or merge them.",
            },
            {
                "heading": "Split the payment",
                "body": [
                    "Open Charge and enter the first tender: choose the method and the amount, then add it. The remaining balance updates. Add the second tender for the rest and finish when the balance is zero.",
                    "Do not complete a sale while a balance remains unless your policy allows it; the payment record should match what the customer actually handed over.",
                ],
                "steps": [
                    "Choose Charge.",
                    "Choose the first method and enter its amount.",
                    "Add the tender.",
                    "Choose the second method and enter the remaining amount.",
                    "Complete the sale when the balance reaches zero.",
                ],
            },
            {
                "heading": "Refund the right way",
                "body": [
                    "Open Orders, find the sale and choose Refund. Choose the quantity to refund for each line, pick the refund method and add a reason. Confirm only when the quantities and method are correct.",
                    "A full refund returns the whole sale; a partial refund returns only the chosen quantities. For tracked goods, the stock returns to inventory. For serial-tracked goods, the serial is released.",
                ],
                "steps": [
                    "Open Orders and find the sale.",
                    "Choose Refund.",
                    "Set the quantity for each line; use zero for lines that stay.",
                    "Choose the refund method and enter a reason.",
                    "Confirm and give the customer the refund receipt.",
                ],
                "tip": "If your team uses approvals, a large refund may pause for a manager. That pause is a control, not an error; ask the manager to approve it.",
            },
            {
                "heading": "Cancel an unpaid order",
                "body": [
                    "An order that was never paid should be cancelled, not refunded. Open Orders, filter to Pending, open the order and choose Cancel. Add a reason. No stock changes because the sale never took payment.",
                ],
                "steps": [
                    "Open Orders and filter to Pending.",
                    "Open the order.",
                    "Choose Cancel and add a reason.",
                    "Confirm the order is marked cancelled.",
                ],
                "tip": "Refunding a paid order and cancelling an unpaid one are different actions. Using the wrong one makes the day's totals misleading.",
            },
        ],
        "takeaways": [
            "Hold keeps a live order without deleting the cart.",
            "Split payments add tenders until the balance is zero.",
            "Refund the paid lines and quantities; cancel only unpaid orders.",
            "Approval rules can pause a refund or discount for a manager.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "keep-stock-honest",
        "title": "Keep stock honest without slowing service",
        "summary": "Track the goods you count, set reorder points and receive deliveries without turning the bar into a warehouse.",
        "group_title": "Run your shop",
        "level": "intermediate",
        "estimated_minutes": 15,
        "is_featured": False,
        "position": 9,
        "seo_title": "Coffee shop inventory, reorder points and purchase orders | Chmaba guides",
        "seo_description": "A practical inventory routine for coffee shops in Chmaba: track countable goods, set reorder points, receive stock and record waste.",
        "intro": [
            "Inventory goes wrong in coffee shops for a simple reason: teams try to track every gram of milk on every sale, give up, and then trust no number at all. A better routine tracks the goods you physically count and reconciles them on a schedule.",
        ],
        "learning_points": [
            "Choose which goods deserve stock tracking",
            "Set a reorder point that matches supplier lead time",
            "Receive a delivery and record waste",
            "Use purchase orders and suppliers without extra admin",
        ],
        "requirements": [
            "A list of countable goods: beans, milk, cups, pastries, retail bags",
            "Opening counts for those goods",
            "Supplier names and delivery lead times",
        ],
        "sections": [
            {
                "heading": "Track what you can count in a minute",
                "body": [
                    "Track bags of beans, cartons of milk, sleeves of cups, pastry trays and retail bags. Do not track made-to-order drinks; they are recipes, not stock. The aim is a count a barista can finish before opening, not a full cost-accounting system.",
                    "If milk and beans matter to your margin, track them as products and adjust them at stock count. Start with the five or ten items that would hurt most if they ran out.",
                ],
                "steps": [
                    "List the goods you order every week.",
                    "Mark the ones that would stop service if they ran out.",
                    "Turn on inventory tracking and set opening stock for those.",
                    "Leave drinks and assembled items untracked.",
                ],
            },
            {
                "heading": "Set a reorder point that actually warns you",
                "body": [
                    "A reorder point is the level at which someone should order, not the level at which you are already out. If your milk supplier delivers twice a week, the reorder point should cover the days between deliveries plus a buffer for a busy weekend.",
                    "Set the reorder point per product or variant. Overview and Inventory show low-stock items when the count crosses it.",
                ],
                "steps": [
                    "Calculate average daily use for each tracked item.",
                    "Add the supplier lead time in days.",
                    "Add a safety buffer for weekends and events.",
                    "Set that number as the reorder point.",
                    "Check the low-stock list each morning.",
                ],
                "tip": "A reorder point of one unit is a warning that arrives too late. Use days of cover, not a round number.",
            },
            {
                "heading": "Receive deliveries and record waste",
                "body": [
                    "When a delivery arrives, open Inventory, find the product and choose Restock. Enter the quantity received and a reason such as Delivery. On-hand stock updates for every register in that store.",
                    "Waste is a stock movement too. Spilled milk, stale pastries and cups used for training should be adjusted down with a reason. If waste is invisible, your margin report will blame the menu for a process problem.",
                ],
                "steps": [
                    "Count the delivery before signing for it.",
                    "Use Restock to add the received quantity.",
                    "Choose Adjust and a minus quantity for waste or breakage.",
                    "Pick a reason so the movement is explainable later.",
                    "Review Stock history when a count does not match.",
                ],
            },
            {
                "heading": "Use suppliers and purchase orders when ordering gets complex",
                "body": [
                    "For a single shop, a paper order list is fine. When you have several suppliers, lead times or stores, record them. Open Suppliers and add the contact and phone number. Open Purchase orders, create an order with the product, supplier and quantity, and receive it when the delivery arrives.",
                    "A purchase order gives you a record of what was ordered versus what arrived, which is the quickest way to catch a short delivery.",
                ],
                "steps": [
                    "Add each regular supplier with a contact name and phone.",
                    "Create a purchase order for the next delivery.",
                    "Receive the order when the stock arrives.",
                    "Compare the received quantity with the order before closing it.",
                    "Transfer stock to another store only when it physically moves.",
                ],
            },
        ],
        "takeaways": [
            "Track countable goods, not made-to-order drinks.",
            "Set reorder points from daily use plus lead time plus a buffer.",
            "Record deliveries and waste as stock movements with reasons.",
            "Use purchase orders when suppliers or stores multiply.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "open-and-close-the-day",
        "title": "Open and close the day",
        "summary": "A repeatable opening routine, a cash count that reconciles and a close that leaves tomorrow ready.",
        "group_title": "Run your shop",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 10,
        "seo_title": "Coffee shop opening and closing routine | Chmaba guides",
        "seo_description": "Open the shift, count the float, close the till, read the day's report and record waste in Chmaba.",
        "intro": [
            "A shift is the bridge between the cash in the drawer and the sales in the system. A short, repeated opening and closing routine is the cheapest loss prevention a coffee shop can have.",
        ],
        "learning_points": [
            "Open a shift with a known cash float",
            "Close the shift and explain any variance",
            "Read the daily summary before leaving",
            "Record waste and hand over the next shift",
        ],
        "requirements": [
            "A cash drawer with a counted float",
            "The shift setting enabled or a decision to use it",
        ],
        "sections": [
            {
                "heading": "Open with a counted float",
                "body": [
                    "Count the opening cash before the first sale and enter it when you open the shift. Count it with a second person if the amount is large. The float is not sales; it is the cash that must still be in the drawer at close.",
                    "If the shop does not use shifts, at least count the drawer at the start of the day and write the number down. A number you cannot compare is not a control.",
                ],
                "steps": [
                    "Count the opening cash.",
                    "Open Point of sale and choose Open shift.",
                    "Enter the float.",
                    "Start selling; every sale is linked to the shift.",
                    "Keep the float separate from the day's takings if your drawer allows it.",
                ],
            },
            {
                "heading": "Close with a real count",
                "body": [
                    "At the end of service, choose Close shift, count the cash in the drawer and enter the counted amount. The app compares expected cash with the counted cash and shows the difference.",
                    "Investigate a variance the same day. A small difference can be a tip or a rounding issue; a large one is a process problem. The point is not to punish the cashier but to find the missing step.",
                ],
                "steps": [
                    "Choose Close shift.",
                    "Count all cash, including the float.",
                    "Enter the counted amount.",
                    "Read the expected, counted and difference figures.",
                    "Write a note for any difference before confirming.",
                ],
                "tip": "Count in the same order every day. A consistent routine catches a mistake before it becomes a mystery.",
            },
            {
                "heading": "Read the daily summary",
                "body": [
                    "Open Reports and choose Today. Check gross sales, refunds, discounts, tax and the number of transactions. Compare the payment mix with what you expect: if KHQR is usually half of sales and today it is zero, a link or a device may be down.",
                    "Open the top products and the low-stock list. This is also the moment to notice a drink that is selling far more than usual, or a category with no sales because it was hidden.",
                ],
                "steps": [
                    "Open Reports and choose Today.",
                    "Check sales, refunds and discounts.",
                    "Check the payment methods.",
                    "Check top products and low stock.",
                    "Note one thing to fix tomorrow.",
                ],
            },
            {
                "heading": "Record waste and hand over",
                "body": [
                    "Before leaving, adjust stock for waste with a reason. Leave a short handover note: what ran low, what is being repaired, what promotion is live and any cash variance.",
                    "The next shift should not have to reconstruct the day from memory. A two-minute close saves ten minutes of confusion at opening.",
                ],
                "steps": [
                    "Adjust stock for waste and breakage.",
                    "Check the low-stock list for tomorrow's order.",
                    "Leave a handover note for the next shift.",
                    "Lock the cash drawer and the register.",
                    "Close the shift if it is still open.",
                ],
            },
        ],
        "takeaways": [
            "The opening float is the anchor for the whole day's cash.",
            "A close is a count plus an explanation, not just a button.",
            "Read sales, payments, top products and low stock before leaving.",
            "Record waste and leave a handover note.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "train-your-team",
        "title": "Train your baristas and protect the till",
        "summary": "Invite the right people, give them only the access they need and set approval rules that do not slow service.",
        "group_title": "Train & go live",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 11,
        "seo_title": "Coffee shop team roles and till controls | Chmaba guides",
        "seo_description": "Invite baristas and managers to Chmaba, assign the right roles and set approval rules for discounts and refunds.",
        "intro": [
            "A small team still needs clear boundaries. The goal is not to distrust the people at the counter; it is to make the safe action the easy action and to keep an accurate record when someone needs help.",
        ],
        "learning_points": [
            "Invite a manager and a cashier with the right role",
            "Restrict a team member to the stores they work in",
            "Set discount and refund approvals",
            "Run a first-shift training checklist",
        ],
        "requirements": [
            "The team member's email address",
            "A decision on which stores each person can access",
            "A discount and refund policy",
        ],
        "sections": [
            {
                "heading": "Use the smallest role that fits",
                "body": [
                    "The owner has full access, including billing and team management. A manager runs the store and sees reports and approvals. An inventory manager handles products, stock, suppliers and purchases. A cashier sells and looks after customers without settings or reports.",
                    "Give each person the smallest role that lets them do their job. A barista does not need billing access to make coffee.",
                ],
                "steps": [
                    "Open Team access and choose Invite.",
                    "Enter the email address.",
                    "Choose the role: manager, inventory manager or cashier.",
                    "Choose the stores the person can work in.",
                    "Send the invitation and ask them to accept it.",
                ],
                "tip": "You can also accept an invitation on a member's behalf from the invitations list if the email is slow to arrive.",
            },
            {
                "heading": "Keep store access deliberate",
                "body": [
                    "A team member can be limited to specific stores. That matters when a manager covers one branch and the owner covers all of them. Check the store list when you invite and when someone changes location.",
                ],
                "steps": [
                    "When inviting, select only the stores the person needs.",
                    "Review access after a transfer or a new branch opens.",
                    "Deactivate a leaver instead of deleting the history.",
                    "Remove access for good when the person will not return.",
                ],
            },
            {
                "heading": "Set approvals for the exceptions",
                "body": [
                    "Most sales should not need a manager. Set the approval policy so only the exceptions pause: a discount above your floor, a refund above a threshold, a price or cost change. This keeps the queue moving while protecting the margin.",
                    "Decide the thresholds before training. A rule announced after an incident feels like punishment; a rule explained on day one feels like the job.",
                ],
                "steps": [
                    "Decide the maximum cashier discount.",
                    "Decide the refund threshold that needs approval.",
                    "Set the approval policy.",
                    "Explain what happens on screen when approval is required.",
                    "Review approvals in Activity after the first week.",
                ],
            },
            {
                "heading": "Run a first-shift checklist",
                "body": [
                    "A new barista should spend the first shift learning the register, not the whole back office. Keep the checklist to the tasks they will actually do.",
                ],
                "steps": [
                    "Sign in and open the shift with a float.",
                    "Find a product and add a size and a modifier.",
                    "Hold and resume an order.",
                    "Take a cash sale and read the change.",
                    "Take a KHQR sale and wait for confirmation.",
                    "Close the shift with a count under supervision.",
                    "Show where to ask for help when something is wrong.",
                ],
                "tip": "Change the cashier session length in Settings if a shared register should sign out automatically between users.",
            },
        ],
        "takeaways": [
            "Give each person the smallest role that fits the job.",
            "Limit store access deliberately and review it after changes.",
            "Use approvals only for the exceptions you named in advance.",
            "Train the register loop first; teach the back office later.",
        ],
    },
    {
        "category": "coffee-shop",
        "slug": "coffee-shop-launch-checklist",
        "title": "Go live: the coffee shop launch checklist",
        "summary": "The final checks for the day before opening, launch day and the first week of real sales.",
        "group_title": "Train & go live",
        "level": "beginner",
        "estimated_minutes": 8,
        "is_featured": True,
        "position": 12,
        "seo_title": "Coffee shop POS launch checklist | Chmaba guides",
        "seo_description": "A practical launch checklist for opening a coffee shop on Chmaba: menu, payments, receipts, stock, team and the first week of reports.",
        "intro": [
            "You are ready when the menu can be rung up without translation, a payment can be taken without a workaround and the close can be explained. Run this checklist once before opening and once after the first week.",
        ],
        "learning_points": [
            "Confirm the menu, prices and modifiers are complete",
            "Test every payment path you will use",
            "Check stock, receipts and team access",
            "Know what to review after the first week",
        ],
        "requirements": [
            "The previous guides completed",
            "A quiet hour to test the full sale flow",
        ],
        "sections": [
            {
                "heading": "The day before",
                "body": [
                    "Run a full test sale for each payment path: cash, KHQR and a split. Print a receipt and read it. Count the opening float. Make sure every drink on the board is on the register and no test item is still live.",
                ],
                "steps": [
                    "Ring up one cash sale and check the change.",
                    "Ring up one KHQR sale and wait for confirmation.",
                    "Ring up one split payment.",
                    "Print a receipt and check the modifiers appear.",
                    "Confirm the opening float and the drawer.",
                    "Hide or remove test products and test sales.",
                ],
            },
            {
                "heading": "Launch day",
                "body": [
                    "Open the shift before the first customer, keep the receipt printer loaded and keep a cash fallback for a network drop. Put one person in charge of the register and one person in charge of the bar so a problem at the till does not stop the drinks.",
                ],
                "steps": [
                    "Open the shift with the counted float.",
                    "Check the receipt paper and the customer display.",
                    "Confirm KHQR is visible at checkout.",
                    "Keep the manager logged in nearby for approvals.",
                    "At close, count the cash and read the summary.",
                ],
                "tip": "Do not launch a promotion and a new process on the same day. Change one thing at a time.",
            },
            {
                "heading": "After the first week",
                "body": [
                    "The first week is data, not a verdict. Read the reports and look for the three decisions that will make the next week better: a product to reprice, a product to promote and a process to simplify.",
                    "Check discount and refund totals, low-stock items and the payment mix. Ask the team which step on the register caused the most hesitation.",
                ],
                "steps": [
                    "Read the weekly sales and margin reports.",
                    "Review discounts and refunds.",
                    "Review low stock and waste.",
                    "Ask each team member for one friction point.",
                    "Change one menu or process item before the next week.",
                ],
            },
            {
                "heading": "Then keep it small",
                "body": [
                    "A coffee shop does not need a complex back office to be well run. It needs a menu that matches the board, prices that cover costs, a payment path that works and a closing count that is honest.",
                    "Add suppliers, multi-store reporting and advanced stock only when the shop needs them. The routine is the system.",
                ],
                "steps": [
                    "Keep the closing checklist visible.",
                    "Review the margin report every month.",
                    "Update costs when suppliers change.",
                    "Add the next location only when the first one closes cleanly.",
                ],
            },
        ],
        "takeaways": [
            "Test every payment path before the first customer.",
            "Launch with the menu and routine you can repeat, not the most complete setup.",
            "Use the first week's reports to make three concrete changes.",
            "Keep the daily routine small enough to actually happen.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "plan-your-restaurant",
        "title": "Plan your restaurant before you set it up",
        "summary": "Choose the service, menu, floor and kitchen flow first so the build is data entry instead of a redesign after opening.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": True,
        "position": 1,
        "seo_title": "How to plan a restaurant before opening | Chmaba guides",
        "seo_description": "A practical pre-launch plan for restaurants: service style, menu structure, floor layout, kitchen tickets, payments and the details to prepare before setup.",
        "intro": [
            "A restaurant is a menu, a floor and a kitchen moving at the same time. The register is only the point where they meet.",
            "Decide the service and the ticket flow first. Then the workspace, menu, tables and kitchen screens become one connected setup rather than four separate jobs.",
        ],
        "learning_points": [
            "Choose dine-in, takeaway and delivery deliberately",
            "Build a menu the kitchen can actually execute",
            "Plan areas, tables and seats before furniture arrives",
            "Gather the details needed for a one-pass setup",
        ],
        "requirements": [
            "Your menu with prices and rough food costs",
            "A floor plan with table numbers and seat counts",
            "Your tax rate and preferred payment methods",
            "The first team members and their roles",
        ],
        "sections": [
            {
                "heading": "Choose the service you will actually run",
                "body": [
                    "Start with how guests arrive. A dine-in restaurant needs a floor, table numbers and a kitchen that can see open tickets. A takeaway shop can run with a counter and a pickup shelf. Delivery adds an address, a driver and a dispatch step.",
                    "You can run more than one, but decide the default now. Order type at the register changes what the kitchen sees and what reports can separate later.",
                ],
                "steps": [
                    "List each way a guest can order: dine-in, takeaway, delivery or table QR.",
                    "Pick the service you will open with; add the others when the team is ready.",
                    "Decide whether guests are seated by staff or order from a QR code.",
                    "Write down how a ticket reaches the kitchen today.",
                ],
                "tip": "Opening with dine-in only is easier than launching every channel on the same day.",
            },
            {
                "heading": "Build a menu the kitchen can execute",
                "body": [
                    "A menu is a kitchen promise. Keep the opening menu small enough that every station can execute it during a full room: six to ten starters, mains and desserts is a useful starting size for a small kitchen.",
                    "Name dishes the way the pass calls them. Put modifiers where they change the plate (rare, extra sauce, no onion) and variants where they change the portion or price.",
                ],
                "steps": [
                    "Group dishes into starters, mains, desserts and drinks.",
                    "Remove dishes that share a station but no prep during service.",
                    "Write the cost of one portion for every dish.",
                    "Mark which items are cooked to order and which are ready to serve.",
                ],
            },
            {
                "heading": "Plan the floor before the furniture",
                "body": [
                    "Table numbers are not decoration; they are how the kitchen, the floor and the bill agree on one ticket. Walk the room and number tables in a logical order - by area, then from the door inward.",
                    "Areas also make the Floor view readable. Ground floor, terrace and private room are enough for most restaurants; avoid one area per table.",
                ],
                "steps": [
                    "Draw the room and number every table.",
                    "Record seats per table and any joinable tables.",
                    "Group tables into two or three areas.",
                    "Decide where the QR code will sit if you use table ordering.",
                ],
                "tip": "A table with the wrong seat count makes seat routing and split bills harder on the first shift.",
            },
            {
                "heading": "Gather the details for setup",
                "body": [
                    "Setup is quick when the information already exists on paper. Collect it before creating the workspace.",
                ],
                "steps": [
                    "Restaurant and store names, address and phone.",
                    "Primary currency and any second currency you accept.",
                    "Tax rate and whether menu prices include tax - confirm with your accountant.",
                    "Menu with price and cost per dish.",
                    "Areas, table names and seat counts.",
                    "The first manager and floor staff, with the role each needs.",
                ],
            },
        ],
        "takeaways": [
            "Choose the service and ticket flow before the menu and floor.",
            "A small menu the kitchen can execute beats a long one it cannot.",
            "Number tables by area before the furniture arrives.",
            "Gather names, tax and costs before opening the signup page.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "create-your-restaurant-workspace",
        "title": "Create your restaurant workspace and floor",
        "summary": "Sign up, choose the restaurant business type and create the store your floor and kitchen will share.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 2,
        "seo_title": "Create a restaurant workspace in Chmaba | Chmaba guides",
        "seo_description": "Set up a restaurant workspace with the right business type, currency, tax and first store, ready for tables and kitchen tickets.",
        "intro": [
            "The restaurant business type seeds useful menu categories and turns on the floor, kitchen and delivery packs. You still choose the store details, currency and tax that match the restaurant.",
        ],
        "learning_points": [
            "Create and verify the account",
            "Choose Restaurant / food service during onboarding",
            "Confirm the store, currency and tax",
            "Know which feature packs the floor and kitchen need",
        ],
        "requirements": [
            "An email address you check regularly",
            "Restaurant and first store names",
            "Country, primary currency and tax rate",
        ],
        "sections": [
            {
                "heading": "Create and verify the account",
                "body": [
                    "Choose Start free on chmaba.com. Enter your name, email and a strong password, then confirm the six-digit code sent to your email.",
                    "Use an address the business will keep; it becomes the owner sign-in and receives billing, security and support notices.",
                ],
                "steps": [
                    "Choose Start free.",
                    "Enter the owner name, email and password.",
                    "Open the email and enter the six-digit code.",
                    "If you use Google, finish the same onboarding instead of a code.",
                ],
            },
            {
                "heading": "Answer the onboarding questions",
                "body": [
                    "Onboarding asks for the company, first store, country and currency, then the business type. Choose Restaurant / food service.",
                    "The business type seeds restaurant categories and turns on the defaults a floor and kitchen need: tables, modifiers and delivery. You can still change individual packs later.",
                ],
                "steps": [
                    "Enter the company name as it should appear on reports.",
                    "Enter the restaurant name guests and staff recognise.",
                    "Choose the country and primary currency.",
                    "Choose Restaurant / food service.",
                    "Pick the plan to start on; tables and kitchen need a plan that includes them.",
                ],
                "tip": "The company is the business; the store is the physical restaurant. Add more branches later without rebuilding the company.",
            },
            {
                "heading": "Check the starting data",
                "body": [
                    "A restaurant workspace starts with categories such as Appetizers, Main dishes, Drinks and Desserts, plus sample products so the register is not empty.",
                    "Treat the samples as a placeholder. Rename the categories to the words on your menu and replace the products before the first service.",
                ],
                "steps": [
                    "Open Products and review the seeded categories.",
                    "Rename a category to match the menu board.",
                    "Open Settings and confirm the store address and phone.",
                    "Check that Tables and Delivery appear in the workspace navigation.",
                ],
            },
            {
                "heading": "Set currency, tax and receipts",
                "body": [
                    "Open Settings before the first sale. Confirm the primary currency, enable a second currency only if you take it at the counter, and set the exchange rate you actually use.",
                    "Set the tax rate and whether menu prices include it. Add the receipt logo, address and a short footer before training anyone.",
                ],
                "steps": [
                    "Confirm the currency and exchange rate.",
                    "Set the tax rate and inclusive/exclusive choice.",
                    "Open Store settings and add the address and phone.",
                    "Open Receipts and add the logo, footer and order prefix.",
                    "Print one test receipt before service.",
                ],
                "tip": "Changing tax or currency after the first shift makes yesterday's totals hard to compare. Decide now.",
            },
        ],
        "takeaways": [
            "Choose Restaurant / food service to seed the right categories and packs.",
            "The store is the physical restaurant; add branches later.",
            "Review the seeded menu before service, not during it.",
            "Confirm currency, tax and receipt details before training.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "build-a-menu-the-kitchen-can-run",
        "title": "Build a menu the kitchen can run",
        "summary": "Turn the menu into categories, products and modifiers that make a ticket readable at the pass.",
        "group_title": "Set up your menu",
        "level": "beginner",
        "estimated_minutes": 15,
        "is_featured": False,
        "position": 3,
        "seo_title": "Build a restaurant menu in your POS | Chmaba guides",
        "seo_description": "Structure restaurant categories, dishes, variants and modifiers in Chmaba so the register and kitchen ticket stay fast and readable.",
        "intro": [
            "The kitchen reads a ticket, not a menu description. Build products with names and choices that survive a busy pass.",
        ],
        "learning_points": [
            "Group the menu into stations and courses",
            "Add dishes with a price and a cost",
            "Use variants for portion and modifiers for preparation",
            "Keep ticket names short and unambiguous",
        ],
        "requirements": [
            "The opening menu with prices",
            "Food cost per portion",
            "Preparation choices such as doneness or sides",
        ],
        "sections": [
            {
                "heading": "Group the menu the way the kitchen works",
                "body": [
                    "Use four to six categories a guest or server would recognise: Starters, Mains, Desserts, Drinks. If the kitchen is split into wok and grill, keep separate categories only when they help the floor find the dish quickly.",
                    "Categories are for finding food. Courses on the ticket are for firing it. Do not create a category for every station.",
                ],
                "steps": [
                    "Open Categories and choose Add category.",
                    "Name the categories in menu language.",
                    "Order them the way the menu board reads.",
                    "Keep best sellers near the top of each category.",
                ],
            },
            {
                "heading": "Add each dish as a product",
                "body": [
                    "Open Products and choose Add product. Enter the name, category, selling price and cost price. Use a short ticket name such as 'Beef Lok Lak' rather than a long menu description.",
                    "Turn on inventory tracking only for items you physically count, such as bottled drinks or retail bags. A cooked dish is a recipe, not a stock item.",
                ],
                "steps": [
                    "Open Products and choose Add product.",
                    "Enter the dish name as the pass calls it.",
                    "Choose the category and set the price.",
                    "Enter the cost of one portion.",
                    "Add a SKU and save.",
                    "Add the dish to the register and read the ticket name back.",
                ],
                "tip": "If a ticket name needs an explanation, shorten it until the kitchen can read it in a glance.",
            },
            {
                "heading": "Use variants and modifiers for the real choices",
                "body": [
                    "Use variants when the portion changes the price and cost: small or large soup, half or full portion. Each variant keeps its own price and cost.",
                    "Use a modifier group for preparation choices: rare, medium or well done; extra sauce; no onion. A product can have one modifier group, so make it the group that matters most for that dish.",
                ],
                "steps": [
                    "Open Products and find the dish.",
                    "Use Manage variants for portion sizes.",
                    "Open Modifier groups for preparation choices.",
                    "Create the group, add options and any price difference.",
                    "Open Edit product and attach the group.",
                    "Test the choices on the register.",
                ],
            },
            {
                "heading": "Make the kitchen ticket readable",
                "body": [
                    "A ticket should show the table, the dish, the seat and the preparation choice. Keep product names short, use modifiers for doneness and avoid putting instructions in the product name.",
                    "If a dish is unavailable, hide or deactivate it rather than leaving a button the kitchen cannot fulfil.",
                ],
                "steps": [
                    "Read a test ticket as if you were at the pass.",
                    "Shorten any name that wraps twice.",
                    "Move preparation choices into modifiers.",
                    "Hide sold-out dishes before service.",
                    "Check that modifiers print on the kitchen ticket.",
                ],
                "tip": "The kitchen ticket is the real menu. If it is clear, the register setup is finished.",
            },
        ],
        "takeaways": [
            "Categories help the floor find food; courses help the kitchen fire it.",
            "Use variants for portion and modifiers for preparation.",
            "Use short ticket names.",
            "A product has one modifier group: choose the choice that matters most.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "set-up-tables-and-qr-ordering",
        "title": "Set up tables and QR ordering",
        "summary": "Create areas, number tables, set seats and print table QR codes so the floor and kitchen share one ticket.",
        "group_title": "Set up your floor",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 4,
        "seo_title": "Restaurant tables, floor plan and QR ordering | Chmaba guides",
        "seo_description": "Set up dining areas, table numbers, seats and QR ordering in Chmaba, then use the Floor view through service.",
        "intro": [
            "The Floor view is the restaurant's map: which tables are open, seated, reserved or being cleaned, and which ticket belongs to each table.",
        ],
        "learning_points": [
            "Create two or three dining areas",
            "Add tables with the right seat count",
            "Print and test table QR codes",
            "Use Floor statuses through service",
        ],
        "requirements": [
            "The numbered floor plan",
            "Seat count per table",
            "A printer for table QR codes if you use them",
        ],
        "sections": [
            {
                "heading": "Create the dining areas",
                "body": [
                    "Open Settings and choose Tables. Add areas such as Ground floor, Terrace or Private room. Areas group the floor so staff can find a table quickly.",
                    "Keep the number of areas small. Two or three is enough for most restaurants; one area per table makes the screen scroll.",
                ],
                "steps": [
                    "Open Settings and choose Tables.",
                    "Add the first area name.",
                    "Add the remaining areas in walk order.",
                    "Save and open Floor to check the grouping.",
                ],
            },
            {
                "heading": "Add tables and seats",
                "body": [
                    "Add each table with the name guests and staff use and the number of seats. The seat count controls the seat buttons at the register, so accurate counts matter for split bills.",
                    "Use the same numbering as the floor plan and the QR cards. A table called 'T4' everywhere is easier to run than '4', 'Table 4' and 'Window 4'.",
                ],
                "steps": [
                    "Choose Add table.",
                    "Enter the table name.",
                    "Choose the area.",
                    "Enter the seat count.",
                    "Repeat for every table.",
                    "Open Floor and confirm every table appears in the right area.",
                ],
                "tip": "Joinable tables can be separate tables in the app; transfer or merge the ticket when guests are seated together.",
            },
            {
                "heading": "Print and test table QR codes",
                "body": [
                    "If you use table ordering, each table has its own QR code. Print it from the table row and place it where a guest naturally scans it.",
                    "A table QR opens the store's table-ordering page for that table. Test one code with a phone before printing the rest, and rotate a code if a sticker is copied or lost.",
                ],
                "steps": [
                    "Open the table row and print its QR code.",
                    "Scan it with a phone and confirm the table name appears.",
                    "Place the code on the table.",
                    "Print the rest only after the first test passes.",
                    "Rotate a code if it is lost or misused.",
                ],
            },
            {
                "heading": "Use the Floor through service",
                "body": [
                    "The Floor view groups tables by area. Available tables can start an order; a table with an open ticket opens that ticket; a table without a ticket moves through Occupied, Cleaning and Available as you tap it.",
                    "Use the statuses honestly. A cleaning table that looks available will be seated twice, and a reserved table that is not marked will be given away.",
                ],
                "steps": [
                    "Open Floor before service.",
                    "Tap an available table to start an order.",
                    "Tap a seated table to open its ticket.",
                    "Move a finished table to Cleaning, then Available.",
                    "Check the floor again before the next service.",
                ],
                "tip": "The Floor view and the Kitchen board read the same open tickets. If a ticket is missing, it was never held or sent.",
            },
        ],
        "takeaways": [
            "Two or three areas keep the floor readable.",
            "Table names and seat counts must match the physical room.",
            "Test one QR code before printing every table.",
            "Use Floor statuses honestly so tables are not double-seated.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "take-a-dine-in-order",
        "title": "Take a dine-in order and send it to the kitchen",
        "summary": "Open a table, add dishes with seats and courses, send the ticket to the kitchen and take payment.",
        "group_title": "Sell every day",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": True,
        "position": 5,
        "seo_title": "Take a dine-in restaurant order in Chmaba | Chmaba guides",
        "seo_description": "A dine-in service walkthrough: choose the table, add dishes, assign seats and courses, send the ticket to the kitchen and take payment.",
        "intro": [
            "A dine-in ticket has more moving parts than a retail sale: table, seat, course and timing. The register handles the order; the Floor and Kitchen boards handle the service.",
        ],
        "learning_points": [
            "Start a dine-in order from the floor or the register",
            "Assign seats and courses to a ticket",
            "Send the ticket to the Kitchen board",
            "Take payment and split the bill",
        ],
        "requirements": [
            "At least one open table",
            "At least one product on the menu",
            "A configured payment method",
        ],
        "sections": [
            {
                "heading": "Open the table",
                "body": [
                    "The cleanest path is from Floor: tap an available table and start the order. The register opens with Dine-in and that table already selected.",
                    "You can also open Point of sale, choose Dine-in and pick the table from the order-type row. Seat buttons appear once a table is selected.",
                ],
                "steps": [
                    "Open Floor and tap an available table.",
                    "Confirm the order type is Dine-in and the table is correct.",
                    "Choose a seat if the order belongs to one guest.",
                    "Add the first dishes to the cart.",
                ],
            },
            {
                "heading": "Add dishes and send the ticket",
                "body": [
                    "Add each dish from the grid or search. Choose variants and modifiers where the kitchen needs them.",
                    "Choose Hold to park the ticket and send it to the Kitchen board. The table keeps the ticket, so the guest can order more without starting a new bill.",
                ],
                "steps": [
                    "Add the starters, mains and drinks.",
                    "Choose any required modifiers.",
                    "Choose Hold and label the ticket if needed.",
                    "Open Kitchen and confirm the ticket appears with the table name.",
                ],
                "tip": "Holding is how a dine-in ticket reaches the kitchen. Charging completes the sale and closes the bill.",
            },
            {
                "heading": "Set seats and courses",
                "body": [
                    "Open the ticket from Floor or Kitchen to assign each line to a seat and a course. Seats make split bills readable; courses control when the kitchen fires each part of the meal.",
                    "Set the seat and course before firing. A ticket with every line in 'Other' is much harder to run during a full service.",
                ],
                "steps": [
                    "Open the ticket from Floor or Kitchen.",
                    "Set the seat for each line.",
                    "Set starters, mains, dessert or drinks as the course.",
                    "Fire the course when the table is ready for it.",
                    "Mark the ticket served when the food is at the table.",
                ],
            },
            {
                "heading": "Take payment and close the bill",
                "body": [
                    "When service is finished, open the ticket and charge it. Cash, KHQR and split payments use the same payment screen as any sale.",
                    "Use split on the ticket when guests pay separately, then charge each share. The table becomes available again after the sale and the floor status is cleared.",
                ],
                "steps": [
                    "Open the ticket and choose Charge.",
                    "Take cash, KHQR or a split payment.",
                    "Print or email the receipt.",
                    "Clear the table to Cleaning, then Available.",
                ],
            },
        ],
        "takeaways": [
            "Start from Floor so the table and order type are already correct.",
            "Hold sends the ticket to the Kitchen board.",
            "Assign seats and courses before firing.",
            "Charge the ticket to close the bill and free the table.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "run-the-kitchen-and-deliveries",
        "title": "Run the kitchen board and delivery dispatch",
        "summary": "Read open tickets, fire the right course, mark food served and move delivery orders through dispatch.",
        "group_title": "Sell every day",
        "level": "intermediate",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 6,
        "seo_title": "Restaurant kitchen display and delivery dispatch | Chmaba guides",
        "seo_description": "Use the Kitchen board for open tickets, course firing and served status, then dispatch delivery orders in Chmaba.",
        "intro": [
            "The Kitchen board shows every open ticket in one place. Delivery dispatch is a separate board because the food leaves the building instead of a table.",
        ],
        "learning_points": [
            "Read the kitchen board by age and table",
            "Fire courses and mark tickets served",
            "Handle takeaway and pickup orders",
            "Dispatch a delivery and record the driver",
        ],
        "requirements": [
            "The Tables and Delivery feature packs enabled",
            "At least one open dine-in ticket",
            "A delivery order for the dispatch test",
        ],
        "sections": [
            {
                "heading": "Read the kitchen board",
                "body": [
                    "Open Kitchen to see open tickets, grouped by course and labelled with table, seat and age. The oldest ticket is the one to look at first.",
                    "Tickets from a table QR or online ordering carry a QR or Online badge, so the pass knows where the order came from.",
                ],
                "steps": [
                    "Open Kitchen before service.",
                    "Check the oldest tickets first.",
                    "Confirm table names and item counts.",
                    "Open a ticket to see seats and courses.",
                    "Refresh or leave the board open; it updates on its own.",
                ],
            },
            {
                "heading": "Fire courses and mark served",
                "body": [
                    "Open a ticket and fire the course the kitchen should start now. Starters can be fired while mains wait; firing a course marks those lines so the pass knows what is cooking.",
                    "When the food reaches the table, set the ticket to served. That is the signal the floor and the kitchen share, not a verbal call across the room.",
                ],
                "steps": [
                    "Open the ticket.",
                    "Set the seat and course for any unfiled line.",
                    "Choose Fire for the course that starts now.",
                    "When the food is away, mark the ticket served.",
                    "Check the board for the next oldest ticket.",
                ],
            },
            {
                "heading": "Takeaway and pickup",
                "body": [
                    "Takeaway orders are charged at the register with the Takeaway order type. They do not need a table, but they still need a label the pass can call.",
                    "For pickup or online orders, use the customer name or order number in the ticket label and keep the pickup shelf separate from the dine-in pass.",
                ],
                "steps": [
                    "Set the order type to Takeaway.",
                    "Add the items and take payment.",
                    "Use the customer name or order number on the ticket.",
                    "Place the packed order on the pickup shelf.",
                    "Check the order number with the customer before handover.",
                ],
            },
            {
                "heading": "Dispatch a delivery",
                "body": [
                    "Open Deliveries to see delivery orders waiting to leave. Set the address, assign a driver and advance the status as the order moves.",
                    "Use the statuses as a timeline: Assigned, Out for delivery, Delivered. Mark Failed only when the order genuinely could not be delivered, and add a note for the next shift.",
                ],
                "steps": [
                    "Open Deliveries.",
                    "Set or confirm the delivery address.",
                    "Assign a driver.",
                    "Advance to Out for delivery when it leaves.",
                    "Mark Delivered when it arrives.",
                    "Mark Failed and note the reason if it does not.",
                ],
                "tip": "A delivery order is still an order. If it is paid and dispatched, the kitchen ticket and the delivery board must agree.",
            },
        ],
        "takeaways": [
            "Work the kitchen board oldest-first.",
            "Fire courses deliberately and mark served when food leaves the pass.",
            "Takeaway still needs a callable label.",
            "Delivery dispatch is a status timeline with a named driver.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "close-the-day-and-read-reports",
        "title": "Close the day and read restaurant reports",
        "summary": "Close the shift with a counted drawer, check table service and read the sales, payment mix and menu performance.",
        "group_title": "Run your shop",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 7,
        "seo_title": "Restaurant shift close and daily reports | Chmaba guides",
        "seo_description": "Close a restaurant shift, count cash and read daily sales, payment mix, top dishes and service reports in Chmaba.",
        "intro": [
            "A restaurant close is not just a cash count. It is the moment the floor, the kitchen and the day's money have to agree.",
        ],
        "learning_points": [
            "Close the shift with a real cash count",
            "Clear table and ticket state before leaving",
            "Read sales, payment mix and top dishes",
            "Record waste and prepare the next service",
        ],
        "requirements": [
            "A counted cash drawer",
            "All open tickets either paid or intentionally held",
            "Access to Reports as an owner or manager",
        ],
        "sections": [
            {
                "heading": "Clear the floor before the count",
                "body": [
                    "Walk the Floor view before closing. Every table should be Available or Cleaning, and every ticket should be paid or deliberately held for tomorrow.",
                    "An open ticket left on a table becomes an orphan overnight. Close it, void it with a reason or move it to a hold that the next manager will see.",
                ],
                "steps": [
                    "Open Floor and check every area.",
                    "Open any table with a ticket.",
                    "Charge or hold the ticket deliberately.",
                    "Move finished tables to Cleaning, then Available.",
                ],
            },
            {
                "heading": "Close the shift",
                "body": [
                    "Choose Close shift on Point of sale, count all cash including the float and enter the counted amount. The app shows expected, counted and the difference.",
                    "Explain a variance the same day, in the note and in the handover. A consistently small difference is a process problem; a large one is a control problem.",
                ],
                "steps": [
                    "Choose Close shift.",
                    "Count the drawer in the usual order.",
                    "Enter the counted cash.",
                    "Read the difference and add a note.",
                    "Confirm the shift is closed.",
                ],
            },
            {
                "heading": "Read the daily report",
                "body": [
                    "Open Reports and choose Today. Check gross sales, refunds, discounts, tax and the payment mix. Then look at top dishes and categories.",
                    "Compare the payment mix with the floor: if most bills were cash, the KHQR total should be small. A missing payment method or a broken link shows up here before it becomes a reconciliation problem.",
                ],
                "steps": [
                    "Open Reports and choose Today.",
                    "Check sales, refunds and discounts.",
                    "Check the payment methods.",
                    "Read top dishes and categories.",
                    "Write down one menu or service change for tomorrow.",
                ],
            },
            {
                "heading": "Record waste and hand over",
                "body": [
                    "Record spoilage, breakage and comped meals as stock or discount movements with a reason. If waste is invisible, the margin report blames the menu for a process problem.",
                    "Leave a handover note: low stock, reservations, large parties, a dish to 86 and any cash variance.",
                ],
                "steps": [
                    "Adjust stock for waste and breakage.",
                    "Check low stock for tomorrow's prep.",
                    "Check reservations and large parties.",
                    "Leave a handover note for the next manager.",
                    "Secure the drawer and the register.",
                ],
                "tip": "A two-minute close saves the next shift ten minutes of reconstruction.",
            },
        ],
        "takeaways": [
            "Clear the floor and tickets before counting cash.",
            "A close is a count plus an explanation.",
            "Read payments, top dishes and discounts before leaving.",
            "Record waste and write a handover note.",
        ],
    },
    {
        "category": "restaurant",
        "slug": "train-your-team-and-launch",
        "title": "Train your floor team and launch the restaurant",
        "summary": "Give each person the right access, set approval limits and run a first-service checklist before opening.",
        "group_title": "Train & go live",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 8,
        "seo_title": "Restaurant team roles and opening checklist | Chmaba guides",
        "seo_description": "Invite restaurant managers and floor staff, set discount and refund approvals, and use a first-service launch checklist in Chmaba.",
        "intro": [
            "A restaurant opens with a team, not a login. Keep roles small, set the approval limits once and rehearse one full service before the doors open.",
        ],
        "learning_points": [
            "Invite managers and floor staff with the right roles",
            "Limit access to the stores each person works in",
            "Set discount, void and refund approvals",
            "Run a first-service launch checklist",
        ],
        "requirements": [
            "The team's email addresses",
            "A discount and refund policy",
            "One quiet hour for a full service rehearsal",
        ],
        "sections": [
            {
                "heading": "Use the smallest role that fits",
                "body": [
                    "The owner has full access, including billing and team management. A manager runs the floor and sees reports and approvals. A cashier sells and looks after guests without settings or reports.",
                    "Give each person the smallest role that lets them do the job. A server does not need billing access to take an order.",
                ],
                "steps": [
                    "Open Team access and choose Invite.",
                    "Enter the email address.",
                    "Choose manager or cashier.",
                    "Choose the restaurants the person can work in.",
                    "Send the invitation and ask them to accept it.",
                ],
            },
            {
                "heading": "Set approval limits before service",
                "body": [
                    "Decide what a cashier can do alone: a small discount, a void before the food is fired, a refund under a threshold. Put the larger actions behind manager approval.",
                    "Announce the limits during training. A rule explained on day one feels like the job; a rule announced after an incident feels like punishment.",
                ],
                "steps": [
                    "Decide the maximum cashier discount.",
                    "Decide the refund and void threshold.",
                    "Set the approval policy.",
                    "Explain what the screen does when approval is required.",
                    "Review approvals in Activity after the first service.",
                ],
            },
            {
                "heading": "Rehearse one full service",
                "body": [
                    "Run a complete loop with the team before opening: seat a table, send a ticket, fire a course, mark it served, split the bill, close the table and close the shift.",
                    "Use one real table and one real ticket. Rehearsal is where you find the missing seat count or the modifier that prints on the wrong line.",
                ],
                "steps": [
                    "Open a table from Floor.",
                    "Add a starter and a main.",
                    "Hold the ticket and open it on Kitchen.",
                    "Fire the starter, mark it served.",
                    "Split the bill and take one payment.",
                    "Close the table and close the shift.",
                ],
            },
            {
                "heading": "Launch checklist",
                "body": [
                    "The day before, test one cash sale, one KHQR sale and one split bill. Print a receipt and read it as a guest. Count the float.",
                    "On launch day, open the floor, keep the kitchen board visible and keep a manager nearby for approvals. After the first week, read the reports and change one menu or process item at a time.",
                ],
                "steps": [
                    "Test cash, KHQR and a split payment.",
                    "Print and read a receipt.",
                    "Confirm every table is on the Floor.",
                    "Confirm every dish is on the menu.",
                    "Count the opening float.",
                    "Keep the kitchen board and a manager available for service.",
                ],
                "tip": "Do not launch a new promotion and a new process on the same day. Change one thing at a time.",
            },
        ],
        "takeaways": [
            "Give each person the smallest role that fits.",
            "Set approval limits before the first shift.",
            "Rehearse a full table-to-kitchen-to-payment loop.",
            "Launch with the menu and routine you can repeat.",
        ],
    },
    {
        "category": "mart",
        "slug": "plan-your-mart",
        "title": "Plan your mart before you stock the shelves",
        "summary": "Choose the range, units, barcodes, expiry rules and supplier rhythm before entering the catalogue.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 1,
        "seo_title": "How to plan a mart or grocery store | Chmaba guides",
        "seo_description": "A practical pre-launch plan for a mart: product range, barcodes, units, expiry, suppliers and the details to prepare before setup.",
        "intro": [
            "A mart is a catalogue problem before it is a selling problem. Decide what you range, how you count it and how it expires, and the register becomes fast.",
        ],
        "learning_points": [
            "Choose a range you can count and replenish",
            "Decide barcode and unit rules",
            "Plan batches and expiry for perishables",
            "Prepare supplier and opening-stock details",
        ],
        "requirements": [
            "The opening product list with costs",
            "Barcodes or supplier codes",
            "Units of measure for weighed goods",
            "Supplier names and delivery days",
        ],
        "sections": [
            {
                "heading": "Choose a range you can actually run",
                "body": [
                    "Start with the categories a shopper expects: beverages, snacks, household, produce, and any local staple. Keep the opening range narrow enough that every shelf has a home and a reorder point.",
                    "A product that nobody can count or replenish is a shrink problem. Add it after the opening routine is stable.",
                ],
                "steps": [
                    "Group the opening range into four to six categories.",
                    "Mark fast movers and slow movers.",
                    "Remove products with no supplier or no shelf space.",
                    "Write the cost and expected selling price for each line.",
                ],
            },
            {
                "heading": "Decide barcodes and units",
                "body": [
                    "Barcode scanning is the difference between a queue and a counter. Use the supplier barcode where one exists and a stable internal SKU where it does not.",
                    "Weighed goods need a unit: rice by kilogram, produce by kilogram, liquids by litre. Selling by weight without a unit is how a till ends up charging the wrong amount.",
                ],
                "steps": [
                    "Collect barcodes for packaged goods.",
                    "Assign an internal SKU pattern for loose goods.",
                    "Choose the unit for each weighed product.",
                    "Decide whether a product has pack-size variants.",
                ],
            },
            {
                "heading": "Plan batches, expiry and suppliers",
                "body": [
                    "Perishable goods need a batch and an expiry date. Earliest expiry should leave first; a milk carton at the back of the shelf is cash you lose.",
                    "Write down who supplies each category, how often they deliver and how long an order takes. That lead time becomes the reorder point.",
                ],
                "steps": [
                    "Mark the products that expire.",
                    "Record supplier lead time and minimum order.",
                    "Decide how often you will count the shelf.",
                    "Prepare the opening stock count.",
                ],
                "tip": "If you cannot count it before opening, do not make it a tracked stock item on day one.",
            },
        ],
        "takeaways": [
            "A narrow, countable range beats a full shelf nobody can replenish.",
            "Barcodes for packaged goods, units for weighed goods.",
            "Perishables need batches, expiry and earliest-expiry-first.",
            "Reorder points come from supplier lead time, not guesswork.",
        ],
    },
    {
        "category": "mart",
        "slug": "create-your-mart-workspace",
        "title": "Create your mart workspace",
        "summary": "Sign up, choose the mart business type and set the store, currency, tax and stock defaults.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 8,
        "is_featured": False,
        "position": 2,
        "seo_title": "Create a mart workspace in Chmaba | Chmaba guides",
        "seo_description": "Set up a mart or grocery workspace with the right business type, currency, tax, barcode and batch defaults.",
        "intro": [
            "The mart business type turns on the packs a grocery counter needs: barcodes, units, variants, batches and purchasing. You still confirm the store and tax details.",
        ],
        "learning_points": [
            "Create and verify the owner account",
            "Choose Mart / grocery during onboarding",
            "Confirm currency, tax and receipt details",
            "Check the barcode and batch packs",
        ],
        "requirements": [
            "Email address",
            "Mart and store names",
            "Country, currency and tax rate",
        ],
        "sections": [
            {
                "heading": "Create the account",
                "body": [
                    "Choose Start free, enter the owner name, email and password, then confirm the six-digit code sent to the email.",
                ],
                "steps": [
                    "Choose Start free.",
                    "Enter the owner details.",
                    "Enter the email code.",
                    "Use Google only if you want it as the owner sign-in.",
                ],
            },
            {
                "heading": "Choose the mart business type",
                "body": [
                    "Enter the company, store, country and currency, then choose Mart / grocery. The pack enables barcode, brand, unit of measure, variants, batches and delivery defaults.",
                ],
                "steps": [
                    "Enter the company and store names.",
                    "Choose Cambodia and the currency you price in.",
                    "Choose Mart / grocery.",
                    "Pick a plan that includes purchasing and batches.",
                ],
                "tip": "The business type sets defaults, not limits. You can switch individual packs off later.",
            },
            {
                "heading": "Set currency, tax and receipts",
                "body": [
                    "Confirm the primary currency and any second currency you accept. Set the tax rate and whether shelf prices include it. Add the receipt logo and address before the first sale.",
                ],
                "steps": [
                    "Confirm currency and exchange rate.",
                    "Set the tax rate.",
                    "Add the store address and phone.",
                    "Print a test receipt.",
                ],
            },
        ],
        "takeaways": [
            "Mart / grocery enables barcodes, units, batches and purchasing.",
            "Confirm currency and tax before entering prices.",
            "Set the receipt details before the first customer.",
        ],
    },
    {
        "category": "mart",
        "slug": "build-your-mart-catalogue",
        "title": "Build the mart catalogue",
        "summary": "Add categories, products, barcodes, units and pack variants so the register scans without hesitation.",
        "group_title": "Set up your stock",
        "level": "beginner",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 3,
        "seo_title": "Build a mart product catalogue with barcodes | Chmaba guides",
        "seo_description": "Add categories, barcodes, SKUs, units of measure and pack variants to a mart catalogue in Chmaba.",
        "intro": [
            "The catalogue is the shelf in software form. Every product needs a name, a price, a cost and a way to find it at the counter.",
        ],
        "learning_points": [
            "Create categories that match the aisles",
            "Add products with barcode and SKU",
            "Use units for weighed goods",
            "Use variants for pack sizes",
        ],
        "requirements": [
            "Opening product list",
            "Barcodes",
            "Cost per unit",
        ],
        "sections": [
            {
                "heading": "Create the aisles",
                "body": [
                    "Open Categories and add Beverages, Snacks, Household, Produce and any local staple. Categories are how the cashier finds a product when a barcode will not scan.",
                ],
                "steps": [
                    "Open Categories.",
                    "Add the aisle names.",
                    "Order them like the store.",
                    "Keep each category short enough to scan.",
                ],
            },
            {
                "heading": "Add products with barcode and cost",
                "body": [
                    "Open Products and choose Add product. Enter the name, category, selling price, cost and barcode. Use the supplier barcode unchanged; duplicate barcodes are rejected, which is what prevents two products selling as one.",
                ],
                "steps": [
                    "Add the product name and category.",
                    "Enter the selling price and cost.",
                    "Scan or type the barcode.",
                    "Set the opening stock and reorder point.",
                    "Save and scan it once at the register.",
                ],
            },
            {
                "heading": "Choose units and pack variants",
                "body": [
                    "For loose goods, set the unit to kg, g, l or ml so the register asks for a quantity instead of assuming one piece. For a product sold in several pack sizes, use variants with their own price, cost and barcode.",
                ],
                "steps": [
                    "Set the unit for every weighed product.",
                    "Open Manage variants for pack sizes.",
                    "Give each pack its own price and barcode.",
                    "Test one weighed sale and one pack-size sale.",
                ],
                "tip": "A product with variants uses each variant's SKU and barcode; the parent SKU is only a grouping code.",
            },
        ],
        "takeaways": [
            "Categories are the fallback when a barcode fails.",
            "Every product needs price, cost, barcode and reorder point.",
            "Weighed goods need a unit; pack sizes belong in variants.",
        ],
    },
    {
        "category": "mart",
        "slug": "receive-stock-and-track-expiry",
        "title": "Receive stock and track expiry",
        "summary": "Add suppliers, raise purchase orders, receive deliveries and let batches protect perishable stock.",
        "group_title": "Set up your stock",
        "level": "intermediate",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 4,
        "seo_title": "Mart purchasing, batches and expiry tracking | Chmaba guides",
        "seo_description": "Use suppliers, purchase orders, receiving and batches with expiry dates to keep mart stock accurate.",
        "intro": [
            "Stock arrives in deliveries, not in one opening count. A purchase order tells you what should arrive; receiving it tells the system what actually did.",
        ],
        "learning_points": [
            "Add the regular suppliers",
            "Raise and receive a purchase order",
            "Record batch and expiry for perishables",
            "Set reorder points that reflect lead time",
        ],
        "requirements": [
            "Supplier contact details",
            "A delivery to receive",
            "Expiry dates for perishable lines",
        ],
        "sections": [
            {
                "heading": "Add the suppliers",
                "body": [
                    "Open Suppliers and add the contact person, phone and email for each regular supplier. A purchase order can then name the supplier and a short delivery is easy to trace.",
                ],
                "steps": [
                    "Open Suppliers.",
                    "Add each supplier.",
                    "Record the phone and contact name.",
                    "Save before creating the order.",
                ],
            },
            {
                "heading": "Raise and receive an order",
                "body": [
                    "Open Purchase orders and create an order with the product, supplier and quantity. When the delivery arrives, receive it against the order. Short deliveries stay visible instead of being absorbed into a stock count.",
                ],
                "steps": [
                    "Create a purchase order.",
                    "Set the product, supplier and quantity.",
                    "Receive the delivery.",
                    "Compare received quantity with ordered quantity.",
                    "Record the expiry batch where required.",
                ],
            },
            {
                "heading": "Use batches and reorder points",
                "body": [
                    "For milk, bread and other perishables, record a batch code and expiry date when you receive the stock. Earliest expiry leaves first, and the expiry list warns you before stock becomes waste.",
                    "Set a reorder point from daily sales plus supplier lead time. An order placed when the shelf is already empty is a lost sale, not a reorder.",
                ],
                "steps": [
                    "Add batch and expiry on receipt.",
                    "Open the expiring-batches list weekly.",
                    "Adjust expired stock with a reason.",
                    "Review reorder points after the first month.",
                ],
                "tip": "A stock count without a reason hides shrink. Record waste and expiry as movements so the reports can explain the gap.",
            },
        ],
        "takeaways": [
            "Suppliers and purchase orders make deliveries traceable.",
            "Receive against the order, not by guessing.",
            "Batches and expiry protect perishable margin.",
            "Reorder points come from daily use plus lead time.",
        ],
    },
    {
        "category": "mart",
        "slug": "sell-and-reconcile-your-mart",
        "title": "Sell and reconcile a mart counter",
        "summary": "Scan, weigh, take cash or KHQR, handle a refund and close the drawer with a real count.",
        "group_title": "Sell every day",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 5,
        "seo_title": "Run a mart checkout and close the day | Chmaba guides",
        "seo_description": "A mart checkout walkthrough: scan barcodes, sell by weight, take cash or KHQR, refund a sale and close the shift.",
        "intro": [
            "A mart checkout should be one scan, one quantity and one payment. The close is one count that explains the day.",
        ],
        "learning_points": [
            "Scan packaged goods and weigh loose goods",
            "Take cash, KHQR or a split payment",
            "Refund the right lines",
            "Close the shift and read the day",
        ],
        "requirements": [
            "A product with a barcode",
            "A weighed product with a unit",
            "A configured payment method",
        ],
        "sections": [
            {
                "heading": "Scan and weigh",
                "body": [
                    "Open Point of sale and scan the barcode. For loose goods, search the product, enter the weight and confirm the unit. Out-of-stock items are blocked when inventory tracking is on, so the shelf and the till stay aligned.",
                ],
                "steps": [
                    "Scan a packaged product.",
                    "Search a weighed product.",
                    "Enter the weight and confirm the unit.",
                    "Read the cart back before charging.",
                ],
            },
            {
                "heading": "Take payment and refund",
                "body": [
                    "Choose Charge and take cash, KHQR or a split payment. For a return, open Orders, choose Refund, set the quantity and method, and add a reason. Stock returns to inventory when the refund is confirmed.",
                ],
                "steps": [
                    "Choose Charge.",
                    "Take cash, KHQR or a split.",
                    "Print or email the receipt.",
                    "Refund from Orders when needed.",
                ],
            },
            {
                "heading": "Close the counter",
                "body": [
                    "Close the shift with a counted drawer and read the daily report. Check payment mix, top products and low stock, then record waste and write the next order.",
                ],
                "steps": [
                    "Close the shift and count the cash.",
                    "Read Today in Reports.",
                    "Check low stock and expiring batches.",
                    "Record waste and prepare the order.",
                ],
                "tip": "A reorder point is only useful if someone checks the low-stock list before the delivery cutoff.",
            },
        ],
        "takeaways": [
            "Scan packaged goods and weigh loose goods with the right unit.",
            "Cash, KHQR and split payments use one charge screen.",
            "Refund from Orders so stock and totals stay correct.",
            "Close with a count and use the low-stock list for tomorrow.",
        ],
    },
    {
        "category": "electronics",
        "slug": "plan-your-electronics-store",
        "title": "Plan your electronics store before you stock it",
        "summary": "Decide serial numbers, warranty terms, condition grades, trade-ins and supplier rules before entering devices.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 10,
        "is_featured": True,
        "position": 1,
        "seo_title": "How to plan an electronics store | Chmaba guides",
        "seo_description": "Plan serial/IMEI tracking, warranty terms, condition grading, trade-ins and supplier details before setting up an electronics store.",
        "intro": [
            "An electronics store sells individual units, not anonymous stock. The serial number is the unit's identity, and warranty, condition and service history hang from it.",
        ],
        "learning_points": [
            "Choose serial and IMEI rules",
            "Decide supplier and customer warranty",
            "Set condition grades for used devices",
            "Plan trade-ins and service records",
        ],
        "requirements": [
            "Supplier list and unit costs",
            "Warranty terms from each supplier",
            "Trade-in and used-device policy",
        ],
        "sections": [
            {
                "heading": "Track units, not just models",
                "body": [
                    "A phone model can have fifty units in the shop, each with its own serial, IMEI and warranty. Decide now that every serialized unit is recorded individually and never sold twice.",
                ],
                "steps": [
                    "Choose where the serial number and IMEI are printed.",
                    "Decide which categories need serial tracking.",
                    "Agree a rule for units that arrive without a serial.",
                ],
            },
            {
                "heading": "Write the warranty terms",
                "body": [
                    "Record the supplier warranty and the customer warranty separately. The supplier clock starts when you receive the unit; the customer clock starts when you sell it.",
                ],
                "steps": [
                    "Collect the supplier warranty months for each brand.",
                    "Decide the customer warranty you offer.",
                    "Write the return and repair policy.",
                ],
            },
            {
                "heading": "Set condition grades and trade-ins",
                "body": [
                    "Used devices need a grade such as premium, excellent, good, fair or parts, plus battery health where relevant. A trade-in is a credit you give against a new sale, so decide how you value and record it.",
                ],
                "steps": [
                    "Define the condition grades the shop will use.",
                    "Decide whether battery health is recorded.",
                    "Set the trade-in valuation and payout rule.",
                ],
                "tip": "A grade without a note is hard to defend later. Record battery health and visible faults at intake.",
            },
        ],
        "takeaways": [
            "The serial number is the unit; stock counts alone are not enough.",
            "Supplier and customer warranty start at different times.",
            "Condition grades make used devices sellable and defensible.",
            "Trade-ins need a written valuation rule.",
        ],
    },
    {
        "category": "electronics",
        "slug": "create-your-electronics-workspace",
        "title": "Create your electronics workspace",
        "summary": "Sign up, choose the electronics business type and confirm the packs for serials, brands and barcodes.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 8,
        "is_featured": False,
        "position": 2,
        "seo_title": "Create an electronics store workspace | Chmaba guides",
        "seo_description": "Set up an electronics workspace in Chmaba with serial, brand, barcode and warranty defaults.",
        "intro": [
            "The electronics business type turns on serial tracking, brand, barcode and variant defaults. Confirm those packs before entering devices.",
        ],
        "learning_points": [
            "Create and verify the owner account",
            "Choose Electronics store during onboarding",
            "Confirm serial and barcode packs",
            "Set currency, tax and receipt details",
        ],
        "requirements": [
            "Email address",
            "Store name and address",
            "Country, currency and tax rate",
        ],
        "sections": [
            {
                "heading": "Create the account and store",
                "body": [
                    "Choose Start free and verify the email. Enter the company and first store, then choose Electronics store.",
                ],
                "steps": [
                    "Create the owner account.",
                    "Enter the email code.",
                    "Enter company and store names.",
                    "Choose Electronics store.",
                ],
            },
            {
                "heading": "Confirm the feature packs",
                "body": [
                    "Serials and warranty, barcode scanning, brands and variants should be on for an electronics counter. Check Settings, then Feature packs.",
                ],
                "steps": [
                    "Open Settings and Feature packs.",
                    "Confirm serials and warranty.",
                    "Confirm barcode and brand.",
                    "Turn on variants only if you sell storage or colour options.",
                ],
            },
            {
                "heading": "Set currency, tax and receipts",
                "body": [
                    "Confirm the currency, tax rate and receipt details before the first device is entered. A serialized receipt should show the serial or IMEI for the customer.",
                ],
                "steps": [
                    "Confirm the primary currency.",
                    "Set the tax rate.",
                    "Add the store address and logo.",
                    "Print a test receipt.",
                ],
            },
        ],
        "takeaways": [
            "Electronics store enables serials, warranty, barcode and brand.",
            "Confirm the packs before entering inventory.",
            "Set currency, tax and receipts before the first sale.",
        ],
    },
    {
        "category": "electronics",
        "slug": "build-a-serial-tracked-catalogue",
        "title": "Build a serial-tracked catalogue",
        "summary": "Add models, variants, serial numbers, IMEI, cost, condition grades and warranty terms.",
        "group_title": "Set up your stock",
        "level": "intermediate",
        "estimated_minutes": 12,
        "is_featured": False,
        "position": 3,
        "seo_title": "Serial, IMEI and warranty catalogue setup | Chmaba guides",
        "seo_description": "Add electronics products with serial numbers, IMEI, variants, condition grades and warranty terms in Chmaba.",
        "intro": [
            "A model row is the shelf label; the serial rows are the actual units. Build both, then the register can ask for the exact unit at checkout.",
        ],
        "learning_points": [
            "Create models with brand and barcode",
            "Use variants for storage or colour",
            "Add each unit with serial and IMEI",
            "Record condition and warranty per unit",
        ],
        "requirements": [
            "Model list with cost and price",
            "Serial and IMEI per unit",
            "Condition and warranty terms",
        ],
        "sections": [
            {
                "heading": "Create the model",
                "body": [
                    "Open Products and add the model with brand, category, price, cost and barcode. Turn on Track serials. The product starts at zero stock because each unit must be added with its own identity.",
                ],
                "steps": [
                    "Add the model name, brand and category.",
                    "Set price and cost.",
                    "Turn on Track serials.",
                    "Save and open the unit list.",
                ],
            },
            {
                "heading": "Add each unit",
                "body": [
                    "Open the product and choose Add serials. Enter the serial number, IMEI, unit cost and warranty. For a used device, add the condition grade, battery health and a note.",
                ],
                "steps": [
                    "Choose Add serials.",
                    "Enter serial and IMEI.",
                    "Set unit cost and supplier warranty.",
                    "Set the customer warranty.",
                    "Add condition and battery health for a used unit.",
                ],
                "tip": "Serial numbers must be unique across the company, so the same unit cannot be stocked twice.",
            },
            {
                "heading": "Use variants for storage and colour",
                "body": [
                    "If the model sells in several storage sizes or colours, use variants and add serials under the correct variant. The variant keeps its own price, cost and stock.",
                ],
                "steps": [
                    "Open Manage variants.",
                    "Add storage or colour variants.",
                    "Add serials under each variant.",
                    "Check the register asks for the right variant and unit.",
                ],
            },
        ],
        "takeaways": [
            "A model row is not a unit; add each serial individually.",
            "IMEI, cost and warranty travel with the unit.",
            "Condition grading belongs on used units.",
            "Variants keep storage and colour pricing separate.",
        ],
    },
    {
        "category": "electronics",
        "slug": "sell-service-and-trade-in",
        "title": "Sell, service and trade in devices",
        "summary": "Pick the exact serial at checkout, start the warranty, look up a unit and record service or trade-in.",
        "group_title": "Sell every day",
        "level": "intermediate",
        "estimated_minutes": 12,
        "is_featured": True,
        "position": 4,
        "seo_title": "Sell and service serialized electronics | Chmaba guides",
        "seo_description": "A checkout and service walkthrough for electronics: pick the serial, start warranty, look up a unit and record service or trade-in.",
        "intro": [
            "Selling a phone is also opening a warranty record. The serial picked at checkout is the unit the customer brings back for service.",
        ],
        "learning_points": [
            "Pick the exact unit at checkout",
            "Start the customer warranty at the sale",
            "Look up a serial for warranty or service",
            "Refund or trade in a unit correctly",
        ],
        "requirements": [
            "A serialized product with units in stock",
            "A warranty term per unit",
            "A configured payment method",
        ],
        "sections": [
            {
                "heading": "Pick the unit at checkout",
                "body": [
                    "Add the model at the register. The serial picker opens and lists the units in stock; choose the exact serial or IMEI the customer is buying. The warranty clock starts when the sale completes.",
                ],
                "steps": [
                    "Add the model to the cart.",
                    "Choose the exact serial.",
                    "Confirm the cart line shows the unit.",
                    "Charge and print the receipt with the serial.",
                ],
            },
            {
                "heading": "Look up a serial",
                "body": [
                    "Use Find a serial on POS or Products. A serial lookup shows the sale, customer, warranty and condition history, which is what you need at the counter.",
                ],
                "steps": [
                    "Open Find a serial.",
                    "Type the serial or IMEI.",
                    "Read the sale and warranty dates.",
                    "Open the unit to add a service ticket.",
                ],
            },
            {
                "heading": "Service, refund and trade-in",
                "body": [
                    "A repair is recorded as a service ticket on the serial, not as a new product. A refund returns the unit to stock or marks it defective. A trade-in is a credit against a new sale, recorded against the accepted unit.",
                ],
                "steps": [
                    "Add a service ticket with type, cost and note.",
                    "Refund only the exact serialized unit.",
                    "Record a trade-in before taking payment.",
                    "Mark a returned unit in stock or defective.",
                ],
                "tip": "Never refund a serialized line without choosing the unit. The wrong unit disappears from stock and the right one stays unsellable.",
            },
        ],
        "takeaways": [
            "The serial picked at checkout is the warranty record.",
            "A serial lookup answers warranty questions at the counter.",
            "Service tickets belong to the unit, not the model.",
            "Refunds and trade-ins must name the exact unit.",
        ],
    },
]
