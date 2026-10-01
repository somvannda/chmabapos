import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, CircleHelp, LifeBuoy, Loader2, Search } from "lucide-react";
import { Badge, Button } from "../components/ui";
import { SupportChat } from "../components/SupportChat";
import { ContactSupportForm } from "../components/ContactSupportForm";
import { api } from "../api";

const TICKET_STATUS_STYLE = {
  open: "bg-[#fff6df] text-[#ad7d1c]",
  pending: "bg-[#eaf4ff] text-[#3579b8]",
  resolved: "bg-[#edf9e4] text-[#4f8b32]",
  closed: "bg-[#f1f1f5] text-[#686974]",
};

// The help corpus lives on the API (app/support_content.py) so the web app and
// the future assistant share one source of truth. This view only renders it and
// never hardcodes guide copy.

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
  const [tickets, setTickets] = useState([]);
  const [ticketDetail, setTicketDetail] = useState(null);
  const [ticketReply, setTicketReply] = useState("");
  const [ticketBusy, setTicketBusy] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [contactHistory, setContactHistory] = useState([]);

  const openContact = (history = []) => {
    setContactHistory(history);
    setContactOpen(true);
  };

  const refreshTickets = () => {
    api.supportTickets(token).then((rows) => setTickets(rows || [])).catch(() => {});
  };
  const openTicket = async (id) => {
    try {
      setTicketDetail(await api.supportTicket(token, id));
    } catch {
      /* ignore and keep the list */
    }
  };
  const replyTicket = async () => {
    const body = ticketReply.trim();
    if (!ticketDetail || !body) return;
    setTicketBusy(true);
    try {
      setTicketDetail(await api.supportReplyTicket(token, ticketDetail.id, { body }));
      setTicketReply("");
      refreshTickets();
    } finally {
      setTicketBusy(false);
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
    api.supportTickets(token)
      .then((rows) => { if (active) setTickets(rows || []); })
      .catch(() => { if (active) setTickets([]); });
    return () => { active = false; };
  }, [token]);

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

      <SupportChat token={token} storeId={workspace?.store?.id} language={language} onLanguageChange={changeLanguage} starterPrompts={prompts} className="mt-5" onOpenGuide={(id) => setOpenId(id)} onNavigate={onNavigate} onContactSupport={(history) => openContact(history)} />

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

      {tickets.length > 0 && (
        <div className="mt-8 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]">
          <div className="flex items-center justify-between border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
            <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Your support requests</p>
            <p className="text-[10px] text-[#92939d]">{tickets.length} total</p>
          </div>
          {tickets.slice(0, 5).map((ticket) => (
            <button key={ticket.id} type="button" onClick={() => openTicket(ticket.id)} className="flex w-full items-center gap-3 border-t border-[#f0f0f3] px-4 py-2.5 text-left text-[11px] hover:bg-[#fafafd] dark:border-[#2a2b30] dark:hover:bg-[#26272d]">
              <span className="shrink-0 font-mono text-[10px] text-[#777883] dark:text-[#a9aab3]">{ticket.reference}</span>
              <span className="min-w-0 flex-1 truncate text-[#5d5e68] dark:text-[#b6b7c0]" title={ticket.question}>{ticket.question}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold capitalize ${TICKET_STATUS_STYLE[ticket.status] || ""}`}>{ticket.status}</span>
            </button>
          ))}
        </div>
      )}

      <div className="mt-8 rounded-2xl border border-[#e6e5f3] bg-[#faf9ff] p-5 dark:border-[#33343a] dark:bg-[#202126]">
        <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Still need help?</p>
        <p className="mt-1.5 text-[11px] leading-5 text-[#777883] dark:text-[#a9aab3]">
          If the assistant and guides cannot answer your question, contact our team and we will follow up.
        </p>
        <Button variant="soft" size="sm" className="mt-3" onClick={() => openContact([])}>
          <LifeBuoy size={14} /> Contact support
        </Button>
      </div>

      {contactOpen && (
        <ContactSupportForm
          token={token}
          storeId={workspace?.store?.id}
          history={contactHistory}
          onClose={() => setContactOpen(false)}
        />
      )}

      {ticketDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/40 p-4" onClick={() => setTicketDetail(null)}>
          <div className="flex max-h-[85vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
              <div>
                <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">
                  {ticketDetail.reference}
                  <span className={`ml-1 rounded-full px-2 py-0.5 text-[9px] font-bold capitalize ${TICKET_STATUS_STYLE[ticketDetail.status] || ""}`}>{ticketDetail.status}</span>
                </p>
                <p className="text-[10px] text-[#92939d]">{new Date(ticketDetail.created_at).toLocaleString()}</p>
              </div>
              <button onClick={() => setTicketDetail(null)} className="text-[11px] font-bold text-[#777883] hover:text-[#303139] dark:hover:text-[#e4e4e8]">Close</button>
            </div>
            <div className="app-scrollbar flex-1 space-y-3 overflow-y-auto p-4">
              <div className="rounded-xl bg-[#f7f7fa] p-3 text-xs text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]">
                <p className="mb-1 text-[9px] font-bold uppercase tracking-wide text-[#92939d]">You</p>
                <p className="whitespace-pre-wrap">{ticketDetail.question}</p>
              </div>
              {(ticketDetail.messages || []).map((message) => (
                <div key={message.id} className={`rounded-xl p-3 text-xs ${message.author_type === "agent" ? "bg-[#edf9e4] text-[#38571f] dark:bg-[#223019] dark:text-[#c3e3ab]" : "bg-[#f7f7fa] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"}`}>
                  <p className="mb-1 text-[9px] font-bold uppercase tracking-wide opacity-70">{message.author_type === "agent" ? "Support team" : "You"} · {new Date(message.created_at).toLocaleString()}</p>
                  <p className="whitespace-pre-wrap">{message.body}</p>
                </div>
              ))}
            </div>
            <div className="border-t border-[#f0f0f3] p-4 dark:border-[#2a2b30]">
              <textarea value={ticketReply} onChange={(event) => setTicketReply(event.target.value)} rows={3} placeholder="Write a reply..." className="w-full rounded-xl border border-[#e6e6ed] bg-white p-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]" />
              <div className="mt-2 flex justify-end">
                <button type="button" disabled={ticketBusy || !ticketReply.trim()} onClick={replyTicket} className="rounded-xl bg-[#6957f5] px-4 py-2 text-xs font-bold text-white disabled:opacity-50">{ticketBusy ? "Sending..." : "Send reply"}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { HelpCenterView };
