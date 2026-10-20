import { useEffect, useRef, useState } from "react";

import { ChatBubbleIcon, CloseIcon, FileIcon, MicIcon, PaperclipIcon, ReplyIcon, SendIcon, SmileIcon, StopIcon } from "./ChatIcons";
import { ImageMedia, PendingAttachment, VideoMedia, VoiceMedia } from "./ChatMedia";
import { CHAT_EMOJIS, chatClock, formatBytes, formatDuration, kindForFile, linkify } from "../lib/chat";

const ACCEPTED_FILES = "image/*,video/*,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,audio/*";

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

// A product the store sent: the same card as an order, linking to the item page.
function ProductCard({ product }) {
  if (!product) return null;
  const inner = (
    <span className="mt-1 flex items-center gap-3 rounded-xl border border-line bg-surface p-2">
      {product.image_url ? (
        <img src={product.image_url} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" />
      ) : null}
      <span className="min-w-0">
        <span className="block truncate text-xs font-bold text-ink">{product.name}</span>
        <span className="block text-[10px] text-muted">{product.currency_code} {product.price}</span>
      </span>
    </span>
  );
  return product.url_path ? <a href={product.url_path} className="block">{inner}</a> : inner;
}

function Attachment({ message }) {
  const attachment = message.attachment;
  if (message.kind === "order") return <OrderCard order={message.order} />;
  if (message.kind === "product") return <ProductCard product={message.product} />;
  if (!attachment) return null;
  if (message.kind === "video") {
    return <VideoMedia attachment={attachment} />;
  }
  if (message.kind === "image") {
    return <ImageMedia attachment={attachment} />;
  }
  if (message.kind === "voice") {
    return <VoiceMedia attachment={attachment} />;
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

// A small receipt under the sender's last message: one tick when the server has
// it, two when the other side's client received it, two in the brand colour when
// they have read it. The label is on the element too, so colour is never the only
// signal.
function ReceiptIcon({ state }) {
  if (!state) return null;
  const seen = state === "seen";
  const delivered = state === "delivered" || seen;
  const label = seen ? "Seen" : delivered ? "Delivered" : "Sent";
  return (
    <span
      className={`mt-0.5 flex items-center justify-end gap-1 px-1 text-[10px] font-semibold ${seen ? "text-brand" : "text-muted"}`}
      title={label}
      aria-label={label}
    >
      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d={delivered ? "M2 10.5l3.5 3.5L12 7" : "M5 10.5l3.5 3.5L15 7"} strokeLinecap="round" strokeLinejoin="round" />
        {delivered ? <path d="M9 12.5l2.5 2.5L19 6" strokeLinecap="round" strokeLinejoin="round" /> : null}
      </svg>
    </span>
  );
}

function quotePreview(reply) {
  if (reply.body) return reply.body;
  if (reply.kind === "image") return "Photo";
  if (reply.kind === "video") return "Video";
  if (reply.kind === "voice") return "Voice message";
  if (reply.kind === "file") return reply.attachment_name || "Document";
  if (reply.kind === "order") return "Order";
  if (reply.kind === "product") return "Product";
  return "Message";
}

function MessageBubble({ message, viewer, onReact, onReply, showState = null }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const mine = sameSide(message, viewer);
  const reactions = message.reactions || [];
  return (
    <div id={`chat-message-${message.id}`} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      {!mine && message.author_name ? <p className="mb-0.5 px-1 text-[10px] font-semibold text-muted">{message.author_name}</p> : null}
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-5 shadow-[0_1px_2px_rgba(28,31,42,.06)] ${
          mine ? "bg-brand text-white" : "border border-line bg-surface text-ink-soft"
        }`}
      >
        {message.reply_to ? (
          <div className={`mb-1.5 rounded-lg border-l-2 px-2 py-1 ${mine ? "border-white/60 bg-white/10" : "border-brand bg-brand-soft"}`}>
            <p className={`truncate text-[10px] font-bold ${mine ? "text-white/85" : "text-brand"}`}>
              {message.reply_to.author_name || (message.reply_to.sender_type === "seller" ? "Store" : "Customer")}
            </p>
            <p className={`truncate text-[11px] ${mine ? "text-white/80" : "text-muted"}`}>{quotePreview(message.reply_to)}</p>
          </div>
        ) : null}
        {message.body ? <MessageText body={message.body} linkClass={mine ? "text-white" : "text-brand"} /> : null}
        <Attachment message={message} />
        <p className={`mt-1 text-[10px] ${mine ? "text-white/70" : "text-muted"}`}>{chatClock(message.created_at)}</p>
      </div>
      {showState ? <ReceiptIcon state={showState} /> : null}
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
          onClick={() => onReply?.(message)}
          aria-label="Reply to this message"
          title="Reply"
          className="rounded-full border border-line bg-surface px-1.5 py-0.5 text-muted transition hover:text-brand"
        >
          <ReplyIcon className="h-3.5 w-3.5" />
        </button>
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
  onTyping,
  typingText = "",
  onRefresh,
  emptyText = "Send a message and the store will reply here.",
  footerText,
  compact = false,
}) {
  const [draft, setDraft] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [localError, setLocalError] = useState("");
  const [pending, setPending] = useState(null);
  const [replyTo, setReplyTo] = useState(null);
  const [pull, setPull] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const fileRef = useRef(null);
  const scrollRef = useRef(null);
  const pullStartRef = useRef(null);

  // A picked or recorded file waits here until the shopper presses send, as
  // Telegram and Messenger do: the preview shows what would be uploaded and can
  // be removed, and the composer's text becomes its caption.
  const stage = (file, kind, durationMs = null) => {
    setLocalError("");
    setPending({
      file,
      kind,
      durationMs,
      name: file.name || (kind === "voice" ? "Voice message" : "Attachment"),
      previewUrl: kind === "file" ? null : URL.createObjectURL(file),
    });
  };

  const clearPending = () => setPending(null);

  const { recording, seconds, voiceError, supported, start, stop, cancel } = useVoiceRecorder((file, durationMs) => {
    stage(file, "voice", durationMs);
  });

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, recording]);

  // The preview is a local object URL; release it when the draft is replaced or
  // the thread closes, so a phone does not hold several clips in memory.
  useEffect(() => () => {
    if (pending?.previewUrl) URL.revokeObjectURL(pending.previewUrl);
  }, [pending]);

  const lastOwnIndex = messages.reduce((last, message, index) => (sameSide(message, viewer) ? index : last), -1);

  const submit = async () => {
    if (busy) return;
    const text = draft.trim();
    if (pending) {
      const sent = await onSendAttachment?.({
        kind: pending.kind,
        file: pending.file,
        durationMs: pending.durationMs,
        caption: text || undefined,
        replyToMessageId: replyTo?.id,
      });
      // Keep the staged file when the send failed, so the shopper can retry
      // instead of finding their photo or voice note gone.
      if (sent) {
        setPending(null);
        setReplyTo(null);
        setDraft("");
        setEmojiOpen(false);
      }
      return;
    }
    if (!text) return;
    const sent = await onSendText?.(text, replyTo?.id);
    // A failed send keeps the text, so it can be retried rather than retyped.
    if (sent === false) return;
    setReplyTo(null);
    setDraft("");
    setEmojiOpen(false);
  };

  const onFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const kind = kindForFile(file);
    const limit = kind === "video" ? 25_000_000 : 5_000_000;
    if (file.size > limit) {
      setLocalError(kind === "video" ? "That video is larger than 25 MB." : "That file is larger than 5 MB.");
      return;
    }
    stage(file, kind);
  };

  // Pull-to-refresh is a safety net, not the main path: realtime delivery is the
  // stream. It matters when the stream died while the tab was asleep and the
  // reconnection has not caught up yet.
  const onPullStart = (event) => {
    if (!onRefresh || refreshing) return;
    const node = scrollRef.current;
    if (node && node.scrollTop <= 0) pullStartRef.current = event.touches[0].clientY;
  };

  const onPullMove = (event) => {
    if (pullStartRef.current == null) return;
    const node = scrollRef.current;
    if (node && node.scrollTop > 0) {
      pullStartRef.current = null;
      setPull(0);
      return;
    }
    const distance = event.touches[0].clientY - pullStartRef.current;
    setPull(distance > 0 ? Math.min(72, Math.round(distance * 0.45)) : 0);
  };

  const onPullEnd = async () => {
    if (pullStartRef.current == null) return;
    pullStartRef.current = null;
    if (pull < 44) {
      setPull(0);
      return;
    }
    setRefreshing(true);
    setPull(30);
    try {
      await onRefresh?.();
    } finally {
      setRefreshing(false);
      setPull(0);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {onRefresh ? (
        <div
          aria-live="polite"
          className="flex shrink-0 items-center justify-center overflow-hidden text-[11px] font-semibold text-muted transition-[height] duration-150"
          style={{ height: refreshing ? 30 : pull }}
        >
          {refreshing ? "Refreshing…" : pull >= 44 ? "Release to refresh" : pull > 0 ? "Pull to refresh" : ""}
        </div>
      ) : null}
      <div
        ref={scrollRef}
        onTouchStart={onPullStart}
        onTouchMove={onPullMove}
        onTouchEnd={onPullEnd}
        onTouchCancel={onPullEnd}
        className="flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 py-3"
      >
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
            onReply={setReplyTo}
            showState={index === lastOwnIndex ? message.state : null}
          />
        ))}
      </div>

      {localError || voiceError ? <p className="px-3 pb-1 text-[11px] font-semibold text-danger">{localError || voiceError}</p> : null}

      {typingText ? <p className="px-3 pb-1 text-[10px] font-semibold text-muted">{typingText}</p> : null}

      {replyTo ? (
        <div className="flex items-start gap-2 border-t border-line bg-surface px-3 py-2">
          <span className="mt-0.5 h-8 w-0.5 shrink-0 rounded-full bg-brand" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[10px] font-bold text-brand">
              Replying to {replyTo.author_name || (sameSide(replyTo, viewer) ? "yourself" : viewer === "customer" ? "the store" : "the customer")}
            </p>
            <p className="truncate text-[11px] text-muted">{quotePreview(replyTo)}</p>
          </div>
          <button type="button" onClick={() => setReplyTo(null)} aria-label="Cancel reply" className="p-1 text-muted transition hover:text-ink">
            <CloseIcon />
          </button>
        </div>
      ) : null}

      {pending ? (
        <PendingAttachment pending={pending} busy={busy} compact={compact} onRemove={clearPending} />
      ) : null}

      {recording ? (
        <div className={`flex items-center gap-3 border-t border-line ${compact ? "px-3 py-2" : "px-3 py-2.5"}`}>
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-danger" />
          <span className="text-xs font-bold text-ink-soft">Recording {formatDuration(seconds * 1000)}</span>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" onClick={cancel} className="rounded-lg px-2 py-1 text-[11px] font-bold text-muted">
              Cancel
            </button>
            <button type="button" onClick={stop} className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-white" aria-label="Use voice note">
              <StopIcon />
            </button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(event) => { event.preventDefault(); void submit(); }}
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
              onChange={(event) => { setDraft(event.target.value); onTyping?.(); }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
              rows={1}
              placeholder="Write a message…"
              className="max-h-24 min-h-7 flex-1 resize-none bg-transparent px-1 py-1 text-base text-ink outline-none placeholder:text-muted sm:text-sm"
            />
            <button
              type="submit"
              disabled={busy || (!draft.trim() && !pending)}
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
