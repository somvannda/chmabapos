import { useEffect, useState } from "react";
import { LifeBuoy, Loader2, Send } from "lucide-react";
import { Badge, Button } from "../components/ui";
import { api } from "../api";

// Async support: open a ticket and track it. Real "self-serve" answers live in
// the Knowledge base; this page is for reaching the team and following up.
const TOPICS = [
  "Using the app",
  "Selling / POS",
  "Inventory & stock",
  "Products & catalog",
  "Billing & plans",
  "Team & access",
  "Something is broken",
  "Other",
];

const STATUS_STYLE = {
  open: "bg-[#fff6df] text-[#ad7d1c]",
  pending: "bg-[#eaf4ff] text-[#3579b8]",
  resolved: "bg-[#edf9e4] text-[#4f8b32]",
  closed: "bg-[#f1f1f5] text-[#686974]",
};

function LiveSupportView({ token, workspace }) {
  const [topic, setTopic] = useState(TOPICS[0]);
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [recentChat, setRecentChat] = useState([]);
  const [includeChat, setIncludeChat] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  const loadTickets = () => {
    setLoading(true);
    api.supportTickets(token)
      .then((rows) => setTickets(rows || []))
      .catch(() => setTickets([]))
      .finally(() => setLoading(false));
  };
  useEffect(() => { if (token) loadTickets(); }, [token]);

  useEffect(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem("chmaba.support.recentChat") || "[]");
      if (Array.isArray(stored) && stored.length) {
        setRecentChat(stored);
        setIncludeChat(true);
      }
    } catch {
      /* ignore storage failures */
    }
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    setResult("");
    try {
      const response = await api.supportEscalate(
        token,
        { message: text, topic, contact_email: email.trim() || undefined, history: includeChat ? recentChat : [] },
        workspace?.store?.id,
      );
      setResult(response?.detail || "Our team has been notified.");
      setMessage("");
      loadTickets();
    } catch (err) {
      setError(err.message || "Could not send your request right now.");
    } finally {
      setSending(false);
    }
  };

  const openTicket = async (id) => {
    try {
      setDetail(await api.supportTicket(token, id));
    } catch {
      /* keep the list */
    }
  };

  const sendReply = async () => {
    const body = reply.trim();
    if (!detail || !body) return;
    setBusy(true);
    try {
      setDetail(await api.supportReplyTicket(token, detail.id, { body }));
      setReply("");
      loadTickets();
    } finally {
      setBusy(false);
    }
  };

  const inputClass = "h-10 w-full rounded-xl border border-[#e6e6ed] bg-white px-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]";
  const labelClass = "mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]";

  return <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
    <div className="flex items-center gap-2 text-xs text-[#92939d]">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><LifeBuoy size={15} /></span>
      Support
    </div>
    <h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em] text-[#202128] dark:text-[#e4e4e8]">Contact support</h2>
    <p className="mt-1 text-sm text-[#898a95] dark:text-[#9a9aa4]">
      Tell us what's going on and we'll reply by email. Looking for answers instead? Try the {" "}
      <span className="font-semibold text-[#5d5e68] dark:text-[#b6b7c0]">Knowledge base</span>.
    </p>

    <div className="mt-6 grid gap-5 lg:grid-cols-2">
      <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5 dark:border-[#2a2b30] dark:bg-[#1f2025]">
        <div className="flex items-center gap-2">
          <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">New request</p>
          <Badge tone="violet">We reply by email</Badge>
        </div>

        {result ? (
          <div className="mt-4">
            <p className="rounded-xl border border-[#e4f3d8] bg-[#f4fbf0] p-3 text-xs leading-5 text-[#3f6b28] dark:border-[#2f3a26] dark:bg-[#202a1b] dark:text-[#b7d8a0]">{result}</p>
            <Button variant="soft" size="sm" className="mt-3" onClick={() => setResult("")}>Send another</Button>
          </div>
        ) : (
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <label className="block">
              <span className={labelClass}>Topic</span>
              <select value={topic} onChange={(event) => setTopic(event.target.value)} className={inputClass}>
                {TOPICS.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="block">
              <span className={labelClass}>How can we help?</span>
              <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={6} required placeholder="Describe the issue or question. The more detail, the faster we can help." className="w-full rounded-xl border border-[#e6e6ed] bg-white p-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]" />
            </label>
            <label className="block">
              <span className={labelClass}>Reply email (optional)</span>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Defaults to your account email" className={inputClass} />
            </label>
            {recentChat.length > 0 && (
              <label className="flex items-center gap-2 text-[11px] font-semibold text-[#5d5e68] dark:text-[#b6b7c0]">
                <input type="checkbox" checked={includeChat} onChange={(event) => setIncludeChat(event.target.checked)} />
                Include my recent assistant chat
              </label>
            )}
            {error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-[11px] text-[#c2564b]">{error}</p>}
            <Button type="submit" disabled={sending || !message.trim()} className="w-full">
              {sending ? <><Loader2 size={13} className="animate-spin" /> Sending...</> : <><Send size={14} /> Send request</>}
            </Button>
          </form>
        )}
      </section>

      <section className="overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]">
        <div className="flex items-center justify-between border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
          <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">Your requests</p>
          <p className="text-[10px] text-[#92939d]">{tickets.length} total</p>
        </div>
        {loading
          ? <p className="p-6 text-xs text-[#92939d]">Loading...</p>
          : tickets.length === 0
            ? <p className="p-6 text-xs text-[#92939d]">No requests yet.</p>
            : tickets.map((ticket) => (
              <button key={ticket.id} type="button" onClick={() => openTicket(ticket.id)} className="flex w-full items-center gap-3 border-t border-[#f0f0f3] px-4 py-3 text-left text-[11px] hover:bg-[#fafafd] dark:border-[#2a2b30] dark:hover:bg-[#26272d]">
                <span className="shrink-0 font-mono text-[10px] text-[#777883] dark:text-[#a9aab3]">{ticket.reference}</span>
                <span className="min-w-0 flex-1 truncate text-[#5d5e68] dark:text-[#b6b7c0]" title={ticket.question}>{ticket.question}</span>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold capitalize ${STATUS_STYLE[ticket.status] || ""}`}>{ticket.status}</span>
              </button>
            ))}
      </section>
    </div>

    {detail && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/40 p-4" onClick={() => setDetail(null)}>
        <div className="flex max-h-[85vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]" onClick={(event) => event.stopPropagation()}>
          <div className="flex items-center justify-between border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
            <div>
              <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">
                {detail.reference}
                <span className={`ml-1 rounded-full px-2 py-0.5 text-[9px] font-bold capitalize ${STATUS_STYLE[detail.status] || ""}`}>{detail.status}</span>
              </p>
              <p className="text-[10px] text-[#92939d]">{new Date(detail.created_at).toLocaleString()}</p>
            </div>
            <button onClick={() => setDetail(null)} className="text-[11px] font-bold text-[#777883] hover:text-[#303139] dark:hover:text-[#e4e4e8]">Close</button>
          </div>
          <div className="app-scrollbar flex-1 space-y-3 overflow-y-auto p-4">
            <div className="rounded-xl bg-[#f7f7fa] p-3 text-xs text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wide text-[#92939d]">You</p>
              <p className="whitespace-pre-wrap">{detail.question}</p>
            </div>
            {(detail.messages || []).map((item) => (
              <div key={item.id} className={`rounded-xl p-3 text-xs ${item.author_type === "agent" ? "bg-[#edf9e4] text-[#38571f] dark:bg-[#223019] dark:text-[#c3e3ab]" : "bg-[#f7f7fa] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"}`}>
                <p className="mb-1 text-[9px] font-bold uppercase tracking-wide opacity-70">{item.author_type === "agent" ? "Support team" : "You"} · {new Date(item.created_at).toLocaleString()}</p>
                <p className="whitespace-pre-wrap">{item.body}</p>
              </div>
            ))}
          </div>
          <div className="border-t border-[#f0f0f3] p-4 dark:border-[#2a2b30]">
            <textarea value={reply} onChange={(event) => setReply(event.target.value)} rows={3} placeholder="Write a reply..." className="w-full rounded-xl border border-[#e6e6ed] bg-white p-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]" />
            <div className="mt-2 flex justify-end">
              <Button size="sm" disabled={busy || !reply.trim()} onClick={sendReply}>{busy ? "Sending..." : "Send reply"}</Button>
            </div>
          </div>
        </div>
      </div>
    )}
  </div>;
}

export { LiveSupportView };
