import { useEffect, useRef, useState } from "react";
import { LifeBuoy, Loader2, Send, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api";

// A small, self-contained support chat. It sends the visible transcript as
// history on each turn; the backend grounds answers in the help corpus scoped to
// the caller's business type and role, and streams the answer back.
function SupportChat({ token, starterPrompts = [], className = "", onOpenGuide }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [escalating, setEscalating] = useState(false);
  const [escalation, setEscalation] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    api.supportConversations(token)
      .then((rows) => { if (active) setConversations(rows || []); })
      .catch(() => { if (active) setConversations([]); });
    return () => { active = false; };
  }, [token]);

  const refreshConversations = () => {
    api.supportConversations(token)
      .then((rows) => setConversations(rows || []))
      .catch(() => {});
  };

  const openConversation = async (id) => {
    if (!id) return;
    setError("");
    setEscalation("");
    try {
      const detail = await api.supportConversation(token, id);
      setConversationId(detail.id);
      // Restored turns keep their text; citations are a live-answer affordance.
      setMessages((detail.messages || []).map((message) => ({ role: message.role, content: message.content, guides: [], feedback: null })));
    } catch (err) {
      setError(err.message || "Could not load that conversation.");
    }
  };

  const newChat = () => {
    setMessages([]);
    setConversationId(null);
    setError("");
    setEscalation("");
  };

  const patchLastAssistant = (patch) =>
    setMessages((current) => current.map((message, index) => (index === current.length - 1 ? { ...message, ...patch } : message)));

  const streamAnswer = async (question, history) => {
    const response = await fetch(`${api.baseUrl}/support/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      credentials: "include",
      body: JSON.stringify({ message: question, history, conversation_id: conversationId || undefined }),
    });
    if (!response.ok || !response.body) {
      // Streaming unavailable (older server, proxy buffering): fall back to one-shot.
      const fallback = await api.supportChat(token, { message: question, history, conversation_id: conversationId || undefined });
      if (fallback?.conversation_id) setConversationId(fallback.conversation_id);
      return { answer: fallback?.answer || "", guides: [] };
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let guides = [];
    let streamError = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const event of events) {
        const line = event.split("\n").find((row) => row.startsWith("data:"));
        if (!line) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.conversation_id) setConversationId(parsed.conversation_id);
          if (parsed.guides) {
            guides = parsed.guides;
            patchLastAssistant({ guides });
          }
          if (parsed.delta) {
            answer += parsed.delta;
            patchLastAssistant({ content: answer });
          }
          if (parsed.error) streamError = parsed.error;
        } catch {
          /* ignore a malformed chunk */
        }
      }
    }
    if (streamError) throw new Error(streamError);
    return { answer, guides };
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setError("");
    setEscalation("");
    setInput("");
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((current) => [
      ...current,
      { role: "user", content: question },
      { role: "assistant", content: "", guides: [], feedback: null },
    ]);
    setSending(true);
    try {
      const { answer } = await streamAnswer(question, history);
      patchLastAssistant({ content: answer || "I could not find an answer for that." });
      refreshConversations();
    } catch (err) {
      setError(err.message || "The assistant is unavailable right now.");
      setMessages((current) => current.slice(0, -1));
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

  const escalate = async () => {
    if (escalating) return;
    const lastQuestion = [...messages].reverse().find((message) => message.role === "user")?.content || input.trim();
    if (!lastQuestion) return;
    setEscalating(true);
    setError("");
    try {
      const result = await api.supportEscalate(token, { message: lastQuestion });
      setEscalation(result?.detail || "Our support team has been notified.");
    } catch (err) {
      setError(err.message || "Could not reach support right now.");
    } finally {
      setEscalating(false);
    }
  };

  return (
    <div className={`rounded-2xl border border-[#e6e5f3] bg-white p-4 dark:border-[#33343a] dark:bg-[#1f2025] ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-[#6957f5]" />
          <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Ask the assistant</p>
        </div>
        <div className="flex items-center gap-2">
          {conversations.length > 1 && (
            <select
              value={conversationId || ""}
              onChange={(event) => openConversation(event.target.value)}
              className="h-7 max-w-[150px] rounded-lg border border-[#e4e4eb] bg-white px-1.5 text-[10px] font-semibold text-[#62636d] dark:border-[#363740] dark:bg-[#1a1b1f] dark:text-[#a9aab3]"
            >
              <option value="">Earlier chats</option>
              {conversations.map((row) => (
                <option key={row.id} value={row.id}>{row.title || "Chat"}</option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={newChat}
            className="rounded-lg border border-[#e4e4eb] px-2 py-1 text-[10px] font-bold text-[#62636d] transition hover:border-[#bdb9ee] hover:text-[#6957f5] dark:border-[#363740] dark:text-[#a9aab3]"
          >
            New chat
          </button>
        </div>
      </div>

      {messages.length === 0 && starterPrompts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {starterPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => send(prompt)}
              disabled={sending}
              className="rounded-full border border-[#e4e4eb] bg-[#faf9ff] px-3 py-1 text-[10px] font-semibold text-[#696a76] transition hover:border-[#bdb9ee] hover:text-[#6957f5] disabled:opacity-60 dark:border-[#363740] dark:bg-[#202126] dark:text-[#a9aab3]"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {(messages.length > 0 || sending) && (
        <div ref={scrollRef} className="mt-3 max-h-[360px] space-y-2 overflow-y-auto app-scrollbar">
          {messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${message.role === "user" ? "" : "space-y-1"}`}>
                <div
                  className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-[11px] leading-5 ${
                    message.role === "user"
                      ? "bg-[#6957f5] text-white"
                      : "bg-[#f4f4f8] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"
                  }`}
                >
                  {message.content}
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
          ))}
          {sending && (
            <div className="flex items-center gap-2 text-[11px] text-[#92939d]">
              <Loader2 size={13} className="animate-spin" /> Thinking...
            </div>
          )}
        </div>
      )}

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
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask how to use Chmaba..."
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
        <button
          type="button"
          onClick={escalate}
          disabled={escalating}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#e4e4eb] px-2.5 py-1.5 text-[10px] font-bold text-[#62636d] transition hover:border-[#bdb9ee] hover:text-[#6957f5] disabled:opacity-60 dark:border-[#363740] dark:text-[#a9aab3]"
        >
          <LifeBuoy size={12} /> {escalating ? "Contacting..." : "Talk to a human"}
        </button>
        {escalation && <span className="text-[10px] font-semibold text-[#6daf43]">{escalation}</span>}
      </div>
    </div>
  );
}

export { SupportChat };
