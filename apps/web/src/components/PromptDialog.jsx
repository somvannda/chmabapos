import { useEffect, useState } from "react";
import { Button, Field, Modal } from "./ui";

// A small single-field text dialog used in place of window.prompt, so every
// prompt in the POS matches the in-app modal styling (theme, keyboard, states)
// instead of the native browser popup.
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
  const disabled = required && !value.trim();
  const submit = () => {
    if (!disabled) onConfirm?.(value);
  };
  return (
    <Modal open={open} onClose={onCancel} title={title} description={description} width="max-w-[440px]">
      <Field
        label={label}
        hint={hint}
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
      />
      <div className="mt-5 flex gap-2">
        <Button variant="outline" className="flex-1" onClick={onCancel}>Cancel</Button>
        <Button className="flex-1" onClick={submit} disabled={disabled}>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}

export { PromptDialog };
