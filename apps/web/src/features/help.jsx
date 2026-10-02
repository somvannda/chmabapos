import { useEffect, useMemo, useState } from "react";
import { BookOpen, ChevronDown, CircleHelp, LifeBuoy, Loader2, Search } from "lucide-react";
import { Badge, Button } from "../components/ui";
import { SupportChat } from "../components/SupportChat";
import { api } from "../api";
import { buildNudges } from "../lib/nudges";

// The knowledge base: the guide corpus (app/support_content.py) plus the
// assistant. Guides are shown as compact, expandable question/answer rows.
// Reaching a human or tracking a request lives on the Support page.

function HelpCenterView({ token, workspace, onNavigate }) {
  const vertical = workspace?.company?.vertical || "general";
  const [language, setLanguage] = useState(() => {
    try {
      return localStorage.getItem("chmaba.support.lang") || "en";
    } catch {
      return "en";
    }
  });
  const [query, setQuery] = useState("");
  const [sections, setSections] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [checklist, setChecklist] = useState(null);
  const [lowStock, setLowStock] = useState([]);
  const [nudgesDismissed, setNudgesDismissed] = useState(() => {
    try {
      return sessionStorage.getItem("chmaba.kb.nudgesDismissed") === "1";
    } catch {
      return false;
    }
  });

  const dismissNudges = () => {
    setNudgesDismissed(true);
    try {
      sessionStorage.setItem("chmaba.kb.nudgesDismissed", "1");
    } catch {
      /* ignore storage failures */
    }
  };

  const changeLanguage = (value) => {
    setLanguage(value);
    try {
      localStorage.setItem("chmaba.support.lang", value);
    } catch {
      /* ignore storage failures */
    }
  };

  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    api.supportStarterPrompts(token, language)
      .then((data) => { if (active) setPrompts(data?.prompts || []); })
      .catch(() => { if (active) setPrompts([]); });
    return () => { active = false; };
  }, [token, language]);

  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    setLoading(true);
    setError("");
    const handle = window.setTimeout(() => {
      api.supportArticles(token, { query, language })
        .then((data) => { if (active) setSections(data || []); })
        .catch((err) => { if (active) setError(err.message || "Could not load guides"); })
        .finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => { active = false; window.clearTimeout(handle); };
  }, [token, query, language]);

  useEffect(() => {
    const storeId = workspace?.store?.id;
    if (!token || !storeId) return undefined;
    let active = true;
    api.setupChecklist(token, storeId)
      .then((row) => { if (active) setChecklist(row); })
      .catch(() => { if (active) setChecklist(null); });
    api.inventory(token, storeId, true)
      .then((rows) => { if (active) setLowStock(rows || []); })
      .catch(() => { if (active) setLowStock([]); });
    return () => { active = false; };
  }, [token, workspace?.store?.id]);

  const sectionList = useMemo(() => sections.filter((section) => section.articles.length > 0), [sections]);

  const nudges = useMemo(() => buildNudges(checklist, lowStock), [checklist, lowStock]);

  return (
    <div className="mx-auto max-w-[900px] p-5 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-[#92939d]">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><CircleHelp size={15} /></span>
            Knowledge base
          </div>
          <h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em] text-[#202128] dark:text-[#e4e4e8]">How can we help?</h2>
          <p className="mt-1 text-sm text-[#898a95] dark:text-[#9a9aa4]">
            Ask the assistant, or tap a question to see the steps. Tailored to your {vertical} store.
          </p>
        </div>
        <Badge tone="violet">Guide library</Badge>
      </div>

      <SupportChat token={token} storeId={workspace?.store?.id} language={language} onLanguageChange={changeLanguage} starterPrompts={prompts} className="mt-5" onOpenGuide={(id) => setExpandedId(id)} onNavigate={onNavigate} onContactSupport={() => onNavigate?.("support")} />

      {nudges.length > 0 && !nudgesDismissed && (
        <div className="mt-5 rounded-2xl border border-[#e6e5f3] bg-[#faf9ff] p-4 dark:border-[#33343a] dark:bg-[#202126]">
          <div className="flex items-center justify-between">
            <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Suggested for you</p>
            <button type="button" onClick={dismissNudges} className="text-[10px] font-bold text-[#92939d] hover:text-[#303139] dark:hover:text-[#e4e4e8]">Dismiss</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {nudges.map((nudge) => (
              <button
                key={nudge.id}
                type="button"
                onClick={() => onNavigate?.(nudge.href)}
                className="rounded-xl border border-[#e4e4eb] bg-white px-3 py-2 text-left transition hover:border-[#bdb9ee] dark:border-[#363740] dark:bg-[#1a1b1f]"
              >
                <span className="block text-[11px] font-bold text-[#303139] dark:text-[#e4e4e8]">{nudge.label}</span>
                {nudge.description && <span className="mt-0.5 block text-[10px] text-[#92939d]">{nudge.description}</span>}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 flex items-center gap-2 rounded-xl border border-[#e6e6ed] bg-white px-3 dark:border-[#363740] dark:bg-[#1f2025]">
        <Search size={15} className="text-[#a0a1aa]" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search guides, e.g. refund, restock, shift"
          className="h-11 w-full bg-transparent text-xs text-[#303139] outline-none placeholder:text-[#a0a1aa] dark:text-[#e4e4e8]"
        />
      </div>

      <div className="mt-5 space-y-6">
        {loading && (
          <div className="flex items-center justify-center gap-2 rounded-2xl border border-[#e9e9ef] bg-white p-10 text-sm text-[#92939d] dark:border-[#2a2b30] dark:bg-[#1f2025]">
            <Loader2 size={16} className="animate-spin" /> Loading guides...
          </div>
        )}
        {!loading && error && (
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-10 text-center dark:border-[#2a2b30] dark:bg-[#1f2025]">
            <p className="text-sm font-bold text-[#c2564b]">{error}</p>
            <p className="mt-1 text-xs text-[#92939d]">Check your connection and reload this page.</p>
          </div>
        )}
        {!loading && !error && sectionList.length === 0 && (
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-10 text-center dark:border-[#2a2b30] dark:bg-[#1f2025]">
            <p className="text-sm font-bold text-[#565762] dark:text-[#c6c7d0]">No guides match that search.</p>
            <p className="mt-1 text-xs text-[#92939d]">Try a simpler word, or ask the assistant above.</p>
          </div>
        )}
        {!loading && !error && sectionList.map((section) => (
          <section key={section.id}>
            <div className="flex items-center gap-2">
              <BookOpen size={15} className="text-[#6957f5]" />
              <h3 className="text-sm font-extrabold text-[#303139] dark:text-[#e4e4e8]">{section.title}</h3>
              <span className="text-[11px] text-[#92939d]">{section.blurb}</span>
            </div>
            <div className="mt-3 overflow-hidden rounded-xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]">
              {section.articles.map((article, index) => {
                const open = expandedId === article.id;
                return (
                  <div key={article.id} className={index > 0 ? "border-t border-[#f0f0f3] dark:border-[#2a2b30]" : ""}>
                    <button
                      type="button"
                      onClick={() => setExpandedId(open ? null : article.id)}
                      aria-expanded={open}
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-[#fafafd] dark:hover:bg-[#26272d]"
                    >
                      <span className="text-xs font-bold text-[#303139] dark:text-[#e4e4e8]">{article.title}</span>
                      <ChevronDown size={15} className={`shrink-0 transition ${open ? "rotate-180 text-[#6957f5]" : "text-[#b0b1ba]"}`} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-0.5">
                        <ol className="space-y-2">
                          {article.steps.map((step, stepIndex) => (
                            <li key={stepIndex} className="flex gap-2.5 text-xs leading-5 text-[#5d5e68] dark:text-[#b6b7c0]">
                              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#ece9ff] text-[10px] font-extrabold text-[#6957f5]">{stepIndex + 1}</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                        {article.tip && (
                          <p className="mt-3 rounded-lg border border-[#e6e5f3] bg-[#faf9ff] p-2.5 text-[11px] leading-5 text-[#696a76] dark:border-[#33343a] dark:bg-[#202126] dark:text-[#a9aab3]">
                            <strong className="text-[#545560] dark:text-[#cfd0d8]">Tip: </strong>{article.tip}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-2xl border border-[#e6e5f3] bg-[#faf9ff] p-5 dark:border-[#33343a] dark:bg-[#202126]">
        <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Still need help?</p>
        <p className="mt-1.5 text-[11px] leading-5 text-[#777883] dark:text-[#a9aab3]">
          If the assistant and guides cannot answer your question, contact our team and we will follow up by email.
        </p>
        <Button variant="soft" size="sm" className="mt-3" onClick={() => onNavigate?.("support")}>
          <LifeBuoy size={14} /> Go to Support
        </Button>
      </div>
    </div>
  );
}

export { HelpCenterView };
