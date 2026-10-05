import { useEffect, useRef, useState } from "react";
import { Bold, Italic, Link2, List, ListOrdered, Loader2, Quote, Sparkles, Underline } from "lucide-react";
import { looksLikeHtml, plainTextToHtml } from "../lib/richtextHtml";

// A small, dependency-free WYSIWYG editor for support replies.
//
// The browser sends a conservative subset of HTML; the API sanitises it before
// storing (see chmabapos_api/app/services/richtext.py). When an AI action is
// wired in, the model returns plain text which is converted to simple
// paragraphs with `plainTextToHtml` before it lands in the editor.

// Re-exported for callers that import the helpers alongside the editor.
export { looksLikeHtml, plainTextToHtml };

function ToolButton({ label, onClick, disabled, children }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      // Keep the caret/selection in the editable area when a toolbar button is pressed.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md text-[#62636d] transition hover:bg-[#f0efff] hover:text-[#5b4be3] disabled:opacity-40 dark:text-[#a9aab3] dark:hover:bg-[#2a2b32]"
    >
      {children}
    </button>
  );
}

export function RichTextEditor({
  value,
  onChange,
  placeholder = "Write a message...",
  disabled = false,
  minHeight = 96,
  onAiAction = null,
  aiBusy = false,
  aiLabel = "Rewrite with AI",
}) {
  const ref = useRef(null);
  const [empty, setEmpty] = useState(!(value || "").trim());

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const next = value || "";
    if (el.innerHTML !== next) {
      el.innerHTML = next;
      setEmpty(!el.textContent.trim());
    }
  }, [value]);

  const sync = () => {
    const el = ref.current;
    if (!el) return;
    setEmpty(!el.textContent.trim());
    onChange?.(el.innerHTML);
  };

  const exec = (command, arg = null) => {
    if (disabled) return;
    const el = ref.current;
    if (!el) return;
    el.focus();
    try {
      // Prefer tags over inline styles so the stored HTML stays simple.
      document.execCommand("styleWithCSS", false, false);
      document.execCommand(command, false, arg);
    } catch {
      /* execCommand unsupported: leave the content untouched */
    }
    sync();
  };

  const addLink = () => {
    const url = window.prompt("Link URL", "https://");
    if (url) exec("createLink", url);
  };

  return (
    <div className={`overflow-hidden rounded-xl border border-[#e6e6ed] bg-white focus-within:border-[#bdb9ee] dark:border-[#363740] dark:bg-[#1a1b1f] ${disabled ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-center gap-0.5 border-b border-[#f0f0f3] px-1.5 py-1 dark:border-[#2a2b30]">
        <ToolButton label="Bold" onClick={() => exec("bold")} disabled={disabled}><Bold size={14} /></ToolButton>
        <ToolButton label="Italic" onClick={() => exec("italic")} disabled={disabled}><Italic size={14} /></ToolButton>
        <ToolButton label="Underline" onClick={() => exec("underline")} disabled={disabled}><Underline size={14} /></ToolButton>
        <ToolButton label="Bulleted list" onClick={() => exec("insertUnorderedList")} disabled={disabled}><List size={14} /></ToolButton>
        <ToolButton label="Numbered list" onClick={() => exec("insertOrderedList")} disabled={disabled}><ListOrdered size={14} /></ToolButton>
        <ToolButton label="Quote" onClick={() => exec("formatBlock", "blockquote")} disabled={disabled}><Quote size={14} /></ToolButton>
        <ToolButton label="Link" onClick={addLink} disabled={disabled}><Link2 size={14} /></ToolButton>
        {onAiAction && (
          <button
            type="button"
            disabled={disabled || aiBusy}
            onMouseDown={(event) => event.preventDefault()}
            onClick={onAiAction}
            className="ml-auto flex h-7 items-center gap-1.5 rounded-md bg-[#f0efff] px-2 text-[10px] font-bold text-[#5b4be3] transition hover:bg-[#e7e4ff] disabled:opacity-50 dark:bg-[#2b2850] dark:text-[#b9afff]"
          >
            {aiBusy ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {aiBusy ? "Writing..." : aiLabel}
          </button>
        )}
      </div>
      <div className="relative">
        <div
          ref={ref}
          contentEditable={!disabled}
          suppressContentEditableWarning
          role="textbox"
          aria-multiline="true"
          onInput={sync}
          onBlur={sync}
          className="rich-text app-scrollbar w-full overflow-y-auto px-3 py-2 text-xs leading-5 text-[#303139] outline-none dark:text-[#e4e4e8]"
          style={{ minHeight }}
        />
        {empty && <span className="pointer-events-none absolute left-3 top-2 text-xs text-[#92939d]">{placeholder}</span>}
      </div>
    </div>
  );
}

export function RichBody({ html, className = "" }) {
  const content = html || "";
  if (!content) return null;
  if (looksLikeHtml(content)) {
    return <div className={`rich-text ${className}`} dangerouslySetInnerHTML={{ __html: content }} />;
  }
  return <p className={`whitespace-pre-wrap ${className}`}>{content}</p>;
}
