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
            {
                "id": "getting-started.categories",
                "title": "Organize products into categories",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Categories and choose Add category.",
                    "Enter a name; optionally pick a parent to make it a subcategory.",
                    "Save, then set the category when you add or edit a product.",
                    "Categories group the POS grid and the product list so items are quick to find.",
                ],
                "tip": "Use subcategories for sections such as Hot drinks and Cold drinks.",
            },
            {
                "id": "getting-started.store-profile",
                "title": "Set up your store details",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Company profile to set your company name, address, phone and Tax ID.",
                    "Choose Store settings to set the store name, phone, address, timezone and service tax rate.",
                    "Save. These details print on receipts and show on the customer display.",
                    "To add a branch, open Store settings and choose Add store.",
                ],
                "tip": "Give each branch its own store so stock and reports stay separate.",
            },
            {
                "id": "getting-started.onboarding",
                "title": "Set up your account and store",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Sign up, then open the verification email and confirm your address.",
                    "In setup, enter your company name, first store name, business type and default currency.",
                    "Choose a plan; the free plan needs no payment.",
                    "When setup finishes you land on Overview, ready to add products.",
                ],
                "tip": "You can change your company and store details later in Settings.",
            },
            {
                "id": "getting-started.signin",
                "title": "Sign in to Chmaba",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "Open chmaba.com and choose Sign in, or Create account if you are new.",
                    "Enter your email and password, then choose Remember me if this is your own device.",
                    "New accounts confirm their email first; open the verification link we send you.",
                    "After signing in you land on Overview.",
                ],
            },
            {
                "id": "getting-started.reset-password",
                "title": "Reset a forgotten password",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "On the sign-in page choose Forgot password.",
                    "Enter the email for your account and submit.",
                    "Open the reset link in the email we send you.",
                    "Choose a new password, enter it twice, and submit. Then sign in with it.",
                ],
                "tip": "Reset links expire, so request a new one if the link no longer works.",
            },
            {
                "id": "getting-started.google-signin",
                "title": "Sign in with Google",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "On the sign-in page choose Continue with Google.",
                    "Pick your Google account and allow access.",
                    "New Google users go to setup to create a store; existing users land on Overview.",
                    "Use the same method next time so your account stays linked.",
                ],
                "tip": "If your account was created with a password, sign in with that instead of Google.",
            },
        ],
    },
    {
        "id": "overview",
        "title": "Overview",
        "blurb": "See how today is going at a glance.",
        "articles": [
            {
                "id": "overview.dashboard",
                "title": "Use your Overview dashboard",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "Open Overview to see today's sales, transactions, average order and low-stock count.",
                    "Follow the setup checklist; each step links to the page you need.",
                    "Review top products and the low-stock list before you start the day.",
                    "Choose New sale to jump straight to the register.",
                ],
            },
            {
                "id": "overview.notifications",
                "title": "Read your notifications",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Choose the bell in the header to open your notifications.",
                    "Low-stock and refund alerts appear here.",
                    "Open an alert to jump to the item, or choose Mark all read to clear the list.",
                ],
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
            {
                "id": "inventory.adjust",
                "title": "Adjust stock or write off items",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Inventory and find the product or variant.",
                    "Choose Adjust and enter the change; use a minus to remove stock.",
                    "Pick a reason such as Damage, Theft or Stock count.",
                    "Save. The movement is recorded in stock history.",
                ],
            },
            {
                "id": "inventory.transfer",
                "title": "Transfer stock to another store",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Inventory, choose the product, then choose Transfer.",
                    "Pick the destination store and enter the quantity.",
                    "For serial-tracked items, choose the exact units to move.",
                    "Confirm. Stock leaves this store and arrives at the destination.",
                ],
            },
            {
                "id": "inventory.history",
                "title": "View stock movement history",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Inventory and choose Stock history.",
                    "Filter by product to see every restock, sale, adjustment and transfer.",
                    "Each row shows the type, reason, quantity and who made the change.",
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
            {
                "id": "electronics.lookup",
                "title": "Look up a serial number",
                "verticals": ["electronics"],
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "On Point of sale or Products choose Find a serial.",
                    "Type the serial number to see the unit's sale, warranty and condition.",
                    "The result shows where it was sold and whether it is still under warranty.",
                    "Use it at the counter to answer a customer's warranty question.",
                ],
                "tip": "Serial numbers are unique across your company, so each unit can be found once.",
            },
            {
                "id": "electronics.service",
                "title": "Log a repair or service ticket",
                "verticals": ["electronics"],
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Find the serial and open it.",
                    "Choose Add service ticket and pick the type: repair, warranty or inspection.",
                    "Add the cost and a note, then save.",
                    "The ticket stays on the serial's history for next time.",
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
            {
                "id": "team.roles",
                "title": "Understand team roles",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Owner: full access, including billing, team and adding stores.",
                    "Manager: runs the store and sees reports and approvals.",
                    "Inventory manager: manages products, stock, suppliers and purchases.",
                    "Cashier: sells and looks after customers; no settings or reports.",
                ],
                "tip": "You can limit each member to specific stores when you invite or edit them.",
            },
            {
                "id": "billing.cycle",
                "title": "Choose a billing cycle",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Billing & plans.",
                    "Switch between monthly, semi-annual and annual billing.",
                    "Longer cycles cost less; the price updates before you pay.",
                    "Confirm to move your current plan to the new cycle.",
                ],
                "tip": "The annual cycle is the cheapest way to keep a paid plan active.",
            },
            {
                "id": "team.manage",
                "title": "Change or remove a team member",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Team access and find the member.",
                    "Choose Edit to change their role or which stores they can work in.",
                    "Choose Deactivate to pause their access without deleting their history.",
                    "Choose Remove to revoke access for good; the owner account cannot be removed.",
                ],
                "tip": "You can also accept an invitation on a member's behalf from the invitations list.",
            },
            {
                "id": "billing.schedule",
                "title": "Schedule or cancel a plan change",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Billing & plans and choose the plan you want.",
                    "Choose Schedule change to move to it at the end of the current period.",
                    "To stop renewing, choose Cancel at period end.",
                    "Choose Remove scheduled change to undo it before it takes effect.",
                ],
                "tip": "When a plan ends, extra stores or members are paused rather than deleted.",
            },
            {
                "id": "billing.receipts",
                "title": "Find your billing receipts",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Billing & plans.",
                    "Scroll to Payment history to see every charge and its status.",
                    "Open a receipt to print or save it.",
                ],
            },
        ],
    },
    {
        "id": "point-of-sale",
        "title": "Point of sale",
        "blurb": "Run the register and the customer screen.",
        "articles": [
            {
                "id": "pos.customer-display",
                "title": "Set up the customer display",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "In Settings, open Customer display and turn on Enable the customer display.",
                    "Add a receipt logo and a store address so customers see where they are paying (Settings, then Receipts and Store settings).",
                    "On the register, tap Open customer display. A second window opens showing the order and, at checkout, the KHQR code.",
                    "Move that window to the customer-facing monitor. It stays in sync with the register for every sale.",
                    "To stop sharing, turn Enable the customer display back off; the button disappears from the register.",
                ],
                "tip": "The display only shows data while a register is open on the same computer. Opened on its own, it shows Waiting for the register.",
            },
            {
                "id": "pos.shift",
                "title": "Open and close a shift",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "On Point of sale, choose Open shift and enter the opening cash float.",
                    "Sell as normal; every sale is linked to your open shift.",
                    "At the end of the shift choose Close shift, then count and enter the cash in the drawer.",
                    "The app shows expected against counted cash and the difference, then records the shift.",
                    "Choose Shifts to see past shifts for the store.",
                ],
                "tip": "If Settings requires an open shift, you cannot charge a sale until you open one.",
            },
            {
                "id": "pos.hold-orders",
                "title": "Hold and resume an order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "With items in the cart, choose Hold and add an optional label such as a name or table.",
                    "The order is parked and the register is free for the next customer.",
                    "Choose Held to see parked orders, then resume the one you want.",
                    "Resume loads the items back into the cart; discard removes it for good.",
                ],
                "tip": "If the cart already has items, choose whether to replace or merge them.",
            },
            {
                "id": "pos.split-payment",
                "title": "Take a split payment",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Choose Charge to open the payment screen.",
                    "Enter the first tender: pick the method and amount, then add it.",
                    "Add a second tender for the rest of the total.",
                    "Finish when the remaining balance is zero, then complete the sale.",
                ],
                "tip": "You can mix cash and KHQR on the same sale.",
            },
            {
                "id": "pos.khqr",
                "title": "Accept a KHQR payment",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Connect ABA PayWay first: Settings, then Bank & KHQR, then add and verify your PayWay link.",
                    "At checkout choose KHQR as the payment method.",
                    "Show the QR code to the customer to scan with their banking app.",
                    "The screen updates when the payment is confirmed, then the receipt prints.",
                ],
                "tip": "KHQR needs an active internet connection to confirm payment. The receipt prints on its own when auto-print is on.",
            },
            {
                "id": "pos.receipt-printing",
                "title": "Print receipts without a dialog",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Turn on Auto-print receipt in Settings, then POS preferences, so each completed sale prints by itself.",
                    "In a normal browser tab the receipt still waits on the print dialog. To print with no dialog, open the register with the browser's kiosk-printing option.",
                    "On Windows, launch the POS with the included start-pos.ps1 script, or add --kiosk-printing to your Chrome or Edge shortcut.",
                    "Set your receipt printer as the Windows default printer; kiosk printing always uses it.",
                    "Without the flag everything still works — receipts just go through the normal print dialog.",
                ],
                "tip": "This is what lets a KHQR sale confirm, close and print its receipt with nobody at the keyboard.",
            },
            {
                "id": "pos.discount-tip",
                "title": "Apply a discount or a tip",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "In the cart, choose Discount and enter a percentage or a fixed amount.",
                    "Choose Tip to add a tip for the sale.",
                    "The new total updates before you charge.",
                ],
                "tip": "If discounts are turned off in Settings, ask an owner or manager to ring it up.",
            },
            {
                "id": "pos.order-type",
                "title": "Set takeaway, dine-in or delivery",
                "verticals": ["restaurant", "coffee", "general"],
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "On Point of sale, open the order type menu above the cart.",
                    "Choose Takeaway, Dine-in or Delivery before you charge.",
                    "The choice is saved on the order and shown in your reports.",
                ],
                "tip": "Dine-in orders can be linked to a table from the restaurant floor view.",
            },
            {
                "id": "pos.scan",
                "title": "Scan items at the register",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "On Point of sale, choose Scan item.",
                    "Scan a barcode or type an SKU, product name or serial number.",
                    "Press Enter; the item is added, or you are asked to pick the exact unit.",
                    "Repeat for each item, or use the search box to find products without a barcode.",
                ],
                "tip": "Out-of-stock items are blocked so you never sell what you do not have.",
            },
            {
                "id": "pos.serials-checkout",
                "title": "Pick a unit at checkout",
                "verticals": ["electronics"],
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "When you add a product that tracks serials, the picker opens automatically.",
                    "Choose the exact serial number the customer is buying.",
                    "The warranty for that unit starts when the sale completes.",
                    "If the unit is missing, check Inventory or the product's serials list.",
                ],
            },
        ],
    },
    {
        "id": "orders",
        "title": "Orders",
        "blurb": "Find, refund and reprint past sales.",
        "articles": [
            {
                "id": "orders.refund",
                "title": "Refund an order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Orders, find the sale and choose Refund.",
                    "Choose the quantity to refund for each line, and pick the exact serials for tracked items.",
                    "Choose the refund method and add a reason.",
                    "Confirm. Stock is returned, serials are released and the refund is recorded.",
                ],
                "tip": "If your team uses approvals, a large refund may wait for a manager to approve it.",
            },
            {
                "id": "orders.cancel",
                "title": "Cancel an unpaid order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Orders and filter to Pending.",
                    "Choose the order and choose Cancel.",
                    "Add a reason and confirm. No stock changes because the order was never paid.",
                ],
            },
            {
                "id": "orders.receipt",
                "title": "Print or email a receipt",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Orders and choose the sale to see the receipt.",
                    "Choose Print to send it to your receipt printer.",
                    "If the order has a customer email, choose Email receipt to send a copy.",
                ],
                "tip": "Turn on auto-print in Settings to print every receipt without asking. For no dialog at all, launch the POS with kiosk printing (see Print receipts without a dialog).",
            },
            {
                "id": "orders.find",
                "title": "Find an order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "Open Orders and use the tabs to filter Paid, Pending or Cancelled.",
                    "Search or scroll the list, then choose Load more to see older sales.",
                    "Open an order to see its lines and receipt.",
                ],
            },
        ],
    },
    {
        "id": "approvals",
        "title": "Approvals",
        "blurb": "Review requests from your team.",
        "articles": [
            {
                "id": "approvals.review",
                "title": "Approve or reject a request",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Approvals to see everything waiting for a decision.",
                    "Each row shows the action, the amount and the reason.",
                    "Choose Approve to let it through, or Reject and add a reason.",
                    "The requester is notified and the decision is written to the activity log.",
                ],
            },
            {
                "id": "approvals.policy",
                "title": "Set up an approval policy",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Approval policy.",
                    "Turn on approvals, then choose a mode for each action: Off, Review or Approval.",
                    "Set the amount threshold and the roles allowed to approve.",
                    "Save. Requests over the threshold now wait in Approvals.",
                ],
                "tip": "Approvals only work once you have more than one team member.",
            },
        ],
    },
    {
        "id": "customers",
        "title": "Customers & loyalty",
        "blurb": "Keep customer details and rewards.",
        "articles": [
            {
                "id": "customers.manage",
                "title": "Add and manage customers",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Customers and choose Add customer.",
                    "Enter the name, phone and email, plus any note, then save.",
                    "Search by name or phone to find a customer, or open one to see their orders and spend.",
                    "Deactivate a customer to hide them without deleting their history.",
                ],
                "tip": "Customers with past orders cannot be deleted, so deactivate them instead.",
            },
            {
                "id": "customers.loyalty",
                "title": "Reward customers with loyalty points",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "In Settings choose Loyalty & rewards and set how many points each unit of spend earns.",
                    "Attach the customer when you sell so their points are added automatically.",
                    "Open a customer to see their points, then adjust them up or down if needed.",
                    "Redeem points at the register to take them off the total.",
                ],
            },
        ],
    },
    {
        "id": "products",
        "title": "Products",
        "blurb": "Build and organize your catalog.",
        "articles": [
            {
                "id": "products.variants",
                "title": "Add product variants",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products, edit the product and choose Variants.",
                    "Add each option with its own name, SKU, price and cost.",
                    "Set opening stock and a reorder point per variant.",
                    "Save; the POS now asks which variant is being sold.",
                ],
                "tip": "A product with variants uses each variant's SKU, so the parent SKU is locked.",
            },
            {
                "id": "products.modifiers",
                "title": "Add modifiers and options",
                "verticals": ["coffee", "restaurant", "general"],
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products, edit the product and choose Modifiers.",
                    "Create a group such as Sugar level or Milk, then add its options and any price difference.",
                    "Save and attach the group to the product.",
                    "At the register, pick the options when the item is added to the cart.",
                ],
            },
            {
                "id": "products.batches",
                "title": "Track batches and expiry dates",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products, edit the product and choose Batches.",
                    "Add each batch with a code, expiry date and quantity.",
                    "The list shows how much of each batch is left.",
                    "Sell from the oldest batch first so nothing expires on the shelf.",
                ],
            },
            {
                "id": "products.attributes",
                "title": "Add product attributes",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products and edit the product.",
                    "In Attributes add a key and value, such as Colour: Red or Size: Large.",
                    "Save; attributes show on the product and can print on the receipt.",
                ],
            },
            {
                "id": "products.images",
                "title": "Add product images",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products and edit the product.",
                    "In the image area, upload a photo or pick one from the media library.",
                    "For a product with variants you can set a separate image per variant.",
                    "Save; the image shows on the POS grid and the product list.",
                ],
            },
            {
                "id": "products.import-export",
                "title": "Import and export your products",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products and choose Export to download your catalog as a CSV file.",
                    "To add or update many products, choose Import and pick a CSV.",
                    "Match your columns to the product fields before uploading.",
                    "Review the result; imported products appear in the list.",
                ],
                "tip": "Export first to get a file with the right columns, then edit and re-import it.",
            },
            {
                "id": "products.supplier-prices",
                "title": "Set supplier cost prices",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Products, edit a product and choose Supplier prices.",
                    "Add a supplier with their cost price, supplier SKU, lead time and minimum order.",
                    "Mark one supplier as preferred.",
                    "Use these costs when you create purchase orders.",
                ],
            },
        ],
    },
    {
        "id": "suppliers",
        "title": "Suppliers",
        "blurb": "Keep your supplier contacts in one place.",
        "articles": [
            {
                "id": "suppliers.add",
                "title": "Add a supplier",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Suppliers and choose Add supplier.",
                    "Enter the name, contact person, phone and email.",
                    "Save; the supplier can now be used on stock receipts and purchase orders.",
                ],
            },
        ],
    },
    {
        "id": "purchasing",
        "title": "Purchase orders",
        "blurb": "Order and receive stock.",
        "articles": [
            {
                "id": "purchasing.create",
                "title": "Create a purchase order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Purchase orders and choose New purchase order.",
                    "Pick the product, supplier and quantity, and add a note if needed.",
                    "Save; the order is listed as Ordered.",
                    "Choose Cancel to close it, or Receive when the stock arrives.",
                ],
            },
            {
                "id": "purchasing.receive",
                "title": "Receive a purchase order",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Purchase orders and find the order.",
                    "Choose Receive to add the stock to inventory.",
                    "For serial-tracked products, enter each unit's serial number and cost as prompted.",
                    "The order is marked Received and stock updates for the store.",
                ],
            },
        ],
    },
    {
        "id": "reports",
        "title": "Reports",
        "blurb": "Understand how your store is doing.",
        "articles": [
            {
                "id": "reports.summary",
                "title": "Read your sales reports",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Reports and choose a period such as Today or Last 7 days.",
                    "The summary shows gross and net sales, tax, discounts, transactions and average order.",
                    "Scroll to see sales by day, categories, payment methods and top products.",
                    "Choose an order in the table to open its receipt.",
                ],
            },
            {
                "id": "reports.gdt",
                "title": "Export a GDT tax report",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Reports and choose the period you need.",
                    "Choose Export and pick the GDT CSV format.",
                    "Open the downloaded file in your accounting tool or send it to your accountant.",
                ],
            },
            {
                "id": "reports.margins",
                "title": "Check your profit margin",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager"],
                "steps": [
                    "Open Reports and choose the Margin report.",
                    "It compares your sales against the cost price recorded on each product.",
                    "Set a cost price on every product so the numbers are complete.",
                ],
            },
            {
                "id": "reports.stores",
                "title": "Compare all your stores",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Reports and switch from a single store to Consolidated.",
                    "Pick the stores to include, or leave them all selected.",
                    "The summary and charts combine every chosen store.",
                ],
                "tip": "Consolidated reports are included on paid plans.",
            },
        ],
    },
    {
        "id": "activity",
        "title": "Activity log",
        "blurb": "See who changed what.",
        "articles": [
            {
                "id": "activity.audit",
                "title": "Review the activity log",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Activity to see a record of changes in your workspace.",
                    "Each row shows when it happened, who did it, the action and the item.",
                    "Use it to check stock edits, refunds, price changes and team updates.",
                ],
            },
        ],
    },
    {
        "id": "settings",
        "title": "Settings",
        "blurb": "Tune your workspace to fit your store.",
        "articles": [
            {
                "id": "settings.receipts",
                "title": "Customize your receipt",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Receipts.",
                    "Set the order prefix, paper size and language, and choose a template.",
                    "Edit the layout: add or remove blocks and change their alignment and font.",
                    "Use the preview to check it at true paper size, then print a test.",
                ],
            },
            {
                "id": "settings.currencies",
                "title": "Add currencies and exchange rates",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Currencies.",
                    "Turn on the currencies you accept and pick the primary one.",
                    "Add an exchange rate for each extra currency.",
                    "At checkout you can tender in any enabled currency.",
                ],
            },
            {
                "id": "settings.bank-khqr",
                "title": "Connect ABA PayWay for KHQR",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Settings and choose Bank & KHQR.",
                    "Paste your ABA PayWay link for the company, or for one store.",
                    "Choose Save link, then Test connection to confirm it works.",
                    "Once verified, KHQR appears as a payment method at checkout.",
                ],
                "tip": "A store-level link overrides the company link for that store.",
            },
            {
                "id": "settings.pos-preferences",
                "title": "Set your POS preferences",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose POS preferences.",
                    "Turn discounts, tips, the sale sound and auto-print on or off.",
                    "Set whether a shift must be open before selling.",
                    "Save; the register follows these settings.",
                ],
                "tip": "Auto-print prints with no browser dialog only when the POS was opened with kiosk printing (see Print receipts without a dialog).",
            },
            {
                "id": "settings.notifications",
                "title": "Choose your notifications",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Notifications.",
                    "Turn on the alerts you want: daily summary, low stock, refunds, shift reminders and team activity.",
                    "Save; alerts appear under the bell in the header.",
                ],
            },
            {
                "id": "settings.feature-packs",
                "title": "Turn on feature packs",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Feature packs.",
                    "Switch on the fields your store needs, such as barcodes, brands, units, variants, modifiers, serials or batches.",
                    "Save; the extra fields appear on products and at the register.",
                ],
                "tip": "Your business type sets sensible defaults; you can override them per store.",
            },
            {
                "id": "settings.inventory",
                "title": "Set inventory defaults",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Inventory defaults.",
                    "Set the default reorder point that new products start with.",
                    "Save; you can still change the reorder point on each product.",
                ],
            },
            {
                "id": "settings.sessions",
                "title": "Manage cashier sessions",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner"],
                "steps": [
                    "Open Settings and choose Cashier sessions.",
                    "Pick how long a sign-in lasts before a cashier must sign in again.",
                    "Save; the change applies to new sessions.",
                ],
            },
            {
                "id": "settings.media",
                "title": "Use the media library",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Media library.",
                    "Upload the images you want to reuse across products and receipts.",
                    "When you set a product or variant image, choose one from the library.",
                    "Delete an image you no longer need.",
                ],
            },
            {
                "id": "settings.security",
                "title": "Change your password",
                "verticals": list(ALL_VERTICALS),
                "roles": ["owner", "manager", "inventory_manager", "cashier"],
                "steps": [
                    "Open Settings and choose Security.",
                    "Enter your current password and the new one twice.",
                    "Save. You stay signed in on this device.",
                ],
            },
        ],
    },
    {
        "id": "restaurant",
        "title": "Restaurant & tables",
        "blurb": "Set up the dining floor for dine-in service.",
        "articles": [
            {
                "id": "restaurant.tables",
                "title": "Manage dining areas and tables",
                "verticals": ["restaurant", "coffee"],
                "roles": ["owner", "manager"],
                "steps": [
                    "Open Settings and choose Tables.",
                    "Add areas such as Ground floor or Terrace.",
                    "Add tables with a name and seat count, and assign an area.",
                    "Dine-in orders can then be seated at these tables.",
                ],
                "tip": "The Tables section is shown for restaurant and coffee businesses.",
            },
            {
                "id": "restaurant.floor",
                "title": "Use the Floor view",
                "verticals": ["restaurant", "coffee"],
                "roles": ["owner", "manager", "cashier"],
                "steps": [
                    "Open Floor to see your dining room grouped by area.",
                    "Each tile shows a table and its status: Available, Occupied, Reserved or Cleaning.",
                    "Tap a table to move it to the next status as service progresses.",
                    "Choose Dine-in as the order type when you take a seated order.",
                ],
                "tip": "The Floor view appears once the Tables pack is on; set areas and tables in Settings, then Tables.",
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


# Extra search terms per article, so a merchant's wording ("checkout", "menu",
# "refund") finds the right guide even when it is not in the article text. Used
# by both the help search and the assistant's grounding.
ARTICLE_KEYWORDS: Final[dict[str, list[str]]] = {
    "getting-started.first-sale": ["sell", "sale", "checkout", "charge", "pay", "payment", "receipt", "cash", "khqr", "customer", "order"],
    "getting-started.add-products": ["product", "item", "menu", "price", "catalog", "barcode", "sku", "create"],
    "inventory.restock": ["stock", "restock", "receive", "delivery", "supplier", "inventory", "quantity"],
    "inventory.low-stock": ["reorder", "low stock", "out of stock", "replenish", "running out"],
    "electronics.serials": ["serial", "imei", "unit", "track", "device"],
    "electronics.warranty": ["warranty", "grade", "grading", "condition", "refurbished", "used", "second hand", "battery"],
    "team.invite": ["invite", "staff", "team", "employee", "member", "permission", "role", "access"],
    "billing.change-plan": ["plan", "subscription", "upgrade", "downgrade", "billing", "payment", "invoice"],
    "overview.dashboard": ["dashboard", "overview", "home", "summary", "today", "checklist", "metrics"],
    "overview.notifications": ["notification", "notifications", "alert", "alerts", "bell", "unread"],
    "pos.order-type": ["order type", "takeaway", "take out", "dine in", "dine-in", "delivery", "table"],
    "pos.customer-display": ["customer display", "customer screen", "second screen", "display", "អេក្រង់អតិថិជន"],
    "pos.scan": ["scan", "scanner", "barcode", "sku", "search", "lookup"],
    "pos.receipt-printing": ["print", "printing", "receipt", "auto print", "auto-print", "silent", "kiosk", "kiosk printing", "no dialog", "print dialog", "printer", "thermal receipt"],
    "pos.serials-checkout": ["serial", "unit", "pick", "choose", "checkout"],
    "orders.find": ["order", "orders", "find", "history", "search", "filter", "past sale"],
    "products.attributes": ["attribute", "attributes", "colour", "color", "size", "key value"],
    "products.images": ["image", "photo", "picture", "media", "upload", "gallery"],
    "products.import-export": ["import", "export", "csv", "bulk", "spreadsheet", "download", "upload"],
    "products.supplier-prices": ["supplier price", "cost", "lead time", "moq", "preferred supplier"],
    "electronics.lookup": ["serial", "lookup", "find", "warranty check", "verify"],
    "electronics.service": ["service", "repair", "ticket", "inspection", "fix"],
    "reports.margins": ["margin", "profit", "cost", "markup", "profitability"],
    "reports.stores": ["consolidated", "all stores", "multi store", "multistore", "compare", "combined"],
    "getting-started.onboarding": ["sign up", "register", "onboarding", "verify email", "setup", "plan", "account"],
    "team.manage": ["remove member", "deactivate", "suspend", "change role", "offboard", "revoke"],
    "billing.schedule": ["schedule change", "cancel plan", "downgrade", "renew", "cancel at period end"],
    "billing.receipts": ["billing receipt", "invoice", "payment history", "charge"],
    "settings.bank-khqr": ["aba", "payway", "khqr", "bank", "payment link", "qr", "verify connection"],
    "settings.pos-preferences": ["pos preferences", "discounts", "tips", "sale sound", "auto print", "require shift"],
    "settings.notifications": ["notifications", "alerts", "daily summary", "low stock alert", "team activity"],
    "settings.feature-packs": ["feature pack", "feature packs", "capabilities", "barcode", "variants", "modifiers", "serials", "batches", "fields"],
    "settings.inventory": ["inventory defaults", "reorder point", "default reorder"],
    "settings.sessions": ["cashier session", "session length", "sign in timeout", "logout"],
    "settings.media": ["media", "media library", "images", "photos", "upload", "assets"],
    "settings.security": ["password", "security", "change password", "sign in"],
    "restaurant.tables": ["table", "tables", "dining", "area", "floor", "seat", "dine in"],
    "getting-started.signin": ["sign in", "login", "log in", "remember me", "verify email", "account"],
    "getting-started.reset-password": ["forgot password", "reset password", "forgot", "reset", "link expired"],
    "getting-started.google-signin": ["google", "continue with google", "gmail", "social sign in"],
    "restaurant.floor": ["floor", "dining room", "table status", "occupied", "available", "reserved", "cleaning"],
}


def _km_value(item: dict[str, Any], field: str) -> Any:
    """Return the Khmer value for a field.

    Prefers an inline ``*_km`` value (DB rows) and falls back to the static
    ``KH_TRANSLATIONS`` overlay, so both corpus shapes localize the same way.
    """
    inline = item.get(f"{field}_km")
    if inline:
        return inline
    return KH_TRANSLATIONS.get(item.get("id", ""), {}).get(field)


def _article_matches(article: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    if not needle:
        return True
    # Match both languages plus the keyword synonyms so either language and
    # everyday wording find the article.
    haystack = " ".join(
        [
            article.get("title", ""),
            *article.get("steps", []),
            article.get("tip") or "",
            *ARTICLE_KEYWORDS.get(article.get("id", ""), []),
            _km_value(article, "title") or "",
            *(_km_value(article, "steps") or []),
            _km_value(article, "tip") or "",
        ]
    ).lower()
    return needle in haystack


def filter_sections(
    sections: list[dict[str, Any]],
    *,
    vertical: str | None = None,
    role: str | None = None,
    query: str | None = None,
    language: str = "en",
) -> list[dict[str, Any]]:
    """Filter and localize a corpus of sections.

    Works for both the static ``SUPPORT_SECTIONS`` (Khmer via ``KH_TRANSLATIONS``)
    and DB rows (Khmer inline via ``*_km`` fields). Sections with no remaining
    articles are dropped; ordering is preserved.
    """
    khmer = language == "km"
    result: list[dict[str, Any]] = []
    for section in sections:
        rows: list[dict[str, Any]] = []
        for article in section["articles"]:
            if vertical and vertical not in article["verticals"]:
                continue
            if role and role not in article["roles"]:
                continue
            if not _article_matches(article, query):
                continue
            rows.append(
                {
                    **article,
                    "title": _km_value(article, "title") if khmer else article["title"],
                    "steps": (_km_value(article, "steps") or article["steps"]) if khmer else article["steps"],
                    "tip": (_km_value(article, "tip") or article.get("tip")) if khmer else article.get("tip"),
                }
            )
        if rows:
            result.append(
                {
                    "id": section["id"],
                    "title": _km_value(section, "title") if khmer else section["title"],
                    "blurb": _km_value(section, "blurb") if khmer else section["blurb"],
                    "articles": rows,
                }
            )
    return result


def articles_for(
    *,
    vertical: str | None = None,
    role: str | None = None,
    query: str | None = None,
    language: str = "en",
) -> list[dict[str, Any]]:
    """Filter and localize the static corpus (the fallback baseline)."""
    return filter_sections(SUPPORT_SECTIONS, vertical=vertical, role=role, query=query, language=language)


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
    "getting-started.categories": {
        "title": "រៀបចំទំនិញជាប្រភេទ",
        "steps": [
            "បើក ប្រភេទ ហើយចុច បន្ថែមប្រភេទ។",
            "បញ្ចូលឈ្មោះ ហើយអាចជ្រើសប្រភេទមេ ដើម្បីធ្វើជាប្រភេទរង។",
            "រក្សាទុក បន្ទាប់មកកំណត់ប្រភេទនៅពេលបន្ថែម ឬកែទំនិញ។",
            "ប្រភេទជួយរៀបចំផ្ទាំងលក់ និងបញ្ជីទំនិញឲ្យងាយរក។",
        ],
        "tip": "ប្រើប្រភេទរងសម្រាប់ផ្នែកដូចជា ភេសជ្ជៈក្តៅ និង ភេសជ្ជៈត្រជាក់។",
    },
    "getting-started.store-profile": {
        "title": "កំណត់ព័ត៌មានហាង",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស ប្រវត្តិក្រុមហ៊ុន ដើម្បីកំណត់ឈ្មោះក្រុមហ៊ុន អាសយដ្ឋាន ទូរស័ព្ទ និងលេខសម្គាល់ពន្ធ។",
            "ជ្រើស ការកំណត់ហាង ដើម្បីកំណត់ឈ្មោះហាង ទូរស័ព្ទ អាសយដ្ឋាន តំបន់ពេលវេលា និងអត្រាពន្ធសេវា។",
            "រក្សាទុក។ ព័ត៌មាននេះបង្ហាញនៅលើវិក្កយបត្រ និងអេក្រង់អតិថិជន។",
            "ដើម្បីបន្ថែមសាខា បើក ការកំណត់ហាង ហើយចុច បន្ថែមហាង។",
        ],
        "tip": "ដាក់សាខានីមួយៗជាហាងដោយឡែក ដើម្បីឲ្យស្តុក និងរបាយការណ៍បែងចែកដាច់ដោយឡែក។",
    },
    "inventory.adjust": {
        "title": "កែសម្រួលស្តុក ឬកាត់ចោល",
        "steps": [
            "បើក ស្តុក ហើយរកទំនិញ ឬម៉ូដ។",
            "ជ្រើស កែសម្រួល ហើយបញ្ចូលចំនួនប្តូរ; ប្រើសញ្ញាដក ដើម្បីបន្ថយស្តុក។",
            "ជ្រើសមូលហេតុ ដូចជា ខូចខាត ចោរកម្ម ឬ ការរាប់ស្តុក។",
            "រក្សាទុក។ ចលនានេះត្រូវបានកត់ត្រាក្នុងប្រវត្តិស្តុក។",
        ],
    },
    "inventory.transfer": {
        "title": "ផ្ទេរស្តុកទៅហាងផ្សេង",
        "steps": [
            "បើក ស្តុក ជ្រើសទំនិញ បន្ទាប់មកជ្រើស ផ្ទេរ។",
            "ជ្រើសហាងគោលដៅ ហើយបញ្ចូលចំនួន។",
            "សម្រាប់ទំនិញតាមដានសេរៀល សូមជ្រើសឯកតាជាក់លាក់ដែលត្រូវផ្ទេរ។",
            "បញ្ជាក់។ ស្តុកចេញពីហាងនេះ ហើយទៅដល់ហាងគោលដៅ។",
        ],
    },
    "inventory.history": {
        "title": "មើលប្រវត្តិចលនាស្តុក",
        "steps": [
            "បើក ស្តុក ហើយជ្រើស ប្រវត្តិស្តុក។",
            "ចម្រាញ់តាមទំនិញ ដើម្បីមើលការបន្ថែមស្តុក ការលក់ ការកែសម្រួល និងការផ្ទេរ។",
            "ជួរនីមួយៗបង្ហាញប្រភេទ មូលហេតុ ចំនួន និងអ្នកដែលបានធ្វើ។",
        ],
    },
    "team.roles": {
        "title": "ស្គាល់តួនាទីក្រុម",
        "steps": [
            "ម្ចាស់: ចូលដំណើរការពេញលេញ រួមទាំងវិក្កយបត្រ ក្រុម និងការបន្ថែមហាង។",
            "អ្នកគ្រប់គ្រង: ដំណើរការហាង និងមើលរបាយការណ៍ និងការអនុម័ត។",
            "អ្នកគ្រប់គ្រងស្តុក: គ្រប់គ្រងទំនិញ ស្តុក អ្នកផ្គត់ផ្គង់ និងការបញ្ជាទិញទំនិញ។",
            "អ្នកគិតលុយ: លក់ និងថែទាំអតិថិជន; គ្មានការកំណត់ ឬរបាយការណ៍។",
        ],
        "tip": "អ្នកអាចកំណត់សមាជិកនីមួយៗឲ្យប្រើបានតែហាងជាក់លាក់ នៅពេលអញ្ជើញ ឬកែពួកគេ។",
    },
    "billing.cycle": {
        "title": "ជ្រើសវដ្តវិក្កយបត្រ",
        "steps": [
            "បើក វិក្កយបត្រ និងគម្រោង។",
            "ប្តូររវាងវិក្កយបត្រប្រចាំខែ ប្រចាំពាក់កណ្តាលឆ្នាំ និងប្រចាំឆ្នាំ។",
            "វដ្តវែងជាងមានតម្លៃថោកជាង; តម្លៃធ្វើបច្ចុប្បន្នភាពមុនពេលបង់ប្រាក់។",
            "បញ្ជាក់ ដើម្បីប្តូរគម្រោងបច្ចុប្បន្នទៅវដ្តថ្មី។",
        ],
        "tip": "វដ្តប្រចាំឆ្នាំជាវិធីថោកបំផុតដើម្បីរក្សាគម្រោងបង់ប្រាក់ឲ្យសកម្ម។",
    },
    "point-of-sale": {"title": "ចំណុចលក់", "blurb": "ដំណើរការម៉ាស៊ីនគិតលុយ និងអេក្រង់អតិថិជន។"},
    # Draft Khmer pending native-speaker review (added to close the only
    # English-only gap in the corpus; see docs for the translation workflow).
    "pos.customer-display": {
        "title": "រៀបចំអេក្រង់អតិថិជន",
        "steps": [
            "នៅ ការកំណត់ បើក អេក្រង់អតិថិជន ហើយបើកជម្រើស បើកអេក្រង់អតិថិជន។",
            "បន្ថែមរូបសញ្ញាវិក្កយបត្រ និងអាសយដ្ឋានហាង ដើម្បីឲ្យអតិថិជនឃើញកន្លែងដែលពួកគេកំពុងបង់ប្រាក់ (ការកំណត់ បន្ទាប់មក វិក្កយបត្រ និង ការកំណត់ហាង)។",
            "នៅម៉ាស៊ីនគិតលុយ ចុច បើកអេក្រង់អតិថិជន។ បង្អួចទីពីរនឹងបើកបង្ហាញការបញ្ជាទិញ ហើយនៅពេលគិតលុយ កូដ KHQR។",
            "ផ្លាស់បង្អួចនោះទៅអេក្រង់ដែលបែរមុខទៅអតិថិជន។ វាធ្វើបច្ចុប្បន្នភាពស្របនឹងម៉ាស៊ីនគិតលុយសម្រាប់រាល់ការលក់។",
            "ដើម្បីបញ្ឈប់ការចែករំលែក សូមបិទជម្រើស បើកអេក្រង់អតិថិជនវិញ; ប៊ូតុងនឹងបាត់ពីម៉ាស៊ីនគិតលុយ។",
        ],
        "tip": "អេក្រង់បង្ហាញទិន្នន័យ លុះត្រាតែមានម៉ាស៊ីនគិតលុយបើកនៅលើកុំព្យូទ័រតែមួយ។ បើបើកដោយឡែក វាបង្ហាញ កំពុងរង់ចាំម៉ាស៊ីនគិតលុយ។",
    },
    "pos.shift": {
        "title": "បើក និងបិទវេន",
        "steps": [
            "នៅ ចំណុចលក់ ជ្រើស បើកវេន ហើយបញ្ចូលប្រាក់សាច់ប្រាក់ចាប់ផ្តើម។",
            "លក់ជាធម្មតា; ការលក់នីមួយៗភ្ជាប់ទៅវេនដែលបើក។",
            "នៅចុងវេន ជ្រើស បិទវេន បន្ទាប់មករាប់ និងបញ្ចូលសាច់ប្រាក់ក្នុងថត។",
            "ប្រព័ន្ធបង្ហាញសាច់ប្រាក់រំពឹងទុក ធៀបនឹងសាច់ប្រាក់រាប់បាន និងភាពខុសគ្នា បន្ទាប់មកកត់ត្រាវេន។",
            "ជ្រើស វេន ដើម្បីមើលវេនកន្លងមក។",
        ],
        "tip": "ប្រសិនបើការកំណត់តម្រូវឲ្យបើកវេន អ្នកមិនអាចគិតលុយបានទេ រហូតបើកវេន។",
    },
    "pos.hold-orders": {
        "title": "ផ្អាក និងបន្តការបញ្ជាទិញ",
        "steps": [
            "ពេលមានទំនិញក្នុងកន្ត្រក ជ្រើស ផ្អាក ហើយបន្ថែមស្លាកដូចជាឈ្មោះ ឬតុ។",
            "ការបញ្ជាទិញត្រូវផ្អាក ហើយម៉ាស៊ីនគិតលុយទំនេរសម្រាប់អតិថិជនបន្ទាប់។",
            "ជ្រើស ផ្អាក ដើម្បីមើលការបញ្ជាទិញដែលផ្អាក បន្ទាប់មកបន្តវិញ។",
            "ការបន្តផ្ទុកទំនិញមកកន្ត្រកវិញ; ការបោះបង់លុបវាចោលទាំងស្រុង។",
        ],
        "tip": "ប្រសិនបើកន្ត្រកមានទំនិញរួចហើយ សូមជ្រើសថាត្រូវជំនួស ឬបញ្ចូល។",
    },
    "pos.split-payment": {
        "title": "ទទួលការបង់ប្រាក់បែងចែក",
        "steps": [
            "ជ្រើស គិតប្រាក់ ដើម្បីបើកអេក្រង់ទូទាត់។",
            "បញ្ចូលការទូទាត់ទីមួយ: ជ្រើសវិធី និងចំនួន បន្ទាប់មកបន្ថែម។",
            "បន្ថែមការទូទាត់ទីពីរសម្រាប់ចំនួននៅសល់។",
            "បញ្ចប់នៅពេលចំនួននៅសល់ស្មើសូន្យ បន្ទាប់មកបញ្ចប់ការលក់។",
        ],
        "tip": "អ្នកអាចលាយសាច់ប្រាក់ និង KHQR ក្នុងការលក់តែមួយ។",
    },
    "pos.khqr": {
        "title": "ទទួលការបង់ប្រាក់តាម KHQR",
        "steps": [
            "ភ្ជាប់ ABA PayWay ជាមុន: ការកំណត់ បន្ទាប់មក ធនាគារ និង KHQR បន្ទាប់មកបន្ថែម និងផ្ទៀងផ្ទាត់តំណ PayWay។",
            "ពេលគិតលុយ ជ្រើស KHQR ជាវិធីទូទាត់។",
            "បង្ហាញកូដ QR ឲ្យអតិថិជនស្កេនដោយកម្មវិធីធនាគាររបស់ពួកគេ។",
            "អេក្រង់ធ្វើបច្ចុប្បន្នភាពនៅពេលទូទាត់បានបញ្ជាក់ បន្ទាប់មកវិក្កយបត្របោះពុម្ព។",
        ],
        "tip": "KHQR ត្រូវការអ៊ីនធឺណិតសកម្មដើម្បីបញ្ជាក់ការទូទាត់។ វិក្កយបត្របោះពុម្ពដោយខ្លួនឯងនៅពេលបើកការបោះពុម្ពស្វ័យប្រវត្តិ។",
    },
    "pos.receipt-printing": {
        "title": "បោះពុម្ពវិក្កយបត្រដោយគ្មានប្រអប់សន្ទនា",
        "steps": [
            "បើក ការបោះពុម្ពស្វ័យប្រវត្តិ ក្នុង ការកំណត់ បន្ទាប់មក ចំណូលចិត្តចំណុចលក់ ដើម្បីឲ្យការលក់នីមួយៗបោះពុម្ពដោយខ្លួនឯង។",
            "ក្នុងផ្ទាំងកម្មវិធីរុករកធម្មតា វិក្កយបត្រនៅតែរង់ចាំប្រអប់សន្ទនាបោះពុម្ព។ ដើម្បីបោះពុម្ពដោយគ្មានប្រអប់សន្ទនា បើកម៉ាស៊ីនគិតលុយជាមួយជម្រើស kiosk-printing របស់កម្មវិធីរុករក។",
            "នៅលើ Windows ចាប់ផ្តើមចំណុចលក់ដោយស្គ្រីប start-pos.ps1 ដែលរួមបញ្ចូល ឬបន្ថែម --kiosk-printing ទៅផ្លូវកាត់ Chrome ឬ Edge របស់អ្នក។",
            "កំណត់ម៉ាស៊ីនបោះពុម្ពវិក្កយបត្រជាម៉ាស៊ីនបោះពុម្ពលំនាំដើមរបស់ Windows; ការបោះពុម្ព kiosk ប្រើវាជានិច្ច។",
            "បើគ្មានជម្រើសនេះ អ្វីៗនៅតែដំណើរការ — វិក្កយបត្រគ្រាន់តែឆ្លងកាត់ប្រអប់សន្ទនាបោះពុម្ពធម្មតា។",
        ],
        "tip": "នេះជាអ្វីដែលធ្វើឲ្យការលក់តាម KHQR បញ្ជាក់ បិទ និងបោះពុម្ពវិក្កយបត្រដោយគ្មាននរណាម្នាក់នៅក្តារចុច។",
    },
    "pos.discount-tip": {
        "title": "ដាក់ការបញ្ចុះតម្លៃ ឬប្រាក់ជំនួយ",
        "steps": [
            "ក្នុងកន្ត្រក ជ្រើស បញ្ចុះតម្លៃ ហើយបញ្ចូលជាភាគរយ ឬចំនួនថេរ។",
            "ជ្រើស ប្រាក់ជំនួយ ដើម្បីបន្ថែមប្រាក់ជំនួយសម្រាប់ការលក់។",
            "សរុបថ្មីធ្វើបច្ចុប្បន្នភាពមុនពេលគិតលុយ។",
        ],
        "tip": "ប្រសិនបើការបញ្ចុះតម្លៃត្រូវបានបិទក្នុងការកំណត់ សូមស្នើឲ្យម្ចាស់ ឬអ្នកគ្រប់គ្រងធ្វើវា។",
    },
    "orders": {"title": "ការបញ្ជាទិញ", "blurb": "រក បង្វិលប្រាក់ និងបោះពុម្ពវិក្កយបត្រឡើងវិញ។"},
    "orders.refund": {
        "title": "បង្វិលប្រាក់ការបញ្ជាទិញ",
        "steps": [
            "បើក ការបញ្ជាទិញ រកការលក់ ហើយជ្រើស បង្វិលប្រាក់។",
            "ជ្រើសចំនួនដែលត្រូវបង្វិលសម្រាប់ជួរនីមួយៗ និងជ្រើសសេរៀលជាក់លាក់សម្រាប់ទំនិញតាមដាន។",
            "ជ្រើសវិធីបង្វិលប្រាក់ ហើយបន្ថែមមូលហេតុ។",
            "បញ្ជាក់។ ស្តុកត្រូវបានត្រឡប់ សេរៀលត្រូវបានដោះលែង ហើយការបង្វិលប្រាក់ត្រូវបានកត់ត្រា។",
        ],
        "tip": "ប្រសិនបើក្រុមរបស់អ្នកប្រើការអនុម័ត ការបង្វិលប្រាក់ធំអាចរង់ចាំការអនុម័តពីអ្នកគ្រប់គ្រង។",
    },
    "orders.cancel": {
        "title": "បោះបង់ការបញ្ជាទិញមិនទាន់បង់ប្រាក់",
        "steps": [
            "បើក ការបញ្ជាទិញ ហើយចម្រាញ់ទៅ កំពុងរង់ចាំ។",
            "ជ្រើសការបញ្ជាទិញ ហើយជ្រើស បោះបង់។",
            "បន្ថែមមូលហេតុ ហើយបញ្ជាក់។ ស្តុកមិនប្តូរទេ ព្រោះការបញ្ជាទិញមិនទាន់បង់ប្រាក់។",
        ],
    },
    "orders.receipt": {
        "title": "បោះពុម្ព ឬផ្ញើវិក្កយបត្រតាមអ៊ីមែល",
        "steps": [
            "បើក ការបញ្ជាទិញ ហើយជ្រើសការលក់ ដើម្បីមើលវិក្កយបត្រ។",
            "ជ្រើស បោះពុម្ព ដើម្បីបញ្ជូនទៅម៉ាស៊ីនបោះពុម្ពវិក្កយបត្រ។",
            "ប្រសិនបើការបញ្ជាទិញមានអ៊ីមែលអតិថិជន ជ្រើស ផ្ញើវិក្កយបត្រ ដើម្បីផ្ញើច្បាប់ចម្លង។",
        ],
        "tip": "បើកការបោះពុម្ពស្វ័យប្រវត្តិក្នុងការកំណត់ ដើម្បីបោះពុម្ពវិក្កយបត្រគ្រប់ការលក់។ ដើម្បីឲ្យគ្មានប្រអប់សន្ទនាទាល់តែសោះ សូមបើកចំណុចលក់ជាមួយការបោះពុម្ព kiosk (មើល បោះពុម្ពវិក្កយបត្រដោយគ្មានប្រអប់សន្ទនា)។",
    },
    "approvals": {"title": "ការអនុម័ត", "blurb": "ពិនិត្យសំណើពីក្រុមការងារ។"},
    "approvals.review": {
        "title": "អនុម័ត ឬបដិសេធសំណើ",
        "steps": [
            "បើក ការអនុម័ត ដើម្បីមើលអ្វីៗដែលរង់ចាំសេចក្តីសម្រេច។",
            "ជួរនីមួយៗបង្ហាញសកម្មភាព ចំនួន និងមូលហេតុ។",
            "ជ្រើស អនុម័ត ដើម្បីឲ្យវាបន្ត ឬ បដិសេធ ហើយបន្ថែមមូលហេតុ។",
            "អ្នកស្នើត្រូវបានជូនដំណឹង ហើយសេចក្តីសម្រេចត្រូវកត់ត្រាក្នុងកំណត់ហេតុសកម្មភាព។",
        ],
    },
    "approvals.policy": {
        "title": "កំណត់គោលនយោបាយអនុម័ត",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស គោលនយោបាយអនុម័ត។",
            "បើកការអនុម័ត បន្ទាប់មកជ្រើសរបៀបសម្រាប់សកម្មភាពនីមួយៗ: បិទ ពិនិត្យ ឬ អនុម័ត។",
            "កំណត់កម្រិតចំនួន និងតួនាទីដែលអាចអនុម័តបាន។",
            "រក្សាទុក។ សំណើលើសកម្រិតនឹងរង់ចាំក្នុង ការអនុម័ត។",
        ],
        "tip": "ការអនុម័តដំណើរការតែនៅពេលអ្នកមានសមាជិកក្រុមច្រើនជាងម្នាក់។",
    },
    "customers": {"title": "អតិថិជន និងរង្វាន់", "blurb": "រក្សាទុកព័ត៌មានអតិថិជន និងរង្វាន់។"},
    "customers.manage": {
        "title": "បន្ថែម និងគ្រប់គ្រងអតិថិជន",
        "steps": [
            "បើក អតិថិជន ហើយជ្រើស បន្ថែមអតិថិជន។",
            "បញ្ចូលឈ្មោះ ទូរស័ព្ទ និងអ៊ីមែល ព្រមទាំងកំណត់សម្គាល់ បន្ទាប់មករក្សាទុក។",
            "ស្វែងរកតាមឈ្មោះ ឬទូរស័ព្ទ ឬបើកអតិថិជន ដើម្បីមើលការបញ្ជាទិញ និងការចំណាយ។",
            "បិទដំណើរការអតិថិជន ដើម្បីលាក់ដោយមិនលុបប្រវត្តិ។",
        ],
        "tip": "អតិថិជនដែលមានការបញ្ជាទិញកន្លងមកមិនអាចលុបបានទេ ដូច្នេះសូមបិទដំណើរការជំនួស។",
    },
    "customers.loyalty": {
        "title": "ផ្តល់រង្វាន់ដល់អតិថិជនដោយពិន្ទុស្មោះ",
        "steps": [
            "ក្នុងការកំណត់ ជ្រើស ភាពស្មោះត្រង់ និងរង្វាន់ ហើយកំណត់ចំនួនពិន្ទុក្នុងមួយឯកតាចំណាយ។",
            "ភ្ជាប់អតិថិជនពេលលក់ ដើម្បីបន្ថែមពិន្ទុដោយស្វ័យប្រវត្តិ។",
            "បើកអតិថិជន ដើម្បីមើលពិន្ទុ បន្ទាប់មកកែបន្ថែម ឬបន្ថយតាមតម្រូវការ។",
            "ប្តូរពិន្ទុនៅម៉ាស៊ីនគិតលុយ ដើម្បីកាត់ចេញពីសរុប។",
        ],
    },
    "products": {"title": "ទំនិញ", "blurb": "បង្កើត និងរៀបចំបញ្ជីទំនិញរបស់អ្នក។"},
    "products.variants": {
        "title": "បន្ថែមម៉ូដទំនិញ",
        "steps": [
            "បើក ទំនិញ កែទំនិញ ហើយជ្រើស ម៉ូដ។",
            "បន្ថែមជម្រើសនីមួយៗជាមួយឈ្មោះ SKU តម្លៃ និងតម្លៃដើមផ្ទាល់ខ្លួន។",
            "កំណត់ស្តុកដំបូង និងចំណុចបញ្ជាទិញឡើងវិញសម្រាប់ម៉ូដនីមួយៗ។",
            "រក្សាទុក; ផ្ទាំងលក់នឹងសួរថាម៉ូដណាដែលលក់។",
        ],
        "tip": "ទំនិញដែលមានម៉ូដប្រើ SKU របស់ម៉ូដនីមួយៗ ដូច្នេះ SKU មេត្រូវបានចាក់សោ។",
    },
    "products.modifiers": {
        "title": "បន្ថែមជម្រើសបន្ថែម",
        "steps": [
            "បើក ទំនិញ កែទំនិញ ហើយជ្រើស ជម្រើសបន្ថែម។",
            "បង្កើតក្រុមដូចជា កម្រិតស្ករ ឬ ទឹកដោះគោ បន្ទាប់មកបន្ថែមជម្រើស និងភាពខុសគ្នាតម្លៃ។",
            "រក្សាទុក ហើយភ្ជាប់ក្រុមទៅទំនិញ។",
            "នៅម៉ាស៊ីនគិតលុយ ជ្រើសជម្រើសនៅពេលបន្ថែមទំនិញទៅកន្ត្រក។",
        ],
    },
    "products.batches": {
        "title": "តាមដានឡូ និងកាលបរិច្ឆេទផុតកំណត់",
        "steps": [
            "បើក ទំនិញ កែទំនិញ ហើយជ្រើស ឡូ។",
            "បន្ថែមឡូនីមួយៗជាមួយលេខកូដ កាលបរិច្ឆេទផុតកំណត់ និងចំនួន។",
            "បញ្ជីបង្ហាញថានៅសល់ប៉ុន្មានក្នុងឡូនីមួយៗ។",
            "លក់ពីឡូចាស់មុន ដើម្បីកុំឲ្យមានទំនិញផុតកំណត់លើធ្នើ។",
        ],
    },
    "suppliers": {"title": "អ្នកផ្គត់ផ្គង់", "blurb": "រក្សាព័ត៌មានអ្នកផ្គត់ផ្គង់។"},
    "suppliers.add": {
        "title": "បន្ថែមអ្នកផ្គត់ផ្គង់",
        "steps": [
            "បើក អ្នកផ្គត់ផ្គង់ ហើយជ្រើស បន្ថែមអ្នកផ្គត់ផ្គង់។",
            "បញ្ចូលឈ្មោះ អ្នកទំនាក់ទំនង ទូរស័ព្ទ និងអ៊ីមែល។",
            "រក្សាទុក; អ្នកផ្គត់ផ្គង់អាចប្រើលើការទទួលស្តុក និងការបញ្ជាទិញទំនិញ។",
        ],
    },
    "purchasing": {"title": "ការបញ្ជាទិញទំនិញ", "blurb": "បញ្ជាទិញ និងទទួលស្តុក។"},
    "purchasing.create": {
        "title": "បង្កើតការបញ្ជាទិញទំនិញ",
        "steps": [
            "បើក ការបញ្ជាទិញទំនិញ ហើយជ្រើស បង្កើតការបញ្ជាទិញថ្មី។",
            "ជ្រើសទំនិញ អ្នកផ្គត់ផ្គង់ និងចំនួន ហើយបន្ថែមកំណត់សម្គាល់ប្រសិនបើចាំបាច់។",
            "រក្សាទុក; ការបញ្ជាទិញបង្ហាញជា បានបញ្ជាទិញ។",
            "ជ្រើស បោះបង់ ដើម្បីបិទ ឬ ទទួល នៅពេលទំនិញមកដល់។",
        ],
    },
    "purchasing.receive": {
        "title": "ទទួលការបញ្ជាទិញទំនិញ",
        "steps": [
            "បើក ការបញ្ជាទិញទំនិញ ហើយរកការបញ្ជាទិញ។",
            "ជ្រើស ទទួល ដើម្បីបន្ថែមស្តុកទៅស្តុក។",
            "សម្រាប់ទំនិញតាមដានសេរៀល សូមបញ្ចូលលេខសេរៀល និងតម្លៃដើមរបស់ឯកតានីមួយៗ។",
            "ការបញ្ជាទិញសម្គាល់ជា បានទទួល ហើយស្តុកធ្វើបច្ចុប្បន្នភាពសម្រាប់ហាង។",
        ],
    },
    "reports": {"title": "របាយការណ៍", "blurb": "យល់ដឹងពីស្ថានភាពហាងរបស់អ្នក។"},
    "reports.summary": {
        "title": "អានរបាយការណ៍លក់របស់អ្នក",
        "steps": [
            "បើក របាយការណ៍ ហើយជ្រើសរយៈពេល ដូចជា ថ្ងៃនេះ ឬ ៧ ថ្ងៃចុងក្រោយ។",
            "សេចក្តីសង្ខេបបង្ហាញការលក់សរុប ពន្ធ ការបញ្ចុះតម្លៃ ប្រតិបត្តិការ និងតម្លៃមធ្យម។",
            "រំកិលចុះក្រោមដើម្បីមើលការលក់តាមថ្ងៃ ប្រភេទ វិធីទូទាត់ និងទំនិញកំពូល។",
            "ជ្រើសការបញ្ជាទិញក្នុងតារាង ដើម្បីបើកវិក្កយបត្រ។",
        ],
    },
    "reports.gdt": {
        "title": "នាំចេញរបាយការណ៍ពន្ធ GDT",
        "steps": [
            "បើក របាយការណ៍ ហើយជ្រើសរយៈពេលដែលអ្នកត្រូវការ។",
            "ជ្រើស នាំចេញ ហើយជ្រើសទ្រង់ទ្រាយ GDT CSV។",
            "បើកឯកសារដែលបានទាញយកក្នុងកម្មវិធីគណនេយ្យ ឬផ្ញើទៅគណនេយ្យកររបស់អ្នក។",
        ],
    },
    "activity": {"title": "សកម្មភាព", "blurb": "មើលថាអ្នកណាបានធ្វើអ្វី។"},
    "activity.audit": {
        "title": "ពិនិត្យកំណត់ហេតុសកម្មភាព",
        "steps": [
            "បើក សកម្មភាព ដើម្បីមើលកំណត់ត្រានៃការផ្លាស់ប្តូរក្នុងកន្លែងធ្វើការ។",
            "ជួរនីមួយៗបង្ហាញពេលវេលា អ្នកធ្វើ សកម្មភាព និងវត្ថុ។",
            "ប្រើវាដើម្បីពិនិត្យការកែស្តុក ការបង្វិលប្រាក់ ការប្តូរតម្លៃ និងការធ្វើបច្ចុប្បន្នភាពក្រុម។",
        ],
    },
    "settings": {"title": "ការកំណត់", "blurb": "កែសម្រួលកន្លែងធ្វើការរបស់អ្នកឲ្យសមនឹងហាង។"},
    "settings.receipts": {
        "title": "កែសម្រួលវិក្កយបត្ររបស់អ្នក",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស វិក្កយបត្រ។",
            "កំណត់បុព្វបទលេខការបញ្ជាទិញ ទំហំក្រដាស និងភាសា ហើយជ្រើសគំរូ។",
            "កែសម្រួលប្លង់: បន្ថែម ឬដកប្លុក ប្តូរការតម្រឹម និងពុម្ពអក្សរ។",
            "ប្រើការមើលជាមុនដើម្បីពិនិត្យទំហំក្រដាសពិត បន្ទាប់មកបោះពុម្ពសាកល្បង។",
        ],
    },
    "settings.currencies": {
        "title": "បន្ថែមរូបិយប័ណ្ណ និងអត្រាប្តូរប្រាក់",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស រូបិយប័ណ្ណ។",
            "បើករូបិយប័ណ្ណដែលអ្នកទទួលយក ហើយជ្រើសរូបិយប័ណ្ណចម្បង។",
            "បន្ថែមអត្រាប្តូរប្រាក់សម្រាប់រូបិយប័ណ្ណបន្ថែមនីមួយៗ។",
            "ពេលគិតលុយ អ្នកអាចទូទាត់ជារូបិយប័ណ្ណណាមួយដែលបានបើក។",
        ],
    },
    "overview": {"title": "ផ្ទាំងសង្ខេប", "blurb": "មើលស្ថានភាពថ្ងៃនេះភ្លាមៗ។"},
    "overview.dashboard": {
        "title": "ប្រើផ្ទាំងសង្ខេបរបស់អ្នក",
        "steps": [
            "បើក ផ្ទាំងសង្ខេប ដើម្បីមើលការលក់ថ្ងៃនេះ ប្រតិបត្តិការ តម្លៃមធ្យម និងចំនួនទំនិញជិតអស់។",
            "អនុវត្តតាមបញ្ជីត្រៀមរៀបចំ; ជំហាននីមួយៗភ្ជាប់ទៅទំព័រដែលអ្នកត្រូវការ។",
            "ពិនិត្យទំនិញលក់ដាច់ និងបញ្ជីទំនិញជិតអស់មុនចាប់ផ្តើមថ្ងៃ។",
            "ជ្រើស ការលក់ថ្មី ដើម្បីទៅម៉ាស៊ីនគិតលុយភ្លាម។",
        ],
    },
    "overview.notifications": {
        "title": "អានការជូនដំណឹងរបស់អ្នក",
        "steps": [
            "ជ្រើសកណ្តឹងនៅលើផ្នែកខាងលើ ដើម្បីបើកការជូនដំណឹង។",
            "ការជូនដំណឹងស្តុកជិតអស់ និងការបង្វិលប្រាក់បង្ហាញនៅទីនេះ។",
            "បើកការជូនដំណឹង ដើម្បីទៅកាន់ទំនិញ ឬជ្រើស សម្គាល់ថាបានអានទាំងអស់។",
        ],
    },
    "pos.order-type": {
        "title": "កំណត់យកទៅផ្ទះ ទទួលទានក្នុងហាង ឬដឹកជញ្ជូន",
        "steps": [
            "នៅ ចំណុចលក់ បើកម៉ឺនុយប្រភេទការបញ្ជាទិញពីលើកន្ត្រក។",
            "ជ្រើស យកទៅផ្ទះ ទទួលទានក្នុងហាង ឬ ដឹកជញ្ជូន មុនពេលគិតលុយ។",
            "ជម្រើសត្រូវបានរក្សាទុកលើការបញ្ជាទិញ និងបង្ហាញក្នុងរបាយការណ៍។",
        ],
        "tip": "ការបញ្ជាទិញទទួលទានក្នុងហាងអាចភ្ជាប់ទៅតុពីផ្ទាំងកម្រាលហាងបាន។",
    },
    "pos.scan": {
        "title": "ស្កេនទំនិញនៅម៉ាស៊ីនគិតលុយ",
        "steps": [
            "នៅ ចំណុចលក់ ជ្រើស ស្កេនទំនិញ។",
            "ស្កេនបាកូដ ឬវាយ SKU ឈ្មោះទំនិញ ឬលេខសេរៀល។",
            "ចុច Enter; ទំនិញត្រូវបានបន្ថែម ឬសួរអ្នកឲ្យជ្រើសឯកតាជាក់លាក់។",
            "ធ្វើដូចនេះសម្រាប់ទំនិញនីមួយៗ ឬប្រើប្រអប់ស្វែងរកសម្រាប់ទំនិញគ្មានបាកូដ។",
        ],
        "tip": "ទំនិញអស់ស្តុកត្រូវបានទប់ស្កាត់ ដូច្នេះអ្នកមិនលក់អ្វីដែលគ្មានទេ។",
    },
    "pos.serials-checkout": {
        "title": "ជ្រើសឯកតានៅពេលគិតលុយ",
        "steps": [
            "នៅពេលបន្ថែមទំនិញដែលតាមដានសេរៀល ប្រអប់ជ្រើសនឹងបើកដោយស្វ័យប្រវត្តិ។",
            "ជ្រើសលេខសេរៀលជាក់លាក់ដែលអតិថិជនទិញ។",
            "ការធានាសម្រាប់ឯកតានោះចាប់ផ្តើមនៅពេលការលក់បញ្ចប់។",
            "ប្រសិនបើរកឯកតាមិនឃើញ សូមពិនិត្យ ស្តុក ឬបញ្ជីសេរៀលរបស់ទំនិញ។",
        ],
    },
    "orders.find": {
        "title": "រកការបញ្ជាទិញ",
        "steps": [
            "បើក ការបញ្ជាទិញ ហើយប្រើផ្ទាំងដើម្បីចម្រាញ់ បង់ប្រាក់ កំពុងរង់ចាំ ឬ បានបោះបង់។",
            "ស្វែងរក ឬរំកិលបញ្ជី បន្ទាប់មកជ្រើស ផ្ទុកបន្ថែម ដើម្បីមើលការលក់ចាស់។",
            "បើកការបញ្ជាទិញ ដើម្បីមើលជួរទំនិញ និងវិក្កយបត្រ។",
        ],
    },
    "products.attributes": {
        "title": "បន្ថែមគុណលក្ខណៈទំនិញ",
        "steps": [
            "បើក ទំនិញ ហើយកែទំនិញ។",
            "ក្នុង គុណលក្ខណៈ បន្ថែមកូនសោ និងតម្លៃ ដូចជា ពណ៌: ក្រហម ឬ ទំហំ: ធំ។",
            "រក្សាទុក; គុណលក្ខណៈបង្ហាញលើទំនិញ និងអាចបោះពុម្ពលើវិក្កយបត្រ។",
        ],
    },
    "products.images": {
        "title": "បន្ថែមរូបភាពទំនិញ",
        "steps": [
            "បើក ទំនិញ ហើយកែទំនិញ។",
            "នៅតំបន់រូបភាព បញ្ចូលរូបថត ឬជ្រើសពីបណ្ណាល័យប្រព័ន្ធផ្សព្វផ្សាយ។",
            "សម្រាប់ទំនិញដែលមានម៉ូដ អ្នកអាចកំណត់រូបភាពដោយឡែកសម្រាប់ម៉ូដនីមួយៗ។",
            "រក្សាទុក; រូបភាពបង្ហាញនៅផ្ទាំងលក់ និងបញ្ជីទំនិញ។",
        ],
    },
    "products.import-export": {
        "title": "នាំចូល និងនាំចេញទំនិញ",
        "steps": [
            "បើក ទំនិញ ហើយជ្រើស នាំចេញ ដើម្បីទាញយកបញ្ជីទំនិញជាឯកសារ CSV។",
            "ដើម្បីបន្ថែម ឬធ្វើបច្ចុប្បន្នភាពទំនិញច្រើន ជ្រើស នាំចូល ហើយជ្រើសឯកសារ CSV។",
            "ផ្គូផ្គងជួរឈររបស់អ្នកទៅនឹងព័ត៌មានទំនិញមុនពេលបញ្ចូល។",
            "ពិនិត្យលទ្ធផល; ទំនិញដែលនាំចូលបង្ហាញក្នុងបញ្ជី។",
        ],
        "tip": "នាំចេញជាមុនដើម្បីទទួលឯកសារដែលមានជួរឈរត្រឹមត្រូវ បន្ទាប់មកកែ និងនាំចូលវិញ។",
    },
    "products.supplier-prices": {
        "title": "កំណត់តម្លៃដើមពីអ្នកផ្គត់ផ្គង់",
        "steps": [
            "បើក ទំនិញ កែទំនិញ ហើយជ្រើស តម្លៃអ្នកផ្គត់ផ្គង់។",
            "បន្ថែមអ្នកផ្គត់ផ្គង់ជាមួយតម្លៃដើម SKU របស់អ្នកផ្គត់ផ្គង់ រយៈពេលដឹកជញ្ជូន និងចំនួនអប្បបរមា។",
            "សម្គាល់អ្នកផ្គត់ផ្គង់ម្នាក់ជាចម្បង។",
            "ប្រើតម្លៃទាំងនេះនៅពេលបង្កើតការបញ្ជាទិញទំនិញ។",
        ],
    },
    "electronics.lookup": {
        "title": "រកលេខសេរៀល",
        "steps": [
            "នៅ ចំណុចលក់ ឬ ទំនិញ ជ្រើស រកសេរៀល។",
            "វាយលេខសេរៀល ដើម្បីមើលការលក់ ការធានា និងស្ថានភាពរបស់ឯកតា។",
            "លទ្ធផលបង្ហាញកន្លែងលក់ និងថាតើនៅក្រោមការធានាឬអត់។",
            "ប្រើវានៅចំណុចលក់ដើម្បីឆ្លើយសំណួរអំពីការធានារបស់អតិថិជន។",
        ],
        "tip": "លេខសេរៀលមានតែមួយគត់ក្នុងក្រុមហ៊ុន ដូច្នេះឯកតានីមួយៗរកឃើញបានតែម្តង។",
    },
    "electronics.service": {
        "title": "កត់ត្រាការជួសជុល ឬសំបុត្រសេវា",
        "steps": [
            "រកសេរៀល ហើយបើកវា។",
            "ជ្រើស បន្ថែមសំបុត្រសេវា ហើយជ្រើសប្រភេទ: ជួសជុល ធានា ឬ ត្រួតពិនិត្យ។",
            "បន្ថែមតម្លៃ និងកំណត់សម្គាល់ បន្ទាប់មករក្សាទុក។",
            "សំបុត្រត្រូវរក្សាទុកក្នុងប្រវត្តិសេរៀលសម្រាប់លើកក្រោយ។",
        ],
    },
    "reports.margins": {
        "title": "ពិនិត្យចំណេញរបស់អ្នក",
        "steps": [
            "បើក របាយការណ៍ ហើយជ្រើសរបាយការណ៍ ចំណេញ។",
            "វាប្រៀបធៀបការលក់របស់អ្នកទៅនឹងតម្លៃដើមដែលកត់ត្រាលើទំនិញនីមួយៗ។",
            "កំណត់តម្លៃដើមលើទំនិញគ្រប់មុខ ដើម្បីឲ្យលេខពេញលេញ។",
        ],
    },
    "reports.stores": {
        "title": "ប្រៀបធៀបគ្រប់ហាងរបស់អ្នក",
        "steps": [
            "បើក របាយការណ៍ ហើយប្តូរពីហាងតែមួយទៅ រួមបញ្ចូល។",
            "ជ្រើសហាងដែលត្រូវបញ្ចូល ឬទុកជ្រើសទាំងអស់។",
            "សេចក្តីសង្ខេប និងក្រាបរួមបញ្ចូលគ្រប់ហាងដែលបានជ្រើស។",
        ],
        "tip": "របាយការណ៍រួមបញ្ចូលរួមនៅក្នុងគម្រោងបង់ប្រាក់។",
    },
    "getting-started.onboarding": {
        "title": "កំណត់គណនី និងហាងរបស់អ្នក",
        "steps": [
            "ចុះឈ្មោះ បន្ទាប់មកបើកអ៊ីមែលផ្ទៀងផ្ទាត់ ហើយបញ្ជាក់អាសយដ្ឋានរបស់អ្នក។",
            "ក្នុងការរៀបចំ បញ្ចូលឈ្មោះក្រុមហ៊ុន ឈ្មោះហាងដំបូង ប្រភេទអាជីវកម្ម និងរូបិយប័ណ្ណលំនាំដើម។",
            "ជ្រើសគម្រោង; គម្រោងឥតគិតថ្លៃមិនត្រូវការបង់ប្រាក់ទេ។",
            "នៅពេលរៀបចំរួច អ្នកចូលដល់ ផ្ទាំងសង្ខេប ដែលត្រៀមបន្ថែមទំនិញ។",
        ],
        "tip": "អ្នកអាចកែព័ត៌មានក្រុមហ៊ុន និងហាងនៅពេលក្រោយក្នុង ការកំណត់។",
    },
    "team.manage": {
        "title": "ប្តូរ ឬដកសមាជិកក្រុម",
        "steps": [
            "បើក ការចូលប្រើក្រុម ហើយរកសមាជិក។",
            "ជ្រើស កែ ដើម្បីប្តូរតួនាទី ឬហាងដែលពួកគេអាចធ្វើការបាន។",
            "ជ្រើស បិទដំណើរការ ដើម្បីផ្អាកការចូលប្រើដោយមិនលុបប្រវត្តិ។",
            "ជ្រើស ដក ដើម្បីដកសិទ្ធិទាំងស្រុង; គណនីម្ចាស់មិនអាចដកបានទេ។",
        ],
        "tip": "អ្នកអាចទទួលយកការអញ្ជើញជំនួសសមាជិកពីបញ្ជីអញ្ជើញ។",
    },
    "billing.schedule": {
        "title": "កំណត់ ឬបោះបង់ការប្តូរគម្រោង",
        "steps": [
            "បើក វិក្កយបត្រ និងគម្រោង ហើយជ្រើសគម្រោងដែលអ្នកចង់បាន។",
            "ជ្រើស កំណត់ការប្តូរ ដើម្បីប្តូរទៅវានៅចុងរយៈពេលបច្ចុប្បន្ន។",
            "ដើម្បីឈប់បន្ត ជ្រើស បោះបង់នៅចុងរយៈពេល។",
            "ជ្រើស ដកការប្តូរដែលបានកំណត់ ដើម្បីបោះបង់មុនពេលវាចាប់ផ្តើម។",
        ],
        "tip": "នៅពេលគម្រោងបញ្ចប់ ហាង ឬសមាជិកលើសត្រូវបានផ្អាក មិនលុបចោលទេ។",
    },
    "billing.receipts": {
        "title": "រកវិក្កយបត្របង់ប្រាក់",
        "steps": [
            "បើក វិក្កយបត្រ និងគម្រោង។",
            "រំកិលទៅ ប្រវត្តិការបង់ប្រាក់ ដើម្បីមើលការគិតប្រាក់ទាំងអស់ និងស្ថានភាព។",
            "បើកវិក្កយបត្រ ដើម្បីបោះពុម្ព ឬរក្សាទុក។",
        ],
    },
    "settings.bank-khqr": {
        "title": "ភ្ជាប់ ABA PayWay សម្រាប់ KHQR",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស ធនាគារ និង KHQR។",
            "បញ្ចូលតំណ ABA PayWay សម្រាប់ក្រុមហ៊ុន ឬសម្រាប់ហាងមួយ។",
            "ជ្រើស រក្សាទុកតំណ បន្ទាប់មក សាកល្បងការតភ្ជាប់ ដើម្បីបញ្ជាក់ថាវាដំណើរការ។",
            "នៅពេលផ្ទៀងផ្ទាត់រួច KHQR បង្ហាញជាវិធីទូទាត់នៅពេលគិតលុយ។",
        ],
        "tip": "តំណកម្រិតហាងនឹងជំនួសតំណក្រុមហ៊ុនសម្រាប់ហាងនោះ។",
    },
    "settings.pos-preferences": {
        "title": "កំណត់ចំណូលចិត្តចំណុចលក់",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស ចំណូលចិត្តចំណុចលក់។",
            "បើក ឬបិទ ការបញ្ចុះតម្លៃ ប្រាក់ជំនួយ សំឡេងលក់ និងការបោះពុម្ពស្វ័យប្រវត្តិ។",
            "កំណត់ថាតើត្រូវបើកវេនមុនពេលលក់ឬអត់។",
            "រក្សាទុក; ម៉ាស៊ីនគិតលុយអនុវត្តតាមការកំណត់ទាំងនេះ។",
        ],
        "tip": "ការបោះពុម្ពស្វ័យប្រវត្តិនឹងគ្មានប្រអប់សន្ទនារបស់កម្មវិធីរុករក លុះត្រាតែចំណុចលក់ត្រូវបានបើកជាមួយការបោះពុម្ព kiosk (មើល បោះពុម្ពវិក្កយបត្រដោយគ្មានប្រអប់សន្ទនា)។",
    },
    "settings.notifications": {
        "title": "ជ្រើសការជូនដំណឹងរបស់អ្នក",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស ការជូនដំណឹង។",
            "បើកការជូនដំណឹងដែលអ្នកចង់បាន: សេចក្តីសង្ខេបប្រចាំថ្ងៃ ស្តុកជិតអស់ ការបង្វិលប្រាក់ ការរំលឹកវេន និងសកម្មភាពក្រុម។",
            "រក្សាទុក; ការជូនដំណឹងបង្ហាញក្រោមកណ្តឹងនៅផ្នែកខាងលើ។",
        ],
    },
    "settings.feature-packs": {
        "title": "បើកកញ្ចប់លក្ខណៈពិសេស",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស កញ្ចប់លក្ខណៈពិសេស។",
            "បើកវាលដែលហាងរបស់អ្នកត្រូវការ ដូចជា បាកូដ ម៉ាក ឯកតា ម៉ូដ ជម្រើសបន្ថែម សេរៀល ឬឡូ។",
            "រក្សាទុក; វាលបន្ថែមបង្ហាញលើទំនិញ និងនៅម៉ាស៊ីនគិតលុយ។",
        ],
        "tip": "ប្រភេទអាជីវកម្មកំណត់លំនាំដើមសមស្រប; អ្នកអាចកែតាមហាង។",
    },
    "settings.inventory": {
        "title": "កំណត់លំនាំដើមស្តុក",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស លំនាំដើមស្តុក។",
            "កំណត់ចំណុចបញ្ជាទិញឡើងវិញលំនាំដើមដែលទំនិញថ្មីចាប់ផ្តើម។",
            "រក្សាទុក; អ្នកនៅតែអាចកែចំណុចបញ្ជាទិញឡើងវិញលើទំនិញនីមួយៗ។",
        ],
    },
    "settings.sessions": {
        "title": "គ្រប់គ្រងសេសសិនអ្នកគិតលុយ",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស សេសសិនអ្នកគិតលុយ។",
            "ជ្រើសរយៈពេលដែលការចូលប្រើមានសុពលភាព មុនពេលអ្នកគិតលុយត្រូវចូលម្តងទៀត។",
            "រក្សាទុក; ការផ្លាស់ប្តូរអនុវត្តចំពោះសេសសិនថ្មី។",
        ],
    },
    "settings.media": {
        "title": "ប្រើបណ្ណាល័យប្រព័ន្ធផ្សព្វផ្សាយ",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស បណ្ណាល័យប្រព័ន្ធផ្សព្វផ្សាយ។",
            "បញ្ចូលរូបភាពដែលអ្នកចង់ប្រើឡើងវិញលើទំនិញ និងវិក្កយបត្រ។",
            "នៅពេលកំណត់រូបភាពទំនិញ ឬម៉ូដ សូមជ្រើសពីបណ្ណាល័យ។",
            "លុបរូបភាពដែលអ្នកលែងត្រូវការ។",
        ],
    },
    "settings.security": {
        "title": "ប្តូរពាក្យសម្ងាត់របស់អ្នក",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស សុវត្ថិភាព។",
            "បញ្ចូលពាក្យសម្ងាត់បច្ចុប្បន្ន និងពាក្យសម្ងាត់ថ្មីពីរដង។",
            "រក្សាទុក។ អ្នកនៅតែចូលប្រើនៅឧបករណ៍នេះ។",
        ],
    },
    "restaurant": {"title": "ភោជនីយដ្ឋាន និងតុ", "blurb": "រៀបចំកម្រាលអាហារសម្រាប់សេវាក្នុងហាង។"},
    "restaurant.tables": {
        "title": "គ្រប់គ្រងតំបន់ និងតុ",
        "steps": [
            "បើក ការកំណត់ ហើយជ្រើស តុ។",
            "បន្ថែមតំបន់ ដូចជា ជាន់ផ្ទាល់ដី ឬ រានហាល។",
            "បន្ថែមតុជាមួយឈ្មោះ និងចំនួនកៅអី ហើយកំណត់តំបន់។",
            "ការបញ្ជាទិញទទួលទានក្នុងហាងអាចដាក់នៅតុទាំងនេះ។",
        ],
        "tip": "ផ្នែក តុ បង្ហាញសម្រាប់អាជីវកម្មភោជនីយដ្ឋាន និងកាហ្វេ។",
    },
    "getting-started.signin": {
        "title": "ចូលប្រើ Chmaba",
        "steps": [
            "បើក chmaba.com ហើយជ្រើស ចូលប្រើ ឬ បង្កើតគណនី ប្រសិនបើអ្នកថ្មី។",
            "បញ្ចូលអ៊ីមែល និងពាក្យសម្ងាត់ បន្ទាប់មកជ្រើស ចងចាំខ្ញុំ ប្រសិនបើជាឧបករណ៍ផ្ទាល់ខ្លួន។",
            "គណនីថ្មីត្រូវបញ្ជាក់អ៊ីមែលជាមុន; បើកតំណផ្ទៀងផ្ទាត់ដែលយើងផ្ញើ។",
            "បន្ទាប់ពីចូលប្រើ អ្នកចូលដល់ ផ្ទាំងសង្ខេប។",
        ],
    },
    "getting-started.reset-password": {
        "title": "កំណត់ពាក្យសម្ងាត់ឡើងវិញ",
        "steps": [
            "នៅទំព័រចូលប្រើ ជ្រើស ភ្លេចពាក្យសម្ងាត់។",
            "បញ្ចូលអ៊ីមែលរបស់គណនីអ្នក ហើយផ្ញើ។",
            "បើកតំណកំណត់ឡើងវិញក្នុងអ៊ីមែលដែលយើងផ្ញើ។",
            "ជ្រើសពាក្យសម្ងាត់ថ្មី បញ្ចូលពីរដង ហើយផ្ញើ។ បន្ទាប់មកចូលប្រើដោយវា។",
        ],
        "tip": "តំណកំណត់ឡើងវិញផុតកំណត់ ដូច្នេះស្នើសុំថ្មីប្រសិនបើតំណលែងដំណើរការ។",
    },
    "getting-started.google-signin": {
        "title": "ចូលប្រើដោយ Google",
        "steps": [
            "នៅទំព័រចូលប្រើ ជ្រើស បន្តជាមួយ Google។",
            "ជ្រើសគណនី Google របស់អ្នក ហើយអនុញ្ញាតការចូល។",
            "អ្នកប្រើ Google ថ្មីត្រូវរៀបចំបង្កើតហាង; អ្នកប្រើដែលមានស្រាប់ចូលដល់ ផ្ទាំងសង្ខេប។",
            "ប្រើវិធីដូចគ្នាលើកក្រោយ ដើម្បីឲ្យគណនីត្រូវបានភ្ជាប់ត្រឹមត្រូវ។",
        ],
        "tip": "ប្រសិនបើគណនីរបស់អ្នកបង្កើតដោយពាក្យសម្ងាត់ សូមចូលប្រើដោយវាជំនួស Google។",
    },
    "restaurant.floor": {
        "title": "ប្រើទិដ្ឋភាពកម្រាលហាង",
        "steps": [
            "បើក កម្រាលហាង ដើម្បីមើលបន្ទប់ទទួលទានដោយចែកតាមតំបន់។",
            "ក្រឡានីមួយៗបង្ហាញតុ និងស្ថានភាព: ទំនេរ កំពុងប្រើ បានកក់ ឬ កំពុងសម្អាត។",
            "ចុចលើតុដើម្បីប្តូរទៅស្ថានភាពបន្ទាប់តាមលំដាប់សេវា។",
            "ជ្រើស ទទួលទានក្នុងហាង ជាប្រភេទការបញ្ជាទិញ នៅពេលបើកការបញ្ជាទិញតាមតុ។",
        ],
        "tip": "ទិដ្ឋភាពកម្រាលហាងបង្ហាញនៅពេលកញ្ចប់ តុ បានបើក; រៀបចំតំបន់ និងតុក្នុង ការកំណត់ បន្ទាប់មក តុ។",
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




