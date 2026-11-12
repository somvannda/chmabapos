import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coffee,
  Compass,
  ListChecks,
  RotateCcw,
  Search,
  Sparkles,
  Store,
  UtensilsCrossed,
} from "lucide-react";
import { api } from "../api";
import { Button } from "../components/ui";
import { MarketingHeader, SiteFooter } from "./marketing";
import { GuideScreen } from "./guideScreens";

// The public User Guides library.
//
// This is the long-form, pre-signup counterpart to the in-app help center. It
// lives on the marketing site so a merchant can read the whole launch path
// before creating an account, and it is driven entirely by the API so a
// platform admin can publish a new guide without a front-end deploy.

const STAGE_ORDER = ["Start here", "Set up your menu", "Sell every day", "Run your shop", "Train & go live"];

const CATEGORY_ICONS = { Coffee, Store, UtensilsCrossed };

// Reading progress is local to the browser: the guides are public and there is
// no shopper account, so localStorage is the honest place for "where was I".
const PROGRESS_KEY = "chmaba.guide.progress.v1";

// Each guide's steps get a real screen recreation, in order. The key is the
// guide slug; the value is one screen per section. A missing entry falls back to
// the menu grid, so a newly published guide still renders.
const GUIDE_SCREENS = {
  "plan-your-coffee-shop": ["plan", "menu", "payments", "workspace"],
  "create-your-workspace": ["workspace", "workspace", "menu", "settings"],
  "build-your-coffee-menu": ["menu", "product", "inventory", "pos"],
  "sizes-milk-and-extras": ["variants", "modifiers", "variants", "pick"],
  "price-for-margin": ["product", "reports", "orders", "reports"],
  "payments-receipts-and-display": ["payments", "settings", "receipt", "display"],
  "ring-up-your-first-sale": ["shift", "pick", "charge", "receipt"],
  "holds-splits-and-refunds": ["hold", "charge", "orders", "orders"],
  "keep-stock-honest": ["inventory", "inventory", "inventory", "purchase"],
  "open-and-close-the-day": ["shift", "shift-close", "reports", "inventory"],
  "train-your-team": ["team", "team", "settings", "pos"],
  "coffee-shop-launch-checklist": ["checklist", "charge", "reports", "checklist"],
};

function readProgress() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PROGRESS_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeProgress(next) {
  try {
    window.localStorage.setItem(PROGRESS_KEY, JSON.stringify(next));
  } catch {
    /* private mode / storage full: progress is a convenience, never a gate */
  }
}

function progressFor(slug) {
  return readProgress()[slug] || null;
}

function saveGuideProgress(slug, value) {
  const map = readProgress();
  map[slug] = { ...value, updatedAt: Date.now() };
  writeProgress(map);
}

// Work out the next thing to do in a category from local progress. "Complete"
// wins over "started", and a guide with a saved step but no completed flag is
// resumed at that step rather than restarted.
function pathSnapshot(guides) {
  const entries = guides.map((guide) => ({ guide, saved: progressFor(guide.slug) }));
  const completed = entries.filter((entry) => entry.saved?.complete).length;
  const next = entries.find((entry) => !entry.saved?.complete) || null;
  const allComplete = entries.length > 0 && completed === entries.length;
  return {
    completed,
    total: entries.length,
    next: next?.guide || null,
    nextSaved: next?.saved || null,
    allComplete,
    target: allComplete ? entries[0]?.guide || null : next?.guide || null,
    targetSaved: allComplete ? entries[0]?.saved || null : next?.saved || null,
  };
}

const LEVEL_LABEL = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };

const LEVEL_TONE = {
  beginner: "bg-[#eef7e8] text-[#4f8b32] dark:bg-[#243021] dark:text-[#a8d98d]",
  intermediate: "bg-[#fff6df] text-[#ad7d1c] dark:bg-[#332a18] dark:text-[#e6c375]",
  advanced: "bg-[#fdeceb] text-[#c2564b] dark:bg-[#362322] dark:text-[#eda9a2]",
};

function guideHref(categorySlug, guideSlug) {
  return guideSlug ? `/guides/${categorySlug}/${guideSlug}` : categorySlug ? `/guides/${categorySlug}` : "/guides";
}

function readingLabel(minutes) {
  return `${minutes} min read`;
}

function groupByStage(guides) {
  const groups = [];
  const indexByTitle = new Map();
  for (const guide of guides) {
    const title = guide.group_title || "Start here";
    if (!indexByTitle.has(title)) {
      indexByTitle.set(title, groups.length);
      groups.push({ title, guides: [] });
    }
    groups[indexByTitle.get(title)].guides.push(guide);
  }
  return groups.sort((a, b) => {
    const aIndex = STAGE_ORDER.includes(a.title) ? STAGE_ORDER.indexOf(a.title) : STAGE_ORDER.length;
    const bIndex = STAGE_ORDER.includes(b.title) ? STAGE_ORDER.indexOf(b.title) : STAGE_ORDER.length;
    return aIndex - bIndex;
  });
}

function GuideLink({ href, onClick, className = "", children, ariaLabel }) {
  return (
    <a
      href={href}
      aria-label={ariaLabel}
      onClick={(event) => {
        if (!onClick) return;
        event.preventDefault();
        onClick();
      }}
      className={className}
    >
      {children}
    </a>
  );
}

function Meta({ guide, className = "" }) {
  return (
    <span className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-semibold text-[#92939d] ${className}`}>
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[.08em] ${LEVEL_TONE[guide.level] || LEVEL_TONE.beginner}`}>
        {LEVEL_LABEL[guide.level] || "Guide"}
      </span>
      <span className="inline-flex items-center gap-1">
        <Clock3 size={12} /> {readingLabel(guide.estimated_minutes)}
      </span>
      {guide.step_count > 0 && (
        <span className="inline-flex items-center gap-1">
          <ListChecks size={12} /> {guide.step_count} steps
        </span>
      )}
      {guide.group_title && <span className="hidden sm:inline">/</span>}{guide.group_title && <span className="hidden sm:inline">{guide.group_title}</span>}
    </span>
  );
}

function GuideCard({ guide, index, onOpenGuide, compact = false }) {
  const saved = progressFor(guide.slug);
  const total = guide.step_count || saved?.total || 0;
  const done = saved?.complete ? total : Math.min(saved?.done?.length || 0, total);
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <GuideLink
      href={guideHref(guide.category_slug, guide.slug)}
      onClick={() => onOpenGuide?.(guide.category_slug, guide.slug)}
      className={`group flex h-full flex-col rounded-2xl border border-[#e9e9ef] bg-white p-5 transition hover:-translate-y-0.5 hover:border-[#d7d2f5] hover:shadow-soft dark:border-[#2a2b30] dark:bg-[#1a1b20] dark:hover:border-[#3d3a55] ${compact ? "" : "sm:p-6"}`}
      ariaLabel={guide.title}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f0efff] text-xs font-extrabold text-[#6957f5] dark:bg-[#2b2850] dark:text-[#b9afff]">
          {String(index + 1).padStart(2, "0")}
        </span>
        <ArrowRight size={17} className="mt-1.5 shrink-0 text-[#c2c2c9] transition group-hover:translate-x-0.5 group-hover:text-[#6957f5]" />
      </div>
      <h3 className="mt-4 text-base font-extrabold leading-6 tracking-[-.02em] text-[#202128] dark:text-[#e4e4e8]">{guide.title}</h3>
      <p className="mt-2 line-clamp-3 flex-1 text-[13px] leading-6 text-[#747580] dark:text-[#9c9ca6]">{guide.summary}</p>
      <Meta guide={guide} className="mt-4" />
      {saved && total > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] font-bold text-[#92939d]">
            <span>{saved.complete ? "Completed" : `Continue at step ${Math.min((saved.step || 0) + 1, total)}`}</span>
            <span>{percent}%</span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-[#f0f0f5] dark:bg-[#2a2b32]">
            <div className={`h-full rounded-full ${saved.complete ? "bg-[#78bd4f]" : "bg-[#6957f5]"}`} style={{ width: `${percent}%` }} />
          </div>
        </div>
      )}
    </GuideLink>
  );
}

function CategoryChip({ category, onOpenGuide, progress }) {
  const Icon = CATEGORY_ICONS[category.icon] || Coffee;
  const percent = progress && progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
  const started = Boolean(progress && (progress.completed > 0 || progress.targetSaved));
  const label = progress?.allComplete
    ? `Path complete · ${progress.total} of ${progress.total}`
    : started
      ? `${progress.completed} of ${progress.total} complete · Continue`
      : `${category.guide_count} ${category.guide_count === 1 ? "guide" : "guides"}`;
  return (
    <GuideLink
      href={guideHref(category.slug)}
      onClick={() => onOpenGuide?.(category.slug)}
      className="group flex items-center gap-4 rounded-2xl border border-[#e9e9ef] bg-white p-5 transition hover:-translate-y-0.5 hover:shadow-soft dark:border-[#2a2b30] dark:bg-[#1a1b20]"
      ariaLabel={category.name}
    >
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-white" style={{ backgroundColor: category.accent || "#b46b3e" }}>
        <Icon size={21} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">{category.name}</span>
        <span className="mt-1 block text-xs text-[#898a95] dark:text-[#9c9ca6]">{label}</span>
        {started && (
          <span className="mt-2 block h-1 overflow-hidden rounded-full bg-[#f0f0f5] dark:bg-[#2a2b32]">
            <span className={`block h-full rounded-full ${progress.allComplete ? "bg-[#78bd4f]" : "bg-[#6957f5]"}`} style={{ width: `${percent}%` }} />
          </span>
        )}
      </span>
      <ChevronRight size={17} className="shrink-0 text-[#c2c2c9] transition group-hover:translate-x-0.5 group-hover:text-[#6957f5]" />
    </GuideLink>
  );
}

function GuidesLoading({ label = "Loading the guides..." }) {
  return (
    <div className="mx-auto flex min-h-[320px] max-w-[1240px] items-center justify-center px-5">
      <div className="flex items-center gap-3 text-sm font-semibold text-[#898a95]">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#d8d5f7] border-t-[#6957f5]" />
        {label}
      </div>
    </div>
  );
}

function GuidesError({ message, onRetry, onBack }) {
  return (
    <div className="mx-auto max-w-[720px] px-5 py-24 text-center">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#fff1e9] text-[#c87448]">
        <Compass size={24} />
      </span>
      <h1 className="mt-6 text-2xl font-extrabold tracking-[-.04em] text-[#202128] dark:text-[#e4e4e8]">This guide could not open</h1>
      <p className="mt-2 text-sm leading-6 text-[#747580] dark:text-[#9c9ca6]">{message || "It may have moved, or it is not published yet."}</p>
      <div className="mt-7 flex justify-center gap-3">
        {onRetry && <Button onClick={onRetry}>Try again</Button>}
        <Button variant="outline" onClick={onBack}>Back to guides</Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Index
// ---------------------------------------------------------------------------

function GuidesIndex({ onOpenGuide, onSignUp, onSignIn, onSection, onOpenLegal }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError("");
    api.publicGuides()
      .then((payload) => setData(payload))
      .catch((requestError) => setError(requestError.message || "Could not load the guides"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    document.title = "User guides | Chmaba";
    return () => { document.title = "Chmaba"; };
  }, []);

  const guides = data?.guides || [];
  const query = search.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!query) return guides;
    return guides.filter((guide) =>
      [guide.title, guide.summary, guide.group_title, guide.category_name]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query)),
    );
  }, [guides, query]);

  const stages = useMemo(() => groupByStage(filtered), [filtered]);
  const categories = data?.categories || [];
  const categoryProgress = useMemo(
    () => Object.fromEntries(categories.map((category) => [
      category.slug,
      pathSnapshot(guides.filter((guide) => guide.category_slug === category.slug)),
    ])),
    [categories, guides],
  );

  return (
    <div className="min-h-screen overflow-x-clip bg-[#fafafd] text-[#17181c] dark:bg-[#111114] dark:text-[#e4e4e8]">
      <MarketingHeader onSignIn={onSignIn} onSignUp={onSignUp} onSection={onSection} />
      <main>
        <section className="relative overflow-hidden border-b border-[#eaeaef] dark:border-[#2a2b30]">
          <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-[#c4f27c]/30 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-40 left-1/4 h-80 w-80 rounded-full bg-[#ada3ff]/20 blur-3xl" />
          <div className="relative mx-auto max-w-[1240px] px-5 py-16 lg:px-8 lg:py-24">
            <div className="max-w-[760px]">
              <div className="inline-flex items-center gap-2 rounded-full border border-[#dfdff0] bg-white px-3 py-1.5 text-[11px] font-bold uppercase tracking-[.12em] text-[#6658df] shadow-sm dark:border-[#33344a] dark:bg-[#1a1b20] dark:text-[#b9afff]">
                <BookOpen size={13} /> User guides
              </div>
              <h1 className="mt-6 text-[42px] font-extrabold leading-[1.04] tracking-[-.06em] text-[#17181c] dark:text-[#f1f1f4] sm:text-[58px]">
                Set up your shop,<br /><span className="text-[#6957f5]">one calm step at a time.</span>
              </h1>
              <p className="mt-6 max-w-[600px] text-base leading-7 text-[#747580] dark:text-[#9c9ca6]">
                Practical, start-to-finish guides for the business you actually run. Begin with the coffee counter:
                plan the menu, price the drinks, take the first payment and close the till with confidence.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                <label className="relative flex-1 sm:max-w-[420px]">
                  <span className="sr-only">Search guides</span>
                  <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#a1a2ab]" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search a task, such as refunds or KHQR"
                    className="h-12 w-full rounded-xl border border-[#e1e1ea] bg-white pl-11 pr-4 text-sm text-[#303139] outline-none transition placeholder:text-[#aaabb4] focus:border-[#887bf3] focus:ring-4 focus:ring-[#6957f5]/10 dark:border-[#33343d] dark:bg-[#1a1b20] dark:text-[#e4e4e8]"
                  />
                </label>
                <Button size="lg" onClick={onSignUp}>Open your workspace <ArrowRight size={16} /></Button>
              </div>
              {data && (
                <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-semibold text-[#898a94] dark:text-[#9c9ca6]">
                  <span className="inline-flex items-center gap-1.5"><BookOpen size={13} className="text-[#6957f5]" /> {guides.length} guides</span>
                  <span className="inline-flex items-center gap-1.5"><ListChecks size={13} className="text-[#6957f5]" /> {stages.length} stages</span>
                  <span className="inline-flex items-center gap-1.5"><Check size={13} className="text-[#6957f5]" /> Written for real counters</span>
                </div>
              )}
            </div>
          </div>
        </section>

        {loading ? <GuidesLoading /> : error ? (
          <GuidesError message={error} onRetry={load} onBack={() => { window.location.href = "/"; }} />
        ) : (
          <>
            {!query && data?.featured?.length > 0 && (
              <section className="mx-auto max-w-[1240px] px-5 py-14 lg:px-8 lg:py-16">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[.16em] text-[#6957f5]">Start here</p>
                    <h2 className="mt-2 text-2xl font-extrabold tracking-[-.04em] text-[#191a1f] dark:text-[#e4e4e8] sm:text-3xl">The shortest path to a first sale</h2>
                  </div>
                  <p className="max-w-[340px] text-xs leading-5 text-[#898a95]">Three guides cover the decisions that make the rest of setup quick.</p>
                </div>
                <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {data.featured.map((guide, index) => <GuideCard key={guide.id} guide={guide} index={index} onOpenGuide={onOpenGuide} />)}
                </div>
              </section>
            )}

            {!query && categories.length > 0 && (
              <section className="border-y border-[#eaeaef] bg-white px-5 py-12 dark:border-[#2a2b30] dark:bg-[#17181c] lg:px-8">
                <div className="mx-auto max-w-[1240px]">
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[.16em] text-[#6957f5]">Browse by business</p>
                      <h2 className="mt-2 text-2xl font-extrabold tracking-[-.04em] text-[#191a1f] dark:text-[#e4e4e8]">A library that grows with the businesses we support</h2>
                    </div>
                    <span className="rounded-full border border-[#e4e4eb] px-3 py-1 text-[10px] font-bold uppercase tracking-[.1em] text-[#92939d] dark:border-[#2a2b30]">New categories soon</span>
                  </div>
                  <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {categories.map((category) => <CategoryChip key={category.id} category={category} progress={categoryProgress[category.slug]} onOpenGuide={onOpenGuide} />)}
                    <div className="flex items-center gap-4 rounded-2xl border border-dashed border-[#dcdce6] bg-[#fafafd] p-5 dark:border-[#33343d] dark:bg-[#1a1b20]">
                      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#f0f0f5] text-[#a1a2ab] dark:bg-[#26272e]"><Sparkles size={20} /></span>
                      <span className="min-w-0">
                        <span className="block text-sm font-extrabold text-[#4f5059] dark:text-[#c8c9d0]">Restaurant, mart, retail...</span>
                        <span className="mt-1 block text-xs text-[#92939d]">More setup paths are on the way.</span>
                      </span>
                    </div>
                  </div>
                </div>
              </section>
            )}

            <section className="mx-auto max-w-[1240px] px-5 py-14 lg:px-8 lg:py-20">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[.16em] text-[#6957f5]">{query ? "Search results" : "The full library"}</p>
                  <h2 className="mt-2 text-2xl font-extrabold tracking-[-.04em] text-[#191a1f] dark:text-[#e4e4e8] sm:text-3xl">
                    {query ? `${filtered.length} ${filtered.length === 1 ? "guide" : "guides"} for “${search.trim()}”` : "Every guide, in the order to read them"}
                  </h2>
                </div>
                {query && <button type="button" onClick={() => setSearch("")} className="text-xs font-bold text-[#6957f5] hover:underline">Clear search</button>}
              </div>

              {filtered.length === 0 ? (
                <div className="mt-10 rounded-2xl border border-[#e9e9ef] bg-white p-10 text-center dark:border-[#2a2b30] dark:bg-[#1a1b20]">
                  <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">No guide matches that search yet.</p>
                  <p className="mt-2 text-xs text-[#898a95]">Try a shorter word such as “refund”, “menu” or “KHQR”.</p>
                </div>
              ) : (
                <div className="mt-10 space-y-12">
                  {stages.map((stage) => (
                    <div key={stage.title}>
                      <div className="flex items-center gap-3">
                        <span className="flex h-2 w-2 rounded-full bg-[#6957f5]" />
                        <h3 className="text-sm font-extrabold uppercase tracking-[.12em] text-[#4f5059] dark:text-[#c8c9d0]">{stage.title}</h3>
                        <span className="h-px flex-1 bg-[#eaeaef] dark:bg-[#2a2b30]" />
                        <span className="text-[10px] font-bold text-[#a1a2ab]">{stage.guides.length}</span>
                      </div>
                      <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                        {stage.guides.map((guide) => (
                          <GuideCard key={guide.id} guide={guide} index={guides.findIndex((row) => row.id === guide.id)} onOpenGuide={onOpenGuide} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="px-5 pb-20 lg:px-8">
              <div className="mx-auto flex max-w-[1240px] flex-col items-start justify-between gap-5 rounded-[24px] bg-[#17181c] px-7 py-9 text-white sm:flex-row sm:items-center sm:px-10">
                <div className="max-w-[680px]">
                  <p className="text-xs font-bold uppercase tracking-[.14em] text-[#c4f27c]">Ready to try it</p>
                  <h2 className="mt-3 text-2xl font-extrabold tracking-[-.04em]">Your first sale is a few setup steps away.</h2>
                  <p className="mt-2 text-sm leading-6 text-[#a9aab2]">Create a free workspace, follow the coffee shop path and ring up a test order. No payment details needed.</p>
                </div>
                <Button onClick={onSignUp}>Open your workspace <ArrowRight size={16} /></Button>
              </div>
            </section>
          </>
        )}
      </main>
      <SiteFooter onOpenLegal={onOpenLegal} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Category
// ---------------------------------------------------------------------------

function GuidesCategory({ categorySlug, onOpenGuide, onSignUp, onSignIn, onSection, onOpenLegal }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError("");
    api.publicGuideCategory(categorySlug)
      .then((payload) => setData(payload))
      .catch((requestError) => setError(requestError.message || "Could not load this category"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    window.scrollTo(0, 0);
  }, [categorySlug]);

  useEffect(() => {
    if (data?.category?.name) document.title = `${data.category.name} guides | Chmaba`;
  }, [data]);

  const category = data?.category;
  const Icon = CATEGORY_ICONS[category?.icon] || Coffee;
  const total = data?.total || 0;
  const flat = data?.groups.flatMap((group) => group.guides) || [];
  const path = pathSnapshot(flat);
  const resumeGuide = path.target;
  const resumeSaved = path.targetSaved;
  const resumeStep = resumeGuide ? Math.min((resumeSaved?.step || 0) + 1, resumeGuide.step_count || 1) : 1;
  const resumeStarted = Boolean(resumeSaved && ((resumeSaved.done?.length || 0) > 0 || (resumeSaved.step || 0) > 0));
  const percent = path.total > 0 ? Math.round((path.completed / path.total) * 100) : 0;

  return (
    <div className="min-h-screen overflow-x-clip bg-[#fafafd] text-[#17181c] dark:bg-[#111114] dark:text-[#e4e4e8]">
      <MarketingHeader onSignIn={onSignIn} onSignUp={onSignUp} onSection={onSection} />
      <main>
        <section className="border-b border-[#eaeaef] dark:border-[#2a2b30]">
          <div className="mx-auto max-w-[1240px] px-5 py-10 lg:px-8 lg:py-14">
            <nav className="flex items-center gap-2 text-xs font-semibold text-[#92939d]">
              <GuideLink href="/guides" onClick={() => onOpenGuide?.()} className="hover:text-[#6957f5]">User guides</GuideLink>
              <ChevronRight size={12} />
              <span className="text-[#4f5059] dark:text-[#c8c9d0]">{category?.name || "Category"}</span>
            </nav>
            <div className="mt-7 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-[720px]">
                <span className="inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-[11px] font-bold uppercase tracking-[.12em] text-white" style={{ backgroundColor: category?.accent || "#b46b3e" }}>
                  <Icon size={13} /> {category?.name || "Category"}
                </span>
                <h1 className="mt-4 text-4xl font-extrabold leading-[1.06] tracking-[-.055em] sm:text-5xl">
                  {category?.name === "Coffee shop" ? "Run a calmer coffee counter." : `${category?.name || "Setup"} guides.`}
                </h1>
                <p className="mt-4 max-w-[640px] text-sm leading-7 text-[#747580] dark:text-[#9c9ca6]">
                  {category?.description || "Step-by-step setup guides for this business type."}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3 rounded-2xl border border-[#e9e9ef] bg-white px-4 py-3 dark:border-[#2a2b30] dark:bg-[#1a1b20]">
                <span className="text-3xl font-extrabold tracking-[-.05em] text-[#202128] dark:text-[#e4e4e8]">{total}</span>
                <span className="text-[10px] font-bold uppercase leading-4 tracking-[.1em] text-[#92939d]">guides<br />in this path</span>
              </div>
            </div>
          </div>
        </section>

        {loading ? <GuidesLoading /> : error ? (
          <GuidesError message={error} onRetry={load} onBack={() => onOpenGuide?.()} />
        ) : (
          <section className="mx-auto max-w-[1240px] px-5 py-12 lg:px-8 lg:py-16">
            {resumeGuide && (
              <div className="relative mb-10 overflow-hidden rounded-[24px] bg-[#17181c] px-6 py-6 text-white sm:px-8">
                <div className="pointer-events-none absolute -right-10 -top-16 h-44 w-44 rounded-full bg-[#c4f27c]/15 blur-3xl" />
                <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="max-w-[720px]">
                    <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#c4f27c]">
                      {path.allComplete ? "Path complete" : resumeStarted ? "Continue your path" : "Start your path"}
                    </p>
                    <h2 className="mt-2 text-xl font-extrabold tracking-[-.03em] sm:text-2xl">
                      {path.allComplete ? "Review the path from the start" : `Guide ${flat.findIndex((guide) => guide.slug === resumeGuide.slug) + 1} of ${path.total} · ${resumeGuide.title}`}
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-[#a9aab2]">
                      {path.allComplete
                        ? `You have finished all ${path.total} guides. Review from the beginning whenever you need a refresher.`
                        : resumeStarted
                          ? `Pick up at step ${resumeStep} of ${resumeGuide.step_count || 1}. Progress is saved in this browser.`
                          : `${path.completed} of ${path.total} complete. This is the next guide in the path.`}
                    </p>
                    <div className="mt-4 flex items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/15">
                        <div className="h-full rounded-full bg-[#c4f27c] transition-all" style={{ width: `${percent}%` }} />
                      </div>
                      <span className="text-[10px] font-bold text-[#c4f27c]">{percent}%</span>
                    </div>
                  </div>
                  <Button className="shrink-0" onClick={() => onOpenGuide?.(resumeGuide.category_slug, resumeGuide.slug)}>
                    {path.allComplete ? "Review from the beginning" : resumeStarted ? "Resume guide" : "Start this guide"} <ArrowRight size={16} />
                  </Button>
                </div>
              </div>
            )}
            <div className="space-y-14">
              {data?.groups.map((group, groupIndex) => (
                <div key={group.title}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#f0efff] text-[11px] font-extrabold text-[#6957f5] dark:bg-[#2b2850] dark:text-[#b9afff]">{groupIndex + 1}</span>
                    <h2 className="text-lg font-extrabold tracking-[-.03em] text-[#202128] dark:text-[#e4e4e8]">{group.title}</h2>
                    <span className="h-px flex-1 bg-[#eaeaef] dark:bg-[#2a2b30]" />
                  </div>
                  <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                    {group.guides.map((guide) => {
                      const guideIndex = flat.findIndex((row) => row.id === guide.id);
                      return <GuideCard key={guide.id} guide={guide} index={guideIndex} onOpenGuide={onOpenGuide} />;
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-16 flex flex-col items-start justify-between gap-5 rounded-[24px] bg-[#17181c] px-7 py-9 text-white sm:flex-row sm:items-center sm:px-10">
              <div className="max-w-[680px]">
                <p className="text-xs font-bold uppercase tracking-[.14em] text-[#c4f27c]">Put the guides to work</p>
                <h2 className="mt-3 text-2xl font-extrabold tracking-[-.04em]">Build the workspace as you read.</h2>
                <p className="mt-2 text-sm leading-6 text-[#a9aab2]">Create the free workspace, then follow the path from planning to the first sale.</p>
              </div>
              <Button onClick={onSignUp}>Open your workspace <ArrowRight size={16} /></Button>
            </div>
          </section>
        )}
      </main>
      <SiteFooter onOpenLegal={onOpenLegal} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail
// ---------------------------------------------------------------------------

function progressState(guide) {
  const saved = progressFor(guide.slug);
  if (saved?.complete) return "complete";
  if (saved && ((saved.done?.length || 0) > 0 || (saved.step || 0) > 0)) return "started";
  return "todo";
}

function GuidePathTimeline({ guide, onOpenGuide }) {
  const series = guide.series || [];
  if (series.length < 2) return null;
  const currentIndex = Math.max(0, series.findIndex((row) => row.slug === guide.slug));
  const completed = series.filter((row) => progressState(row) === "complete").length;
  const nextGuide = guide.next || series[currentIndex + 1] || null;

  return (
    <section className="border-b border-[#eaeaef] bg-white px-5 py-5 dark:border-[#2a2b30] dark:bg-[#17181c] lg:px-8">
      <div className="mx-auto max-w-[1240px]">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#6957f5] dark:text-[#b9afff]">Your coffee shop path</p>
            <h2 className="mt-1 text-sm font-extrabold tracking-[-.02em] text-[#202128] dark:text-[#e4e4e8]">
              Guide {currentIndex + 1} of {series.length}
              <span className="ml-2 font-semibold text-[#92939d]">
                {completed === series.length ? "· path complete" : `· ${completed} completed`}
              </span>
            </h2>
          </div>
          {nextGuide ? (
            <p className="text-xs font-semibold text-[#898a95]">
              Up next: <span className="font-extrabold text-[#4f5059] dark:text-[#c8c9d0]">{nextGuide.title}</span>
            </p>
          ) : (
            <p className="text-xs font-semibold text-[#4f8b32]">You are on the last guide in this path.</p>
          )}
        </div>

        <div className="app-scrollbar relative mt-5 overflow-x-auto pb-2">
          <div className="relative min-w-[720px]">
            <span className="absolute left-4 right-4 top-[18px] h-px bg-[#e7e7ee] dark:bg-[#33343d]" aria-hidden="true" />
            <ol className="relative flex items-start justify-between gap-1">
              {series.map((item, index) => {
                const state = progressState(item);
                const isCurrent = item.slug === guide.slug;
                const isNext = !isCurrent && nextGuide?.slug === item.slug;
                return (
                  <li key={item.id} className="flex min-w-0 flex-1 flex-col items-center">
                    <button
                      type="button"
                      onClick={() => onOpenGuide?.(item.category_slug, item.slug)}
                      title={`${index + 1}. ${item.title}`}
                      aria-label={`Guide ${index + 1}: ${item.title}${isCurrent ? " (current)" : state === "complete" ? " (completed)" : ""}`}
                      className="group flex w-full flex-col items-center focus:outline-none"
                    >
                      <span
                        className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full text-[11px] font-extrabold transition group-hover:scale-110 ${
                          state === "complete"
                            ? "bg-[#17181c] text-[#c4f27c] dark:bg-[#c4f27c] dark:text-[#17181c]"
                            : isCurrent
                              ? "bg-[#6957f5] text-white ring-4 ring-[#e9e6ff] dark:ring-[#2c2948]"
                              : state === "started"
                                ? "border-2 border-[#6957f5] bg-white text-[#6957f5] dark:bg-[#1a1b20]"
                                : "border border-[#e1e1e9] bg-white text-[#a1a2ab] dark:border-[#3a3b44] dark:bg-[#1a1b20]"
                        }`}
                      >
                        {state === "complete" ? <Check size={14} className="guide-check-pop" /> : index + 1}
                        {isCurrent && <span className="absolute -bottom-1 h-1.5 w-1.5 rounded-full bg-[#6957f5] ring-2 ring-white dark:ring-[#17181c]" />}
                      </span>
                      <span className={`mt-2 flex min-h-[26px] items-start justify-center text-center text-[9px] font-bold leading-3 ${isCurrent ? "text-[#5b4be3] dark:text-[#b9afff]" : state === "complete" ? "text-[#898a95]" : "text-[#a1a2ab]"}`}>
                        {isCurrent ? "You are here" : state === "complete" ? "Done" : isNext ? "Up next" : " "}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}

function GuidePlayer({ guide, onOpenGuide, onSignUp, onProgressChange }) {
  const steps = guide.sections || [];
  const saved = progressFor(guide.slug);
  const initialIndex = (() => {
    const hashStep = Number((window.location.hash.match(/^#step-(\d+)/) || [])[1]);
    if (hashStep >= 1 && hashStep <= steps.length) return hashStep - 1;
    const stored = Number(saved?.step);
    if (stored >= 0 && stored < steps.length) return stored;
    return 0;
  })();

  const [stepIndex, setStepIndex] = useState(initialIndex);
  const [done, setDone] = useState(() => new Set(Array.isArray(saved?.done) ? saved.done : []));
  const [checks, setChecks] = useState(saved?.checks && typeof saved.checks === "object" ? saved.checks : {});
  const [finished, setFinished] = useState(Boolean(saved?.complete));
  const [showDetail, setShowDetail] = useState(false);

  const step = steps[stepIndex] || steps[0] || { heading: "", body: [], steps: [] };
  const body = step.body || [];
  const checklist = step.steps || [];
  const screen = GUIDE_SCREENS[guide.slug]?.[stepIndex] || "menu";
  const checkedInStep = checklist.filter((_, itemIndex) => checks[`${stepIndex}:${itemIndex}`]).length;
  const allChecked = checklist.length > 0 && checkedInStep === checklist.length;
  const completedCount = finished ? steps.length : done.size;
  const percent = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;
  const isLast = stepIndex === steps.length - 1;

  const persist = (nextStep, nextDone, nextChecks, complete) => {
    saveGuideProgress(guide.slug, {
      step: nextStep,
      done: [...nextDone],
      checks: nextChecks,
      total: steps.length,
      complete,
    });
    onProgressChange?.();
  };

  const scrollToPlayer = () => {
    const player = document.getElementById("guide-player");
    if (!player) return;
    const top = player.getBoundingClientRect().top + window.scrollY - 96;
    window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  };

  const goTo = (next, { mark = true } = {}) => {
    if (next < 0 || next >= steps.length) return;
    const nextDone = new Set(done);
    if (mark) nextDone.add(stepIndex);
    setDone(nextDone);
    setStepIndex(next);
    setFinished(false);
    setShowDetail(false);
    persist(next, nextDone, checks, false);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#step-${next + 1}`);
    window.requestAnimationFrame(scrollToPlayer);
  };

  const finish = () => {
    const nextDone = new Set(done);
    nextDone.add(stepIndex);
    setDone(nextDone);
    setFinished(true);
    persist(stepIndex, nextDone, checks, true);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#complete`);
    window.requestAnimationFrame(scrollToPlayer);
  };

  const restart = () => {
    setFinished(false);
    setDone(new Set());
    setChecks({});
    setStepIndex(0);
    setShowDetail(false);
    saveGuideProgress(guide.slug, { step: 0, done: [], checks: {}, total: steps.length, complete: false });
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#step-1`);
    window.requestAnimationFrame(scrollToPlayer);
  };

  const toggleCheck = (itemIndex) => {
    const key = `${stepIndex}:${itemIndex}`;
    const nextChecks = { ...checks, [key]: !checks[key] };
    setChecks(nextChecks);
    persist(stepIndex, done, nextChecks, finished);
  };

  useEffect(() => {
    const onKey = (event) => {
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.key === "ArrowRight" && !isLast) goTo(stepIndex + 1);
      if (event.key === "ArrowLeft" && stepIndex > 0) goTo(stepIndex - 1, { mark: false });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stepIndex, isLast, done, checks, finished]);

  const nextGuide = guide.next;

  return (
    <div className="mx-auto grid max-w-[1240px] gap-8 px-5 pb-16 pt-8 lg:grid-cols-[250px_minmax(0,1fr)] lg:px-8 lg:pb-24">
      {/* Desktop step rail: the reader can always see where they are and jump. */}
      <aside className="hidden lg:block">
        <div className="sticky top-24 space-y-3">
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-4 dark:border-[#2a2b30] dark:bg-[#1a1b20]">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#92939d]">Your progress</p>
              <span className="text-xs font-extrabold text-[#202128] dark:text-[#e4e4e8]">{percent}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#f0f0f5] dark:bg-[#2a2b32]">
              <div className={`guide-bar h-full rounded-full ${finished ? "bg-[#78bd4f]" : "bg-[#6957f5]"}`} style={{ width: `${percent}%` }} />
            </div>
            <div className="mt-4 space-y-1">
              {steps.map((item, index) => {
                const isCurrent = !finished && index === stepIndex;
                const isDone = finished || done.has(index);
                return (
                  <button
                    key={`${item.heading}-${index}`}
                    type="button"
                    onClick={() => goTo(index, { mark: index > stepIndex })}
                    className={`flex w-full items-start gap-2.5 rounded-xl px-2 py-2 text-left transition ${isCurrent ? "bg-[#f0efff] dark:bg-[#262343]" : "hover:bg-[#f7f7fa] dark:hover:bg-[#23242a]"}`}
                  >
                    <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-extrabold ${isDone ? "bg-[#eef7e8] text-[#4f8b32]" : isCurrent ? "bg-[#6957f5] text-white" : "border border-[#e2e2e9] text-[#92939d] dark:border-[#3a3b44]"}`}>
                      {isDone ? <Check size={11} className="guide-check-pop" /> : index + 1}
                    </span>
                    <span className={`text-[11px] font-semibold leading-4 ${isCurrent ? "text-[#4a3bd8] dark:text-[#b9afff]" : isDone ? "text-[#898a95]" : "text-[#5d5e68] dark:text-[#b7b8c0]"}`}>{item.heading}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-4 dark:border-[#2a2b30] dark:bg-[#1a1b20]">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#747580] dark:text-[#9c9ca6]"><Clock3 size={13} /> {readingLabel(guide.estimated_minutes)}</p>
            <p className="mt-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-[#747580] dark:text-[#9c9ca6]"><ListChecks size={13} /> {steps.length} short steps</p>
            <p className="mt-1.5 text-[10px] leading-4 text-[#a1a2ab]">Progress saves in this browser, so you can come back.</p>
          </div>
        </div>
      </aside>

      <section id="guide-player" className="min-w-0 scroll-mt-24">
        <div className="lg:hidden">
          <div className="flex items-center justify-between text-[11px] font-bold text-[#747580] dark:text-[#9c9ca6]">
            <span>Step {finished ? steps.length : stepIndex + 1} of {steps.length}</span>
            <span>{percent}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#f0f0f5] dark:bg-[#2a2b32]">
            <div className={`h-full rounded-full ${finished ? "bg-[#78bd4f]" : "bg-[#6957f5]"}`} style={{ width: `${percent}%` }} />
          </div>
          <div className="app-scrollbar mt-3 flex gap-1.5 overflow-x-auto pb-1">
            {steps.map((item, index) => {
              const isCurrent = !finished && index === stepIndex;
              const isDone = finished || done.has(index);
              return (
                <button key={`${item.heading}-${index}`} type="button" onClick={() => goTo(index, { mark: index > stepIndex })} className={`flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${isCurrent ? "border-[#6957f5] bg-[#f0efff] text-[#5b4be3] dark:bg-[#262343]" : isDone ? "border-[#dcebd0] bg-[#f6fbf2] text-[#4f8b32] dark:border-[#2f4027] dark:bg-[#1b2418]" : "border-[#e4e4eb] text-[#92939d] dark:border-[#33343d]"}`}>
                  {isDone ? <Check size={10} /> : index + 1} {item.heading.length > 24 ? `${item.heading.slice(0, 24)}…` : item.heading}
                </button>
              );
            })}
          </div>
        </div>

        {finished ? (
          <div className="mt-6 overflow-hidden rounded-3xl border border-[#dcebd0] bg-white shadow-[0_24px_60px_rgba(30,30,50,.08)] dark:border-[#2f4027] dark:bg-[#1a1b20]">
            <div className="relative overflow-hidden bg-[#17181c] px-6 py-10 text-center text-white sm:px-10">
              <div className="pointer-events-none absolute -right-10 -top-12 h-44 w-44 rounded-full bg-[#c4f27c]/20 blur-3xl" />
              <span className="guide-check-pop mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#c4f27c] text-[#17181c]"><CheckCircle2 size={30} /></span>
              <p className="mt-5 text-[10px] font-bold uppercase tracking-[.16em] text-[#c4f27c]">
                {(guide.series || []).length > 1
                  ? `Guide ${(guide.series || []).findIndex((row) => row.slug === guide.slug) + 1} of ${(guide.series || []).length} complete`
                  : "Guide complete"}
              </p>
              <h2 className="mx-auto mt-3 max-w-[560px] text-3xl font-extrabold tracking-[-.05em] sm:text-4xl">You made it through, step by step.</h2>
              <p className="mx-auto mt-3 max-w-[520px] text-sm leading-6 text-[#a9aab2]">Come back to any step from the rail. Your progress is saved in this browser.</p>
            </div>
            <div className="p-6 sm:p-8">
              {guide.takeaways?.length > 0 && (
                <>
                  <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#92939d]">Take these with you</p>
                  <ul className="mt-4 grid gap-3 sm:grid-cols-2">
                    {guide.takeaways.map((takeaway) => (
                      <li key={takeaway} className="flex items-start gap-2.5 rounded-xl border border-[#eef1ea] bg-[#fbfdf9] p-3 text-[13px] leading-5 text-[#4f5059] dark:border-[#2f4027] dark:bg-[#1b2418] dark:text-[#b7b8c0]">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#eef7e8] text-[#4f8b32] dark:bg-[#263420]"><Check size={12} /></span>
                        {takeaway}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <div className="mt-8 flex flex-col gap-2 sm:flex-row">
                {nextGuide ? (
                  <Button size="lg" onClick={() => onOpenGuide?.(nextGuide.category_slug, nextGuide.slug)}>
                    Next guide: {nextGuide.title.length > 34 ? `${nextGuide.title.slice(0, 34)}…` : nextGuide.title} <ArrowRight size={16} />
                  </Button>
                ) : (
                  <Button size="lg" onClick={() => onOpenGuide?.(guide.category_slug)}>Back to {guide.category_name} guides <ArrowRight size={16} /></Button>
                )}
                <Button size="lg" variant="outline" onClick={() => setFinished(false)}><RotateCcw size={15} /> Review the steps</Button>
              </div>
              <div className="mt-6 flex flex-col justify-between gap-3 border-t border-[#f0f0f3] pt-5 sm:flex-row sm:items-center dark:border-[#2a2b30]">
                <p className="text-xs text-[#898a95]">Ready to do it in the app?</p>
                <Button variant="soft" onClick={onSignUp}>Open your free workspace <ArrowRight size={14} /></Button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div key={`${guide.id}-${stepIndex}`} className="guide-step-in mt-6 overflow-hidden rounded-3xl border border-[#e9e9ef] bg-white shadow-[0_18px_50px_rgba(30,30,50,.06)] dark:border-[#2a2b30] dark:bg-[#1a1b20]">
              <div className="border-b border-[#f0f0f3] px-6 py-5 sm:px-8 dark:border-[#2a2b30]">
                <div className="flex items-center justify-between gap-4">
                  <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#6957f5] dark:text-[#b9afff]">Step {stepIndex + 1} of {steps.length}</p>
                  <span className="rounded-full bg-[#f4f4f9] px-2.5 py-1 text-[10px] font-bold text-[#92939d] dark:bg-[#26272e]">~{Math.max(1, Math.round(guide.estimated_minutes / Math.max(steps.length, 1)))} min</span>
                </div>
                <h2 className="mt-3 text-2xl font-extrabold leading-8 tracking-[-.04em] text-[#202128] sm:text-[28px] dark:text-[#e4e4e8]">{step.heading}</h2>
              </div>

              <div className="px-6 py-6 sm:px-8">
                <GuideScreen kind={screen} />

                {body.length > 0 && (
                  <div className="mt-7">
                    <p className="text-[15px] leading-8 text-[#5d5e68] dark:text-[#b7b8c0]">{body[0]}</p>
                    {body.length > 1 && (
                      <>
                        <button type="button" onClick={() => setShowDetail((value) => !value)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-[#6957f5] hover:underline">
                          {showDetail ? "Show less" : `More detail (${body.length - 1})`} <ChevronRight size={13} className={`transition ${showDetail ? "-rotate-90" : ""}`} />
                        </button>
                        {showDetail && (
                          <div className="guide-step-in mt-3 space-y-3 border-l-2 border-[#ece9ff] pl-4 dark:border-[#33324a]">
                            {body.slice(1).map((paragraph, index) => (
                              <p key={index} className="text-[14px] leading-7 text-[#747580] dark:text-[#9c9ca6]">{paragraph}</p>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {checklist.length > 0 && (
                  <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-[#fcfcfd] p-5 dark:border-[#2a2b30] dark:bg-[#17181c]">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#92939d]">Do this in the app</p>
                      <span className={`text-[10px] font-bold ${allChecked ? "text-[#4f8b32]" : "text-[#a1a2ab]"}`}>{checkedInStep}/{checklist.length} done</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {checklist.map((item, itemIndex) => {
                        const checked = Boolean(checks[`${stepIndex}:${itemIndex}`]);
                        return (
                          <button key={itemIndex} type="button" onClick={() => toggleCheck(itemIndex)} className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition ${checked ? "border-[#dcebd0] bg-[#f6fbf2] dark:border-[#2f4027] dark:bg-[#1b2418]" : "border-[#ececf3] bg-white hover:border-[#d7d2f5] dark:border-[#33343d] dark:bg-[#1f2026]"}`}>
                            <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-extrabold transition ${checked ? "border-[#78bd4f] bg-[#78bd4f] text-white" : "border-[#dcdce6] text-transparent dark:border-[#4a4b55]"}`}>
                              <Check size={12} className={checked ? "guide-check-pop" : ""} />
                            </span>
                            <span className={`text-[13px] leading-5 ${checked ? "text-[#5d7a4c] line-through dark:text-[#93b083]" : "text-[#4f5059] dark:text-[#c0c1c9]"}`}>{item}</span>
                          </button>
                        );
                      })}
                    </div>
                    {allChecked && <p className="mt-3 flex items-center gap-1.5 text-[11px] font-bold text-[#4f8b32]"><CheckCircle2 size={13} /> All actions checked. Move on when you are ready.</p>}
                  </div>
                )}

                {step.tip && (
                  <aside className="mt-5 flex items-start gap-3 rounded-xl border border-[#dcebd0] bg-[#f6fbf2] p-4 dark:border-[#2f4027] dark:bg-[#1b2418]">
                    <Compass size={16} className="mt-0.5 shrink-0 text-[#4f8b32] dark:text-[#a8d98d]" />
                    <p className="text-[13px] leading-6 text-[#4d7439] dark:text-[#b6d9a3]"><strong className="font-extrabold">Good to know.</strong> {step.tip}</p>
                  </aside>
                )}
              </div>

              <div className="flex items-center justify-between gap-3 border-t border-[#f0f0f3] bg-[#fcfcfd] px-6 py-4 sm:px-8 dark:border-[#2a2b30] dark:bg-[#17181c]">
                <button type="button" onClick={() => goTo(stepIndex - 1, { mark: false })} disabled={stepIndex === 0} className="inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-xs font-bold text-[#747580] transition hover:bg-white hover:text-[#202128] disabled:cursor-not-allowed disabled:opacity-35 dark:text-[#9c9ca6] dark:hover:bg-[#23242a] dark:hover:text-white">
                  <ChevronLeft size={15} /> Back
                </button>
                <div className="flex items-center gap-2">
                  <span className="hidden text-[10px] font-semibold text-[#b0b0b8] sm:inline">Arrow keys work</span>
                  <Button onClick={isLast ? finish : () => goTo(stepIndex + 1)}>
                    {isLast ? "Finish guide" : "Next step"} {isLast ? <CheckCircle2 size={16} /> : <ArrowRight size={16} />}
                  </Button>
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#e9e9ef] bg-white px-4 py-3 text-xs dark:border-[#2a2b30] dark:bg-[#1a1b20]">
              <p className="text-[#92939d]">Step {stepIndex + 1} of {steps.length} · progress saves automatically</p>
              {nextGuide && (
                <button type="button" onClick={() => onOpenGuide?.(nextGuide.category_slug, nextGuide.slug)} className="inline-flex items-center gap-1 font-bold text-[#6957f5] hover:underline">
                  Skip to next guide <ArrowRight size={12} />
                </button>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail
// ---------------------------------------------------------------------------

function GuideDetail({ categorySlug, guideSlug, onOpenGuide, onSignUp, onSignIn, onSection, onOpenLegal }) {
  const [guide, setGuide] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [, setProgressVersion] = useState(0);

  const load = () => {
    setLoading(true);
    setError("");
    api.publicGuide(categorySlug, guideSlug)
      .then((detail) => setGuide(detail))
      .catch((requestError) => setError(requestError.message || "Could not load this guide"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    window.scrollTo(0, 0);
  }, [categorySlug, guideSlug]);

  useEffect(() => {
    if (!guide) return;
    document.title = guide.seo_title || `${guide.title} | Chmaba guides`;
    const description = document.querySelector('meta[name="description"]');
    if (description && guide.seo_description) description.setAttribute("content", guide.seo_description);
  }, [guide]);

  return (
    <div className="min-h-screen overflow-x-clip bg-[#fafafd] text-[#17181c] dark:bg-[#111114] dark:text-[#e4e4e8]">
      <MarketingHeader onSignIn={onSignIn} onSignUp={onSignUp} onSection={onSection} />
      <main>
        <section className="border-b border-[#eaeaef] dark:border-[#2a2b30]">
          <div className="mx-auto max-w-[1240px] px-5 pb-8 pt-8 lg:px-8 lg:pb-10 lg:pt-10">
            <nav className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[#92939d]">
              <GuideLink href="/guides" onClick={() => onOpenGuide?.()} className="hover:text-[#6957f5]">User guides</GuideLink>
              <ChevronRight size={12} />
              <GuideLink href={`/guides/${guide?.category_slug || categorySlug}`} onClick={() => onOpenGuide?.(guide?.category_slug || categorySlug)} className="hover:text-[#6957f5]">{guide?.category_name || "Coffee shop"}</GuideLink>
              <ChevronRight size={12} />
              <span className="text-[#4f5059] dark:text-[#c8c9d0]">{guide?.group_title || "Guide"}</span>
            </nav>
            {loading ? <GuidesLoading label="Opening the guide..." /> : error ? (
              <GuidesError message={error} onRetry={load} onBack={() => onOpenGuide?.(categorySlug)} />
            ) : guide && (
              <div className="mt-6 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-[780px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <Meta guide={guide} />
                    {(guide.series || []).length > 1 && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-[#e4e4eb] bg-white px-2 py-0.5 text-[10px] font-bold text-[#747580] dark:border-[#33343d] dark:bg-[#1a1b20] dark:text-[#c8c9d0]">
                        Guide {(guide.series || []).findIndex((row) => row.slug === guide.slug) + 1} of {(guide.series || []).length}
                      </span>
                    )}
                    {progressFor(guide.slug)?.complete && <span className="inline-flex items-center gap-1 rounded-full bg-[#eef7e8] px-2 py-0.5 text-[10px] font-bold text-[#4f8b32] dark:bg-[#243021] dark:text-[#a8d98d]"><CheckCircle2 size={11} /> Completed</span>}
                  </div>
                  <h1 className="mt-3 text-[32px] font-extrabold leading-[1.08] tracking-[-.055em] sm:text-[42px]">{guide.title}</h1>
                  <p className="mt-3 max-w-[700px] text-[15px] leading-7 text-[#747580] dark:text-[#9c9ca6]">{guide.summary}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3 rounded-2xl border border-[#e9e9ef] bg-white px-4 py-3 dark:border-[#2a2b30] dark:bg-[#1a1b20]">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f0efff] text-[#6957f5] dark:bg-[#2b2850] dark:text-[#b9afff]"><ListChecks size={17} /></span>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[.1em] text-[#92939d]">Step-by-step</p>
                    <p className="text-xs font-extrabold text-[#202128] dark:text-[#e4e4e8]">{guide.step_count || guide.sections?.length || 0} steps · ~{guide.estimated_minutes} min</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {!loading && !error && guide && (
          <>
            <GuidePathTimeline guide={guide} onOpenGuide={onOpenGuide} />
            <GuidePlayer
              key={guide.id}
              guide={guide}
              onOpenGuide={onOpenGuide}
              onSignUp={onSignUp}
              onProgressChange={() => setProgressVersion((value) => value + 1)}
            />
          </>
        )}
      </main>
      <SiteFooter onOpenLegal={onOpenLegal} />
    </div>
  );
}

export function GuidesPage({ categorySlug, guideSlug, onOpenGuide, onSignUp, onSignIn, onSection, onOpenLegal }) {
  if (categorySlug && guideSlug) {
    return <GuideDetail categorySlug={categorySlug} guideSlug={guideSlug} onOpenGuide={onOpenGuide} onSignUp={onSignUp} onSignIn={onSignIn} onSection={onSection} onOpenLegal={onOpenLegal} />;
  }
  if (categorySlug) {
    return <GuidesCategory categorySlug={categorySlug} onOpenGuide={onOpenGuide} onSignUp={onSignUp} onSignIn={onSignIn} onSection={onSection} onOpenLegal={onOpenLegal} />;
  }
  return <GuidesIndex onOpenGuide={onOpenGuide} onSignUp={onSignUp} onSignIn={onSignIn} onSection={onSection} onOpenLegal={onOpenLegal} />;
}
