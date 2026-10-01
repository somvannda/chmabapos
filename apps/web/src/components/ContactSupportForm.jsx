import { useState } from "react";
import { LifeBuoy, Loader2, X } from "lucide-react";
import { api } from "../api";

// Async support: the merchant opens a ticket (there is no real-time chat). The
// backend replies by email and the ticket is tracked in the admin panel.
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

function ContactSupportForm({ token, storeId, history = [], onClose }) {
  const [topic, setTopic] = useState(TOPICS[0]);
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [includeChat, setIncludeChat] = useState(history.length > 0);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    try {
      const response = await api.supportEscalate(
        token,
        {
          message: text,
          topic,
          contact_email: email.trim() || undefined,
          history: includeChat ? history : [],
        },
        storeId,
      );
      setResult(response?.detail || "Our team has been notified.");
    } catch (err) {
      setError(err.message || "Could not send your request right now.");
    } finally {
      setSending(false);
    }
  };

  const inputClass = "h-10 w-full rounded-xl border border-[#e6e6ed] bg-white px-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/40 p-4" onClick={onClose}>
      <div className="w-full max-w-[460px] rounded-2xl border border-[#e9e9ef] bg-white p-5 shadow-[0_24px_80px_rgba(20,21,28,.22)] dark:border-[#2a2b30] dark:bg-[#1f2025]" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><LifeBuoy size={15} /></span>
            <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">Contact support</p>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="text-[#92939d] hover:text-[#303139] dark:hover:text-[#e4e4e8]"><X size={16} /></button>
        </div>

        {result ? (
          <div className="mt-4">
            <p className="rounded-xl border border-[#e4f3d8] bg-[#f4fbf0] p-3 text-xs leading-5 text-[#3f6b28] dark:border-[#2f3a26] dark:bg-[#202a1b] dark:text-[#b7d8a0]">{result}</p>
            <p className="mt-3 text-[11px] leading-5 text-[#898a95] dark:text-[#9a9aa4]">
              We reply by email. You can track this request under <strong className="text-[#5d5e68] dark:text-[#c6c7d0]">Your support requests</strong> on the Help page.
            </p>
            <button type="button" onClick={onClose} className="mt-4 w-full rounded-xl bg-[#6957f5] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#5a48e0]">Done</button>
          </div>
        ) : (
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <label className="block">
              <span className="mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Topic</span>
              <select value={topic} onChange={(event) => setTopic(event.target.value)} className={inputClass}>
                {TOPICS.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">How can we help?</span>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={5}
                required
                placeholder="Describe the issue or question. The more detail, the faster we can help."
                className="w-full rounded-xl border border-[#e6e6ed] bg-white p-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Reply email (optional)</span>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Defaults to your account email" className={inputClass} />
            </label>
            {history.length > 0 && (
              <label className="flex items-center gap-2 text-[11px] font-semibold text-[#5d5e68] dark:text-[#b6b7c0]">
                <input type="checkbox" checked={includeChat} onChange={(event) => setIncludeChat(event.target.checked)} />
                Include my recent assistant chat
              </label>
            )}
            {error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-[11px] text-[#c2564b]">{error}</p>}
            <div className="flex items-center justify-between gap-3 pt-1">
              <span className="text-[10px] text-[#92939d]">We reply by email, usually within one business day.</span>
              <button type="submit" disabled={sending || !message.trim()} className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-[#6957f5] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#5a48e0] disabled:opacity-50">
                {sending ? <><Loader2 size={13} className="animate-spin" /> Sending...</> : "Send request"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export { ContactSupportForm };
