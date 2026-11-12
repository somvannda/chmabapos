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
]
