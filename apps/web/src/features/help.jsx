import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, CircleHelp, LifeBuoy, Loader2, Search } from "lucide-react";
import { Badge, Button } from "../components/ui";
import { SupportChat } from "../components/SupportChat";
import { api } from "../api";

// The knowledge base: the guide corpus (app/support_content.py) plus the
// assistant. Reaching a human or tracking a request lives on the Support page.

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
  const [openId, setOpenId] = useState(null);

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

  const openArticle = useMemo(() => {
    if (!openId) return null;
    for (const section of sections) {
      const found = section.articles.find((article) => article.id === openId);
      if (found) return found;
    }
    return null;
  }, [openId, sections]);

  return (
    <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-[#92939d]">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><CircleHelp size={15} /></span>
            Knowledge base
          </div>
          <h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em] text-[#202128] dark:text-[#e4e4e8]">How can we help?</h2>
          <p className="mt-1 text-sm text-[#898a95] dark:text-[#9a9aa4]">
            Step-by-step guides and the assistant, tailored to your {vertical} store.
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

      <SupportChat token={token} storeId={workspace?.store?.id} language={language} onLanguageChange={changeLanguage} starterPrompts={prompts} className="mt-5" onOpenGuide={(id) => setOpenId(id)} onNavigate={onNavigate} onContactSupport={() => onNavigate?.("support")} />

      {openArticle ? (
        <div className="mt-5">
          <HelpArticle article={openArticle} onBack={() => setOpenId(null)} />
        </div>
      ) : (
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
          {!loading && !error && sections.length === 0 && (
            <div className="rounded-2xl border border-[#e9e9ef] bg-white p-10 text-center dark:border-[#2a2b30] dark:bg-[#1f2025]">
              <p className="text-sm font-bold text-[#565762] dark:text-[#c6c7d0]">No guides match that search.</p>
              <p className="mt-1 text-xs text-[#92939d]">Try a simpler word, or ask the assistant above.</p>
            </div>
          )}
          {!loading && !error && sections.map((section) => (
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
