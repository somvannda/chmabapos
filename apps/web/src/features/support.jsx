import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ImagePlus, LifeBuoy, Loader2, Send, X } from "lucide-react";
import { Badge, Button } from "../components/ui";
import { RichBody, RichTextEditor, plainTextToHtml } from "../components/RichTextEditor";
import { api } from "../api";
import { formatDateTime } from "../lib/dateFormat";

// Async support: open a ticket and track it. Real "self-serve" answers live in
// the Knowledge base; this page is for reaching the team and following up.
// Opening a request renders a full page (not a modal) so the thread, status and
// reply composer have room to breathe.
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

const STATUS_LABEL = {
  open: "Open",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

// Reference images are uploaded only when the request/reply is sent, so an
// abandoned draft leaves nothing behind. Held locally with object-URL previews.
const MAX_ATTACHMENTS = 5;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";

// True when a composed reply has no visible text (ignores empty markup).
function isBlankHtml(html) {
  return !(html || "").replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
}

function AttachmentPicker({ items, onChange, disabled }) {
  const inputRef = useRef(null);
  const pick = (event) => {
    const chosen = Array.from(event.target.files || []);
    event.target.value = "";
    if (!chosen.length) return;
    const next = [...items];
    for (const file of chosen) {
      if (next.length >= MAX_ATTACHMENTS) break;
      if (file.size > MAX_ATTACHMENT_BYTES) continue;
      next.push({ file, url: URL.createObjectURL(file) });
    }
    onChange(next);
  };
  const remove = (index) => {
    const item = items[index];
    if (item?.url) URL.revokeObjectURL(item.url);
    onChange(items.filter((_, position) => position !== index));
  };
  return <div className="mt-1.5">
    <div className="flex flex-wrap items-center gap-2">
      {items.map((item, index) => <span key={item.url} className="relative inline-block">
        <img src={item.url} alt="" className="h-12 w-12 rounded-lg border border-[#e6e6ed] object-cover dark:border-[#363740]" />
        <button type="button" onClick={() => remove(index)} disabled={disabled} className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#17181c] text-white disabled:opacity-50"><X size={10} /></button>
      </span>)}
      {items.length < MAX_ATTACHMENTS && <button type="button" disabled={disabled} onClick={() => inputRef.current?.click()} className="flex h-12 items-center gap-1.5 rounded-lg border border-dashed border-[#d9d9e3] px-3 text-[11px] font-semibold text-[#6957f5] disabled:opacity-50 dark:border-[#363740]"><ImagePlus size={14} /> Add image</button>}
    </div>
    <p className="mt-1 text-[10px] text-[#92939d]">{items.length}/{MAX_ATTACHMENTS} images · PNG, JPG, WEBP or GIF, up to 5MB each</p>
    <input ref={inputRef} type="file" accept={IMAGE_ACCEPT} multiple className="hidden" onChange={pick} />
  </div>;
}

function AttachmentStrip({ items }) {
  if (!items?.length) return null;
  return <div className="mt-2 flex flex-wrap gap-2">
    {items.map((item) => <a key={item.id} href={item.url} target="_blank" rel="noreferrer" title={item.original_filename || "Attachment"}>
      <img src={item.url} alt={item.original_filename || "Attachment"} className="h-16 w-16 rounded-lg border border-black/5 object-cover" />
    </a>)}
  </div>;
}

function TicketThread({ detail }) {
  return <div className="space-y-3">
    <div className="rounded-xl bg-[#f7f7fa] p-4 text-xs text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]">
      <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wide text-[#92939d]">You</p>
      <p className="whitespace-pre-wrap">{detail.question}</p>
      <AttachmentStrip items={detail.attachments} />
    </div>
    {(detail.messages || []).map((item) => (
      <div key={item.id} className={`rounded-xl p-4 text-xs ${item.author_type === "agent" ? "bg-[#edf9e4] text-[#38571f] dark:bg-[#223019] dark:text-[#c3e3ab]" : "bg-[#f7f7fa] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"}`}>
        <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wide opacity-70">{item.author_type === "agent" ? "Support team" : "You"} · {formatDateTime(item.created_at)}</p>
        <RichBody html={item.body} />
        <AttachmentStrip items={item.attachments} />
      </div>
    ))}
  </div>;
}

function TicketDetailPage({ token, detail, onBack, onUpdated }) {
  const [reply, setReply] = useState("");
  const [replyFiles, setReplyFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [error, setError] = useState("");

  const uploadAttachments = async () => {
    const ids = [];
    for (const item of replyFiles) {
      const asset = await api.uploadSupportAttachment(token, item.file);
      ids.push(asset.id);
    }
    return ids;
  };

  const clearReplyFiles = () => setReplyFiles((current) => {
    current.forEach((item) => URL.revokeObjectURL(item.url));
    return [];
  });

  const aiRewrite = async () => {
    if (aiBusy) return;
    setAiBusy(true);
    setError("");
    try {
      const result = await api.supportAiDraftTicket(token, detail.id, { body: reply });
      setReply(plainTextToHtml(result.body));
    } catch (err) {
      setError(err.message || "The assistant could not write a draft right now.");
    } finally {
      setAiBusy(false);
    }
  };

  const sendReply = async () => {
    if (isBlankHtml(reply) || busy) return;
    setBusy(true);
    setError("");
    try {
      const attachmentIds = await uploadAttachments();
      const updated = await api.supportReplyTicket(token, detail.id, { body: reply, attachment_ids: attachmentIds });
      setReply("");
      clearReplyFiles();
      onUpdated?.(updated);
    } catch (err) {
      setError(err.message || "Could not send your reply.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="mx-auto max-w-[820px] p-5 lg:p-8">
    <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 text-xs font-bold text-[#777883] transition hover:text-[#303139] dark:hover:text-[#e4e4e8]">
      <ArrowLeft size={14} /> All requests
    </button>
    <div className="mt-4 flex flex-wrap items-start justify-between gap-3 border-b border-[#f0f0f3] pb-4 dark:border-[#2a2b30]">
      <div>
        <p className="flex items-center gap-2 text-lg font-extrabold tracking-[-.03em] text-[#202128] dark:text-[#e4e4e8]">
          {detail.reference}
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${STATUS_STYLE[detail.status] || ""}`}>{STATUS_LABEL[detail.status] || detail.status}</span>
        </p>
        <p className="mt-0.5 text-[11px] text-[#92939d]">Opened {formatDateTime(detail.created_at)}</p>
      </div>
    </div>

    <div className="mt-5"><TicketThread detail={detail} /></div>

    <div className="mt-6 rounded-2xl border border-[#e9e9ef] bg-white p-4 dark:border-[#2a2b30] dark:bg-[#1f2025]">
      <p className="text-xs font-extrabold text-[#202128] dark:text-[#e4e4e8]">Add a reply</p>
      <p className="mt-0.5 text-[11px] text-[#92939d]">Our support team is notified and replies by email. You can use the assistant to help word it.</p>
      <div className="mt-3">
        <RichTextEditor
          value={reply}
          onChange={setReply}
          disabled={busy}
          placeholder="Write a reply..."
          minHeight={120}
          onAiAction={aiRewrite}
          aiBusy={aiBusy}
          aiLabel="Help me write"
        />
        <AttachmentPicker items={replyFiles} onChange={setReplyFiles} disabled={busy} />
      </div>
      {error && <p className="mt-2 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-[11px] text-[#c2564b]">{error}</p>}
      <div className="mt-3 flex justify-end">
        <Button disabled={busy || isBlankHtml(reply)} onClick={sendReply}>{busy ? <><Loader2 size={13} className="animate-spin" /> Sending...</> : <><Send size={14} /> Send reply</>}</Button>
      </div>
    </div>
  </div>;
}

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
  const [newFiles, setNewFiles] = useState([]);

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

  const uploadAttachments = async (items) => {
    const ids = [];
    for (const item of items) {
      const asset = await api.uploadSupportAttachment(token, item.file);
      ids.push(asset.id);
    }
    return ids;
  };

  const clearFiles = (setter) => setter((current) => {
    current.forEach((item) => URL.revokeObjectURL(item.url));
    return [];
  });

  const submit = async (event) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    setResult("");
    try {
      const attachmentIds = await uploadAttachments(newFiles);
      const response = await api.supportEscalate(
        token,
        { message: text, topic, contact_email: email.trim() || undefined, history: includeChat ? recentChat : [], attachment_ids: attachmentIds },
        workspace?.store?.id,
      );
      setResult(response?.detail || "Our team has been notified.");
      setMessage("");
      clearFiles(setNewFiles);
      loadTickets();
    } catch (err) {
      setError(err.message || "Could not send your request right now.");
    } finally {
      setSending(false);
    }
  };

  const openTicket = async (id) => {
    setError("");
    try {
      setDetail(await api.supportTicket(token, id));
    } catch {
      /* keep the list */
    }
  };

  const refreshDetail = (updated) => {
    setDetail(updated);
    loadTickets();
  };

  const inputClass = "h-10 w-full rounded-xl border border-[#e6e6ed] bg-white px-3 text-xs text-[#303139] outline-none dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]";
  const labelClass = "mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]";

  if (detail) {
    return <TicketDetailPage token={token} detail={detail} onBack={() => setDetail(null)} onUpdated={refreshDetail} />;
  }

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
            <div>
              <span className={labelClass}>Attach images (optional)</span>
              <AttachmentPicker items={newFiles} onChange={setNewFiles} disabled={sending} />
            </div>
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
  </div>;
}

export { LiveSupportView };
