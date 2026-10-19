import { useEffect, useRef, useState } from "react";

import { ChatBubbleIcon, CloseIcon, FileIcon, MicIcon, PaperclipIcon, SendIcon, SmileIcon, StopIcon } from "./ChatIcons";
import { CHAT_EMOJIS, chatClock, formatBytes, formatDuration, kindForFile, linkify } from "../lib/chat";

const ACCEPTED_FILES = "image/*,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,audio/*";

// A voice note is recorded here and handed to the parent as a File, because the
// parent owns the upload+send dance and the failure copy. MediaRecorder picks its
// own container per browser (WebM on Chrome/Firefox, MP4 on Safari), so the
// filename suffix is derived from the negotiated mime type rather than assumed.
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
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : type.includes("wav") ? "wav" : "webm";
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

  const stop = () => {
    try { recorderRef.current?.stop(); } catch { /* already stopped */ }
  };

  const cancel = () => {
    cancelledRef.current = true;
    stop();
  };

  return { recording, seconds, voiceError, supported, start, stop, cancel };
}

function sameSide(message, viewer) {
  return message.sender_type === viewer;
}

// An order the store sent: a card the shopper can open, rather than a number
// they have to hunt for.
function OrderCard({ order, linkBase = "" }) {
  if (!order) return null;
  const href = order.public_token ? `${linkBase}/order/${order.public_token}` : null;
  const inner = (
    <span className="mt-1 flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-3 py-2">
      <span className="min-w-0">
        <span className="block truncate text-xs font-bold text-ink">📦 Order #{order.order_number}</span>
        <span className="block text-[10px] text-muted">{order.status}</span>
      </span>
      <span className="shrink-0 text-xs font-extrabold text-ink">{order.currency_code} {order.total}</span>
    </span>
  );
  return href ? (
    <a href={href} target="_blank" rel="noreferrer" className="block">{inner}</a>
  ) : inner;
}

function Attachment({ message }) {
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
    // An overlay keeps the shopper in the conversation; a new tab would throw
    // them out of it, which is the opposite of what an image is for here.
    return (
      <>
        <button type="button" onClick={() => setZoomed(true)} className="mt-1 block" aria-label="Open photo">
          <img src={attachment.url} alt={attachment.name || "Photo"} className="max-h-60 w-full rounded-xl object-cover" />
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
      <FileIcon />
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

function MessageBubble({ message, viewer, onReact, showSeen = false }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const mine = sameSide(message, viewer);
  const reactions = message.reactions || [];
  return (
    <div className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      {!mine && message.author_name ? <p className="mb-0.5 px-1 text-[10px] font-semibold text-muted">{message.author_name}</p> : null}
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-5 shadow-[0_1px_2px_rgba(28,31,42,.06)] ${
          mine ? "bg-brand text-white" : "border border-line bg-surface text-ink-soft"
        }`}
      >
        {message.body ? <MessageText body={message.body} linkClass={mine ? "text-white" : "text-brand"} /> : null}
        <Attachment message={message} />
        <p className={`mt-1 text-[10px] ${mine ? "text-white/70" : "text-muted"}`}>{chatClock(message.created_at)}</p>
      </div>
      {showSeen ? <p className="mt-0.5 px-1 text-[10px] font-semibold text-muted">Seen</p> : null}
      <div className="mt-1 flex flex-wrap items-center gap-1">
        {reactions.map((reaction) => (
          <button
            key={reaction.emoji}
            type="button"
            onClick={() => onReact?.(message, reaction.emoji)}
            className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${
              reaction.reacted ? "border-brand bg-brand-soft text-brand" : "border-line bg-surface text-muted"
            }`}
          >
            <span>{reaction.emoji}</span>
            <span className="font-bold">{reaction.count}</span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => setPickerOpen((value) => !value)}
          aria-label="React to this message"
          className="rounded-full border border-line bg-surface px-1.5 py-0.5 text-[11px] text-muted transition hover:text-brand"
        >
          ＋
        </button>
        {pickerOpen ? (
          <span className="flex items-center gap-0.5 rounded-full border border-line bg-surface px-1.5 py-0.5">
            {CHAT_EMOJIS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                onClick={() => { setPickerOpen(false); onReact?.(message, emoji); }}
                className="px-0.5 text-sm transition hover:scale-125"
              >
                {emoji}
              </button>
            ))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

// The thread is shared by the store page widget and the account inbox: both are
// one customer talking to one store, and the server already decides which side a
// message belongs to with `sender_type`.
export default function ChatThread({
  messages = [],
  viewer = "customer",
  busy = false,
  onSendText,
  onSendAttachment,
  onReact,
  hasMore = false,
  onLoadEarlier,
  loadingEarlier = false,
  emptyText = "Send a message and the store will reply here.",
  footerText,
  compact = false,
}) {
  const [draft, setDraft] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);
  const scrollRef = useRef(null);
  const { recording, seconds, voiceError, supported, start, stop, cancel } = useVoiceRecorder((file, durationMs) => {
    onSendAttachment?.({ kind: "voice", file, durationMs });
  });

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, recording]);

  const lastOwnIndex = messages.reduce((last, message, index) => (sameSide(message, viewer) ? index : last), -1);

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setEmojiOpen(false);
    onSendText?.(text);
  };

  const onFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > 5_000_000) {
      setLocalError("That file is larger than 5 MB.");
      return;
    }
    setLocalError("");
    onSendAttachment?.({ kind: kindForFile(file), file });
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {hasMore ? (
          <div className="flex justify-center pb-1">
            <button
              type="button"
              onClick={onLoadEarlier}
              disabled={loadingEarlier}
              className="rounded-full border border-line bg-surface px-3 py-1 text-[11px] font-semibold text-muted transition hover:text-ink disabled:opacity-50"
            >
              {loadingEarlier ? "Loading…" : "Load earlier"}
            </button>
          </div>
        ) : null}
        {messages.length === 0 ? <p className="py-8 text-center text-xs text-muted">{emptyText}</p> : null}
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            viewer={viewer}
            onReact={onReact}
            showSeen={index === lastOwnIndex && Boolean(message.seen)}
          />
        ))}
      </div>

      {localError || voiceError ? <p className="px-3 pb-1 text-[11px] font-semibold text-danger">{localError || voiceError}</p> : null}

      {recording ? (
        <div className={`flex items-center gap-3 border-t border-line ${compact ? "px-3 py-2" : "px-3 py-2.5"}`}>
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-danger" />
          <span className="text-xs font-bold text-ink-soft">Recording {formatDuration(seconds * 1000)}</span>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" onClick={cancel} className="rounded-lg px-2 py-1 text-[11px] font-bold text-muted">
              Cancel
            </button>
            <button type="button" onClick={stop} className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-white" aria-label="Send voice note">
              <StopIcon />
            </button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(event) => { event.preventDefault(); submit(); }}
          className={`border-t border-line ${compact ? "px-2 py-2" : "px-3 py-2.5"}`}
        >
          <div className="flex items-end gap-1.5 rounded-2xl border border-line bg-surface px-2 py-1.5">
            <button type="button" onClick={() => setEmojiOpen((value) => !value)} aria-label="Emoji" className="p-1 text-muted transition hover:text-brand">
              <SmileIcon />
            </button>
            <button type="button" onClick={() => fileRef.current?.click()} aria-label="Attach a file" className="p-1 text-muted transition hover:text-brand">
              <PaperclipIcon />
            </button>
            {supported ? (
              <button type="button" onClick={start} aria-label="Record a voice note" className="p-1 text-muted transition hover:text-brand">
                <MicIcon />
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
              placeholder="Write a message…"
              className="max-h-24 min-h-7 flex-1 resize-none bg-transparent px-1 py-1 text-sm text-ink outline-none placeholder:text-muted"
            />
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Send"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-white disabled:opacity-40"
            >
              <SendIcon />
            </button>
          </div>
          {emojiOpen ? (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {CHAT_EMOJIS.map((emoji) => (
                <button
                  key={emoji}
                  type="button"
                  onClick={() => { setDraft((value) => value + emoji); setEmojiOpen(false); }}
                  className="text-lg transition hover:scale-125"
                >
                  {emoji}
                </button>
              ))}
            </div>
          ) : null}
          <input ref={fileRef} type="file" accept={ACCEPTED_FILES} onChange={onFileChange} className="hidden" />
        </form>
      )}

      {footerText ? <p className="border-t border-line px-3 py-1.5 text-center text-[10px] text-muted">{footerText}</p> : null}
    </div>
  );
}

export { ChatBubbleIcon, CloseIcon };
