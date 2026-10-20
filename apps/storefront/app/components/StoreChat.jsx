import { useCallback, useEffect, useRef, useState } from "react";

import {
  chatHeaders,
  chatStreamUrl,
  fetchChatMessages,
  fetchChatSession,
  fetchChatTyping,
  markChatRead,
  reactToChatMessage,
  sendChatMessage,
  sendChatTyping,
  uploadChatFile,
} from "../lib/api";
import { CHAT_OPEN_EVENT, clearChatRecord, readChatRecord, streamChatEvents, writeChatRecord } from "../lib/chat";
import { MOBILE_QUERY, launcherBottom, visibleViewportBox } from "../lib/viewport";
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

// Phones are treated as a full-screen sheet, and their visible area is smaller
// than the layout viewport: a floating browser toolbar sits over the bottom, and
// the keyboard covers more. Measuring the visual viewport is the only way to
// keep the composer on screen in every one of those states.
function useVisibleViewport() {
  const [state, setState] = useState({ mobile: false, box: null });
  useEffect(() => {
    const query = window.matchMedia?.(MOBILE_QUERY);
    const viewport = window.visualViewport;
    const update = () => {
      const nextMobile = query ? query.matches : window.innerWidth < 640;
      const nextBox = visibleViewportBox(viewport, window.innerHeight);
      // Scroll and keyboard events arrive in bursts; keep the previous state
      // unless something a shopper can see actually moved.
      setState((previous) => (
        previous.mobile === nextMobile &&
        previous.box?.top === nextBox?.top &&
        previous.box?.height === nextBox?.height
          ? previous
          : { mobile: nextMobile, box: nextBox }
      ));
    };
    update();
    query?.addEventListener?.("change", update);
    viewport?.addEventListener?.("resize", update);
    viewport?.addEventListener?.("scroll", update);
    window.addEventListener("resize", update);
    return () => {
      query?.removeEventListener?.("change", update);
      viewport?.removeEventListener?.("resize", update);
      viewport?.removeEventListener?.("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);
  return state;
}

// The floating storefront chat: one thread between this visitor and the store,
// resumable across reloads with the visitor token the server hands back.
//
// `hidden` is set while the cart sheet is expanded: the launcher sits above the
// cart bar, and on a phone it would otherwise float over the checkout fields.
export default function StoreChat({ companySlug, storeSlug, storeName, isOpen, hidden = false }) {
  const [open, setOpen] = useState(false);
  const [hasConversation, setHasConversation] = useState(false);
  const [messages, setMessages] = useState([]);
  const [unread, setUnread] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [guestName, setGuestName] = useState("");
  const [guestPhone, setGuestPhone] = useState("");
  const [guestEmail, setGuestEmail] = useState("");
  const [peerTyping, setPeerTyping] = useState(false);
  const typingSentRef = useRef(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  // While the existing thread is being looked up, do not show the guest form:
  // asking a returning shopper to type their details again (and potentially
  // starting a second thread) was the wrong first impression.
  const [checkingSession, setCheckingSession] = useState(true);

  const recordRef = useRef(null);
  const tokenRef = useRef(null);
  const afterSeqRef = useRef(0);
  const { mobile, box } = useVisibleViewport();

  const auth = useCallback(
    () => ({ token: tokenRef.current, chatToken: recordRef.current?.visitor_token }),
    []
  );

  const adopt = useCallback((session) => {
    if (!session?.conversation) return;
    const record = {
      visitor_token: session.visitor_token,
      guest_name: session.guest_name,
      guest_phone: recordRef.current?.guest_phone,
      guest_email: recordRef.current?.guest_email,
    };
    recordRef.current = record;
    writeChatRecord(companySlug, storeSlug, record);
    if (record.guest_name) setGuestName(record.guest_name);
    setHasConversation(true);
  }, [companySlug, storeSlug]);

  // A guest must leave a name and phone before opening a thread, so the store can
  // get back to them. A signed-in shopper already has an account, so this only
  // applies to a brand-new guest thread.
  const ensureContact = () => {
    if (!recordRef.current?.visitor_token && !tokenRef.current && (!guestName.trim() || !guestPhone.trim())) {
      setError("Please add your name and phone number so the store can get back to you.");
      return false;
    }
    return true;
  };

  // Load once, on mount: the browser cannot be read during the server render, so
  // this is the first moment the widget can know whether a thread exists.
  useEffect(() => {
    let active = true;
    tokenRef.current = readShopperToken();
    setSignedIn(Boolean(tokenRef.current));
    recordRef.current = readChatRecord(companySlug, storeSlug);
    if (recordRef.current?.guest_name) setGuestName(recordRef.current.guest_name);
    if (recordRef.current?.guest_phone) setGuestPhone(recordRef.current.guest_phone);
    if (recordRef.current?.guest_email) setGuestEmail(recordRef.current.guest_email);
    // A hung request must not leave the guest staring at "Checking…" forever:
    // after a few seconds the form is the better answer.
    const fallback = window.setTimeout(() => {
      if (active) setCheckingSession(false);
    }, 4000);
    (async () => {
      try {
        const session = await fetchChatSession(companySlug, storeSlug, auth());
        if (!active) return;
        if (session?.conversation) {
          adopt(session);
          setMessages(session.messages || []);
          setUnread(session.unread_count || 0);
          setHasMore(Boolean(session.has_more));
          afterSeqRef.current = highestSeq(session.messages);
        } else if (recordRef.current) {
          // A stored token the server no longer recognises: forget it rather than
          // keep sending a dead thread id.
          recordRef.current = null;
          clearChatRecord(companySlug, storeSlug);
        }
      } catch {
        // Offline or a transient failure: the widget still opens and retries.
      } finally {
        window.clearTimeout(fallback);
        if (active) setCheckingSession(false);
      }
    })();
    return () => {
      active = false;
      window.clearTimeout(fallback);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companySlug, storeSlug]);

  // On a phone the sheet covers the page, so the page underneath must not keep
  // scrolling behind it - that scroll is what used to push the composer off
  // screen. The scroll position is preserved because overflow is the only thing
  // changed; pinning the body would jump the shopper to the top on close.
  useEffect(() => {
    if (!open || !mobile) return undefined;
    const root = document.documentElement;
    const body = document.body;
    const previousRoot = root.style.overflow;
    const previousBody = body.style.overflow;
    root.style.overflow = "hidden";
    body.style.overflow = "hidden";
    return () => {
      root.style.overflow = previousRoot;
      body.style.overflow = previousBody;
    };
  }, [open, mobile]);

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

  // While the panel is open, ask whether the store is typing.
  useEffect(() => {
    if (!open || !hasConversation) return undefined;
    const timer = window.setInterval(async () => {
      if (document.hidden) return;
      try {
        const result = await fetchChatTyping(companySlug, storeSlug, auth());
        setPeerTyping(Boolean(result?.typing));
      } catch {
        // The next tick retries; typing is not worth an error banner.
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [open, hasConversation, companySlug, storeSlug, auth]);

  // Tell the store we are typing, at most every couple of seconds.
  const pingTyping = () => {
    if (!hasConversation || !recordRef.current) return;
    const now = Date.now();
    if (now - typingSentRef.current < 2000) return;
    typingSentRef.current = now;
    sendChatTyping(companySlug, storeSlug, auth()).catch(() => {});
  };

  // The store page's contact row offers a second chat entry point and cannot
  // reach this component's state, so it announces an open over the window.
  useEffect(() => {
    const handler = async (event) => {
      setOpen(true);
      setUnread(0);
      if (recordRef.current) markChatRead(companySlug, storeSlug, auth()).catch(() => {});
      // Opened from a product page: seed the thread with that product as a card.
      const productId = event?.detail?.productId;
      if (!productId) return;
      if (!ensureContact()) return;
      setBusy(true);
      setError("");
      try {
        const result = await sendChatMessage(
          companySlug,
          storeSlug,
          { kind: "product", product_id: productId, name: guestName.trim() || undefined, phone: guestPhone.trim() || undefined, email: guestEmail.trim() || undefined },
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
    window.addEventListener(CHAT_OPEN_EVENT, handler);
    return () => window.removeEventListener(CHAT_OPEN_EVENT, handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companySlug, storeSlug, guestName, guestPhone, guestEmail]);

  const openPanel = () => {
    setOpen(true);
    setUnread(0);
    if (recordRef.current) markChatRead(companySlug, storeSlug, auth()).catch(() => {});
  };

  const remember = (result) => {
    if (!result) return;
    recordRef.current = {
      visitor_token: result.visitor_token,
      guest_name: result.conversation?.guest_name || guestName.trim() || undefined,
      guest_phone: guestPhone.trim() || recordRef.current?.guest_phone || undefined,
      guest_email: guestEmail.trim() || recordRef.current?.guest_email || undefined,
    };
    writeChatRecord(companySlug, storeSlug, recordRef.current);
    if (result.conversation?.guest_name) setGuestName(result.conversation.guest_name);
    setHasConversation(true);
    setMessages((previous) => mergeMessages(previous, [result.message]));
    afterSeqRef.current = Math.max(afterSeqRef.current, result.message.seq);
  };

  const handleSendText = async (text) => {
    if (!ensureContact()) return false;
    setBusy(true);
    setError("");
    try {
      const result = await sendChatMessage(
        companySlug,
        storeSlug,
        { kind: "text", body: text, name: guestName.trim() || undefined, phone: guestPhone.trim() || undefined, email: guestEmail.trim() || undefined },
        auth()
      );
      remember(result);
      requestNotificationPermission();
      return true;
    } catch (sendError) {
      setError(await errorText(sendError));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleSendAttachment = async ({ kind, file, durationMs, caption }) => {
    if (!ensureContact()) return false;
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
          body: caption?.trim() || undefined,
          attachment_url: uploaded.url,
          attachment_name: uploaded.original_filename,
          attachment_content_type: uploaded.content_type || file.type,
          attachment_byte_size: uploaded.byte_size,
          attachment_duration_ms: durationMs ?? null,
          name: guestName.trim() || undefined,
          phone: guestPhone.trim() || undefined,
          email: guestEmail.trim() || undefined,
        },
        auth()
      );
      remember(result);
      requestNotificationPermission();
      return true;
    } catch (sendError) {
      setError(await errorText(sendError));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const loadEarlier = async () => {
    const oldest = messages[0]?.seq;
    if (oldest == null || loadingEarlier) return;
    setLoadingEarlier(true);
    try {
      const older = await fetchChatMessages(companySlug, storeSlug, { beforeSeq: oldest, ...auth() });
      if (Array.isArray(older) && older.length) {
        setMessages((previous) => mergeMessages(previous, older));
      }
      setHasMore(Boolean(older?.length));
    } catch {
      // Leave the control in place so the shopper can retry.
    } finally {
      setLoadingEarlier(false);
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

  const launcherLabel = storeName ? `Chat with ${storeName}` : "Chat with the store";
  // Measured only on a phone; the desktop card keeps its Tailwind offsets.
  const launcherStyle = mobile && box ? { bottom: `${launcherBottom(box.bottomGap)}px` } : undefined;
  const panelStyle = mobile && box ? { top: `${box.top}px`, height: `${box.height}px` } : undefined;

  if (!open) {
    if (hidden) return null;
    return (
      <button
        type="button"
        onClick={openPanel}
        aria-label={launcherLabel}
        data-testid="store-chat-launcher"
        style={launcherStyle}
        className="fixed bottom-20 right-4 z-40 flex h-12 max-w-[calc(100vw-2rem)] items-center gap-2 rounded-full bg-brand px-4 text-sm font-bold text-white shadow-[0_10px_30px_rgba(28,31,42,.28)] transition hover:opacity-95 sm:bottom-6 sm:right-4"
      >
        <ChatBubbleIcon />
        <span className="truncate">{launcherLabel}</span>
        {unread > 0 ? (
          <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-white px-1 text-[10px] font-extrabold text-brand">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>
    );
  }

  return (
    <div
      style={panelStyle}
      className="fixed inset-x-0 top-0 z-50 flex h-[100dvh] flex-col overflow-hidden border-t border-line bg-page shadow-[0_-12px_36px_rgba(28,31,42,.18)] sm:inset-auto sm:bottom-6 sm:right-4 sm:h-[560px] sm:max-h-[calc(100dvh-3rem)] sm:w-[390px] sm:rounded-2xl sm:border"
    >
      <header className="flex shrink-0 items-center gap-3 border-b border-line bg-surface px-4 py-3 sm:rounded-t-2xl">
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

      {!hasConversation && !signedIn && checkingSession ? (
        <p className="shrink-0 border-b border-line bg-surface px-4 py-2.5 text-[11px] text-muted">
          Checking your conversation…
        </p>
      ) : null}

      {!hasConversation && !signedIn && !checkingSession ? (
        <div className="max-h-[38dvh] shrink-0 overflow-y-auto overscroll-contain border-b border-line bg-surface px-4 py-2.5">
          <label htmlFor="store-chat-name" className="block text-[11px] font-semibold text-muted">
            Your name — so the store knows who you are
          </label>
          <input
            id="store-chat-name"
            required
            value={guestName}
            onChange={(event) => setGuestName(event.target.value)}
            maxLength={120}
            placeholder="e.g. Sokha"
            className="mt-1 h-10 w-full rounded-lg border border-line bg-page px-2.5 text-base text-ink outline-none placeholder:text-muted sm:h-8 sm:text-xs"
          />
          <label htmlFor="store-chat-phone" className="mt-2 block text-[11px] font-semibold text-muted">
            Phone number — so the store can get back to you
          </label>
          <input
            id="store-chat-phone"
            type="tel"
            required
            value={guestPhone}
            onChange={(event) => setGuestPhone(event.target.value)}
            maxLength={40}
            placeholder="e.g. 012 345 678"
            className="mt-1 h-10 w-full rounded-lg border border-line bg-page px-2.5 text-base text-ink outline-none placeholder:text-muted sm:h-8 sm:text-xs"
          />
          <label htmlFor="store-chat-email" className="mt-2 block text-[11px] font-semibold text-muted">
            Email me the reply (optional)
          </label>
          <input
            id="store-chat-email"
            type="email"
            value={guestEmail}
            onChange={(event) => setGuestEmail(event.target.value)}
            maxLength={320}
            placeholder="you@example.com"
            className="mt-1 h-10 w-full rounded-lg border border-line bg-page px-2.5 text-base text-ink outline-none placeholder:text-muted sm:h-8 sm:text-xs"
          />
        </div>
      ) : null}

      {error ? <p className="shrink-0 border-b border-line bg-danger-soft px-4 py-1.5 text-[11px] font-semibold text-danger">{error}</p> : null}

      <div className="min-h-0 flex-1">
        <ChatThread
          messages={messages}
          viewer="customer"
          busy={busy}
          onSendText={handleSendText}
          onSendAttachment={handleSendAttachment}
          onReact={handleReact}
          hasMore={hasMore}
          onLoadEarlier={loadEarlier}
          loadingEarlier={loadingEarlier}
          onTyping={pingTyping}
          typingText={peerTyping ? `${storeName || "The store"} is typing…` : ""}
          compact
          emptyText={`Ask ${storeName || "the store"} anything — about an item, delivery, or your order.`}
          footerText="Messages are shared with the store."
        />
      </div>
    </div>
  );
}
