import { useEffect, useRef, useState } from "react";
import { LifeBuoy, Loader2, Send, Sparkles } from "lucide-react";
import { api } from "../api";

// A small, self-contained support chat. It sends the visible transcript as
// history on each turn; the backend grounds answers in the help corpus scoped to
// the caller's business type and role.
function SupportChat({ token, starterPrompts = [], className = "" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [escalating, setEscalating] = useState(false);
  const [escalation, setEscalation] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  const updateLastAssistant = (content) =>
    setMessages((current) => current.map((message, index) => (index === current.length - 1 ? { ...message, content } : message)));

  const streamAnswer = async (question, history) => {
    const response = await fetch(`${api.baseUrl}/support/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      credentials: "include",
      body: JSON.stringify({ message: question, history }),
    });
    if (!response.ok || !response.body) {
      // Streaming unavailable (older server, proxy buffering): fall back to one-shot.
      const fallback = await api.supportChat(token, { message: question, history });
      return fallback?.answer || "";
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
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
          if (parsed.delta) {
            answer += parsed.delta;
            updateLastAssistant(answer);
          }
          if (parsed.error) streamError = parsed.error;
        } catch {
          /* ignore a malformed chunk */
        }
      }
    }
    if (streamError) throw new Error(streamError);
    return answer;
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setError("");
    setInput("");
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setSending(true);
    try {
      const answer = await streamAnswer(question, history);
      updateLastAssistant(answer || "I could not find an answer for that.");
    } catch (err) {
      setError(err.message || "The assistant is unavailable right now.");
      setMessages((current) => current.slice(0, -1));
    } finally {
      setSending(false);
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
      <div className="flex items-center gap-2">
        <Sparkles size={15} className="text-[#6957f5]" />
        <p className="text-xs font-extrabold text-[#303139] dark:text-[#e4e4e8]">Ask the assistant</p>
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
        <div ref={scrollRef} className="mt-3 max-h-[340px] space-y-2 overflow-y-auto app-scrollbar">
          {messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-[11px] leading-5 ${
                  message.role === "user"
                    ? "bg-[#6957f5] text-white"
                    : "bg-[#f4f4f8] text-[#454652] dark:bg-[#2a2b32] dark:text-[#d3d4dc]"
                }`}
              >
                {message.content}
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
