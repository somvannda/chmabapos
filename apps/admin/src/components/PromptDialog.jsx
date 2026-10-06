import { useEffect, useState } from "react";
import { X } from "lucide-react";

// A small single-field text dialog used in place of window.prompt so admin
// prompts match the in-app modal styling. Self-contained on purpose: the
// platform primitives (Modal/Field/Button) live inside App.jsx and importing
// them here would create a cycle.
function PromptDialog({
  open,
  title,
  description,
  label,
  hint,
  placeholder,
  defaultValue = "",
  confirmLabel = "Save",
  required = false,
  type = "text",
  onConfirm,
  onCancel,
}) {
  const [value, setValue] = useState(defaultValue);
  useEffect(() => {
    if (open) setValue(defaultValue);
  }, [open, defaultValue]);
  if (!open) return null;
  const disabled = required && !value.trim();
  const submit = () => {
    if (!disabled) onConfirm?.(value);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/45 p-4 backdrop-blur-[3px]" onMouseDown={(event) => event.target === event.currentTarget && onCancel?.()}>
      <div className="max-h-[92vh] w-full max-w-[440px] overflow-y-auto rounded-2xl bg-white shadow-[0_24px_80px_rgba(20,21,28,.22)] dark:bg-[#1f2025]">
        <div className="flex items-start justify-between border-b border-[#eeeeF2] px-5 py-4 dark:border-[#2a2b30]">
          <div>
            <h2 className="text-base font-bold text-[#202128] dark:text-[#e4e4e8]">{title}</h2>
            {description && <p className="mt-1 text-xs text-[#898a95]">{description}</p>}
          </div>
          <button type="button" aria-label="Close" title="Close" onClick={onCancel} className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0eff5] hover:text-[#272831] dark:text-[#9a9aa4] dark:hover:bg-[#2a2b32]">
            <X size={17} />
          </button>
        </div>
        <div className="p-5">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold text-[#4f5059] dark:text-[#c8c9d0]">{label}</span>
            <input
              type={type}
              value={value}
              placeholder={placeholder}
              autoFocus
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  submit();
                }
              }}
              className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm text-[#22232a] outline-none transition placeholder:text-[#aaabb4] focus:border-[#887bf3] focus:ring-4 focus:ring-[#6957f5]/10 dark:border-[#363740] dark:bg-[#17181c] dark:text-[#e4e4e8]"
            />
            {hint && <span className="mt-1.5 block text-[11px] text-[#92939d]">{hint}</span>}
          </label>
          <div className="mt-5 flex gap-2">
            <button type="button" onClick={onCancel} className="h-10 flex-1 rounded-xl border border-[#dedee7] bg-white text-sm font-semibold text-[#282930] transition hover:border-[#bdbbc9] hover:bg-[#fafafd] dark:border-[#4a4b51] dark:bg-transparent dark:text-white dark:hover:bg-[#303137]">Cancel</button>
            <button type="button" onClick={submit} disabled={disabled} className="h-10 flex-1 rounded-xl bg-[#6957f5] text-sm font-semibold text-white shadow-[0_7px_16px_rgba(105,87,245,.2)] transition hover:bg-[#5845e7] disabled:cursor-not-allowed disabled:opacity-50">{confirmLabel}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export { PromptDialog };
