// Company-wide date/time display formatting.
//
// A merchant picks one date pattern and one time style in Settings. The choice
// is stored on the company and applied everywhere dates appear, including
// printed receipts. An empty value means "use the device default", so an
// untouched workspace keeps rendering exactly as before.
//
// The active choice lives in a tiny module-level store so non-React helpers and
// deeply nested components can call formatDate/formatDateTime directly. React
// views subscribe through subscribeDateFormat to re-render when it changes.
//
// Kept dependency-free and pure so it can be unit-tested with node:test.

export const DATE_FORMAT_OPTIONS = [
  { value: "", label: "Device default" },
  { value: "DD/MM/YYYY", label: "Day first (31/12/2026)" },
  { value: "MM/DD/YYYY", label: "Month first (12/31/2026)" },
  { value: "YYYY-MM-DD", label: "ISO (2026-12-31)" },
  { value: "D MMM YYYY", label: "Text month (31 Dec 2026)" },
];

export const TIME_FORMAT_OPTIONS = [
  { value: "", label: "Device default" },
  { value: "12h", label: "12-hour (6:05 PM)" },
  { value: "24h", label: "24-hour (18:05)" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let active = { dateFormat: "", timeFormat: "" };
const listeners = new Set();

export function getDateFormatConfig() {
  return { ...active };
}

export function setDateFormatConfig(next) {
  const dateFormat = typeof next?.dateFormat === "string" ? next.dateFormat : "";
  const timeFormat = typeof next?.timeFormat === "string" ? next.timeFormat : "";
  if (dateFormat === active.dateFormat && timeFormat === active.timeFormat) return;
  active = { dateFormat, timeFormat };
  listeners.forEach((listener) => {
    try {
      listener(active);
    } catch {
      /* a broken subscriber must not stop the others */
    }
  });
}

export function subscribeDateFormat(listener) {
  if (typeof listener !== "function") return () => {};
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function pad(value) {
  return String(value).padStart(2, "0");
}

// Parse ISO strings, timestamps and Date objects into a local Date. A bare
// "YYYY-MM-DD" is treated as a local calendar day, not UTC midnight, so a
// date-only value never shifts a day in negative-offset timezones.
export function toDate(value) {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.trim())) {
    const [year, month, day] = value.trim().split("-").map(Number);
    const parsed = new Date(year, month - 1, day);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDateWith(value, dateFormat = "") {
  const date = toDate(value);
  if (!date) return "";
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  switch (dateFormat) {
    case "DD/MM/YYYY":
      return `${pad(day)}/${pad(month)}/${year}`;
    case "MM/DD/YYYY":
      return `${pad(month)}/${pad(day)}/${year}`;
    case "YYYY-MM-DD":
      return `${year}-${pad(month)}-${pad(day)}`;
    case "D MMM YYYY":
      return `${day} ${MONTHS[month - 1]} ${year}`;
    default:
      return date.toLocaleDateString();
  }
}

export function formatTimeWith(value, timeFormat = "") {
  const date = toDate(value);
  if (!date) return "";
  if (timeFormat === "24h") return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  if (timeFormat === "12h") {
    const hours = date.getHours();
    const hour12 = hours % 12 === 0 ? 12 : hours % 12;
    return `${hour12}:${pad(date.getMinutes())} ${hours < 12 ? "AM" : "PM"}`;
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(value) {
  return formatDateWith(value, active.dateFormat);
}

export function formatTime(value) {
  return formatTimeWith(value, active.timeFormat);
}

export function formatDateTime(value) {
  const date = toDate(value);
  if (!date) return "";
  // Nothing chosen: match the old toLocaleString() behaviour exactly.
  if (!active.dateFormat && !active.timeFormat) return date.toLocaleString();
  return `${formatDateWith(date, active.dateFormat)} ${formatTimeWith(date, active.timeFormat)}`;
}
