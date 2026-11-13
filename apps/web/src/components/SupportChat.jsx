import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, LifeBuoy, Loader2, Send, Sparkles, ThumbsDown, ThumbsUp, UserRound } from "lucide-react";

import { api } from "../api";
import { highestSeq, mergeMessages, parseSseChunk } from "../lib/inbox";

// The floating assistant and the Support page are the same conversation now.
// Every question is stored in a support-chat thread, so the ops inbox can see
// what the assistant answered and join without asking the merchant to repeat it.
const GUIDE_VIEWS = {
  "getting-started.first-sale": "pos",
  "getting-started.add-products": "products",
  "inventory.restock": "inventory",
  "inventory.low-stock": "inventory",
  "electronics.serials": "products",
  "electronics.warranty": "products",
  "team.invite": "team",
  "billing.change-plan": "billing",
};

const VIEW_LABELS = {
  pos: "Point of sale",
  products: "Products",
  inventory: "Inventory",
  team: "Team access",
  billing: "Billing & plans",
  reports: "Reports",
  customers: "Customers",
  settings: "Settings",
};

function viewMessage(message) {
  const role = message.author_type === "merchant"
    ? "user"
    : message.author_type === "assistant"
      ? "assistant"
      : message.author_type === "agent"
        ? "agent"
        : "system";
  return {
    id: message.id,
    seq: message.seq,
    role,
    content: message.body || "",
    guides: [],
    feedback: null,
    authorName: message.author_name,
    createdAt: message.created_at,
    attachment: message.attachment,
  };
}

function SupportChat({ token, storeId, language = "en", onLanguageChange, starterPrompts = [], className = "", onOpenGuide, onNavigate, onContactSupport }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [thread, setThread] = useState(null);
  const [typing, setTyping] = useState(false);

  const scrollRef = useRef(null);
  const cursorRef = useRef(0);
  const typingSentRef = useRef(0);

  const scrollToEnd = useCallback(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToEnd();
  }, [messages, sending, scrollToEnd]);

  const loadThread = useCallback(async (id) => {
    const detail = await api.supportChatThread(token, id);
    setThread(detail);
    setMessages((detail.messages || []).map(viewMessage));
    cursorRef.current = highestSeq(detail.messages || []);
    return detail;
  }, [token]);

  // Resume the caller's own latest thread. Using `mine` matters for an owner:
  // without it the panel could open a colleague's conversation.
  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    (async () => {
      try {
        const rows = await api.supportChatConversations(token, { mine: 1, limit: 1 });
        const latest = rows?.[0];
        if (active && latest?.id) await loadThread(latest.id);
      } catch {
        /* the first send will create a thread if this read failed */
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token, loadThread]);

  // Realtime updates once a thread exists. During a send the optimistically
  // rendered turns are not persisted yet, so the stream pauses and resumes
  // afterwards from the real cursor.
  useEffect(() => {
    if (!token || !thread?.id || sending) return undefined;
    let active = true;
    let controller = null;
    let retry = null;

    const connect = async () => {
      controller = new AbortController();
      try {
        const response = await fetch(
          `${api.baseUrl}/support/chat/conversations/${thread.id}/stream?after_seq=${cursorRef.current || 0}`,
          { headers: { Authorization: `Bearer ${token}` }, credentials: "include", signal: controller.signal },
        );
        if (!response.ok || !response.body) return;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done || !active) break;
          buffer += decoder.decode(value, { stream: true });
          const { events, rest } = parseSseChunk(buffer);
          buffer = rest;
          for (const event of events) {
            if (!event.data || event.data === "[DONE]") continue;
            let payload;
            try { payload = JSON.parse(event.data); } catch { continue; }
            const message = payload?.message;
            if (!message) continue;
            cursorRef.current = Math.max(cursorRef.current, message.seq || 0);
            setMessages((current) => mergeMessages(current, [viewMessage(message)]));
            if (message.author_type === "agent") {
              setThread((current) => current ? {
                ...current,
                status: "live",
                assigned_admin_name: message.author_name || current.assigned_admin_name,
                last_message_at: message.created_at,
              } : current);
            }
            scrollToEnd();
          }
        }
      } catch {
        /* reconnect below while the panel is still open */
      }
      if (active) retry = window.setTimeout(connect, 1500);
    };

    connect();
    return () => {
      active = false;
      controller?.abort();
      if (retry) window.clearTimeout(retry);
    };
  }, [token, thread?.id, sending, scrollToEnd]);

  // Typing presence only matters once a human is involved.
  useEffect(() => {
    if (!token || !thread?.id || thread.status === "ai") {
      setTyping(false);
      return undefined;
    }
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      api.supportChatTypingState(token, thread.id)
        .then((result) => setTyping(Boolean(result?.typing)))
        .catch(() => {});
    }, 6000);
    return () => window.clearInterval(timer);
  }, [token, thread?.id, thread?.status]);

  const ensureThread = async () => {
    if (thread?.id) return thread;
    const detail = await api.supportChatStart(token, {}, storeId);
    setThread(detail);
    setMessages([]);
    cursorRef.current = 0;
    return detail;
  };

  const streamAnswer = async (threadId, question) => {
    const response = await fetch(`${api.baseUrl}/support/chat/conversations/${threadId}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(storeId ? { "X-Store-ID": storeId } : {}),
      },
      credentials: "include",
      body: JSON.stringify({ message: question, language }),
    });
    if (!response.ok) {
      let detail = "The assistant is unavailable right now.";
      try {
        const payload = await response.json();
        if (payload?.detail) detail = payload.detail;
      } catch { /* keep the default */ }
      throw new Error(detail);
    }
    if (!response.body) throw new Error("The assistant is unavailable right now.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let guides = [];
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSseChunk(buffer);
      buffer = rest;
      for (const event of events) {
        if (!event.data || event.data === "[DONE]") continue;
        let payload;
        try { payload = JSON.parse(event.data); } catch { continue; }
        if (payload?.error) throw new Error(payload.error);
        if (payload?.guides) {
          guides = payload.guides;
          setMessages((current) => current.map((message, index) => (
            index === current.length - 1 ? { ...message, guides } : message
          )));
        }
        if (payload?.delta) {
          answer += payload.delta;
          setMessages((current) => current.map((message, index) => (
            index === current.length - 1 ? { ...message, content: answer } : message
          )));
          scrollToEnd();
        }
      }
    }
    return { answer, guides };
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setError("");
    setInput("");
    setSending(true);
    let current = null;
    try {
      current = await ensureThread();
      if (current.status !== "ai") {
        const result = await api.supportChatSend(token, current.id, { body: question });
        setThread((value) => value ? { ...value, ...result.conversation } : result.conversation);
        setMessages((value) => mergeMessages(value, [viewMessage(result.message)]));
        cursorRef.current = Math.max(cursorRef.current, result.message.seq || 0);
        return;
      }

      // Keep the turn visible while the answer streams; the server persists both
      // and the panel reloads once the stream closes.
      setMessages((current) => [
        ...current,
        {
          id: `local-user-${Date.now()}`,
          seq: Number.MAX_SAFE_INTEGER - 2,
          role: "user",
          content: question,
          guides: [],
          feedback: null,
          createdAt: new Date().toISOString(),
        },
        {
          id: `local-assistant-${Date.now()}`,
          seq: Number.MAX_SAFE_INTEGER - 1,
          role: "assistant",
          content: "",
          guides: [],
          feedback: null,
          createdAt: new Date().toISOString(),
        },
      ]);
      scrollToEnd();
      const result = await streamAnswer(current.id, question);
      const detail = await loadThread(current.id);
      setMessages((value) => {
        const persisted = (detail.messages || []).map(viewMessage);
        const last = persisted[persisted.length - 1];
        if (last?.role === "assistant" && result.answer && last.content === result.answer) {
          last.guides = result.guides || [];
        }
        return persisted.length ? persisted : value;
      });
    } catch (requestError) {
      setError(requestError.message || "The assistant is unavailable right now.");
      if (current?.id) {
        try { await loadThread(current.id); } catch { /* keep the local turns */ }
      }
    } finally {
      setSending(false);
    }
  };

  const requestHuman = async () => {
    if (sending) return;
    setError("");
    setSending(true);
    try {
      const current = await ensureThread();
      const updated = await api.supportChatHandoff(token, current.id, {});
      setThread((value) => value ? { ...value, ...updated } : updated);
    } catch (requestError) {
      setError(requestError.message || "Could not notify the support team.");
    } finally {
      setSending(false);
    }
  };

  const rate = async (index, rating) => {
    const message = messages[index];
    if (!message || message.role !== "assistant" || message.feedback) return;
    const question = messages[index - 1]?.content || "";
    setMessages((current) => current.map((item, i) => (i === index ? { ...item, feedback: rating } : item)));
    try {
      await api.supportFeedback(token, {
        rating,
        question: question.slice(0, 1000),
        answer: (message.content || "").slice(0, 4000),
        guide_ids: (message.guides || []).map((guide) => (typeof guide === "string" ? guide : guide.id)),
      });
    } catch {
      /* feedback is best-effort; keep the local state */
    }
  };

  const onChange = (value) => {
    setInput(value);
    const now = Date.now();
    if (thread?.id && value.trim() && now - typingSentRef.current > 2500) {
      typingSentRef.current = now;
      api.supportChatTyping(token, thread.id).catch(() => {});
    }
  };

  const status = thread?.status || "ai";
  const live = status === "live";
  const waiting = status === "waiting";
  const closed = status === "resolved" || status === "closed";
  const placeholder = status === "ai" ? "Ask how to use Chmaba..." : "Write a message to support...";

  return (
    <div className={`rounded-2xl border border-[#e6e5f3] bg-white p-4 dark:border-[#33343a] dark:bg-[#1f2025] ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {live ? <UserRound size={15} className="text-[#4f8b32]" /> : <Sparkles size={15} className="text-[#6957f5]" />}
          <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">{live ? "Chmaba support" : "Ask the assistant"}</p>
          {thread?.reference && <span className="rounded-full bg-[#f4f4f8] px-1.5 py-0.5 text-[8px] font-bold text-[#92939d] dark:bg-[#2a2b32]">{thread.reference}</span>}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(event) => onLanguageChange?.(event.target.value)}
            aria-label="Language"
            className="h-7 rounded-lg border border-[#e4e4eb] bg-white px-1.5 text-[10px] font-semibold text-[#62636d] dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#a9aab3]"
          >
            <option value="en">EN</option>
            <option value="km">ខ្មែរ</option>
          </select>
        </div>
      </div>

      {waiting && <p className="mt-2 rounded-xl border border-[#f2e3bd] bg-[#fffaf0] px-2.5 py-1.5 text-[10px] font-semibold text-[#8a661a] dark:border-[#4a3f22] dark:bg-[#2a2518] dark:text-[#d8b45f]">
        A support teammate has been notified. You can keep typing here; they will see it.
      </p>}
      {live && <p className="mt-2 rounded-xl border border-[#dcefd0] bg-[#f6fbf2] px-2.5 py-1.5 text-[10px] font-semibold text-[#4f7a33] dark:border-[#33452a] dark:bg-[#202a1b] dark:text-[#b7d8a0]">
        Chatting with {thread?.assigned_admin_name || "Chmaba support"}. This is a live conversation.
      </p>}
      {closed && <p className="mt-2 rounded-xl border border-[#e6e6ed] bg-[#fafafd] px-2.5 py-1.5 text-[10px] font-semibold text-[#777883] dark:border-[#363740] dark:bg-[#26272d] dark:text-[#a9aab3]">
        This conversation is closed. Send a message to reopen it.
      </p>}

      <div ref={scrollRef} className="mt-3 min-h-[380px] max-h-[60vh] space-y-2 overflow-y-auto app-scrollbar">
        {loading && messages.length === 0 && <p className="text-[11px] text-[#92939d]">Loading...</p>}
        {!loading && messages.length === 0 && !sending && starterPrompts.length > 0 && (
          <div className="space-y-2.5">
            <p className="text-[11px] font-semibold text-[#92939d] dark:text-[#9a9aa4]">Try one of these to get started:</p>
            <div className="grid grid-cols-2 gap-2">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => send(prompt)}
                  className="rounded-xl border border-[#e4e4eb] bg-[#faf9ff] px-3 py-2 text-left text-[10px] font-semibold leading-4 text-[#696a76] transition hover:border-[#bdb9ee] hover:text-[#6957f5] dark:border-[#363740] dark:bg-[#202126] dark:text-[#a9aab3]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => {
          if (message.role === "system") {
            return <p key={message.id || index} className="mx-auto max-w-[85%] rounded-full bg-[#f4f4f8] px-3 py-1 text-center text-[9px] font-semibold text-[#777883] dark:bg-[#2a2b32] dark:text-[#a9aab3]">{message.content}</p>;
          }
          const salesman = message.role === "agent";
          return (
            <div key={message.id || index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${message.role === "user" ? "" : "space-y-1"}`}>
                {message.role !== "user" && (
                  <p className={`text-[9px] font-bold ${salesman ? "text-[#4f8b32]" : "text-[#6957f5]"}`}>
                    {salesman ? (message.authorName || "Support") : "Chmaba assistant"}
                  </p>
                )}
                <div
                  className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-[11px] leading-5 ${
                    message.role === "user"
                      ? "bg-[#6957f5] text-white"
                      : salesman
                        ? "rounded-tl-sm bg-[#edf9e4] text-[#31471f] dark:bg-[#223019] dark:text-[#c3e3ab]"
                        : "rounded-tl-sm bg-[#f4f4f8] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"
                  }`}
                >
                  {message.content}
                  {message.attachment?.url ? (
                    <a href={message.attachment.url} target="_blank" rel="noreferrer" className="mt-1.5 block text-[10px] font-bold underline">
                      {message.attachment.name || "Attachment"}
                    </a>
                  ) : null}
                </div>

                {message.role === "assistant" && message.content && message.guides?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {message.guides.map((guide) => (
                      <button
                        key={typeof guide === "string" ? guide : guide.id}
                        type="button"
                        onClick={() => onOpenGuide?.(typeof guide === "string" ? guide : guide.id)}
                        className="rounded-full border border-[#e4e4eb] bg-white px-2 py-0.5 text-[9px] font-semibold text-[#777883] transition hover:border-[#bdb9ee] hover:text-[#6957f5] dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#a9aab3]"
                      >
                        {typeof guide === "string" ? guide : guide.title}
                      </button>
                    ))}
                  </div>
                )}

                {message.role === "assistant" && message.content && onNavigate && (() => {
                  const views = [...new Set((message.guides || []).map((guide) => GUIDE_VIEWS[typeof guide === "string" ? guide : guide.id]).filter(Boolean))];
                  if (views.length === 0) return null;
                  return (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {views.map((view) => (
                        <button
                          key={view}
                          type="button"
                          onClick={() => onNavigate(view)}
                          className="rounded-lg bg-[#6957f5] px-2.5 py-1 text-[9px] font-bold text-white transition hover:bg-[#5a48e0]"
                        >
                          Go to {VIEW_LABELS[view] || view}
                        </button>
                      ))}
                    </div>
                  );
                })()}

                {message.role === "assistant" && message.content && !(sending && index === messages.length - 1) && (
                  <div className="flex items-center gap-2 pt-1 text-[#b0b1ba]">
                    <span className="text-[9px]">{message.feedback ? "Thanks for the feedback" : "Was this helpful?"}</span>
                    <button
                      type="button"
                      aria-label="Helpful"
                      onClick={() => rate(index, "up")}
                      disabled={Boolean(message.feedback)}
                      className={`transition hover:text-[#6daf43] disabled:cursor-default ${message.feedback === "up" ? "text-[#6daf43]" : ""}`}
                    >
                      <ThumbsUp size={12} />
                    </button>
                    <button
                      type="button"
                      aria-label="Not helpful"
                      onClick={() => rate(index, "down")}
                      disabled={Boolean(message.feedback)}
                      className={`transition hover:text-[#c2564b] disabled:cursor-default ${message.feedback === "down" ? "text-[#c2564b]" : ""}`}
                    >
                      <ThumbsDown size={12} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {sending && (
          <div className="flex items-center gap-2 text-[11px] text-[#92939d]">
            <Loader2 size={13} className="animate-spin" /> {status === "ai" ? "Thinking..." : "Sending..."}
          </div>
        )}
        {typing && <p className="text-[9px] font-semibold text-[#92939d]">Support is typing...</p>}
      </div>

      {error && <p className="mt-2 text-[11px] font-semibold text-[#c2564b]">{error}</p>}

      <form
        className="mt-3 flex items-center gap-2 rounded-xl border border-[#e6e6ed] bg-white px-2 dark:border-[#363740] dark:bg-[#1a1b1f]"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="h-11 w-full bg-transparent px-1 text-xs text-[#303139] outline-none placeholder:text-[#a0a1aa] dark:text-[#e4e4e8]"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          aria-label="Send"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#6957f5] text-white transition hover:bg-[#5a48e0] disabled:opacity-50"
        >
          <Send size={14} />
        </button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {status === "ai" && (
          <button
            type="button"
            onClick={requestHuman}
            disabled={sending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#e4e4eb] px-2.5 py-1.5 text-[10px] font-bold text-[#62636d] transition hover:border-[#bdb9ee] hover:text-[#6957f5] disabled:opacity-50 dark:border-[#363740] dark:text-[#a9aab3]"
          >
            <LifeBuoy size={12} /> Talk to a human
          </button>
        )}
        {waiting && <span className="text-[10px] font-semibold text-[#ad7d1c]">Waiting for support...</span>}
        {live && <span className="text-[10px] font-semibold text-[#4f8b32]">Support is live</span>}
        {thread?.id && onContactSupport && (
          <button
            type="button"
            onClick={() => onContactSupport(thread.id)}
            className="ml-auto inline-flex items-center gap-1 text-[10px] font-semibold text-[#777883] transition hover:text-[#6957f5] dark:text-[#a9aab3]"
          >
            <ExternalLink size={11} /> Open in Support
          </button>
        )}
      </div>
    </div>
  );
}

export { SupportChat };
