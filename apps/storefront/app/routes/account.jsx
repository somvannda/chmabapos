import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import {
  claimChatThread,
  fetchChatMessages,
  fetchMyChatConversations,
  fetchChatSession,
  fetchMyOrders,
  fetchShopperMe,
  googleShopperSignIn,
  markChatRead,
  reactToChatMessage,
  requestShopperCode,
  sendChatMessage,
  telegramShopperSignIn,
  uploadChatFile,
  verifyShopperCode,
} from "../lib/api";
import { storedChatThreads } from "../lib/chat";
import ChatThread from "../components/ChatThread";

function mergeMessages(existing, incoming) {
  const byId = new Map(existing.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return Array.from(byId.values()).sort((a, b) => a.seq - b.seq);
}

function highestSeq(messages) {
  return (messages || []).reduce((max, message) => Math.max(max, message.seq), 0);
}

const TOKEN_KEY = "chmaba.shopper_token";
// Both are optional. A provider whose value is blank simply does not offer a
// button, so the page never shows one that cannot work.
const GOOGLE_CLIENT_ID = (import.meta.env.VITE_GOOGLE_CLIENT_ID || "").trim();
const TELEGRAM_BOT_USERNAME = (import.meta.env.VITE_TELEGRAM_BOT_USERNAME || "").trim();

export function meta() {
  // One person's orders: useful to them, not content to index.
  return [{ title: "Your orders" }, { name: "robots", content: "noindex" }];
}

// The storefront is server-rendered, so this page cannot read localStorage while
// rendering - that would produce markup the client immediately disagrees with. It
// therefore starts as the signed-out form and upgrades itself once mounted, which
// is the only way to be both SSR-correct and signed-in when a token exists.
//
// The provider scripts are treated the same way: Google Identity and the Telegram
// widget are both injected after mount, because neither can run during a server
// render.
export default function Account() {
  const [searchParams] = useSearchParams();
  const [checking, setChecking] = useState(true);
  const [shopper, setShopper] = useState(null);
  const [orders, setOrders] = useState([]);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState("email");
  const [mode, setMode] = useState(searchParams.get("mode") === "signup" ? "signup" : "signin");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("orders");
  const [conversations, setConversations] = useState([]);
  const [activeChat, setActiveChat] = useState(null);
  const [threadMessages, setThreadMessages] = useState([]);
  const [threadBusy, setThreadBusy] = useState(false);
  const tokenRef = useRef("");

  const googleRef = useRef(null);
  const telegramRef = useRef(null);
  const googleReady = useRef(false);

  const loadConversations = async (token) => {
    const chats = await fetchMyChatConversations(token);
    setConversations(Array.isArray(chats) ? chats : []);
  };

  // A guest thread lives under a visitor token in this browser. Signing in
  // adopts every one of them, across stores, so the thread is already in the
  // account before the shopper sends another message or returns to that store.
  const claimStoredThreads = async (token) => {
    const threads = storedChatThreads(typeof window === "undefined" ? null : window.localStorage);
    if (!threads.length) return;
    await Promise.all(
      threads.map(({ companySlug, storeSlug, visitorToken }) =>
        claimChatThread(companySlug, storeSlug, { token, chatToken: visitorToken }).catch(() => null)
      )
    );
  };

  const completeSignIn = async (result) => {
    window.localStorage.setItem(TOKEN_KEY, result.access_token);
    tokenRef.current = result.access_token;
    setShopper(result.shopper);
    setError("");
    await claimStoredThreads(result.access_token);
    const [history, chats] = await Promise.all([
      fetchMyOrders(result.access_token),
      fetchMyChatConversations(result.access_token).catch(() => []),
    ]);
    setOrders(Array.isArray(history) ? history : []);
    setConversations(Array.isArray(chats) ? chats : []);
  };

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const token = window.localStorage.getItem(TOKEN_KEY);
        tokenRef.current = token || "";
        if (token) {
          await claimStoredThreads(token);
          const [me, history, chats] = await Promise.all([
            fetchShopperMe(token),
            fetchMyOrders(token),
            fetchMyChatConversations(token).catch(() => []),
          ]);
          if (active) {
            setShopper(me);
            setOrders(Array.isArray(history) ? history : []);
            setConversations(Array.isArray(chats) ? chats : []);
          }
        }
      } catch {
        // A revoked or expired token just means signed out. That is not an error
        // worth showing someone.
        window.localStorage.removeItem(TOKEN_KEY);
      } finally {
        if (active) setChecking(false);
      }
    })();
    return () => { active = false; };
  }, []);

  // Google Identity, loaded only when configured and only while signed out.
  useEffect(() => {
    if (shopper || stage !== "email" || !GOOGLE_CLIENT_ID || googleReady.current) return undefined;
    let cancelled = false;
    const configure = () => {
      if (cancelled || !window.google?.accounts?.id || !googleRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          setBusy(true);
          setError("");
          try {
            await completeSignIn(await googleShopperSignIn(response.credential));
          } catch {
            setError("Google sign-in failed. Please try again.");
          } finally {
            setBusy(false);
          }
        },
      });
      window.google.accounts.id.renderButton(googleRef.current, { theme: "outline", size: "large", width: 320 });
      googleReady.current = true;
    };
    const existing = document.getElementById("gsi-client");
    if (existing) {
      configure();
    } else {
      const script = document.createElement("script");
      script.id = "gsi-client";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = configure;
      document.head.appendChild(script);
    }
    return () => { cancelled = true; };
  }, [shopper, stage]);

  // Telegram Login Widget. Its callback has to be a *global* function, which is
  // how the widget is designed, so it is installed only while the button is on
  // screen and removed again afterwards.
  useEffect(() => {
    if (shopper || stage !== "email" || !TELEGRAM_BOT_USERNAME) return undefined;
    window.onTelegramAuth = async (user) => {
      setBusy(true);
      setError("");
      try {
        await completeSignIn(await telegramShopperSignIn(user));
      } catch {
        setError("Telegram sign-in failed. Please try again.");
      } finally {
        setBusy(false);
      }
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", TELEGRAM_BOT_USERNAME);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    telegramRef.current?.appendChild(script);
    return () => {
      delete window.onTelegramAuth;
    };
  }, [shopper, stage]);

  const sendCode = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestShopperCode(email.trim());
      setStage("code");
    } catch (requestError) {
      setError(requestError instanceof Response ? await requestError.text() : "Could not send the code");
    } finally {
      setBusy(false);
    }
  };

  const verify = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await completeSignIn(
        await verifyShopperCode(
          email.trim(),
          code.trim(),
          mode === "signup" ? { fullName, phone } : {}
        )
      );
      setCode("");
      setStage("email");
      setMode("signin");
      setFullName("");
      setPhone("");
    } catch (requestError) {
      // The API returns one message for every failure, so there is nothing more
      // specific to say - and saying more would help someone guess codes.
      setError(
        requestError instanceof Response && requestError.status === 400
          ? "That code is not valid."
          : "Could not sign in. Please try again."
      );
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    window.localStorage.removeItem(TOKEN_KEY);
    tokenRef.current = "";
    setShopper(null);
    setOrders([]);
    setConversations([]);
    setActiveChat(null);
    setThreadMessages([]);
    setTab("orders");
  };

  // Keep a ref of the thread so the polling effect can ask "what arrived after
  // the last message I have?" without re-subscribing on every message.
  const threadRef = useRef([]);
  useEffect(() => { threadRef.current = threadMessages; }, [threadMessages]);

  const openConversation = async (conversation) => {
    setActiveChat(conversation);
    setThreadMessages([]);
    setConversations((previous) =>
      previous.map((item) => (item.id === conversation.id ? { ...item, unread_count: 0 } : item))
    );
    markChatRead(conversation.company_slug, conversation.store_slug, { token: tokenRef.current }).catch(() => {});
    try {
      const session = await fetchChatSession(conversation.company_slug, conversation.store_slug, { token: tokenRef.current });
      setThreadMessages(session?.messages || []);
    } catch {
      setThreadMessages([]);
    }
  };

  // A signed-in inbox still polls: it is one thread on screen at a time, and a
  // poll every few seconds keeps it current without holding a stream open on the
  // account page too.
  useEffect(() => {
    if (!activeChat) return undefined;
    const timer = window.setInterval(async () => {
      if (document.hidden) return;
      try {
        const incoming = await fetchChatMessages(activeChat.company_slug, activeChat.store_slug, {
          afterSeq: highestSeq(threadRef.current),
          token: tokenRef.current,
        });
        if (Array.isArray(incoming) && incoming.length) {
          setThreadMessages((previous) => mergeMessages(previous, incoming));
        }
      } catch {
        // The next tick retries.
      }
    }, 8000);
    return () => window.clearInterval(timer);
  }, [activeChat]);

  const sendThreadText = async (text, replyToMessageId = null) => {
    if (!activeChat) return false;
    setThreadBusy(true);
    try {
      const result = await sendChatMessage(
        activeChat.company_slug,
        activeChat.store_slug,
        { kind: "text", body: text, reply_to_message_id: replyToMessageId || undefined },
        { token: tokenRef.current }
      );
      if (result?.message) setThreadMessages((previous) => mergeMessages(previous, [result.message]));
      return true;
    } catch {
      return false;
    } finally {
      setThreadBusy(false);
    }
  };

  const sendThreadAttachment = async ({ kind, file, durationMs, caption, replyToMessageId = null }) => {
    if (!activeChat) return false;
    setThreadBusy(true);
    try {
      const uploaded = await uploadChatFile(activeChat.company_slug, activeChat.store_slug, file, { token: tokenRef.current });
      if (!uploaded) return false;
      const result = await sendChatMessage(
        activeChat.company_slug,
        activeChat.store_slug,
        {
          kind: uploaded.kind || kind,
          body: caption?.trim() || undefined,
          reply_to_message_id: replyToMessageId || undefined,
          attachment_url: uploaded.url,
          attachment_name: uploaded.original_filename,
          attachment_content_type: uploaded.content_type || file.type,
          attachment_byte_size: uploaded.byte_size,
          attachment_duration_ms: durationMs ?? null,
        },
        { token: tokenRef.current }
      );
      if (result?.message) setThreadMessages((previous) => mergeMessages(previous, [result.message]));
      return true;
    } catch {
      // The composer keeps the staged file so it can be retried.
      return false;
    } finally {
      setThreadBusy(false);
    }
  };

  const reactThread = async (message, emoji) => {
    if (!activeChat) return;
    try {
      const updated = await reactToChatMessage(activeChat.company_slug, activeChat.store_slug, message.id, emoji, { token: tokenRef.current });
      if (updated) setThreadMessages((previous) => mergeMessages(previous, [updated]));
    } catch {
      // A failed reaction is not worth surfacing.
    }
  };

  if (checking) {
    return <main className="mx-auto max-w-[560px] px-5 py-20 text-center text-sm text-muted">Loading…</main>;
  }

  if (shopper) {
    const unreadChats = conversations.reduce((sum, item) => sum + (item.unread_count || 0), 0);
    return (
      <div className="min-h-screen bg-page px-5 py-10">
        <main className="mx-auto max-w-[640px]">
          <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">
            {activeChat ? activeChat.store_name || "Messages" : tab === "messages" ? "Your messages" : "Your orders"}
          </h1>
          <p className="mt-1 text-xs text-muted">{shopper.email || "Signed in with Telegram"}</p>

          {activeChat ? (
            <div className="mt-5">
              <button
                type="button"
                onClick={() => {
                  setActiveChat(null);
                  loadConversations(tokenRef.current).catch(() => {});
                }}
                className="mb-3 inline-flex items-center gap-1 text-xs font-bold text-brand"
              >
                ← All messages
              </button>
              <div className="flex h-[560px] flex-col overflow-hidden rounded-2xl border border-line bg-page">
                <ChatThread
                  messages={threadMessages}
                  viewer="customer"
                  busy={threadBusy}
                  onSendText={sendThreadText}
                  onSendAttachment={sendThreadAttachment}
                  onReact={reactThread}
                  emptyText="No messages in this thread yet."
                  footerText="Replies from the store arrive here."
                />
              </div>
            </div>
          ) : (
            <>
              <div className="mt-4 flex gap-1 rounded-xl bg-surface-sunken p-1">
                <button
                  type="button"
                  onClick={() => setTab("orders")}
                  className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-bold ${tab === "orders" ? "bg-surface text-ink shadow-[0_1px_2px_rgba(28,31,42,.08)]" : "text-muted"}`}
                >
                  Orders
                </button>
                <button
                  type="button"
                  onClick={() => setTab("messages")}
                  className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-bold ${tab === "messages" ? "bg-surface text-ink shadow-[0_1px_2px_rgba(28,31,42,.08)]" : "text-muted"}`}
                >
                  Messages{unreadChats ? ` · ${unreadChats}` : ""}
                </button>
              </div>

              {tab === "orders" ? (
                orders.length === 0 ? (
                  <p className="mt-8 rounded-2xl border border-line bg-surface p-8 text-center text-sm text-muted">
                    No orders yet. Orders you place while signed in appear here.
                  </p>
                ) : (
                  <ul className="mt-6 space-y-2">
                    {orders.map((order) => (
                      <li
                        key={order.public_token || `${order.created_at}-${order.label}`}
                        className="rounded-xl border border-line bg-surface p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-ink-soft">{order.store_name}</p>
                            <p className="mt-0.5 text-[11px] text-muted">
                              {order.label || "Order"} · {new Date(order.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <span className="shrink-0 text-sm font-extrabold text-ink">{order.subtotal}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-3">
                          <span className="rounded-lg bg-surface-sunken px-2 py-1 text-[10px] font-bold text-ink-soft">
                            {order.status}
                          </span>
                          {order.public_token ? (
                            <Link to={`/order/${order.public_token}`} className="text-[11px] font-semibold text-brand">
                              Track this order
                            </Link>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )
              ) : conversations.length === 0 ? (
                <p className="mt-8 rounded-2xl border border-line bg-surface p-8 text-center text-sm text-muted">
                  No conversations yet. Chat with a store from its page and it appears here.
                </p>
              ) : (
                <ul className="mt-6 space-y-2">
                  {conversations.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => openConversation(item)}
                        className="w-full rounded-xl border border-line bg-surface p-4 text-left transition hover:border-brand"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-ink-soft">{item.store_name || "Store"}</p>
                            <p className="mt-0.5 truncate text-[11px] text-muted">
                              {item.last_message_preview || "No messages yet"}
                            </p>
                          </div>
                          {item.unread_count ? (
                            <span className="shrink-0 rounded-full bg-brand px-2 py-0.5 text-[10px] font-extrabold text-white">
                              {item.unread_count}
                            </span>
                          ) : (
                            <span className="shrink-0 text-[10px] text-muted">
                              {item.last_message_at ? new Date(item.last_message_at).toLocaleDateString() : ""}
                            </span>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          <button
            type="button"
            onClick={signOut}
            className="mt-6 rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-soft"
          >
            Sign out
          </button>
        </main>
      </div>
    );
  }

  const hasProviders = Boolean(GOOGLE_CLIENT_ID || TELEGRAM_BOT_USERNAME);

  return (
    <div className="min-h-screen bg-page px-5 py-12">
      <main className="mx-auto max-w-[420px]">
        <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">
          {mode === "signup" ? "Create your account" : "Your orders"}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {mode === "signup"
            ? "One account for every store on Chmaba. No password needed."
            : "Sign in to see your orders. No password needed."}
        </p>

        <div className="mt-5 flex rounded-xl border border-line bg-surface p-1">
          <button
            type="button"
            onClick={() => { setMode("signin"); setStage("email"); setCode(""); setError(""); }}
            className={`flex-1 rounded-lg px-3 py-2 text-xs font-bold transition ${
              mode === "signin" ? "bg-brand text-white" : "text-muted hover:text-ink"
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => { setMode("signup"); setStage("email"); setCode(""); setError(""); }}
            className={`flex-1 rounded-lg px-3 py-2 text-xs font-bold transition ${
              mode === "signup" ? "bg-brand text-white" : "text-muted hover:text-ink"
            }`}
          >
            Create account
          </button>
        </div>

        {hasProviders ? (
          <div className="mt-6 space-y-3">
            {GOOGLE_CLIENT_ID ? <div ref={googleRef} className="flex justify-center" /> : null}
            {TELEGRAM_BOT_USERNAME ? <div ref={telegramRef} className="flex justify-center" /> : null}
            <p className="text-center text-[10px] uppercase tracking-wide text-muted">or use your email</p>
          </div>
        ) : null}

        <form onSubmit={stage === "email" ? sendCode : verify} className="mt-4 space-y-3">
          {mode === "signup" ? (
            <>
              <input
                required
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Your full name"
                maxLength={160}
                disabled={stage === "code"}
                className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm text-ink outline-none focus:border-brand disabled:opacity-60"
              />
              <input
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="Phone number (optional)"
                maxLength={40}
                disabled={stage === "code"}
                className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm text-ink outline-none focus:border-brand disabled:opacity-60"
              />
            </>
          ) : null}
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            disabled={stage === "code"}
            className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm text-ink outline-none focus:border-brand disabled:opacity-60"
          />
          {stage === "code" ? (
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="6-digit code"
              className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm tracking-[.3em] text-ink outline-none focus:border-brand"
            />
          ) : null}
          {error ? <p className="text-xs font-semibold text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60"
          >
            {busy ? "Working…" : stage === "email" ? "Send me a code" : mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>

        {stage === "code" ? (
          <button type="button" onClick={() => setStage("email")} className="mt-3 text-xs font-semibold text-brand">
            Use a different email
          </button>
        ) : null}

        <p className="mt-8 text-center text-[10px] text-muted">Powered by Chmaba</p>
      </main>
    </div>
  );
}
