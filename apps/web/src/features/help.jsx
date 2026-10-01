import { useMemo, useState } from "react";
import { ArrowRight, BookOpen, CircleHelp, LifeBuoy, Search, Sparkles } from "lucide-react";
import { Badge, Button } from "../components/ui";

// Static help catalog. Mirrors the markdown articles planned under docs/help/
// so the web app ships useful, reviewable guidance before the AI assistant
// lands. Each article is intentionally short: what it is for, then the steps.
const HELP_SECTIONS = [
  {
    id: "getting-started",
    title: "Getting started",
    blurb: "Set up your store and ring up your first sale.",
    articles: [
      {
        id: "getting-started.first-sale",
        title: "Ring up your first sale",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner", "manager", "cashier"],
        steps: [
          "Open Point of sale from the sidebar.",
          "Tap the products your customer is buying to add them to the cart.",
          "Choose a payment method — cash or KHQR.",
          "For cash, enter the amount received; the change is calculated for you.",
          "Tap Charge to complete the sale and print the receipt.",
        ],
        tip: "If your store requires an open shift, open one from Overview before your first sale.",
      },
      {
        id: "getting-started.add-products",
        title: "Add your products",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner", "manager", "inventory_manager"],
        steps: [
          "Go to Products and tap Add product.",
          "Enter a name, price and, if you have one, a barcode.",
          "Optionally set a cost price so margin reports work.",
          "Set stock on hand, or leave inventory tracking off for made-to-order items.",
          "Save. The product now appears on the Point of sale screen.",
        ],
        tip: "Group products into Categories so the POS grid stays quick to scan.",
      },
    ],
  },
  {
    id: "inventory",
    title: "Inventory",
    blurb: "Keep stock counts accurate.",
    articles: [
      {
        id: "inventory.restock",
        title: "Receive stock into a store",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner", "manager", "inventory_manager"],
        steps: [
          "Open Inventory and find the product.",
          "Choose Restock and enter the quantity received.",
          "Add a reason such as Delivery or Stock count.",
          "Save. On-hand stock updates immediately for every register in this store.",
        ],
      },
      {
        id: "inventory.low-stock",
        title: "Watch for low stock",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner", "manager", "inventory_manager"],
        steps: [
          "Set a reorder point on each product you track.",
          "Overview shows a Low stock items count when any product drops below it.",
          "Open Inventory and filter to low items to restock before you run out.",
        ],
      },
    ],
  },
  {
    id: "electronics",
    title: "Serials & warranty",
    blurb: "For electronics stores that track individual units.",
    articles: [
      {
        id: "electronics.serials",
        title: "Add serial numbers and IMEI",
        verticals: ["electronics"],
        roles: ["owner", "manager", "inventory_manager"],
        steps: [
          "Turn on Track serials when creating or editing a product.",
          "Open the product and use Add serials to enter each unit's serial number.",
          "Record the IMEI and cost price per unit for accurate resale and warranty.",
          "At checkout, pick the exact unit being sold so its warranty clock starts.",
        ],
        tip: "Serial numbers must be unique across your company, so a unit can never be sold twice.",
      },
      {
        id: "electronics.warranty",
        title: "Track warranty and used grades",
        verticals: ["electronics"],
        roles: ["owner", "manager", "inventory_manager"],
        steps: [
          "On a serial, set the supplier warranty and the customer warranty separately.",
          "The customer warranty only starts when the unit is actually sold.",
          "For used or refurbished units, record a condition grade and battery health.",
          "Grade history is kept, so a re-graded unit never loses its earlier assessment.",
        ],
      },
    ],
  },
  {
    id: "team-billing",
    title: "Team, billing & settings",
    blurb: "Manage people, your plan and preferences.",
    articles: [
      {
        id: "team.invite",
        title: "Invite a team member",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner"],
        steps: [
          "Open Team access and choose Invite.",
          "Enter their email and pick a role — manager, inventory manager or cashier.",
          "Choose which stores they can work in.",
          "They receive an email and join once they accept.",
        ],
      },
      {
        id: "billing.change-plan",
        title: "Change your plan",
        verticals: ["coffee", "restaurant", "mart", "electronics", "shop", "general"],
        roles: ["owner"],
        steps: [
          "Open Billing & plans.",
          "Compare the plans and their included features.",
          "Choose a plan and complete payment to unlock it.",
          "Downgrading pauses extra stores or members instead of deleting them.",
        ],
      },
    ],
  },
];

const WHAT_YOU_CAN_ASK = [
  "How do I refund an order?",
  "How do I open and close a shift?",
  "How do I receive stock from a supplier?",
  "How do I read my sales report?",
];

function articleMatches(article, query, vertical) {
  if (vertical && !article.verticals.includes(vertical)) return false;
  if (!query) return true;
  const haystack = `${article.title} ${(article.steps || []).join(" ")} ${article.tip || ""}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function HelpArticle({ article, onBack }) {
  return (
    <article className="rounded-2xl border border-[#e9e9ef] bg-white p-6 dark:border-[#2a2b30] dark:bg-[#1f2025]">
      <button onClick={onBack} className="text-[11px] font-bold text-[#6957f5] hover:underline">
        ← All guides
      </button>
      <h3 className="mt-3 text-lg font-extrabold tracking-[-.03em] text-[#202128] dark:text-[#e4e4e8]">{article.title}</h3>
      <ol className="mt-4 space-y-2.5">
        {article.steps.map((step, index) => (
          <li key={index} className="flex gap-3 text-xs leading-5 text-[#5d5e68] dark:text-[#b6b7c0]">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#ece9ff] text-[10px] font-extrabold text-[#6957f5]">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      {article.tip && (
        <p className="mt-4 rounded-xl border border-[#e6e5f3] bg-[#faf9ff] p-3 text-[11px] leading-5 text-[#696a76] dark:border-[#33343a] dark:bg-[#202126] dark:text-[#a9aab3]">
          <strong className="text-[#545560] dark:text-[#cfd0d8]">Tip: </strong>{article.tip}
        </p>
      )}
    </article>
  );
}

function HelpCenterView({ workspace, onNavigate }) {
  const vertical = workspace?.company?.vertical || "general";
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState(null);

  const sections = useMemo(() => {
    return HELP_SECTIONS.map((section) => ({
      ...section,
      articles: section.articles.filter((article) => articleMatches(article, query, vertical)),
    })).filter((section) => section.articles.length > 0);
  }, [query, vertical]);

  const openArticle = useMemo(() => {
    if (!openId) return null;
    for (const section of HELP_SECTIONS) {
      const found = section.articles.find((article) => article.id === openId);
      if (found) return found;
    }
    return null;
  }, [openId]);

  return (
    <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-[#92939d]">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><CircleHelp size={15} /></span>
            Help &amp; support
          </div>
          <h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em] text-[#202128] dark:text-[#e4e4e8]">How can we help?</h2>
          <p className="mt-1 text-sm text-[#898a95] dark:text-[#9a9aa4]">
            Step-by-step guides tailored to your {vertical} store.
          </p>
        </div>
        <Badge tone="violet">Guide library</Badge>
      </div>

      <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#e6e6ed] bg-white px-3 dark:border-[#363740] dark:bg-[#1f2025]">
        <Search size={15} className="text-[#a0a1aa]" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search guides, e.g. refund, restock, shift"
          className="h-11 w-full bg-transparent text-xs text-[#303139] outline-none placeholder:text-[#a0a1aa] dark:text-[#e4e4e8]"
        />
      </div>

      {openArticle ? (
        <div className="mt-5">
          <HelpArticle article={openArticle} onBack={() => setOpenId(null)} />
        </div>
      ) : (
        <div className="mt-5 space-y-6">
          {sections.length === 0 && (
            <div className="rounded-2xl border border-[#e9e9ef] bg-white p-10 text-center dark:border-[#2a2b30] dark:bg-[#1f2025]">
              <p className="text-sm font-bold text-[#565762] dark:text-[#c6c7d0]">No guides match that search.</p>
              <p className="mt-1 text-xs text-[#92939d]">Try a simpler word, or ask the assistant once it is enabled.</p>
            </div>
          )}
          {sections.map((section) => (
            <section key={section.id}>
              <div className="flex items-center gap-2">
                <BookOpen size={15} className="text-[#6957f5]" />
                <h3 className="text-sm font-extrabold text-[#303139] dark:text-[#e4e4e8]">{section.title}</h3>
                <span className="text-[11px] text-[#92939d]">{section.blurb}</span>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {section.articles.map((article) => (
                  <button
                    key={article.id}
                    onClick={() => setOpenId(article.id)}
                    className="group rounded-2xl border border-[#e9e9ef] bg-white p-4 text-left transition hover:border-[#bdb9ee] hover:shadow-soft dark:border-[#2a2b30] dark:bg-[#1f2025]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">{article.title}</span>
                      <ArrowRight size={14} className="shrink-0 text-[#b0b1ba] transition group-hover:text-[#6957f5]" />
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-[11px] leading-4 text-[#898a95] dark:text-[#9a9aa4]">
                      {article.steps[0]}
                    </p>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <div className="mt-8 rounded-2xl border border-[#e6e5f3] bg-[#faf9ff] p-5 dark:border-[#33343a] dark:bg-[#202126]">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-[#6957f5]" />
          <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">The assistant is coming soon</p>
        </div>
        <p className="mt-1.5 text-[11px] leading-5 text-[#777883] dark:text-[#a9aab3]">
          Soon you will be able to ask questions in plain language and get answers grounded in these guides.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {WHAT_YOU_CAN_ASK.map((prompt) => (
            <span key={prompt} className="rounded-full border border-[#e4e4eb] bg-white px-3 py-1 text-[10px] font-semibold text-[#777883] dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#a9aab3]">
              {prompt}
            </span>
          ))}
        </div>
        <Button
          variant="soft"
          size="sm"
          className="mt-4"
          onClick={() => onNavigate?.("settings")}
        >
          <LifeBuoy size={14} /> Contact support
        </Button>
      </div>
    </div>
  );
}

export { HelpCenterView, HELP_SECTIONS };
