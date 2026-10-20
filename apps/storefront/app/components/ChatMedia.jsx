import { useCallback, useEffect, useRef, useState } from "react";

import { CloseIcon, FileIcon, MicIcon, ReloadIcon } from "./ChatIcons";
import { formatBytes, formatDuration, retryMediaUrl } from "../lib/chat";

// Media that has just been uploaded occasionally sits in a permanent "loading"
// state in iOS Safari and Chrome - the same element that plays after a page
// reload never receives its metadata. The clip itself is fine (the URL is
// content-addressed and immutable), so the cure is the one a reload performs:
// ask for it again. Each element keeps an attempt counter and re-requests its
// URL with a cache-busting query on an error, a stall, or a metadata timeout.
// After a few attempts it offers a tap-to-reload control rather than pretending
// to still be busy forever.
const MAX_RETRIES = 3;
const STALL_MS = 4000;

function useReloadableMedia(url) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const attemptRef = useRef(0);

  useEffect(() => {
    attemptRef.current = 0;
    setAttempt(0);
    setFailed(false);
  }, [url]);

  const retry = useCallback(() => {
    if (attemptRef.current >= MAX_RETRIES) {
      setFailed(true);
      return;
    }
    attemptRef.current += 1;
    setAttempt(attemptRef.current);
  }, []);

  const reload = useCallback(() => {
    attemptRef.current = 0;
    setAttempt(0);
    setFailed(false);
  }, []);

  return { src: retryMediaUrl(url, attempt), failed, retry, reload };
}

// A media element can report no error and simply never move past HAVE_NOTHING.
// Give it a few seconds, then treat that like a failed request.
function useStallRetry(ref, src, retry, failed) {
  useEffect(() => {
    if (failed) return undefined;
    const timer = window.setTimeout(() => {
      const node = ref.current;
      if (node && node.readyState < 1) retry();
    }, STALL_MS);
    return () => window.clearTimeout(timer);
  }, [ref, src, retry, failed]);
}

function ReloadControl({ label, onReload }) {
  return (
    <button
      type="button"
      onClick={onReload}
      className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[11px] font-semibold text-ink-soft transition hover:text-brand"
    >
      <ReloadIcon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

export function ImageMedia({ attachment }) {
  const { src, failed, retry, reload } = useReloadableMedia(attachment.url);
  const [zoomed, setZoomed] = useState(false);
  useEffect(() => {
    if (!zoomed) return undefined;
    const onKey = (event) => { if (event.key === "Escape") setZoomed(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoomed]);
  if (failed) return <ReloadControl label="Reload photo" onReload={reload} />;
  return (
    <>
      <button type="button" onClick={() => setZoomed(true)} className="mt-1 block" aria-label="Open photo">
        <img
          key={src}
          src={src}
          alt={attachment.name || "Photo"}
          className="max-h-60 w-full rounded-xl bg-surface-sunken object-cover"
          onError={retry}
        />
      </button>
      {zoomed ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={attachment.name || "Photo"}
          onClick={() => setZoomed(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4"
        >
          {/* The retried URL, not the stored one: the first request may have
              failed, and the enlarged copy must be the one that worked. */}
          <img src={src} alt={attachment.name || "Photo"} className="max-h-full max-w-full rounded-xl" />
        </div>
      ) : null}
    </>
  );
}

export function VideoMedia({ attachment }) {
  const { src, failed, retry, reload } = useReloadableMedia(attachment.url);
  const videoRef = useRef(null);
  useStallRetry(videoRef, src, retry, failed);
  if (failed) return <ReloadControl label="Reload video" onReload={reload} />;
  return (
    <video
      key={src}
      ref={videoRef}
      controls
      playsInline
      preload="metadata"
      src={src}
      onError={retry}
      className="mt-1 max-h-60 w-full rounded-xl bg-black/5"
    />
  );
}

export function VoiceMedia({ attachment }) {
  const { src, failed, retry, reload } = useReloadableMedia(attachment.url);
  const audioRef = useRef(null);
  const [loading, setLoading] = useState(true);
  useStallRetry(audioRef, src, retry, failed);
  if (failed) return <ReloadControl label="Reload voice note" onReload={reload} />;
  return (
    <div className="mt-1">
      <audio
        key={src}
        ref={audioRef}
        controls
        preload="metadata"
        src={src}
        onLoadedMetadata={() => setLoading(false)}
        onCanPlay={() => setLoading(false)}
        onError={retry}
        className="h-9 w-56 max-w-full"
      />
      <p className="mt-0.5 text-[10px] opacity-70">
        {loading ? "Loading voice note…" : attachment.duration_ms ? formatDuration(attachment.duration_ms) : "Voice note"}
      </p>
    </div>
  );
}

// A staged attachment: a local object URL, so the shopper can check a photo or
// listen to a voice note before it is uploaded and sent.
export function PendingAttachment({ pending, busy, compact = false, onRemove }) {
  return (
    <div className={`border-t border-line ${compact ? "px-3 py-2" : "px-3 py-2.5"}`}>
      <div className="flex items-center gap-2 rounded-xl border border-line bg-surface p-2">
        {pending.kind === "image" ? (
          <img src={pending.previewUrl} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" />
        ) : pending.kind === "video" ? (
          <video src={pending.previewUrl} muted playsInline className="h-12 w-16 shrink-0 rounded-lg bg-black/5 object-cover" />
        ) : pending.kind === "voice" ? (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
            <MicIcon />
          </span>
        ) : (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-muted">
            <FileIcon />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-bold text-ink-soft">
            {pending.kind === "voice" ? "Voice message" : pending.name || "Attachment"}
          </p>
          <p className="text-[10px] text-muted">
            {pending.kind === "voice" && pending.durationMs ? `${formatDuration(pending.durationMs)} · ` : null}
            {formatBytes(pending.file.size)}
            {" · "}
            {busy ? "Sending…" : "Ready to send"}
          </p>
        </div>
        <button
          type="button"
          onClick={onRemove}
          disabled={busy}
          aria-label="Remove attachment"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted transition hover:bg-surface-sunken hover:text-ink disabled:opacity-40"
        >
          <CloseIcon />
        </button>
      </div>
      {pending.kind === "voice" ? (
        <audio controls preload="metadata" src={pending.previewUrl} className="mt-1.5 h-9 w-full" />
      ) : null}
    </div>
  );
}
