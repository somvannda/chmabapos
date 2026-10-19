import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Bolt, FileText, Info, Mic, Package, Paperclip, Pencil, Send, Smile, Square, Trash2 } from "lucide-react";

import { api } from "../api";
import { Badge, Button, Dropdown } from "../components/ui";
import {
  contactRows,
  conversationLabel,
  formatBytes,
  formatDuration,
  highestSeq,
  isSignedInCustomer,
  kindForFile,
  linkify,
  mergeMessages,
  parseSseChunk,
  playChatChime,
  relativeTime,
  storeSwitcherOptions,
  threadOrders,
  unreadTotal,
} from "../lib/inbox";

const QUICK_EMOJI = ["👍", "❤️", "😄", "😮", "😢", "🙏"];
const ACCEPTED_FILES = "image/*,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,audio/*";
const LIST_POLL_MS = 10000;
const THREAD_POLL_MS = 12000;
const MAX_ATTACHMENT_BYTES = 5_000_000;

// MediaRecorder negotiates its own container per browser, so the file suffix is
// taken from the mime type it chose rather than assumed to be WebM.
function useVoiceRecorder(onStop) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [voiceError, setVoiceError] = useState("");
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const secondsRef = useRef(0);
  const timerRef = useRef(null);
  const cancelledRef = useRef(false);

  const supported =
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    Boolean(window.navigator?.mediaDevices?.getUserMedia);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    try { recorderRef.current?.stop(); } catch { /* already stopped */ }
  }, []);

  const start = async () => {
    setVoiceError("");
    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true });
      const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
      const mimeType = candidates.find((type) => window.MediaRecorder.isTypeSupported?.(type)) || "";
      const recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      cancelledRef.current = false;
      secondsRef.current = 0;
      setSeconds(0);
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        if (timerRef.current) window.clearInterval(timerRef.current);
        timerRef.current = null;
        setRecording(false);
        if (cancelledRef.current) return;
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        if (!blob.size) return;
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        onStop(new File([blob], `voice.${extension}`, { type }), secondsRef.current * 1000);
      };
      recorderRef.current = recorder;
      recorder.start();
      timerRef.current = window.setInterval(() => {
        secondsRef.current += 1;
        setSeconds(secondsRef.current);
      }, 1000);
      setRecording(true);
    } catch {
      setVoiceError("Microphone access is needed to record a voice note.");
    }
  };

  return {
    recording,
    seconds,
    voiceError,
    supported,
    start,
    stop: () => { try { recorderRef.current?.stop(); } catch { /* already stopped */ } },
    cancel: () => { cancelledRef.current = true; try { recorderRef.current?.stop(); } catch { /* already stopped */ } },
  };
}

// The storefront host serves the customer's order page; the POS workspace is a
// different origin, so the link is only offered when that host is configured.
const STOREFRONT_URL = (import.meta.env.VITE_STOREFRONT_URL || "").replace(/\/$/, "");

function OrderCard({ order }) {
  if (!order) return null;
  const href = order.public_token && STOREFRONT_URL ? `${STOREFRONT_URL}/order/${order.public_token}` : null;
  const inner = (
    <span className="mt-1 flex items-center justify-between gap-3 rounded-xl border border-[#e9e9ef] bg-white px-3 py-2 dark:border-[#2a2b30] dark:bg-[#1f2026]">
      <span className="min-w-0">
        <span className="block truncate text-xs font-bold text-[#202128] dark:text-[#e4e4e8]">📦 Order #{order.order_number}</span>
        <span className="block text-[10px] text-[#92939d]">{order.status}</span>
      </span>
      <span className="shrink-0 text-xs font-extrabold text-[#202128] dark:text-[#e4e4e8]">{order.currency_code} {order.total}</span>
    </span>
  );
  return href ? (
    <a href={href} target="_blank" rel="noreferrer" className="block">{inner}</a>
  ) : inner;
}

function Attachment({ message, mine }) {
  const attachment = message.attachment;
  const [zoomed, setZoomed] = useState(false);
  useEffect(() => {
    if (!zoomed) return undefined;
    const onKey = (event) => { if (event.key === "Escape") setZoomed(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoomed]);
  if (message.kind === "order") return <OrderCard order={message.order} />;
  if (!attachment) return null;
  if (message.kind === "image") {
    // A modal keeps the merchant inside the inbox; a new tab loses their place.
    return (
      <>
        <button type="button" onClick={() => setZoomed(true)} className="mt-1 block" aria-label="Open photo">
          <img src={attachment.url} alt={attachment.name || "Photo"} className="max-h-56 w-full rounded-xl object-cover" />
        </button>
        {zoomed ? (
          <div
            role="dialog"
            aria-modal="true"
            aria-label={attachment.name || "Photo"}
            onClick={() => setZoomed(false)}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4"
          >
            <img src={attachment.url} alt={attachment.name || "Photo"} className="max-h-full max-w-full rounded-xl" />
          </div>
        ) : null}
      </>
    );
  }
  if (message.kind === "voice") {
    return (
      <div className="mt-1">
        <audio controls preload="metadata" src={attachment.url} className="h-9 w-56 max-w-full" />
        {attachment.duration_ms ? <p className="mt-0.5 text-[10px] opacity-70">{formatDuration(attachment.duration_ms)}</p> : null}
      </div>
    );
  }
  return (
    <a href={attachment.url} target="_blank" rel="noreferrer" className="mt-1 flex items-center gap-2 rounded-xl bg-black/5 px-2.5 py-2 text-xs font-semibold">
      <FileText size={14} />
      <span className="min-w-0 flex-1 truncate">{attachment.name || "Attachment"}</span>
      {attachment.byte_size ? <span className="opacity-70">{formatBytes(attachment.byte_size)}</span> : null}
    </a>
  );
}

// A message body with its URLs and phone numbers turned into links. Plain runs
// stay text, so nothing a customer typed is ever interpreted as markup.
function MessageText({ body, linkClass }) {
  const segments = linkify(body);
  if (segments.length === 1 && segments[0].type === "text") {
    return <p className="whitespace-pre-wrap break-words">{body}</p>;
  }
  return (
    <p className="whitespace-pre-wrap break-words">
      {segments.map((segment, index) =>
        segment.type === "link" ? (
          <a key={index} href={segment.href} target="_blank" rel="noopener noreferrer" className={`underline ${linkClass}`}>
            {segment.value}
          </a>
        ) : (
          <span key={index}>{segment.value}</span>
        )
      )}
    </p>
  );
}

function MessageBubble({ message, onReact, showSeen = false }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const mine = message.sender_type === "seller";
  const reactions = message.reactions || [];
  return (
    <div className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      {message.author_name ? <p className="mb-0.5 px-1 text-[10px] font-semibold text-[#92939d]">{message.author_name}</p> : null}
      <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-[13px] leading-5 shadow-sm ${mine ? "bg-[#6957f5] text-white" : "border border-[#e9e9ef] bg-white text-[#34353d] dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-[#e4e4e8]"}`}>
        {message.body ? <MessageText body={message.body} linkClass={mine ? "text-white" : "text-[#6957f5]"} /> : null}
        <Attachment message={message} mine={mine} />
        <p className={`mt-1 text-[10px] ${mine ? "text-white/70" : "text-[#92939d]"}`}>
          {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
      {showSeen ? <p className="mt-0.5 px-1 text-[10px] font-semibold text-[#92939d]">Seen</p> : null}
      <div className="mt-1 flex flex-wrap items-center gap-1">
        {reactions.map((reaction) => (
          <button
            key={reaction.emoji}
            type="button"
            onClick={() => onReact(message, reaction.emoji)}
            className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${reaction.reacted ? "border-[#6957f5] bg-[#f0efff] text-[#6957f5]" : "border-[#e9e9ef] text-[#92939d] dark:border-[#2a2b30]"}`}
          >
            <span>{reaction.emoji}</span>
            <span className="font-bold">{reaction.count}</span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => setPickerOpen((value) => !value)}
          aria-label="React to this message"
          className="rounded-full border border-[#e9e9ef] px-1.5 py-0.5 text-[11px] text-[#92939d] dark:border-[#2a2b30]"
        >
          ＋
        </button>
        {pickerOpen ? (
          <span className="flex items-center gap-0.5 rounded-full border border-[#e9e9ef] bg-white px-1.5 py-0.5 dark:border-[#2a2b30] dark:bg-[#1f2026]">
            {QUICK_EMOJI.map((emoji) => (
              <button key={emoji} type="button" onClick={() => { setPickerOpen(false); onReact(message, emoji); }} className="px-0.5 text-sm hover:scale-125">
                {emoji}
              </button>
            ))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ThreadComposer({ busy, onSendText, onSendAttachment, cannedReplies = [], onCreateCanned, onDeleteCanned, orders = [], onSendOrder }) {
  const [draft, setDraft] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [cannedOpen, setCannedOpen] = useState(false);
  const [ordersOpen, setOrdersOpen] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);
  const { recording, seconds, voiceError, supported, start, stop, cancel } = useVoiceRecorder((file, durationMs) => {
    onSendAttachment({ kind: "voice", file, durationMs });
  });

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setEmojiOpen(false);
    onSendText(text);
  };

  if (recording) {
    return (
      <div className="flex items-center gap-3 border-t border-[#e9e9ef] bg-white px-4 py-3 dark:border-[#2a2b30] dark:bg-[#1a1b1f]">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#c2564b]" />
        <span className="text-xs font-bold text-[#34353d] dark:text-[#e4e4e8]">Recording {formatDuration(seconds * 1000)}</span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={cancel}>Cancel</Button>
          <button
            type="button"
            onClick={stop}
            aria-label="Send voice note"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#6957f5] text-white"
          >
            <Square size={13} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-[#e9e9ef] bg-white px-3 py-2.5 dark:border-[#2a2b30] dark:bg-[#1a1b1f]">
      {localError || voiceError ? <p className="pb-1 text-[11px] font-semibold text-[#c2564b]">{localError || voiceError}</p> : null}
      {cannedOpen ? (
        <div className="mb-1.5 rounded-xl border border-[#e9e9ef] bg-white p-2 dark:border-[#2a2b30] dark:bg-[#1f2026]">
          <p className="px-1 pb-1 text-[10px] font-bold uppercase tracking-wide text-[#92939d]">Quick replies</p>
          {cannedReplies.length === 0 ? (
            <p className="px-1 py-2 text-[11px] text-[#92939d]">Save a reply below to reuse it.</p>
          ) : (
            <ul className="max-h-48 overflow-y-auto">
              {cannedReplies.map((item) => (
                <li key={item.id} className="flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-[#f5f5f8] dark:hover:bg-[#2a2b30]">
                  <button
                    type="button"
                    onClick={() => { setDraft((value) => (value ? `${value} ` : "") + item.body); setCannedOpen(false); }}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="block truncate text-xs font-bold text-[#202128] dark:text-[#e4e4e8]">{item.label}</span>
                    <span className="block truncate text-[10px] text-[#92939d]">{item.body}</span>
                  </button>
                  <button type="button" aria-label={`Delete ${item.label}`} onClick={() => onDeleteCanned?.(item.id)} className="p-1 text-[#b0b1ba] hover:text-[#c2564b]">
                    <Trash2 size={12} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-1 flex items-center gap-1.5 border-t border-[#f1f1f5] pt-1.5 dark:border-[#2a2b30]">
            <input
              value={newLabel}
              onChange={(event) => setNewLabel(event.target.value)}
              maxLength={60}
              placeholder="Label for this reply"
              className="h-7 min-w-0 flex-1 rounded-lg border border-[#e9e9ef] px-2 text-[11px] outline-none dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-white"
            />
            <Button
              variant="soft"
              size="xs"
              disabled={!draft.trim() || !newLabel.trim()}
              onClick={() => { onCreateCanned?.(newLabel.trim(), draft.trim()); setNewLabel(""); }}
            >
              Save draft
            </Button>
          </div>
        </div>
      ) : null}
      {ordersOpen ? (
        <div className="mb-1.5 rounded-xl border border-[#e9e9ef] bg-white p-2 dark:border-[#2a2b30] dark:bg-[#1f2026]">
          <p className="px-1 pb-1 text-[10px] font-bold uppercase tracking-wide text-[#92939d]">Recent orders</p>
          {orders.length === 0 ? (
            <p className="px-1 py-2 text-[11px] text-[#92939d]">No recent orders to send.</p>
          ) : (
            <ul className="max-h-48 overflow-y-auto">
              {orders.map((order) => (
                <li key={order.id}>
                  <button
                    type="button"
                    onClick={() => { onSendOrder?.(order.id); setOrdersOpen(false); }}
                    className="flex w-full items-center justify-between gap-2 rounded-lg px-1 py-1 text-left hover:bg-[#f5f5f8] dark:hover:bg-[#2a2b30]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-bold text-[#202128] dark:text-[#e4e4e8]">
                        #{order.order_number} · {order.customer_name || "Walk-in"}
                      </span>
                      <span className="block text-[10px] text-[#92939d]">{order.status}</span>
                    </span>
                    <span className="shrink-0 text-[11px] font-extrabold text-[#202128] dark:text-[#e4e4e8]">{order.currency_code} {order.total}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
      <form
        onSubmit={(event) => { event.preventDefault(); submit(); }}
        className="flex items-end gap-1.5 rounded-2xl border border-[#e9e9ef] px-2 py-1.5 dark:border-[#2a2b30]"
      >
        <button type="button" onClick={() => setCannedOpen((value) => !value)} aria-label="Quick replies" className="p-1 text-[#92939d] hover:text-[#6957f5]">
          <Bolt size={17} />
        </button>
        <button type="button" onClick={() => setOrdersOpen((value) => !value)} aria-label="Send an order" className="p-1 text-[#92939d] hover:text-[#6957f5]">
          <Package size={17} />
        </button>
        <button type="button" onClick={() => setEmojiOpen((value) => !value)} aria-label="Emoji" className="p-1 text-[#92939d] hover:text-[#6957f5]">
          <Smile size={17} />
        </button>
        <button type="button" onClick={() => fileRef.current?.click()} aria-label="Attach a file" className="p-1 text-[#92939d] hover:text-[#6957f5]">
          <Paperclip size={17} />
        </button>
        {supported ? (
          <button type="button" onClick={start} aria-label="Record a voice note" className="p-1 text-[#92939d] hover:text-[#6957f5]">
            <Mic size={17} />
          </button>
        ) : null}
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          rows={1}
          placeholder="Write a reply…"
          className="max-h-28 min-h-7 flex-1 resize-none bg-transparent px-1 py-1 text-sm text-[#202128] outline-none dark:text-[#e4e4e8]"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          aria-label="Send"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#6957f5] text-white disabled:opacity-40"
        >
          <Send size={15} />
        </button>
      </form>
      {emojiOpen ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {QUICK_EMOJI.map((emoji) => (
            <button key={emoji} type="button" onClick={() => { setDraft((value) => value + emoji); setEmojiOpen(false); }} className="text-lg hover:scale-125">
              {emoji}
            </button>
          ))}
        </div>
      ) : null}
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED_FILES}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          if (file.size > MAX_ATTACHMENT_BYTES) {
            setLocalError("That file is larger than 5 MB.");
            return;
          }
          setLocalError("");
          onSendAttachment({ kind: kindForFile(file), file });
        }}
      />
    </div>
  );
}

// The store's chat inbox: the customer threads on the left, one thread on the
// right. A customer can already write from the storefront, so this is where the
// reply happens.
export function LiveInboxView({ token, storeId, notify, chatSound = false, onNotificationsRead, currentUserId, stores = [], onSwitchStore }) {
  const [conversations, setConversations] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("open");
  const [search, setSearch] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [cannedReplies, setCannedReplies] = useState([]);
  const [orders, setOrders] = useState([]);
  const [notesDraft, setNotesDraft] = useState("");
  const [unreadByStore, setUnreadByStore] = useState({});
  // The context panel starts open and can be folded away; it only renders on the
  // widest screens, so narrower layouts are unaffected.
  const [detailsOpen, setDetailsOpen] = useState(true);

  const messagesRef = useRef([]);
  const activeRef = useRef(null);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { activeRef.current = active; }, [active]);

  // Quick replies are the store's saved answers; load them once for the picker.
  useEffect(() => {
    if (!token || !storeId) return undefined;
    let active = true;
    api.storeChatCannedReplies(token, storeId)
      .then((rows) => { if (active) setCannedReplies(Array.isArray(rows) ? rows : []); })
      .catch(() => { /* the picker stays empty until one is saved */ });
    return () => { active = false; };
  }, [token, storeId]);

  // Recent orders, for the "send an order" picker.
  useEffect(() => {
    if (!token || !storeId) return undefined;
    let active = true;
    api.orders(token, storeId, { limit: 20 })
      .then((rows) => { if (active) setOrders(Array.isArray(rows) ? rows : []); })
      .catch(() => { /* the picker stays empty */ });
    return () => { active = false; };
  }, [token, storeId]);

  // Which of the user's stores are waiting on a reply. Only worthwhile when there
  // is more than one store to choose from; each store answers with a single cheap
  // counter, so the switcher can badge them without opening any thread. A failed
  // count just leaves that store unbadged rather than breaking the list.
  useEffect(() => {
    if (!token || stores.length < 2) return undefined;
    let cancelled = false;
    const load = () => {
      Promise.allSettled(stores.map((store) => api.storeChatUnreadCount(token, store.id))).then((results) => {
        if (cancelled) return;
        const next = {};
        results.forEach((result, index) => {
          if (result.status === "fulfilled") next[stores[index].id] = result.value?.unread || 0;
        });
        setUnreadByStore(next);
      });
    };
    load();
    const timer = window.setInterval(load, LIST_POLL_MS);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [token, stores]);

  const loadList = useCallback(async (options = {}) => {
    try {
      const rows = await api.storeChatConversations(token, storeId, {
        status: filter === "all" ? undefined : filter,
        q: search.trim() || undefined,
      });
      if (options.silent) {
        setConversations((previous) => {
          const unreadById = new Map(previous.map((item) => [item.id, item.unread_count]));
          return (Array.isArray(rows) ? rows : []).map((item) => ({ ...item, unread_count: item.unread_count ?? unreadById.get(item.id) ?? 0 }));
        });
      } else {
        setConversations(Array.isArray(rows) ? rows : []);
      }
      setError("");
    } catch (loadError) {
      if (!options.silent) setError(loadError.message || "Could not load conversations");
    } finally {
      setLoading(false);
    }
  }, [token, storeId, filter, search]);

  useEffect(() => {
    setLoading(true);
    const timer = window.setTimeout(() => { loadList(); }, search ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [loadList, search]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden || activeRef.current) return;
      loadList({ silent: true });
    }, LIST_POLL_MS);
    return () => window.clearInterval(timer);
  }, [loadList]);

  const handleIncoming = useCallback((conversationId, message) => {
    if (!conversationId || !message) return;
    // A counter merchant will not watch the badge; an opt-in chime is the nudge.
    if (chatSound && message.sender_type === "customer") playChatChime();
    if (activeRef.current?.id === conversationId) {
      setMessages((previous) => mergeMessages(previous, [message]));
      if (message.sender_type === "customer") {
        api.storeChatMarkRead(token, storeId, conversationId).then(() => onNotificationsRead?.()).catch(() => {});
      }
      setConversations((previous) =>
        previous.map((item) => (item.id === conversationId ? { ...item, unread_count: 0, last_message_preview: message.body || item.last_message_preview, last_message_at: message.created_at } : item))
      );
      return;
    }
    setConversations((previous) => {
      const found = previous.find((item) => item.id === conversationId);
      if (!found) return previous;
      const bumped = {
        ...found,
        unread_count: message.sender_type === "customer" ? (found.unread_count || 0) + 1 : found.unread_count || 0,
        last_message_preview: message.body || found.last_message_preview,
        last_message_at: message.created_at,
      };
      return [bumped, ...previous.filter((item) => item.id !== conversationId)];
    });
  }, [token, storeId, chatSound, onNotificationsRead]);

  // Live updates arrive on one store-wide stream, so a new thread or a reply in a
  // thread that is not on screen still updates the list.
  useEffect(() => {
    if (!token || !storeId) return undefined;
    const controller = new AbortController();
    let stopped = false;
    const run = async () => {
      while (!stopped && !document.hidden) {
        try {
          const response = await fetch(`${api.baseUrl}/store-chat/stream?after_seq=${highestSeq(messagesRef.current)}`, {
            headers: { Authorization: `Bearer ${token}`, "X-Store-ID": storeId, Accept: "text/event-stream" },
            signal: controller.signal,
          });
          if (!response.ok || !response.body) throw new Error("stream unavailable");
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const { events, rest } = parseSseChunk(buffer);
            buffer = rest;
            for (const event of events) {
              if (event.event !== "message" || !event.data) continue;
              try {
                const payload = JSON.parse(event.data);
                handleIncoming(payload?.conversation_id, payload?.message);
              } catch {
                // A malformed frame is dropped rather than killing the stream.
              }
            }
          }
        } catch (streamError) {
          if (streamError?.name === "AbortError" || stopped) return;
        }
        if (stopped) return;
        await new Promise((resolve) => window.setTimeout(resolve, 2500));
      }
    };
    run();
    return () => { stopped = true; controller.abort(); };
  }, [token, storeId, handleIncoming]);

  // The stream is the fast path; this is the safety net for a blocked or broken
  // connection, and it also refreshes the list around the open thread.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      if (activeRef.current) {
        api.storeChatThread(token, storeId, activeRef.current.id)
          .then((thread) => {
            if (!thread || activeRef.current?.id !== thread.id) return;
            setMessages(thread.messages || []);
            setHasMore(Boolean(thread.has_more));
            setActive(thread);
          })
          .catch(() => {});
      }
    }, THREAD_POLL_MS);
    return () => window.clearInterval(timer);
  }, [token, storeId]);

  const openConversation = async (conversation) => {
    setActive(conversation);
    setMessages([]);
    setConversations((previous) => previous.map((item) => (item.id === conversation.id ? { ...item, unread_count: 0 } : item)));
    try {
      const thread = await api.storeChatThread(token, storeId, conversation.id);
      if (thread) {
        setActive(thread);
        setMessages(thread.messages || []);
        setHasMore(Boolean(thread.has_more));
        setNotesDraft(thread.internal_notes || "");
        // Opening the thread clears its notification server-side; drop it from the bell.
        onNotificationsRead?.();
      }
    } catch (openError) {
      setError(openError.message || "Could not open the conversation");
    }
  };

  const appendSent = (result) => {
    if (!result?.message) return;
    setMessages((previous) => mergeMessages(previous, [result.message]));
    setConversations((previous) =>
      previous.map((item) => (item.id === result.conversation?.id ? { ...item, ...result.conversation, unread_count: 0 } : item))
    );
    // A reply settles the thread, so its notification should leave the bell.
    onNotificationsRead?.();
  };

  const sendText = async (text) => {
    if (!active) return;
    setBusy(true);
    try {
      appendSent(await api.storeChatReply(token, storeId, active.id, { kind: "text", body: text }));
    } catch (sendError) {
      notify?.(sendError.message || "Could not send the reply");
    } finally {
      setBusy(false);
    }
  };

  const sendOrder = async (orderId) => {
    if (!active) return;
    setBusy(true);
    try {
      appendSent(await api.storeChatReply(token, storeId, active.id, { kind: "order", order_id: orderId }));
    } catch (sendError) {
      notify?.(sendError.message || "Could not send the order");
    } finally {
      setBusy(false);
    }
  };

  const sendAttachment = async ({ kind, file, durationMs }) => {
    if (!active) return;
    setBusy(true);
    try {
      const uploaded = await api.storeChatUpload(token, storeId, active.id, file);
      if (!uploaded) return;
      appendSent(await api.storeChatReply(token, storeId, active.id, {
        kind: uploaded.kind || kind,
        attachment_url: uploaded.url,
        attachment_name: uploaded.original_filename,
        attachment_content_type: uploaded.content_type || file.type,
        attachment_byte_size: uploaded.byte_size,
        attachment_duration_ms: durationMs ?? null,
      }));
    } catch (sendError) {
      notify?.(sendError.message || "Could not send the attachment");
    } finally {
      setBusy(false);
    }
  };

  const react = async (message, emoji) => {
    if (!active) return;
    try {
      const updated = await api.storeChatReact(token, storeId, active.id, message.id, emoji);
      if (updated) setMessages((previous) => mergeMessages(previous, [updated]));
    } catch {
      // A failed reaction is not worth an error banner.
    }
  };

  const toggleStatus = async () => {
    if (!active) return;
    try {
      const next = active.status === "closed" ? "open" : "closed";
      const updated = await api.storeChatSetStatus(token, storeId, active.id, next);
      setActive((previous) => ({ ...previous, ...updated }));
      setConversations((previous) => previous.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
    } catch (statusError) {
      notify?.(statusError.message || "Could not change the status");
    }
  };

  const applyUpdate = async (patch) => {
    if (!active) return;
    try {
      const updated = await api.storeChatUpdate(token, storeId, active.id, patch);
      setActive((previous) => ({ ...previous, ...updated }));
      setConversations((previous) => previous.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
    } catch (updateError) {
      notify?.(updateError.message || "Could not update the conversation");
    }
  };

  const toggleClaim = () => applyUpdate({ assigned_user_id: active?.assigned_user_id ? null : currentUserId });
  const saveNotes = () => applyUpdate({ internal_notes: notesDraft });

  const startRename = () => {
    setNameDraft(active?.seller_label || "");
    setRenaming(true);
  };

  const saveRename = async () => {
    if (!active) return;
    const label = nameDraft.trim();
    setRenaming(false);
    try {
      const updated = await api.storeChatUpdate(token, storeId, active.id, { seller_label: label });
      setActive((previous) => ({ ...previous, ...updated }));
      setConversations((previous) => previous.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
    } catch (renameError) {
      notify?.(renameError.message || "Could not rename the conversation");
    }
  };

  const loadEarlier = async () => {
    const oldest = messages[0]?.seq;
    if (oldest == null || !active || loadingEarlier) return;
    setLoadingEarlier(true);
    try {
      const page = await api.storeChatThread(token, storeId, active.id, { before_seq: oldest });
      if (page?.messages?.length) setMessages((previous) => mergeMessages(page.messages, previous));
      setHasMore(Boolean(page?.has_more));
    } catch (loadError) {
      notify?.(loadError.message || "Could not load earlier messages");
    } finally {
      setLoadingEarlier(false);
    }
  };

  const createCanned = async (label, body) => {
    try {
      const created = await api.storeChatCannedReplyCreate(token, storeId, { label, body });
      if (created) setCannedReplies((previous) => [...previous, created]);
    } catch (cannedError) {
      notify?.(cannedError.message || "Could not save the quick reply");
    }
  };

  const deleteCanned = async (id) => {
    try {
      await api.storeChatCannedReplyDelete(token, storeId, id);
      setCannedReplies((previous) => previous.filter((item) => item.id !== id));
    } catch (cannedError) {
      notify?.(cannedError.message || "Could not delete the quick reply");
    }
  };

  const total = useMemo(() => unreadTotal(conversations), [conversations]);
  const lastOwnIndex = messages.reduce((last, message, index) => (message.sender_type === "seller" ? index : last), -1);
  const storeOptions = useMemo(() => storeSwitcherOptions(stores, unreadByStore), [stores, unreadByStore]);
  const contacts = useMemo(() => contactRows(active), [active]);
  const sharedOrders = useMemo(() => threadOrders(messages), [messages]);

  return (
    <div className="flex h-[calc(100vh-74px)] min-h-[560px] flex-col overflow-hidden md:flex-row">
      <aside className={`w-full shrink-0 flex-col border-r border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1a1b1f] md:flex md:w-[330px] ${active ? "hidden md:flex" : "flex"}`}>
        <div className="border-b border-[#e9e9ef] px-4 py-3 dark:border-[#2a2b30]">
          {storeOptions.length > 1 ? (
            <div className="mb-3">
              <Dropdown
                value={storeId || ""}
                onChange={(next) => onSwitchStore?.(next)}
                options={storeOptions}
                placeholder="Select store"
                triggerClass="h-10 w-full rounded-xl border border-[#e9e9ef] bg-white px-3 text-xs font-bold text-[#202128] dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-[#e4e4e8]"
              />
            </div>
          ) : null}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">Messages</h2>
            {total > 0 ? <Badge tone="violet">{total} new</Badge> : null}
          </div>
          <div className="mt-2 flex gap-1 rounded-xl bg-[#f3f3f6] p-1 dark:bg-[#26272d]">
            {[["open", "Open"], ["closed", "Closed"], ["all", "All"]].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`flex-1 rounded-lg px-2 py-1 text-[11px] font-bold ${filter === value ? "bg-white text-[#202128] shadow-sm dark:bg-[#1f2026] dark:text-white" : "text-[#92939d]"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name or message"
            className="mt-2 h-9 w-full rounded-xl border border-[#e9e9ef] px-3 text-xs outline-none dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-white"
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading ? (
            <p className="p-6 text-center text-xs text-[#92939d]">Loading…</p>
          ) : error ? (
            <p className="p-6 text-center text-xs font-semibold text-[#c2564b]">{error}</p>
          ) : conversations.length === 0 ? (
            <p className="p-6 text-center text-xs text-[#92939d]">No conversations yet.</p>
          ) : (
            <ul>
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <button
                    type="button"
                    onClick={() => openConversation(conversation)}
                    className={`flex w-full items-start gap-3 border-b border-[#f1f1f5] px-4 py-3 text-left transition hover:bg-[#fafafd] dark:border-[#26272d] dark:hover:bg-[#1f2026] ${active?.id === conversation.id ? "bg-[#f0efff] dark:bg-[#262550]" : ""}`}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#e9e9ef] text-[11px] font-extrabold text-[#34353d] dark:bg-[#2a2b30] dark:text-[#e4e4e8]">
                      {conversationLabel(conversation).slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-xs font-bold text-[#202128] dark:text-[#e4e4e8]">{conversationLabel(conversation)}</span>
                        {isSignedInCustomer(conversation) ? <span className="shrink-0 rounded bg-[#f0efff] px-1 text-[9px] font-bold text-[#6957f5]">account</span> : null}
                        <span className="ml-auto shrink-0 text-[10px] text-[#92939d]">{relativeTime(conversation.last_message_at)}</span>
                      </span>
                      <span className="mt-0.5 block truncate text-[11px] text-[#7c7d87] dark:text-[#92939d]">{conversation.last_message_preview || "No messages yet"}</span>
                    </span>
                    {conversation.unread_count ? (
                      <span className="mt-0.5 flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[#6957f5] px-1 text-[10px] font-extrabold text-white">
                        {conversation.unread_count}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <section className={`min-w-0 flex-1 flex-col bg-[#fafafd] dark:bg-[#111114] ${active ? "flex" : "hidden md:flex"}`}>
        {active ? (
          <>
            <header className="flex items-center gap-3 border-b border-[#e9e9ef] bg-white px-4 py-3 dark:border-[#2a2b30] dark:bg-[#1a1b1f]">
              <button type="button" onClick={() => setActive(null)} aria-label="Back to conversations" className="p-1 text-[#92939d] hover:text-[#202128] md:hidden">
                <ArrowLeft size={17} />
              </button>
              <div className="min-w-0 flex-1">
                {renaming ? (
                  <input
                    autoFocus
                    value={nameDraft}
                    onChange={(event) => setNameDraft(event.target.value)}
                    onBlur={saveRename}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") { event.preventDefault(); saveRename(); }
                      if (event.key === "Escape") { setRenaming(false); }
                    }}
                    maxLength={120}
                    placeholder="Name this conversation"
                    aria-label="Conversation name"
                    className="h-7 w-full max-w-[260px] rounded-lg border border-[#e9e9ef] px-2 text-sm font-bold text-[#202128] outline-none dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-white"
                  />
                ) : (
                  <button type="button" onClick={startRename} title="Rename this conversation" className="group flex min-w-0 items-center gap-1.5 text-left">
                    <span className="truncate text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">{conversationLabel(active)}</span>
                    <Pencil size={12} className="shrink-0 text-[#b0b1ba] opacity-0 transition group-hover:opacity-100" />
                  </button>
                )}
                <p className="text-[11px] text-[#92939d]">
                  {active.store_name}
                  {active.status === "closed" ? " · closed" : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDetailsOpen((value) => !value)}
                aria-label="Toggle thread details"
                aria-pressed={detailsOpen}
                className={`hidden p-1 transition xl:inline-flex ${detailsOpen ? "text-[#6957f5]" : "text-[#92939d] hover:text-[#6957f5]"}`}
              >
                <Info size={17} />
              </button>
              <Button variant="outline" size="sm" onClick={toggleStatus}>
                {active.status === "closed" ? "Reopen" : "Close"}
              </Button>
            </header>
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
                {hasMore ? (
                  <div className="flex justify-center pb-1">
                    <Button variant="outline" size="xs" onClick={loadEarlier} disabled={loadingEarlier}>
                      {loadingEarlier ? "Loading…" : "Load earlier"}
                    </Button>
                  </div>
                ) : null}
                {messages.length === 0 ? <p className="py-10 text-center text-xs text-[#92939d]">No messages in this thread yet.</p> : null}
                {messages.map((message, index) => (
                  <MessageBubble key={message.id} message={message} onReact={react} showSeen={index === lastOwnIndex && Boolean(message.seen)} />
                ))}
              </div>
              <ThreadComposer
                busy={busy}
                onSendText={sendText}
                onSendAttachment={sendAttachment}
                cannedReplies={cannedReplies}
                onCreateCanned={createCanned}
                onDeleteCanned={deleteCanned}
                orders={orders}
                onSendOrder={sendOrder}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center p-10 text-center text-sm text-[#92939d]">
            Pick a conversation to reply.
          </div>
        )}
      </section>

      {active && detailsOpen ? (
        <aside className="hidden w-[300px] shrink-0 flex-col overflow-y-auto border-l border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1a1b1f] xl:flex">
          <div className="border-b border-[#e9e9ef] px-4 py-3 dark:border-[#2a2b30]">
            <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#92939d]">Customer</p>
            <div className="mt-3 flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e9e9ef] text-xs font-extrabold text-[#34353d] dark:bg-[#2a2b30] dark:text-[#e4e4e8]">
                {conversationLabel(active).slice(0, 2).toUpperCase()}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-[#202128] dark:text-[#e4e4e8]">{conversationLabel(active)}</p>
                <p className="text-[11px] text-[#92939d]">{isSignedInCustomer(active) ? "Signed-in customer" : "Guest"}</p>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-[#92939d]">{active.store_name}</p>
            {contacts.length ? (
              <div className="mt-3 space-y-1.5">
                {contacts.map((row) => (
                  <a key={row.label} href={row.href} className="block text-xs font-semibold text-[#6957f5] hover:underline">
                    <span className="mr-1 text-[10px] uppercase tracking-wide text-[#92939d]">{row.label}</span>
                    {row.value}
                  </a>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-[11px] text-[#b0b1ba]">No contact details shared.</p>
            )}
          </div>

          <div className="border-b border-[#e9e9ef] px-4 py-3 dark:border-[#2a2b30]">
            <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#92939d]">Thread</p>
            <dl className="mt-3 space-y-2 text-xs">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[#92939d]">Status</dt>
                <dd className="font-semibold text-[#202128] dark:text-[#e4e4e8]">{active.status === "closed" ? "Closed" : "Open"}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[#92939d]">Unread</dt>
                <dd className="font-semibold text-[#202128] dark:text-[#e4e4e8]">{active.unread_count || 0}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[#92939d]">Opened</dt>
                <dd className="font-semibold text-[#202128] dark:text-[#e4e4e8]">{new Date(active.created_at).toLocaleDateString()}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[#92939d]">Last activity</dt>
                <dd className="font-semibold text-[#202128] dark:text-[#e4e4e8]">{active.last_message_at ? relativeTime(active.last_message_at) : "—"}</dd>
              </div>
            </dl>
          </div>

          <div className="border-b border-[#e9e9ef] px-4 py-3 dark:border-[#2a2b30]">
            <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#92939d]">Handling</p>
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="min-w-0 truncate text-xs font-semibold text-[#202128] dark:text-[#e4e4e8]">
                {active.assigned_user_name ? active.assigned_user_name : "Nobody yet"}
              </p>
              <Button variant="outline" size="xs" onClick={toggleClaim} disabled={!currentUserId}>
                {active.assigned_user_id ? "Release" : "Claim"}
              </Button>
            </div>
            <textarea
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Internal note — the customer never sees this"
              className="mt-3 w-full resize-none rounded-lg border border-[#e9e9ef] bg-white px-2 py-1.5 text-xs text-[#202128] outline-none dark:border-[#2a2b30] dark:bg-[#1f2026] dark:text-white"
            />
            <div className="mt-1 flex justify-end">
              <Button variant="soft" size="xs" onClick={saveNotes}>Save note</Button>
            </div>
          </div>

          <div className="px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#92939d]">Orders in this chat</p>
            {sharedOrders.length === 0 ? (
              <p className="mt-3 text-[11px] text-[#b0b1ba]">No orders shared yet.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {sharedOrders.map((order) => (
                  <li key={order.id} className="rounded-xl border border-[#e9e9ef] px-3 py-2 dark:border-[#2a2b30]">
                    <p className="text-xs font-bold text-[#202128] dark:text-[#e4e4e8]">#{order.order_number}</p>
                    <p className="text-[10px] text-[#92939d]">{order.status}</p>
                    <p className="text-xs font-extrabold text-[#202128] dark:text-[#e4e4e8]">{order.currency_code} {order.total}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      ) : null}
    </div>
  );
}

export default LiveInboxView;
