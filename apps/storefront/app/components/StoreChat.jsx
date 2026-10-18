import { useCallback, useEffect, useRef, useState } from "react";

import {
  chatHeaders,
  chatStreamUrl,
  fetchChatMessages,
  fetchChatSession,
  markChatRead,
  reactToChatMessage,
  sendChatMessage,
  uploadChatFile,
} from "../lib/api";
import { clearChatRecord, readChatRecord, streamChatEvents, writeChatRecord } from "../lib/chat";
import ChatThread from "./ChatThread";
import { ChatBubbleIcon, CloseIcon } from "./ChatIcons";

// The shopper's own sign-in token lives here, next to the account page's copy.
const SHOPPER_TOKEN_KEY = "chmaba.shopper_token";
// While the panel is shut the widget still checks for replies, but rarely: a
// closed chat is not worth a request every few seconds.
const CLOSED_POLL_MS = 20000;

function mergeMessages(existing, incoming) {
  const byId = new Map(existing.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return Array.from(byId.values()).sort((a, b) => a.seq - b.seq);
}

function highestSeq(messages) {
  return (messages || []).reduce((max, message) => Math.max(max, message.seq), 0);
}

function readShopperToken() {
  if (typeof window === "undefined") return null;
  try { return window.localStorage.getItem(SHOPPER_TOKEN_KEY) || null; } catch { return null; }
}

async function errorText(error) {
  if (error instanceof Response) {
    try { return (await error.text()) || "Could not send. Please try again."; } catch { /* fall through */ }
  }
  return "Could not send. Please try again.";
}

// A reply while the tab is in the background raises a desktop notification, but
// only once the shopper has messaged at least once - that gesture is what makes
// asking for permission polite.
function notifyInBackground(storeName, message) {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    if (!document.hidden) return;
    const body = message.body || (message.kind === "voice" ? "Voice message" : message.kind === "image" ? "Photo" : "New message");
    new Notification(storeName || "New message from the store", { body });
  } catch {
    // Notifications are a nicety; never let them break the chat.
  }
}

function requestNotificationPermission() {
  try {
    if (typeof Notification !== "undefined" && Notification.permission === "default") Notification.requestPermission();
  } catch {
    // Ignored.
  }
}

// The floating storefront chat: one thread between this visitor and the store,
// resumable across reloads with the visitor token the server hands back.
export default function StoreChat({ companySlug, storeSlug, storeName, isOpen }) {
  const [open, setOpen] = useState(false);
  const [hasConversation, setHasConversation] = useState(false);
  const [messages, setMessages] = useState([]);
  const [unread, setUnread] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [guestName, setGuestName] = useState("");

  const recordRef = useRef(null);
  const tokenRef = useRef(null);
  const afterSeqRef = useRef(0);

  const auth = useCallback(
    () => ({ token: tokenRef.current, chatToken: recordRef.current?.visitor_token }),
    []
  );

  const adopt = useCallback((session) => {
    if (!session?.conversation) return;
    const record = { visitor_token: session.visitor_token, guest_name: session.guest_name };
    recordRef.current = record;
    writeChatRecord(companySlug, storeSlug, record);
    if (record.guest_name) setGuestName(record.guest_name);
    setHasConversation(true);
  }, [companySlug, storeSlug]);

  // Load once, on mount: the browser cannot be read during the server render, so
  // this is the first moment the widget can know whether a thread exists.
  useEffect(() => {
    let active = true;
    tokenRef.current = readShopperToken();
    recordRef.current = readChatRecord(companySlug, storeSlug);
    if (recordRef.current?.guest_name) setGuestName(recordRef.current.guest_name);
    (async () => {
      try {
        const session = await fetchChatSession(companySlug, storeSlug, auth());
        if (!active) return;
        if (session?.conversation) {
          adopt(session);
          setMessages(session.messages || []);
          setUnread(session.unread_count || 0);
          afterSeqRef.current = highestSeq(session.messages);
        } else if (recordRef.current) {
          // A stored token the server no longer recognises: forget it rather than
          // keep sending a dead thread id.
          recordRef.current = null;
          clearChatRecord(companySlug, storeSlug);
        }
      } catch {
        // Offline or a transient failure: the widget still opens and retries.
      }
    })();
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companySlug, storeSlug]);

  // While the panel is closed, pick up replies so the badge is honest.
  useEffect(() => {
    if (open) return undefined;
    const timer = window.setInterval(async () => {
      if (document.hidden || !recordRef.current) return;
      try {
        const session = await fetchChatSession(companySlug, storeSlug, auth());
        if (!session?.conversation) return;
        setMessages(session.messages || []);
        setUnread(session.unread_count || 0);
        afterSeqRef.current = highestSeq(session.messages);
      } catch {
        // Ignore; the next tick retries.
      }
    }, CLOSED_POLL_MS);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, companySlug, storeSlug]);

  // While the panel is open, stream: the server keeps the connection alive with
  // heartbeats and asks for a reconnect before any proxy would time it out.
  useEffect(() => {
    if (!open || !hasConversation) return undefined;
    const controller = new AbortController();
    let stopped = false;
    const run = async () => {
      while (!stopped && !document.hidden) {
        try {
          await streamChatEvents({
            url: chatStreamUrl(companySlug, storeSlug, afterSeqRef.current),
            headers: chatHeaders(auth()),
            signal: controller.signal,
            onMessage: (payload) => {
              const message = payload?.message;
              if (!message) return;
              setMessages((previous) => mergeMessages(previous, [message]));
              afterSeqRef.current = Math.max(afterSeqRef.current, message.seq);
              if (message.sender_type === "seller") {
                setUnread(0);
                markChatRead(companySlug, storeSlug, auth()).catch(() => {});
                notifyInBackground(storeName, message);
              }
            },
          });
        } catch (streamError) {
          if (streamError?.name === "AbortError" || stopped) return;
        }
        if (stopped) return;
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
    };
    run();
    return () => { stopped = true; controller.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, hasConversation, companySlug, storeSlug, storeName]);

  const openPanel = () => {
    setOpen(true);
    setUnread(0);
    if (recordRef.current) markChatRead(companySlug, storeSlug, auth()).catch(() => {});
  };

  const remember = (result) => {
    if (!result) return;
    recordRef.current = { visitor_token: result.visitor_token, guest_name: result.conversation?.guest_name };
    writeChatRecord(companySlug, storeSlug, recordRef.current);
    if (result.conversation?.guest_name) setGuestName(result.conversation.guest_name);
    setHasConversation(true);
    setMessages((previous) => mergeMessages(previous, [result.message]));
    afterSeqRef.current = Math.max(afterSeqRef.current, result.message.seq);
  };

  const handleSendText = async (text) => {
    setBusy(true);
    setError("");
    try {
      const result = await sendChatMessage(
        companySlug,
        storeSlug,
        { kind: "text", body: text, name: guestName.trim() || undefined },
        auth()
      );
      remember(result);
      requestNotificationPermission();
    } catch (sendError) {
      setError(await errorText(sendError));
    } finally {
      setBusy(false);
    }
  };

  const handleSendAttachment = async ({ kind, file, durationMs }) => {
    setBusy(true);
    setError("");
    try {
      const uploaded = await uploadChatFile(companySlug, storeSlug, file, auth());
      if (!uploaded) throw new Response("Upload failed", { status: 400 });
      const result = await sendChatMessage(
        companySlug,
        storeSlug,
        {
          kind: uploaded.kind || kind,
          attachment_url: uploaded.url,
          attachment_name: uploaded.original_filename,
          attachment_content_type: uploaded.content_type || file.type,
          attachment_byte_size: uploaded.byte_size,
          attachment_duration_ms: durationMs ?? null,
          name: guestName.trim() || undefined,
        },
        auth()
      );
      remember(result);
      requestNotificationPermission();
    } catch (sendError) {
      setError(await errorText(sendError));
    } finally {
      setBusy(false);
    }
  };

  const handleReact = async (message, emoji) => {
    try {
      const updated = await reactToChatMessage(companySlug, storeSlug, message.id, emoji, auth());
      if (updated) setMessages((previous) => mergeMessages(previous, [updated]));
    } catch {
      // A failed reaction is not worth an error banner.
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={openPanel}
        aria-label="Chat with the store"
        className="fixed bottom-24 right-4 z-40 flex h-12 items-center gap-2 rounded-full bg-brand px-4 text-sm font-bold text-white shadow-[0_10px_30px_rgba(28,31,42,.28)] transition hover:opacity-95 sm:right-6"
      >
        <ChatBubbleIcon />
        <span>Chat with the store</span>
        {unread > 0 ? (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-white px-1 text-[10px] font-extrabold text-brand">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>
    );
  }

  return (
    <div className="fixed inset-x-0 bottom-0 top-16 z-50 flex flex-col border-t border-line bg-page shadow-[0_-12px_36px_rgba(28,31,42,.18)] sm:inset-auto sm:bottom-24 sm:right-6 sm:h-[560px] sm:w-[390px] sm:rounded-2xl sm:border">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3 sm:rounded-t-2xl">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-soft text-brand">
          <ChatBubbleIcon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-extrabold text-ink">{storeName || "Chat with the store"}</p>
          <p className="text-[11px] text-muted">
            {isOpen === false ? "Closed now — we'll reply when we open" : "Usually replies within a few minutes"}
          </p>
        </div>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close chat" className="p-1 text-muted transition hover:text-ink">
          <CloseIcon />
        </button>
      </header>

      {!hasConversation ? (
        <div className="border-b border-line bg-surface px-4 py-2">
          <input
            value={guestName}
            onChange={(event) => setGuestName(event.target.value)}
            maxLength={120}
            placeholder="Your name (optional)"
            aria-label="Your name"
            className="h-8 w-full rounded-lg border border-line bg-page px-2.5 text-xs text-ink outline-none placeholder:text-muted"
          />
        </div>
      ) : null}

      {error ? <p className="border-b border-line bg-danger-soft px-4 py-1.5 text-[11px] font-semibold text-danger">{error}</p> : null}

      <div className="min-h-0 flex-1">
        <ChatThread
          messages={messages}
          viewer="customer"
          busy={busy}
          onSendText={handleSendText}
          onSendAttachment={handleSendAttachment}
          onReact={handleReact}
          compact
          emptyText={`Ask ${storeName || "the store"} anything — about an item, delivery, or your order.`}
          footerText="Messages are shared with the store."
        />
      </div>
    </div>
  );
}
