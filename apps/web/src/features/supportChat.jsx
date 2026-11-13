import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, ImagePlus, LifeBuoy, Loader2, Paperclip, Plus, Send, Sparkles, UserRound, X } from "lucide-react";

import { api } from "../api";
import { Button } from "../components/ui";
import { formatDateTime } from "../lib/dateFormat";
import { highestSeq, mergeMessages, parseSseChunk } from "../lib/inbox";

// The merchant's live support inbox: threads on the left, the open conversation
// on the right. The assistant answers until the merchant asks for a human, then
// the same thread continues with an agent - no ticket to re-explain the issue.
const LIST_POLL_MS = 12000;
const THREAD_POLL_MS = 15000;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
const ACCEPTED_FILES = "image/png,image/jpeg,image/webp,image/gif,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx";

const STATUS_META = {
  ai: { label: "Assistant", className: "bg-[#ece9ff] text-[#5b4be3]" },
  waiting: { label: "Waiting", className: "bg-[#fff6df] text-[#ad7d1c]" },
  live: { label: "Live", className: "bg-[#edf9e4] text-[#4f8b32]" },
  resolved: { label: "Resolved", className: "bg-[#f1f1f5] text-[#686974]" },
  closed: { label: "Closed", className: "bg-[#f1f1f5] text-[#686974]" },
};

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.ai;
}

function conversationTitle(conversation) {
  return conversation?.subject || conversation?.last_message_preview || "Support conversation";
}

function timeLabel(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function AttachmentBubble({ attachment }) {
  if (!attachment?.url) return null;
  const isImage = (attachment.content_type || "").startsWith("image/");
  if (isImage) {
    return <a href={attachment.url} target="_blank" rel="noreferrer" className="mt-1.5 block">
      <img src={attachment.url} alt={attachment.name || "Attachment"} className="max-h-56 rounded-xl border border-black/5 object-cover" />
    </a>;
  }
  return <a href={attachment.url} target="_blank" rel="noreferrer" className="mt-1.5 flex items-center gap-2 rounded-xl bg-black/5 px-2.5 py-2 text-xs font-semibold">
    <FileText size={14} />
    <span className="min-w-0 flex-1 truncate">{attachment.name || "Attachment"}</span>
  </a>;
}

function MessageBubble({ message }) {
  if (message.author_type === "system") {
    return <p className="mx-auto max-w-[80%] rounded-full bg-[#f4f4f8] px-3 py-1 text-center text-[10px] font-semibold text-[#777883] dark:bg-[#2a2b32] dark:text-[#a9aab3]">{message.body}</p>;
  }
  const mine = message.author_type === "merchant";
  const assistant = message.author_type === "assistant";
  const agent = message.author_type === "agent";
  return <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
    <div className="max-w-[85%]">
      {!mine && <p className={`mb-1 flex items-center gap-1 text-[9px] font-bold uppercase tracking-wide ${agent ? "text-[#4f8b32]" : "text-[#6957f5]"}`}>
        {assistant ? <Sparkles size={10} /> : <UserRound size={10} />}
        {message.author_name || (assistant ? "Chmaba assistant" : "Support")}
      </p>}
      <div className={`rounded-2xl px-3.5 py-2.5 text-[12px] leading-5 ${
        mine
          ? "bg-[#6957f5] text-white"
          : agent
            ? "rounded-tl-sm bg-[#edf9e4] text-[#31471f] dark:bg-[#223019] dark:text-[#c3e3ab]"
            : "rounded-tl-sm bg-[#f4f4f8] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"
      }`}>
        {message.body ? <p className="whitespace-pre-wrap">{message.body}</p> : null}
        <AttachmentBubble attachment={message.attachment} />
      </div>
      <p className={`mt-1 text-[9px] text-[#a3a4ad] ${mine ? "text-right" : ""}`}>{timeLabel(message.created_at)}</p>
    </div>
  </div>;
}

function EmptyConversation({ onStart, busy, disabled }) {
  return <div className="flex h-full flex-col items-center justify-center p-8 text-center">
    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#ece9ff] text-[#6957f5]"><LifeBuoy size={22} /></span>
    <h3 className="mt-3 text-base font-extrabold text-[#202128] dark:text-[#e4e4e8]">Chat with Chmaba support</h3>
    <p className="mt-1 max-w-[340px] text-xs leading-5 text-[#898a95] dark:text-[#9a9aa4]">
      Ask about billing, setup, a bug, or anything else. The assistant answers instantly, and a teammate can join the same conversation.
    </p>
    <Button className="mt-4" onClick={onStart} disabled={busy || disabled}>
      {busy ? <><Loader2 size={13} className="animate-spin" /> Starting...</> : <><Plus size={14} /> Start a conversation</>}
    </Button>
  </div>;
}

function SupportChatView({ token, workspace, notify, initialConversationId, handoff, onHandoffConsumed }) {
  const storeId = workspace?.store?.id;
  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(initialConversationId || null);
  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [listing, setListing] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [typing, setTyping] = useState(false);

  const threadRef = useRef(null);
  const cursorRef = useRef(0);
  const scrollRef = useRef(null);
  const fileRef = useRef(null);
  const typingSentRef = useRef(0);
  const seededRef = useRef(null);

  threadRef.current = thread;

  const scrollToEnd = useCallback(() => {
    window.requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
  }, []);

  const loadList = useCallback(async () => {
    if (!token) return [];
    try {
      const rows = await api.supportChatConversations(token, { limit: 50 });
      setConversations(Array.isArray(rows) ? rows : []);
      return rows || [];
    } catch {
      return [];
    }
  }, [token]);

  const openThread = useCallback(async (id, options = {}) => {
    if (!token || !id) return;
    setSelectedId(id);
    if (!options.keepSelection) setLoadingThread(true);
    setError("");
    try {
      const detail = await api.supportChatThread(token, id);
      setThread(detail);
      setMessages(detail.messages || []);
      cursorRef.current = highestSeq(detail.messages || []);
      scrollToEnd();
      if (options.fromNotification) notify?.("Support conversation opened");
    } catch (requestError) {
      setError(requestError.message || "Could not open this conversation");
    } finally {
      setLoadingThread(false);
    }
  }, [token, notify, scrollToEnd]);

  // "Contact support" in the floating assistant hands off a short transcript.
  // Creating one thread with those turns means the agent starts with context
  // instead of asking the merchant to repeat themselves.
  useEffect(() => {
    if (!token || !handoff?.history?.length) return;
    if (seededRef.current === handoff.at) return;
    seededRef.current = handoff.at;
    (async () => {
      setCreating(true);
      setError("");
      try {
        const transcript = handoff.history
          .slice(-8)
          .map((turn) => `${turn.role === "user" ? "Me" : "Assistant"}: ${String(turn.content || "").slice(0, 500)}`)
          .join("\n")
          .slice(0, 3500);
        const lastUser = [...handoff.history].reverse().find((turn) => turn.role === "user")?.content || "Support request";
        const detail = await api.supportChatStart(token, {
          subject: String(lastUser).slice(0, 120),
          body: `From my assistant chat:\n\n${transcript}`,
        }, storeId);
        setThread(detail);
        setMessages(detail.messages || []);
        setSelectedId(detail.id);
        cursorRef.current = highestSeq(detail.messages || []);
        await loadList();
        scrollToEnd();
      } catch (requestError) {
        setError(requestError.message || "Could not start a support conversation");
      } finally {
        setCreating(false);
        onHandoffConsumed?.();
      }
    })();
  }, [token, handoff, storeId, loadList, scrollToEnd, onHandoffConsumed]);

  useEffect(() => {
    // A handed-off transcript creates its own thread; do not race it by opening
    // whichever conversation happened to be first in the list.
    if (handoff?.history?.length) {
      setListing(false);
      return undefined;
    }
    let active = true;
    (async () => {
      const rows = await loadList();
      if (!active) return;
      const target = initialConversationId
        || (selectedId && rows.some((row) => row.id === selectedId) ? selectedId : null)
        || rows[0]?.id
        || null;
      if (target) await openThread(target, { fromNotification: Boolean(initialConversationId) });
      setListing(false);
    })();
    return () => { active = false; };
    // The first selection is intentionally a one-time decision; later changes
    // come from the list or a notification.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, initialConversationId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) loadList();
    }, LIST_POLL_MS);
    return () => window.clearInterval(timer);
  }, [loadList]);

  // Live updates for the open thread. The cursor starts at the last message the
  // REST read returned, so nothing is replayed as a duplicate.
  useEffect(() => {
    if (!token || !selectedId) return undefined;
    const controller = new AbortController();
    let active = true;
    const query = new URLSearchParams({ after_seq: String(cursorRef.current || 0) });
    (async () => {
      try {
        const response = await fetch(`${api.baseUrl}/support/chat/conversations/${selectedId}/stream?${query}`, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: "include",
          signal: controller.signal,
        });
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
            if (!payload?.message) continue;
            cursorRef.current = Math.max(cursorRef.current, payload.message.seq || 0);
            setMessages((current) => mergeMessages(current, [payload.message]));
            setThread((current) => current ? {
              ...current,
              last_message_at: payload.message.created_at,
              last_message_preview: payload.message.body || payload.message.attachment?.name || current.last_message_preview,
              last_message_author: payload.message.author_type,
            } : current);
            if (payload.message.author_type === "agent") {
              api.supportChatMarkRead(token, selectedId).catch(() => {});
              loadList();
            }
            scrollToEnd();
          }
        }
      } catch {
        /* a dropped stream reconnects on the next selection */
      }
    })();
    return () => { active = false; controller.abort(); };
  }, [token, selectedId, loadList, scrollToEnd]);

  // A long-lived stream can be cut by a proxy; reconnect on the same cursor.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.hidden || !selectedId) return;
      const currentCursor = cursorRef.current;
      api.supportChatTypingState(token, selectedId)
        .then((result) => setTyping(Boolean(result?.typing)))
        .catch(() => {});
      // A cheap re-read keeps the thread correct if the stream was interrupted.
      if (currentCursor > 0 && Math.random() < 0.25) {
        api.supportChatThread(token, selectedId, { before_seq: undefined })
          .then((detail) => {
            if (detail?.messages?.length && highestSeq(detail.messages) > currentCursor) {
              setMessages((current) => mergeMessages(current, detail.messages));
              cursorRef.current = Math.max(cursorRef.current, highestSeq(detail.messages));
            }
          })
          .catch(() => {});
      }
    }, THREAD_POLL_MS);
    return () => window.clearInterval(timer);
  }, [token, selectedId]);

  const refreshList = async () => {
    const rows = await loadList();
    return rows;
  };

  const createConversation = async () => {
    if (creating) return null;
    setCreating(true);
    setError("");
    try {
      const detail = await api.supportChatStart(token, {}, storeId);
      setThread(detail);
      setMessages(detail.messages || []);
      setSelectedId(detail.id);
      cursorRef.current = highestSeq(detail.messages || []);
      await loadList();
      return detail;
    } catch (requestError) {
      setError(requestError.message || "Could not start a conversation");
      return null;
    } finally {
      setCreating(false);
    }
  };

  const streamAssistant = async (id, text) => {
    const response = await fetch(`${api.baseUrl}/support/chat/conversations/${id}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(storeId ? { "X-Store-ID": storeId } : {}),
      },
      credentials: "include",
      body: JSON.stringify({ message: text, language: "en" }),
    });
    if (!response.ok) {
      let detail = "The assistant could not answer right now.";
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
        if (payload?.delta) {
          answer += payload.delta;
          setMessages((current) => current.map((message, index) => (
            index === current.length - 1 ? { ...message, body: answer } : message
          )));
          scrollToEnd();
        }
      }
    }
  };

  const uploadFiles = async () => {
    const uploaded = [];
    for (const item of files) {
      const asset = await api.supportChatUpload(token, item.file);
      uploaded.push(asset);
    }
    return uploaded;
  };

  const clearFiles = () => setFiles((current) => {
    current.forEach((item) => URL.revokeObjectURL(item.url));
    return [];
  });

  const send = async () => {
    if (busy) return;
    const text = input.trim();
    if (!text && !files.length) return;
    setError("");
    setBusy(true);
    let id = selectedId;
    try {
      if (!id) {
        const started = await createConversation();
        if (!started) return;
        id = started.id;
      }
      const currentStatus = threadRef.current?.status || "ai";
      if (currentStatus === "ai" && !files.length) {
        // The assistant answers in the same thread. A local pair keeps the
        // streaming answer visible before the persisted rows arrive.
        setMessages((current) => [
          ...current,
          { id: `local-user-${Date.now()}`, seq: Number.MAX_SAFE_INTEGER - 2, author_type: "merchant", kind: "text", body: text, author_name: "You", created_at: new Date().toISOString() },
          { id: `local-assistant-${Date.now()}`, seq: Number.MAX_SAFE_INTEGER - 1, author_type: "assistant", kind: "text", body: "", author_name: "Chmaba assistant", created_at: new Date().toISOString() },
        ]);
        setInput("");
        scrollToEnd();
        await streamAssistant(id, text);
      } else {
        if (currentStatus === "ai" && files.length) {
          // A screenshot or document needs a person to look at it.
          await api.supportChatHandoff(token, id, {});
        }
        if (files.length) {
          const uploaded = await uploadFiles();
          for (const asset of uploaded) {
            await api.supportChatSend(token, id, {
              kind: asset.kind === "image" ? "image" : "file",
              attachment_url: asset.url,
              attachment_name: asset.original_filename,
              attachment_content_type: asset.content_type,
              attachment_byte_size: asset.byte_size,
            });
          }
          clearFiles();
        }
        if (text) {
          setInput("");
          await api.supportChatSend(token, id, { body: text });
        }
      }
      setTyping(false);
      await openThread(id, { keepSelection: true });
      await refreshList();
    } catch (requestError) {
      setError(requestError.message || "Could not send your message");
      if (id) await openThread(id, { keepSelection: true });
    } finally {
      setBusy(false);
    }
  };

  const requestHuman = async () => {
    if (!thread || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.supportChatHandoff(token, thread.id, {});
      setThread((current) => current ? { ...current, ...updated } : current);
      notify?.("A support teammate has been notified");
      await refreshList();
    } catch (requestError) {
      setError(requestError.message || "Could not notify support");
    } finally {
      setBusy(false);
    }
  };

  const closeConversation = async () => {
    if (!thread || busy) return;
    setBusy(true);
    try {
      const updated = await api.supportChatClose(token, thread.id);
      setThread((current) => current ? { ...current, ...updated } : current);
      notify?.("Conversation closed");
      await refreshList();
    } catch (requestError) {
      setError(requestError.message || "Could not close the conversation");
    } finally {
      setBusy(false);
    }
  };

  const pickFiles = (event) => {
    const chosen = Array.from(event.target.files || []);
    event.target.value = "";
    const next = [...files];
    for (const file of chosen) {
      if (file.size > MAX_ATTACHMENT_BYTES) continue;
      next.push({ file, url: URL.createObjectURL(file) });
    }
    setFiles(next.slice(0, 5));
  };

  const removeFile = (index) => {
    const item = files[index];
    if (item?.url) URL.revokeObjectURL(item.url);
    setFiles(files.filter((_, position) => position !== index));
  };

  const onComposerChange = (value) => {
    setInput(value);
    const now = Date.now();
    if (selectedId && value.trim() && now - typingSentRef.current > 2500) {
      typingSentRef.current = now;
      api.supportChatTyping(token, selectedId).catch(() => {});
    }
  };

  const meta = statusMeta(thread?.status);
  const canAskAssistant = !thread || thread.status === "ai";
  const isClosed = thread && ["resolved", "closed"].includes(thread.status);

  return <div className="overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white dark:border-[#2a2b30] dark:bg-[#1f2025]">
    <div className="grid min-h-[580px] lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="border-b border-[#f0f0f3] dark:border-[#2a2b30] lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
          <div>
            <p className="text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">Conversations</p>
            <p className="mt-0.5 text-[10px] text-[#92939d]">{conversations.length} total</p>
          </div>
          <Button size="xs" variant="soft" onClick={async () => { await createConversation(); }} disabled={creating}>
            {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />} New
          </Button>
        </div>
        <div className="app-scrollbar max-h-[520px] overflow-y-auto">
          {listing ? <p className="p-4 text-xs text-[#92939d]">Loading...</p>
            : conversations.length === 0
              ? <p className="p-4 text-xs text-[#92939d]">No conversations yet.</p>
              : conversations.map((conversation) => {
                const status = statusMeta(conversation.status);
                return <button
                  key={conversation.id}
                  type="button"
                  onClick={() => openThread(conversation.id)}
                  className={`flex w-full flex-col gap-1 border-b border-[#f0f0f3] px-4 py-3 text-left transition hover:bg-[#fafafd] dark:border-[#2a2b30] dark:hover:bg-[#26272d] ${selectedId === conversation.id ? "bg-[#f7f5ff] dark:bg-[#26272d]" : ""}`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="min-w-0 flex-1 truncate text-xs font-bold text-[#303139] dark:text-[#e4e4e8]">{conversationTitle(conversation)}</span>
                    {conversation.unread_count > 0 && <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[#6957f5] px-1 text-[9px] font-extrabold text-white">{conversation.unread_count > 9 ? "9+" : conversation.unread_count}</span>}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${status.className}`}>{status.label}</span>
                    <span className="truncate text-[10px] text-[#92939d]">{conversation.last_message_preview || "No messages yet"}</span>
                  </span>
                </button>;
              })}
        </div>
      </aside>

      <section className="flex min-w-0 flex-col">
        {!selectedId ? (
          <EmptyConversation onStart={createConversation} busy={creating} disabled={!token} />
        ) : (
          <>
            <header className="flex flex-wrap items-start justify-between gap-2 border-b border-[#f0f0f3] px-4 py-3 dark:border-[#2a2b30]">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">
                  <span className="truncate">{conversationTitle(thread)}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold ${meta.className}`}>{meta.label}</span>
                </p>
                <p className="mt-0.5 text-[10px] text-[#92939d]">
                  {thread?.reference}
                  {thread?.assigned_admin_name ? ` · ${thread.assigned_admin_name}` : ""}
                  {thread?.created_at ? ` · opened ${formatDateTime(thread.created_at)}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                {canAskAssistant && <Button size="xs" variant="outline" onClick={requestHuman} disabled={busy}>
                  <UserRound size={12} /> Talk to a human
                </Button>}
                {!isClosed && <Button size="xs" variant="ghost" onClick={closeConversation} disabled={busy}>Close</Button>}
              </div>
            </header>

            {thread?.status === "waiting" && <p className="border-b border-[#f0f0f3] bg-[#fffaf0] px-4 py-2 text-[11px] font-semibold text-[#8a661a] dark:border-[#2a2b30] dark:bg-[#2a2518] dark:text-[#d8b45f]">
              A support teammate has been notified. You can keep typing - they will see everything here, including the assistant's answers.
            </p>}
            {thread?.status === "live" && <p className="border-b border-[#f0f0f3] bg-[#f6fbf2] px-4 py-2 text-[11px] font-semibold text-[#4f7a33] dark:border-[#2a2b30] dark:bg-[#202a1b] dark:text-[#b7d8a0]">
              You are chatting with {thread?.assigned_admin_name || "Chmaba support"}. Replies arrive here in real time.
            </p>}
            {isClosed && <p className="border-b border-[#f0f0f3] bg-[#fafafd] px-4 py-2 text-[11px] font-semibold text-[#777883] dark:border-[#2a2b30] dark:bg-[#26272d] dark:text-[#a9aab3]">
              This conversation is closed. Send a message to reopen it.
            </p>}

            <div ref={scrollRef} className="app-scrollbar flex-1 space-y-3 overflow-y-auto px-4 py-4" style={{ maxHeight: "440px" }}>
              {loadingThread && messages.length === 0 ? <p className="text-xs text-[#92939d]">Loading conversation...</p> : null}
              {messages.length === 0 && !loadingThread ? <div className="mx-auto max-w-[360px] rounded-2xl bg-[#faf9ff] p-4 text-center dark:bg-[#26272d]">
                <Sparkles size={16} className="mx-auto text-[#6957f5]" />
                <p className="mt-2 text-xs font-bold text-[#303139] dark:text-[#e4e4e8]">How can we help?</p>
                <p className="mt-1 text-[11px] leading-5 text-[#898a95]">Describe the issue below. Billing, setup, a bug - anything.</p>
              </div> : null}
              {messages.map((message) => <MessageBubble key={message.id || message.seq} message={message} />)}
              {typing && <p className="text-[10px] font-semibold text-[#92939d]">Support is typing...</p>}
            </div>

            <div className="border-t border-[#f0f0f3] p-3 dark:border-[#2a2b30]">
              {error && <p className="mb-2 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-[11px] text-[#c2564b] dark:border-[#4a2a28] dark:bg-[#2a1d1b]">{error}</p>}
              {files.length > 0 && <div className="mb-2 flex flex-wrap gap-2">
                {files.map((item, index) => <span key={item.url} className="relative inline-block">
                  <img src={item.url} alt="" className="h-12 w-12 rounded-lg border border-[#e6e6ed] object-cover dark:border-[#363740]" />
                  <button type="button" onClick={() => removeFile(index)} className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#17181c] text-white"><X size={10} /></button>
                </span>)}
              </div>}
              <div className="flex items-end gap-2">
                <button type="button" onClick={() => fileRef.current?.click()} disabled={busy} aria-label="Attach a file" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#e6e6ed] text-[#777883] transition hover:border-[#bdb9ee] hover:text-[#6957f5] disabled:opacity-50 dark:border-[#363740]">
                  <Paperclip size={15} />
                </button>
                <textarea
                  value={input}
                  onChange={(event) => onComposerChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      send();
                    }
                  }}
                  rows={2}
                  placeholder={canAskAssistant ? "Ask the assistant, or describe the issue..." : "Write a message to support..."}
                  className="min-h-[40px] w-full resize-none rounded-xl border border-[#e6e6ed] bg-white px-3 py-2 text-xs text-[#303139] outline-none focus:border-[#bdb9ee] dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#e4e4e8]"
                />
                <Button onClick={send} disabled={busy || (!input.trim() && !files.length)} className="h-10 shrink-0">
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                </Button>
              </div>
              <div className="mt-1.5 flex items-center justify-between gap-2">
                <p className="text-[10px] text-[#92939d]">
                  {canAskAssistant ? "The assistant answers instantly. Ask for a human whenever you want." : "Messages go straight to the support team."}
                </p>
                {canAskAssistant && <label className="flex cursor-pointer items-center gap-1 text-[10px] font-semibold text-[#6957f5]">
                  <ImagePlus size={11} /> Screenshot
                  <input ref={fileRef} type="file" accept={ACCEPTED_FILES} multiple className="hidden" onChange={pickFiles} />
                </label>}
                {!canAskAssistant && <input ref={fileRef} type="file" accept={ACCEPTED_FILES} multiple className="hidden" onChange={pickFiles} />}
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  </div>;
}

export { SupportChatView };
