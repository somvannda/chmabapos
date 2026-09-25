import { useState, useEffect } from "react";
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  GripVertical,
  Mail,
  Plus,
  Printer,
  Receipt,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { Field, Dropdown, Button, Badge, formatCurrencyAmount, Modal } from "../components/ui";
import { api } from "../api";

const BASE_FONT_SIZE = 10;

const RECEIPT_LANG = { en: "English", km: "Khmer", both: "Both" };

const RECEIPT_TRANSLATIONS = {
  en: {
    receipt_no: "Receipt #",
    receipt_heading: "RECEIPT",
    date: "Date",
    cashier: "Cashier",
    phone: "Phone",
    email: "Email",
    tax_id: "Tax ID",
    customer: "Customer",
    subtotal: "Subtotal",
    discount: "Discount",
    tax: "Tax",
    tip: "Tip",
    total: "Total",
    served_by: "Served by",
    thank_you: "Thank you for shopping with",
  },
  km: {
    receipt_no: "លេខវិក្កយបត្រ",
    receipt_heading: "វិក្កយបត្រ",
    date: "កាលបរិច្ឆេទ",
    cashier: "អ្នកគិតលុយ",
    phone: "ទូរស័ព្ទ",
    email: "អ៊ីមែល",
    tax_id: "អត្តលេខពន្ធ",
    customer: "អតិថិជន",
    subtotal: "សរុបរង",
    discount: "បញ្ចុះតម្លៃ",
    tax: "ពន្ធ",
    tip: "ជូត",
    total: "សរុប",
    served_by: "បម្រើដោយ",
    thank_you: "អរគុណដែលបានទិញជាមួយ",
  },
};

const RECEIPT_ALIGN = { left: "Left", center: "Center", right: "Right" };

const RECEIPT_SIZE = { sm: "Small", md: "Normal", lg: "Large" };

const RECEIPT_SPAN = { "1": "1 col", "2": "2 cols", "3": "3 cols" };

const RECEIPT_FONTS = { sans: "Sans", serif: "Serif", mono: "Mono", script: "Script" };

const RECEIPT_FONT_STACKS = {
  sans: "Inter, 'Noto Sans Khmer Web', ui-sans-serif, system-ui, sans-serif",
  serif: "Georgia, 'Times New Roman', 'Noto Sans Khmer Web', serif",
  mono: "ui-monospace, 'SFMono-Regular', Menlo, 'Noto Sans Khmer Web', monospace",
  script: "'Segoe Script', 'Comic Sans MS', 'Noto Sans Khmer Web', cursive",
};

const RECEIPT_ZOOM = { sm: 0.85, md: 1, lg: 1.18 };

const RECEIPT_SECTIONS = [
  { id: "logo", label: "Logo", align: "left", span: "3" },
  { id: "receipt_heading", label: "Receipt heading", align: "center", span: "3" },
  { id: "business_name", label: "Business name", align: "left", span: "3" },
  { id: "store_name", label: "Shop name", align: "left", span: "3" },
  { id: "order_number", label: "Order number", align: "left", span: "1" },
  { id: "receipt_date", label: "Receipt date", align: "left", span: "1" },
  { id: "cashier", label: "Cashier", align: "left", span: "1" },
  { id: "address", label: "Store address", align: "left", span: "3" },
  { id: "phone", label: "Store phone", align: "left", span: "1" },
  { id: "email", label: "Store email", align: "left", span: "1" },
  { id: "tax_id", label: "Tax ID", align: "left", span: "1" },
  { id: "customer_name", label: "Customer name", align: "left", span: "3" },
  { id: "customer_phone", label: "Customer phone", align: "left", span: "1" },
  { id: "customer_email", label: "Customer email", align: "left", span: "1" },
  { id: "items", label: "Items & totals", align: "left", span: "3" },
  { id: "note", label: "Note", align: "center", span: "3" },
];

function tLabel(lang, key, customLabels) {
  const cl = customLabels || {};
  const clEn = cl.en || {};
  const clKm = cl.km || {};
  const defaults = RECEIPT_TRANSLATIONS.en;
  const kmDefaults = RECEIPT_TRANSLATIONS.km;
  const en = clEn[key] || defaults[key] || key;
  const km = clKm[key] || kmDefaults[key] || key;
  if (lang === "en") return en;
  if (lang === "km") return km;
  return km + " / " + en;
}

function sectionType(section) {
  if (section?.type) return section.type;
  const id = String(section?.id || "");
  if (id.startsWith("blank")) return "blank";
  return id;
}

function normalizeSpan(value, fallback) {
  if (RECEIPT_SPAN[String(value)]) return String(value);
  return fallback || "3";
}

function normalizeLayoutSection(section) {
  const type = sectionType(section);
  const def = RECEIPT_SECTIONS.find((item) => item.id === type);
  let fontSize = Number(section.fontSize);
  if (!Number.isFinite(fontSize) || fontSize <= 0) {
    const legacy = RECEIPT_ZOOM[section.size];
    fontSize = legacy ? Number((legacy * BASE_FONT_SIZE).toFixed(2)) : BASE_FONT_SIZE;
  }
  return {
    id: section.id || type,
    type,
    enabled: section.enabled !== false,
    align: RECEIPT_ALIGN[section.align] ? section.align : def?.align || "left",
    span: normalizeSpan(section.span, section.width === "half" ? "1" : def?.span),
    fontSize,
    height: Number(section.height) > 0 ? Number(section.height) : type === "blank" ? 16 : undefined,
    width: type === "blank" ? (Number(section.width) > 0 ? Number(section.width) : null) : undefined,
    font: RECEIPT_FONTS[section.font] ? section.font : "sans",
    bold: Boolean(section.bold),
    italic: Boolean(section.italic),
    underline: Boolean(section.underline),
  };
}

function normalizeLayoutArray(layout) {
  const out = [];
  for (const raw of Array.isArray(layout) ? layout : []) {
    if (sectionType(raw) === "meta") {
      for (const id of ["order_number", "receipt_date", "cashier"]) {
        out.push(normalizeLayoutSection({
          id,
          type: id,
          enabled: raw.enabled,
          align: raw.align,
          span: raw.span,
          fontSize: raw.fontSize,
          size: raw.size,
          font: raw.font,
          bold: raw.bold,
          italic: raw.italic,
          underline: raw.underline,
        }));
      }
      continue;
    }
    out.push(normalizeLayoutSection(raw));
  }
  return out;
}

function getFallbackLayout() {
  return normalizeLayoutArray(["logo", "business_name", "order_number", "receipt_date", "items"].map((id) => {
    const def = RECEIPT_SECTIONS.find((item) => item.id === id);
    return { id, type: id, enabled: true, align: def?.align, span: "3" };
  }));
}

function layoutFromTemplates(prefs) {
  const templates = prefs?.receipt_templates;
  if (!templates || typeof templates !== "object") return null;
  const names = Object.keys(templates);
  if (!names.length) return null;
  const preferred = [prefs.receipt_default_template, prefs.receipt_active_template].find((name) => name && names.includes(name));
  const name = preferred || names[0];
  return normalizeLayoutArray(templates[name]);
}

function getReceiptLayout(prefs = {}) {
  const fromTemplates = layoutFromTemplates(prefs);
  if (fromTemplates) return fromTemplates;
  if (Array.isArray(prefs.receipt_layout)) return normalizeLayoutArray(prefs.receipt_layout);
  return getFallbackLayout();
}

function formatReceiptDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || "");
  const pad = (n) => String(n).padStart(2, "0");
  const hours24 = date.getHours();
  const suffix = hours24 >= 12 ? "PM" : "AM";
  const hours = hours24 % 12 || 12;
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(hours)}:${pad(date.getMinutes())} ${suffix}`;
}

function buildReceiptDemo(workspace, prefs) {
  const currency = workspace?.store?.currency_code || "USD";
  const rate = Number(workspace?.store?.service_tax_rate ?? 10);
  const charge = prefs.charge_tax !== false;
  const inclusive = Boolean(prefs.tax_inclusive);
  const items = [
    { id: "d1", product_name: "Iced Caffè Latte", sku: "ICL-300", quantity: 2, unit_price: 4.5, line_total: 9 },
    { id: "d2", product_name: "Butter croissant", sku: "BCR-110", quantity: 1, unit_price: 2.8, line_total: 2.8 },
    { id: "d3", product_name: "Sparkling water 330ml", sku: "SWA-060", quantity: 3, unit_price: 1.2, line_total: 3.6 },
  ];
  const subtotal = 15.4;
  const tax = charge ? (inclusive ? Number(((subtotal * rate) / (100 + rate)).toFixed(2)) : Number(((subtotal * rate) / 100).toFixed(2))) : 0;
  const total = Number((subtotal + (inclusive ? 0 : tax)).toFixed(2));
  const prefix = (prefs.receipt_prefix || "CHM").toUpperCase();
  const cash = Math.max(20, Math.ceil(total));
  return {
    id: "demo",
    order_number: `${prefix}-1042`,
    status: "paid",
    created_at: "2026-09-01T10:24:00",
    cashier_name: "Somvannda",
    customer: { name: "Pisey Chan", email: "pisey@chmaba.com", phone: "+855 12 345 678" },
    customer_name: "Pisey Chan",
    items,
    subtotal,
    discount: 0,
    tax,
    tip: 0,
    total,
    currency_code: currency,
    tenders: [
      { kind: "payment", method: "cash", amount: cash, currency_code: currency },
      { kind: "change", amount: Number((cash - total).toFixed(2)), currency_code: currency },
    ],
  };
}

function ProfessionalSection({ type, order, workspace, lang = "en", labels = {} }) {
  const currency = order.currency_code || workspace?.store?.currency_code || "USD";
  const prefs = workspace?.store?.preferences || {};
  const customerName = order.customer?.name || order.customer_name;
  const customerPhone = order.customer?.phone;
  const customerEmail = order.customer?.email;
  const address = workspace?.store?.address || workspace?.company?.address;
  const phone = workspace?.company?.phone || workspace?.store?.phone;
  const email = workspace?.store?.email || workspace?.company?.email;
  const taxId = workspace?.company?.tax_id;
  const cols = "grid-cols-[2rem_minmax(0,1fr)_2.5rem_6rem_7rem]";
  if (type === "logo") {
    return prefs.receipt_logo ? (
      <img src={prefs.receipt_logo} alt="logo" className="inline-block h-auto max-h-16 w-auto max-w-full object-contain" />
    ) : (
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-lg bg-[#17181d] text-[15px] font-extrabold text-[#c4f27c]">
        {(workspace?.company?.name || "C").slice(0, 1).toUpperCase()}
      </div>
    );
  }
  if (type === "receipt_heading") return <p className="text-lg font-extrabold uppercase tracking-[.2em]">{tLabel(lang, "receipt_heading", labels)}</p>;
  if (type === "business_name") return <p className="text-xl font-extrabold tracking-[-.03em]">{workspace?.company?.name || "Chmaba"}</p>;
  if (type === "store_name") return <p className="text-[11px] font-extrabold uppercase tracking-wide text-[#17181d]">{workspace?.store?.name || "Store"}</p>;
  if (type === "order_number")
    return <div className="text-[10px] leading-5 text-[#6b6c76]"><span className="font-bold text-[#34353d]">{tLabel(lang, "receipt_no", labels)}:</span> <span className="font-extrabold text-[#17181d]">{order.order_number}</span></div>;
  if (type === "receipt_date")
    return <div className="text-[10px] leading-5 text-[#6b6c76]"><span className="font-bold text-[#34353d]">{tLabel(lang, "date", labels)}:</span> {formatReceiptDate(order.created_at)}</div>;
  if (type === "cashier") {
    const cashier = order.cashier_name || order.cashier;
    if (!cashier) return null;
    return <div className="text-[10px] leading-5 text-[#6b6c76]">{tLabel(lang, "cashier", labels)}: {cashier}</div>;
  }
  if (type === "address") {
    if (!address) return null;
    return <div className="text-[10px] leading-5 text-[#8b8c96]">{address}</div>;
  }
  if (type === "phone") {
    if (!phone) return null;
    return <div className="text-[10px] leading-5 text-[#8b8c96]">{tLabel(lang, "phone", labels)}: {phone}</div>;
  }
  if (type === "email") {
    if (!email) return null;
    return <div className="text-[10px] leading-5 text-[#8b8c96]">{tLabel(lang, "email", labels)}: {email}</div>;
  }
  if (type === "tax_id") {
    if (!taxId) return null;
    return <div className="text-[10px] leading-5 text-[#8b8c96]">{tLabel(lang, "tax_id", labels)}: {taxId}</div>;
  }
  if (type === "customer_name") {
    if (!customerName) return null;
    return <div className="text-[10px] leading-5 text-[#6b6c76]"><span className="font-bold text-[#34353d]">{tLabel(lang, "customer", labels)}:</span> <span className="font-semibold text-[#34353d]">{customerName}</span></div>;
  }
  if (type === "customer_phone") {
    if (!customerPhone) return null;
    return <div className="text-[10px] leading-5 text-[#6b6c76]"><span className="font-bold text-[#34353d]">Phone:</span> {customerPhone}</div>;
  }
  if (type === "customer_email") {
    if (!customerEmail) return null;
    return <div className="text-[10px] leading-5 text-[#6b6c76]"><span className="font-bold text-[#34353d]">Email:</span> {customerEmail}</div>;
  }
  if (type === "items") {
    const subtotal = Number(order.subtotal || 0);
    const discount = Number(order.discount || 0);
    const tax = Number(order.tax || 0);
    const tip = Number(order.tip || 0);
    const total = Number(order.total || 0);
    return (
      <div>
        <div className={`grid ${cols} gap-x-3 rounded-t-lg bg-[#17181d] px-3 py-2 text-[10px] font-extrabold uppercase tracking-wide text-white`}>
          <div>No.</div><div className="pl-1">Item</div><div className="text-center">Qty</div><div className="text-right">Unit</div><div className="text-right">Amount</div>
        </div>
        <div className="border-x border-b border-[#e4e4ea]">
          <div className="divide-y divide-[#ececf1]">
            {order.items.map((item, index) => (
              <div key={item.id || index} className={`grid ${cols} gap-x-3 px-3 py-2 text-[11px]`}>
                <div className="text-[#9a9ba4]">{index + 1}</div>
                <div className="pr-2"><p className="font-bold text-[#34353d]">{item.product_name}</p><p className="mt-0.5 text-[9px] text-[#9a9ba4]">{item.sku || "—"}</p></div>
                <div className="text-center text-[#6b6c76]">{item.quantity}</div>
                <div className="text-right text-[#6b6c76]">{formatCurrencyAmount(Number(item.unit_price), currency)}</div>
                <div className="text-right font-bold text-[#34353d]">{formatCurrencyAmount(Number(item.line_total), currency)}</div>
              </div>
            ))}
          </div>
          <div className="space-y-1.5 border-t border-[#e4e4ea] bg-[#fafafd] px-3 py-3 text-[11px]">
            <div className={`grid ${cols} gap-x-3`}><div className="col-span-4 text-right text-[#6b6c76]">{tLabel(lang, "subtotal", labels)}</div><div className="text-right font-bold text-[#34353d]">{formatCurrencyAmount(subtotal, currency)}</div></div>
            {discount > 0 && <div className={`grid ${cols} gap-x-3`}><div className="col-span-4 text-right text-[#6b6c76]">{tLabel(lang, "discount", labels)}</div><div className="text-right font-bold text-[#34353d]">-{formatCurrencyAmount(discount, currency)}</div></div>}
            {tax > 0 && <div className={`grid ${cols} gap-x-3`}><div className="col-span-4 text-right text-[#6b6c76]">{prefs.tax_label || tLabel(lang, "tax", labels)}</div><div className="text-right font-bold text-[#34353d]">{formatCurrencyAmount(tax, currency)}</div></div>}
            {tip > 0 && <div className={`grid ${cols} gap-x-3`}><div className="col-span-4 text-right text-[#6b6c76]">{tLabel(lang, "tip", labels)}</div><div className="text-right font-bold text-[#34353d]">{formatCurrencyAmount(tip, currency)}</div></div>}
            <div className={`grid ${cols} items-center gap-x-3 border-t border-[#e4e4ea] pt-2`}><div className="col-span-4 text-right text-[11px] font-extrabold uppercase tracking-wide text-[#17181d]">{tLabel(lang, "total", labels)} {currency}</div><div className="text-right text-sm font-extrabold text-[#17181d]">{formatCurrencyAmount(total, currency)}</div></div>
          </div>
        </div>
      </div>
    );
  }
  if (type === "note") {
    const note = prefs.receipt_note;
    if (!note) return null;
    return <p className="whitespace-pre-wrap text-[10px] text-[#9a9ba4]">{note}</p>;
  }
  return null;
}

function ClassicSection({ type, order, workspace, lang = "en", labels = {} }) {
  const currency = order.currency_code || workspace?.store?.currency_code || "USD";
  const prefs = workspace?.store?.preferences || {};
  const customerName = order.customer?.name || order.customer_name;
  const customerPhone = order.customer?.phone;
  const customerEmail = order.customer?.email;
  const address = workspace?.store?.address || workspace?.company?.address;
  const phone = workspace?.company?.phone || workspace?.store?.phone;
  const email = workspace?.store?.email || workspace?.company?.email;
  const taxId = workspace?.company?.tax_id;
  if (type === "logo") {
    if (!prefs.receipt_logo) return null;
    return <img src={prefs.receipt_logo} alt="logo" className="inline-block h-auto max-h-10 w-auto max-w-full object-contain" />;
  }
  if (type === "receipt_heading") return <p className="text-base font-extrabold uppercase tracking-[.2em]">{tLabel(lang, "receipt_heading", labels)}</p>;
  if (type === "business_name") return <p className="text-sm font-extrabold tracking-[-.04em]">{workspace?.company?.name || "Chmaba"}</p>;
  if (type === "store_name") return <p className="text-[10px] font-extrabold text-[#34353d]">{workspace?.store?.name || "Store"}</p>;
  if (type === "order_number")
    return <p className="text-[10px] text-[#92939d]"><span className="font-bold text-[#34353d]">{tLabel(lang, "receipt_no", labels)}:</span> <span className="font-extrabold text-[#34353d]">{order.order_number}</span></p>;
  if (type === "receipt_date")
    return <p className="text-[10px] text-[#92939d]"><span className="font-bold text-[#34353d]">{tLabel(lang, "date", labels)}:</span> {formatReceiptDate(order.created_at)}</p>;
  if (type === "cashier") {
    const cashier = order.cashier_name || order.cashier;
    if (!cashier) return null;
    return <p className="text-[10px] text-[#92939d]">{tLabel(lang, "cashier", labels)}: {cashier}</p>;
  }
  if (type === "address") {
    if (!address) return null;
    return <p className="text-[10px] text-[#92939d]">{address}</p>;
  }
  if (type === "phone") {
    if (!phone) return null;
    return <p className="text-[10px] text-[#92939d]">{tLabel(lang, "phone", labels)}: {phone}</p>;
  }
  if (type === "email") {
    if (!email) return null;
    return <p className="text-[10px] text-[#92939d]">{tLabel(lang, "email", labels)}: {email}</p>;
  }
  if (type === "tax_id") {
    if (!taxId) return null;
    return <p className="text-[10px] text-[#92939d]">{tLabel(lang, "tax_id", labels)}: {taxId}</p>;
  }
  if (type === "customer_name") {
    if (!customerName) return null;
    return <p className="text-[10px] font-bold text-[#34353d]">{customerName}</p>;
  }
  if (type === "customer_phone") {
    if (!customerPhone) return null;
    return <p className="text-[10px] text-[#92939d]"><span className="font-bold text-[#34353d]">{tLabel(lang, "phone", labels)}:</span> {customerPhone}</p>;
  }
  if (type === "customer_email") {
    if (!customerEmail) return null;
    return <p className="text-[10px] text-[#92939d]"><span className="font-bold text-[#34353d]">{tLabel(lang, "email", labels)}:</span> {customerEmail}</p>;
  }
  if (type === "items") {
    return (
      <div>
        <div className="space-y-3">
          {order.items.map((item, index) => (
            <div key={item.id || index} className="flex items-start justify-between gap-3 text-[11px]">
              <div className="min-w-0 flex-1"><p className="font-bold">{index + 1}. {item.product_name}</p><p className="mt-1 text-[9px] text-[#92939d]">{item.quantity} × {formatCurrencyAmount(Number(item.unit_price), currency)}</p></div>
              <span className="font-extrabold">{formatCurrencyAmount(Number(item.line_total), currency)}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 space-y-2 border-t border-[#eeeeF2] pt-3 text-[11px]">
          <div className="flex justify-between text-[#777883]"><span>{tLabel(lang, "subtotal", labels)}</span><span>{formatCurrencyAmount(Number(order.subtotal), currency)}</span></div>
          {Number(order.discount) > 0 && <div className="flex justify-between text-[#777883]"><span>{tLabel(lang, "discount", labels)}</span><span>-{formatCurrencyAmount(Number(order.discount), currency)}</span></div>}
          <div className="flex justify-between text-[#777883]"><span>{prefs.tax_label || tLabel(lang, "tax", labels)}</span><span>{formatCurrencyAmount(Number(order.tax), currency)}</span></div>
          {Number(order.tip) > 0 && <div className="flex justify-between text-[#777883]"><span>{tLabel(lang, "tip", labels)}</span><span>{formatCurrencyAmount(Number(order.tip), currency)}</span></div>}
          <div className="flex justify-between border-t border-[#eeeeF2] pt-2 text-sm font-extrabold"><span>{tLabel(lang, "total", labels)}</span><span>{formatCurrencyAmount(Number(order.total), currency)}</span></div>
        </div>
      </div>
    );
  }
  if (type === "note") {
    const note = prefs.receipt_note;
    if (!note) return null;
    return <p className="whitespace-pre-wrap text-[10px] text-[#92939d]">{note}</p>;
  }
  return null;
}

function spanWidth(span, gap) {
  const safe = Math.min(3, Math.max(1, Number(span) || 3));
  if (safe >= 3) return "100%";
  const col = `calc((100% - 2 * ${gap}) / 3)`;
  return safe === 2 ? `calc(${col} * 2 + ${gap})` : col;
}

function sectionWrapperStyle(section, gap) {
  if (section.type === "blank") {
    const pixel = Number(section.width);
    return {
      flexGrow: 0,
      flexShrink: 0,
      flexBasis: pixel > 0 ? `${pixel}px` : spanWidth(section.span, gap),
      maxWidth: "100%",
      height: section.height || 16,
    };
  }
  if (section.type === "logo") {
    return {
      position: "relative",
      flexGrow: 0,
      flexShrink: 0,
      flexBasis: spanWidth(section.span, gap),
      maxWidth: "100%",
      height: 0,
      textAlign: section.align,
    };
  }
  const span = Math.min(3, Math.max(1, Number(section.span) || 3));
  return {
    flexGrow: span,
    flexShrink: 0,
    flexBasis: spanWidth(section.span, gap),
    maxWidth: "100%",
    textAlign: section.align,
    zoom: (Number(section.fontSize) || BASE_FONT_SIZE) / BASE_FONT_SIZE,
    fontFamily: RECEIPT_FONT_STACKS[section.font],
    fontWeight: section.bold ? 700 : undefined,
    fontStyle: section.italic ? "italic" : undefined,
    textDecoration: section.underline ? "underline" : undefined,
  };
}

function ReceiptProfessionalBody({ order, workspace }) {
  const prefs = workspace?.store?.preferences || {};
  const lang = prefs.receipt_language || "en";
  const labels = prefs.receipt_labels || { en: {}, km: {} };
  const sections = getReceiptLayout(prefs).filter((section) => section.enabled);
  return (
    <div className="receipt-content overflow-hidden px-7 py-7 text-[#17181d] sm:px-8">
      <div className="flex flex-wrap items-start" style={{ gap: "0.25rem 1rem" }}>
        {sections.map((section) => (
          <div key={section.id} className="min-w-0" style={sectionWrapperStyle(section, "1rem")}>
            {section.type === "blank" ? null : section.type === "logo" ? (
              <div className="absolute left-0 top-0 flex w-full" style={{ justifyContent: section.align === "right" ? "flex-end" : section.align === "left" ? "flex-start" : "center" }}>
                <ProfessionalSection type={section.type} order={order} workspace={workspace} lang={lang} labels={labels} />
              </div>
            ) : (
              <ProfessionalSection type={section.type} order={order} workspace={workspace} lang={lang} labels={labels} />
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 border-t border-[#ececf1] pt-3 text-center text-[11px] font-medium text-[#6b6c76]">{tLabel(lang, "thank_you", labels)} {workspace?.store?.name || "us"}.</p>
    </div>
  );
}

function ReceiptClassicBody({ order, workspace }) {
  const prefs = workspace?.store?.preferences || {};
  const lang = prefs.receipt_language || "en";
  const labels = prefs.receipt_labels || { en: {}, km: {} };
  const sections = getReceiptLayout(prefs).filter((section) => section.enabled);
  return (
    <div className="receipt-content overflow-hidden px-3 py-1">
      <div className="flex flex-wrap items-start" style={{ gap: "0.25rem 0.5rem" }}>
        {sections.map((section) => (
          <div key={section.id} className="min-w-0" style={sectionWrapperStyle(section, "0.5rem")}>
            {section.type === "blank" ? null : section.type === "logo" ? (
              <div className="absolute left-0 top-0 flex w-full" style={{ justifyContent: section.align === "right" ? "flex-end" : section.align === "left" ? "flex-start" : "center" }}>
                <ClassicSection type={section.type} order={order} workspace={workspace} lang={lang} labels={labels} />
              </div>
            ) : (
              <ClassicSection type={section.type} order={order} workspace={workspace} lang={lang} labels={labels} />
            )}
          </div>
        ))}
      </div>
      <div className="mt-4 text-center"><p className="text-[10px] text-[#92939d]">{tLabel(lang, "served_by", labels)} Chmaba</p></div>
    </div>
  );
}

function ReceiptSheetBody({ order, workspace }) {
  const prefs = workspace?.store?.preferences || {};
  const size = prefs.receipt_size === "a4" ? "a4" : prefs.receipt_size === "a5" ? "a5" : "thermal";
  const template = size === "thermal" ? "classic" : prefs.receipt_template === "professional" ? "professional" : "classic";
  return template === "professional" ? <ReceiptProfessionalBody order={order} workspace={workspace} /> : <ReceiptClassicBody order={order} workspace={workspace} />;
}

function ReceiptLiveSheet({ workspace, draft }) {
  const prefs = draft || {};
  const size = prefs.receipt_size === "a4" ? "a4" : prefs.receipt_size === "a5" ? "a5" : "thermal";
  const template = size === "thermal" ? "classic" : prefs.receipt_template === "professional" ? "professional" : "classic";
  const mmW = size === "thermal" ? 80 : size === "a5" ? 148 : 210;
  const mmH = size === "thermal" ? null : size === "a5" ? 210 : 297;
  const width = Math.round(mmW * 3.779527559055118);
  const minHeight = mmH ? Math.round(mmH * 3.779527559055118) : null;
  const pw = { ...workspace, store: { ...(workspace?.store || {}), preferences: { ...(workspace?.store?.preferences || {}), ...prefs } } };
  const order = buildReceiptDemo(workspace, prefs);
  const [holder, setHolder] = useState(null);
  const [sheet, setSheet] = useState(null);
  const [scale, setScale] = useState(1);
  const [contentH, setContentH] = useState(minHeight || 600);
  useEffect(() => {
    if (!holder) return;
    const fit = () => setScale(Math.min(1, Math.max(0.25, (holder.clientWidth - 8) / width)));
    fit();
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(fit);
      ro.observe(holder);
      return () => ro.disconnect();
    }
  }, [holder, width]);
  useEffect(() => {
    if (!sheet) return;
    const raf = requestAnimationFrame(() => setContentH((current) => {
      const next = minHeight || sheet.scrollHeight;
      return Math.abs(current - next) > 2 ? next : current;
    }));
    return () => cancelAnimationFrame(raf);
  }, [sheet, minHeight, prefs, template, size]);
  const displayW = Math.round(width * scale);
  const displayH = Math.round(contentH * scale);
  const label = { thermal: "Thermal 80mm", a5: "A5 · 148 × 210 mm", a4: "A4 · 210 × 297 mm" }[size];
  return (
    <div className="rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-extrabold">Live receipt preview</h4>
          <p className="mt-1 text-[11px] text-[#999aa4]">True paper size. Updates instantly as you change settings.</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="violet">{label} · {template === "professional" ? "Professional" : "Classic"}</Badge>
          <Button size="xs" variant="outline" onClick={() => window.print()}><Printer size={13} /> Print test</Button>
        </div>
      </div>
      <div ref={setHolder} className="app-scrollbar mt-4 overflow-x-auto rounded-xl border border-[#ececf1] bg-[#eef0f4] px-5 py-6">
        <div className="mx-auto bg-white shadow-[0_6px_24px_rgba(20,21,28,.08)]" style={{ width: displayW, height: displayH }}>
          <div style={{ width, minHeight, transform: `scale(${scale})`, transformOrigin: "top left" }} ref={setSheet}>
            <ReceiptSheetBody order={order} workspace={pw} />
          </div>
        </div>
      </div>
      <div className="hidden print:block">
        <div className="receipt-print-area bg-white text-[#202128]" data-receipt-size={size} data-template={template} style={{ width }}>
          <ReceiptSheetBody order={order} workspace={pw} />
        </div>
      </div>
    </div>
  );
}

function LabelInput({ label, enDefault, kmDefault, enVal, kmVal, onChange }) {
  return (
    <div className="rounded-lg border border-[#ececf1] p-2.5">
      <p className="text-[10px] font-bold text-[#4f5059]">{label}</p>
      <input value={enVal} onChange={(event) => onChange("en", event.target.value)} placeholder={enDefault} className="mt-1 h-8 w-full rounded-md border border-[#e7e7ed] bg-white px-2 text-[11px] outline-none placeholder:text-[#c0c0c8] focus:border-[#887bf3]" />
      <input value={kmVal} onChange={(event) => onChange("km", event.target.value)} placeholder={kmDefault} className="mt-1 h-8 w-full rounded-md border border-[#e7e7ed] bg-white px-2 text-[11px] outline-none placeholder:text-[#c0c0c8] focus:border-[#887bf3]" />
    </div>
  );
}

function buildInitialTemplates(prefs) {
  const saved = prefs.receipt_templates;
  if (saved && typeof saved === "object" && Object.keys(saved).length) {
    return Object.fromEntries(Object.entries(saved).map(([name, layout]) => [name, normalizeLayoutArray(layout)]));
  }
  return { Default: Array.isArray(prefs.receipt_layout) ? normalizeLayoutArray(prefs.receipt_layout) : [] };
}

function buildInitialName(prefs) {
  const saved = prefs.receipt_templates;
  const names = saved && typeof saved === "object" ? Object.keys(saved) : [];
  if (prefs.receipt_active_template && names.includes(prefs.receipt_active_template)) return prefs.receipt_active_template;
  if (prefs.receipt_default_template && names.includes(prefs.receipt_default_template)) return prefs.receipt_default_template;
  if (names.length) return names[0];
  return "Default";
}

function ReceiptsPane({ workspace, onUpdateStore, notify, loading }) {
  const prefs = workspace?.store?.preferences || {};
  const [form, setForm] = useState({
    receipt_prefix: prefs.receipt_prefix || "CHM",
    tax_label: prefs.tax_label || "Service tax",
    tax_inclusive: Boolean(prefs.tax_inclusive),
    charge_tax: prefs.charge_tax !== false,
    receipt_note: prefs.receipt_note || "",
    receipt_size: prefs.receipt_size || "thermal",
    receipt_template: prefs.receipt_template === "detailed" ? "professional" : prefs.receipt_template || "classic",
    receipt_logo: prefs.receipt_logo || "",
    receipt_language: prefs.receipt_language || "en",
    receipt_labels: prefs.receipt_labels || { en: {}, km: {} },
  });
  const [templates, setTemplates] = useState(() => buildInitialTemplates(prefs));
  const [activeName, setActiveName] = useState(() => buildInitialName(prefs));
  const [defaultName, setDefaultName] = useState(() => {
    const names = prefs.receipt_templates && typeof prefs.receipt_templates === "object" ? Object.keys(prefs.receipt_templates) : [];
    if (prefs.receipt_default_template && names.includes(prefs.receipt_default_template)) return prefs.receipt_default_template;
    if (prefs.receipt_active_template && names.includes(prefs.receipt_active_template)) return prefs.receipt_active_template;
    if (names.length) return names[0];
    return "Default";
  });
  const [newName, setNewName] = useState("");
  const [labelsOpen, setLabelsOpen] = useState(false);
  const [dragIndex, setDragIndex] = useState(null);

  const layout = templates[activeName] || [];
  const updateLayout = (updater) => setTemplates((current) => ({
    ...current,
    [activeName]: typeof updater === "function" ? updater(current[activeName] || []) : updater,
  }));

  const persist = async (nextTemplates, nextActive, nextDefault) => {
    const names = Object.keys(nextTemplates);
    const active = nextActive && nextTemplates[nextActive] ? nextActive : names[0] || "Default";
    const def = nextDefault && nextTemplates[nextDefault] ? nextDefault : active;
    const selectedLayout = nextTemplates[active] || [];
    const updated = await onUpdateStore({
      preferences: {
        ...prefs,
        ...form,
        receipt_templates: nextTemplates,
        receipt_active_template: active,
        receipt_default_template: def,
        receipt_layout: selectedLayout,
      },
    });
    if (updated) notify("Receipt saved");
    return updated;
  };

  const save = () => persist(templates, activeName, defaultName);

  const readLogo = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setForm({ ...form, receipt_logo: String(reader.result) });
    reader.readAsDataURL(file);
  };

  const moveLayout = (from, to) => {
    if (from === to || from == null || to == null) return;
    updateLayout((current) => {
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  const toggleLayout = (sectionId) => updateLayout((current) => current.map((section) => (section.id === sectionId ? { ...section, enabled: !section.enabled } : section)));

  const setSectionProp = (sectionId, prop, value) => updateLayout((current) => current.map((section) => (section.id === sectionId ? { ...section, [prop]: value } : section)));
  const setBlankSpan = (sectionId, span) => updateLayout((current) => current.map((section) => (section.id === sectionId ? { ...section, span, width: null, height: 16 } : section)));

  const removeSection = (sectionId) => updateLayout((current) => current.filter((section) => section.id !== sectionId));

  const addSection = (type) => {
    const def = RECEIPT_SECTIONS.find((item) => item.id === type);
    updateLayout((current) => [...current, normalizeLayoutSection({ id: type, type, enabled: true, align: def?.align, span: def?.span })]);
  };

  const addBlank = () => {
    const id = `blank_${Date.now()}`;
    updateLayout((current) => [...current, normalizeLayoutSection({ id, type: "blank", enabled: true, width: null, height: 16, span: "1", fontSize: BASE_FONT_SIZE })]);
  };

  const switchTemplate = (name) => {
    if (templates[name]) setActiveName(name);
  };

  const createTemplate = async () => {
    const name = newName.trim();
    if (!name || templates[name]) return;
    const next = { ...templates, [name]: [] };
    setTemplates(next);
    setActiveName(name);
    setNewName("");
    await persist(next, name, defaultName);
  };

  const deleteTemplate = async () => {
    const names = Object.keys(templates);
    if (names.length <= 1) return;
    const next = { ...templates };
    delete next[activeName];
    const nextNames = Object.keys(next);
    const nextActive = nextNames[0];
    const nextDefault = defaultName === activeName || !next[defaultName] ? nextActive : defaultName;
    setTemplates(next);
    setActiveName(nextActive);
    setDefaultName(nextDefault);
    await persist(next, nextActive, nextDefault);
  };

  const makeDefault = async () => {
    setDefaultName(activeName);
    await persist(templates, activeName, activeName);
  };

  const showNote = layout.find((section) => section.type === "note")?.enabled !== false;
  const setShowNote = (checked) => updateLayout((current) => current.map((section) => (section.type === "note" ? { ...section, enabled: checked } : section)));

  const priceToggles = [
    { key: "charge_tax", label: "Apply service tax", detail: "Charge tax on sales (based on the service tax rate)" },
    { key: "tax_inclusive", label: "Prices include tax", detail: "Tax is already inside the shelf price" },
  ];

  const availableSections = RECEIPT_SECTIONS.filter((def) => !layout.some((section) => section.type === def.id));

  return (
    <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5 sm:p-7">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-extrabold">Receipts</h3>
          <p className="mt-1 text-xs leading-5 text-[#92939d]">Build a layout block by block and watch the paper preview update as you go.</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f0efff] text-[#6957f5]"><Receipt size={17} /></div>
      </div>

      <div className="mt-6 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,400px)]">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[#e7e7ed] bg-[#fafafd]">
              {form.receipt_logo ? <img src={form.receipt_logo} alt="logo" className="h-full w-full object-contain p-1" /> : <Receipt size={20} className="text-[#a1a2ab]" />}
            </div>
            <label className="flex-1 text-xs font-semibold text-[#6957f5]">
              <input type="file" accept="image/*" className="hidden" onChange={readLogo} />
              <span className="cursor-pointer">Upload logo</span>
              {form.receipt_logo && <button type="button" onClick={() => setForm({ ...form, receipt_logo: "" })} className="ml-2 text-[#c2564b]">Remove</button>}
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Order prefix" value={form.receipt_prefix} onChange={(event) => setForm({ ...form, receipt_prefix: event.target.value })} />
            <Field label="Tax label" value={form.tax_label} onChange={(event) => setForm({ ...form, tax_label: event.target.value })} />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Paper size</span>
              <Dropdown value={form.receipt_size} onChange={(v) => setForm({ ...form, receipt_size: v })} options={[{ value: "thermal", label: "Thermal 80mm" }, { value: "a5", label: "A5 (148 × 210 mm)" }, { value: "a4", label: "A4 (210 × 297 mm)" }]} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Template</span>
              <Dropdown value={form.receipt_template} disabled={form.receipt_size === "thermal"} onChange={(v) => setForm({ ...form, receipt_template: v })} options={[{ value: "classic", label: "Classic" }, { value: "professional", label: "Professional" }]} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Language</span>
              <Dropdown value={form.receipt_language} onChange={(v) => setForm({ ...form, receipt_language: v })} options={Object.entries(RECEIPT_LANG).map(([key, label]) => ({ value: key, label }))} />
            </label>
          </div>

          <div className="rounded-xl border border-[#e9e9ef]">
            <button type="button" onClick={() => setLabelsOpen((value) => !value)} className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
              <span>
                <span className="block text-xs font-extrabold text-[#303139]">Custom labels</span>
                <span className="mt-0.5 block text-[10px] text-[#92939d]">Override the default text for each label. Leave blank to use default.</span>
              </span>
              {labelsOpen ? <ChevronDown size={15} className="shrink-0 text-[#92939d]" /> : <ChevronRight size={15} className="shrink-0 text-[#92939d]" />}
            </button>
            {labelsOpen && (
              <div className="grid gap-3 border-t border-[#f0f0f3] px-4 py-3 sm:grid-cols-2">
                {Object.entries(RECEIPT_TRANSLATIONS.en).map(([key, enDefault]) => {
                  const kmDefault = RECEIPT_TRANSLATIONS.km[key] || enDefault;
                  const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                  return (
                    <LabelInput
                      key={key}
                      label={label}
                      enDefault={enDefault}
                      kmDefault={kmDefault}
                      enVal={(form.receipt_labels.en && form.receipt_labels.en[key]) || ""}
                      kmVal={(form.receipt_labels.km && form.receipt_labels.km[key]) || ""}
                      onChange={(lang, val) => {
                        const labels = { en: Object.assign({}, form.receipt_labels.en), km: Object.assign({}, form.receipt_labels.km) };
                        if (lang === "en") labels.en[key] = val; else labels.km[key] = val;
                        setForm(Object.assign({}, form, { receipt_labels: labels }));
                      }}
                    />
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-1">
            {priceToggles.map((option) => (
              <label key={option.key} className="flex items-center gap-3 rounded-xl border border-[#e9e9ef] px-4 py-3">
                <input type="checkbox" checked={Boolean(form[option.key])} onChange={(event) => setForm({ ...form, [option.key]: event.target.checked })} className="h-4 w-4 accent-[#6957f5]" />
                <span className="text-xs font-semibold text-[#4f5059]">{option.label} <span className="block text-[10px] font-normal text-[#92939d]">{option.detail}</span></span>
              </label>
            ))}
          </div>

          <div className="rounded-xl border border-[#e9e9ef] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-extrabold text-[#303139]">Receipt layout</p>
              <div className="flex items-center gap-2">
                <Dropdown value={activeName} onChange={(v) => switchTemplate(v)} triggerClass="h-9 rounded-lg border border-[#dfdfe8] bg-white px-2.5 text-xs font-semibold text-[#292a31] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]" options={Object.keys(templates).map((name) => ({ value: name, label: name }))} />
                <button type="button" title={defaultName === activeName ? "This is the default template" : "Set as default template"} onClick={makeDefault} className={`flex h-9 items-center gap-1 rounded-lg border px-2.5 text-[11px] font-bold transition ${defaultName === activeName ? "border-[#c4f27c] bg-[#f6ffe8] text-[#4d7a1f]" : "border-[#dfdfe8] bg-white text-[#777883] hover:bg-[#f7f7fa]"}`}>
                  <Star size={13} className={defaultName === activeName ? "fill-[#67a53c]" : ""} /> {defaultName === activeName ? "Default" : "Set default"}
                </button>
                <button type="button" title="Delete template" onClick={deleteTemplate} disabled={Object.keys(templates).length <= 1} className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfdfe8] bg-white text-[#c2564b] transition hover:bg-[#fff0ee] disabled:opacity-40"><Trash2 size={14} /></button>
              </div>
            </div>
            <p className="mt-0.5 text-[10px] text-[#92939d]">Add blocks, then drag to reorder, set width, height, font size and text style per element.</p>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {availableSections.map((def) => (
                <button key={def.id} type="button" onClick={() => addSection(def.id)} className="flex items-center gap-1 rounded-lg border border-dashed border-[#c9c9d2] bg-white px-2 py-1.5 text-[10px] font-semibold text-[#5c5d66] transition hover:border-[#887bf3] hover:text-[#6957f5]">
                  <Plus size={11} /> {def.label}
                </button>
              ))}
              <button type="button" onClick={addBlank} className="flex items-center gap-1 rounded-lg border border-dashed border-[#c9c9d2] bg-white px-2 py-1.5 text-[10px] font-semibold text-[#5c5d66] transition hover:border-[#887bf3] hover:text-[#6957f5]">
                <Plus size={11} /> Blank space
              </button>
            </div>

            <div className="mt-3 flex gap-2">
              <input value={newName} onChange={(event) => setNewName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); createTemplate(); } }} placeholder="New template name" className="h-9 w-40 rounded-lg border border-[#dfdfe8] bg-white px-3 text-xs outline-none placeholder:text-[#aaabb4] focus:border-[#887bf3]" />
              <button type="button" title="Save as new template" onClick={createTemplate} disabled={!newName.trim() || Boolean(templates[newName.trim()])} className="flex h-9 items-center gap-1 rounded-lg bg-[#6957f5] px-3 text-[11px] font-bold text-white transition hover:bg-[#5a49e0] disabled:opacity-40"><Plus size={14} /> Save as new</button>
            </div>

            <div className="mt-3 rounded-xl border border-[#ececf1] bg-[#eef0f4] p-2">
              {layout.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-[#c9c9d2] bg-white/60 px-4 py-10 text-center">
                  <p className="text-[11px] font-bold text-[#5c5d66]">Your template is empty</p>
                  <p className="text-[10px] text-[#92939d]">Click a block above to add it. Receipts fall back to a standard layout until you save one.</p>
                </div>
              ) : (
                <div className="flex flex-wrap items-start gap-1.5">
                  {layout.map((section, index) => {
                    const def = RECEIPT_SECTIONS.find((item) => item.id === section.type);
                    const title = section.type === "blank" ? "Blank space" : def?.label || section.type;
                    return (
                      <div key={section.id} draggable onDragStart={() => setDragIndex(index)} onDragOver={(event) => event.preventDefault()} onDrop={() => moveLayout(dragIndex, index)} onDragEnd={() => setDragIndex(null)} style={section.type === "blank" ? { flexGrow: 0, flexShrink: 0, flexBasis: section.width ? `${Math.max(section.width, 96)}px` : spanWidth(section.span, "0.375rem"), minWidth: 0 } : { flexGrow: Math.min(3, Math.max(1, Number(section.span) || 3)), flexShrink: 0, flexBasis: spanWidth(section.span, "0.375rem"), minWidth: 0 }} className={`rounded-lg border px-2 py-1.5 transition ${dragIndex === index ? "border-[#887bf3] ring-2 ring-[#6957f5]/15" : section.enabled ? "border-[#e7e7ed] bg-white" : "border-dashed border-[#c9c9d2] bg-white/40"}`}>
                        <div className="flex items-center gap-1.5">
                          <GripVertical size={13} className="shrink-0 cursor-grab text-[#b3b4bf]" />
                          <span className={`min-w-0 flex-1 truncate text-[11px] font-semibold ${section.enabled ? "text-[#4f5059]" : "text-[#b3b4bf]"}`}>{title}</span>
                          <input type="checkbox" checked={section.enabled} onChange={() => toggleLayout(section.id)} className="h-3.5 w-3.5 shrink-0 accent-[#6957f5]" />
                          <button type="button" title="Remove" onClick={() => removeSection(section.id)} className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-[#b3b4bf] transition hover:text-[#c2564b]"><X size={12} /></button>
                        </div>
                        {section.enabled && (section.type === "blank" ? (
                          <div className="mt-1 flex flex-wrap items-center gap-1">
                            <Dropdown value={section.span} onChange={(v) => setBlankSpan(section.id, v)} triggerClass="h-6 rounded-md border border-[#e7e7ed] bg-white px-1 text-[9px] font-bold text-[#4f5059] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]" options={Object.entries(RECEIPT_SPAN).map(([value, label]) => ({ value, label }))} />
                            <div className="flex items-center gap-0.5 rounded-md border border-[#e7e7ed] bg-white px-1">
                              <span className="text-[9px] font-bold text-[#92939d]">W</span>
                              <input type="number" min="2" max="600" step="2" title="Blank width (px) — leave empty to follow the column span" placeholder="auto" value={section.width ?? ""} onChange={(event) => setSectionProp(section.id, "width", event.target.value === "" ? null : (Number(event.target.value) || null))} className="h-5 w-11 bg-transparent text-[9px] font-bold text-[#4f5059] outline-none placeholder:text-[#c0c0c8]" />
                              <span className="text-[9px] text-[#92939d]">px</span>
                            </div>
                            <div className="flex items-center gap-0.5 rounded-md border border-[#e7e7ed] bg-white px-1">
                              <span className="text-[9px] font-bold text-[#92939d]">H</span>
                              <input type="number" min="2" max="600" step="2" title="Blank height (px)" value={section.height || 16} onChange={(event) => setSectionProp(section.id, "height", Number(event.target.value) || 16)} className="h-5 w-11 bg-transparent text-[9px] font-bold text-[#4f5059] outline-none" />
                              <span className="text-[9px] text-[#92939d]">px</span>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-1 flex flex-wrap items-center gap-1">
                            <div className="flex items-center gap-0.5 rounded-md border border-[#e7e7ed] p-0.5">
                              <button type="button" title="Bold" onClick={() => setSectionProp(section.id, "bold", !section.bold)} className={`flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold transition ${section.bold ? "bg-[#f0efff] text-[#6957f5]" : "text-[#b3b4bf] hover:text-[#4f5059]"}`}>B</button>
                              <button type="button" title="Italic" onClick={() => setSectionProp(section.id, "italic", !section.italic)} className={`flex h-5 w-5 items-center justify-center rounded text-[10px] italic transition ${section.italic ? "bg-[#f0efff] text-[#6957f5]" : "text-[#b3b4bf] hover:text-[#4f5059]"}`}>I</button>
                              <button type="button" title="Underline" onClick={() => setSectionProp(section.id, "underline", !section.underline)} className={`flex h-5 w-5 items-center justify-center rounded text-[10px] underline transition ${section.underline ? "bg-[#f0efff] text-[#6957f5]" : "text-[#b3b4bf] hover:text-[#4f5059]"}`}>U</button>
                            </div>
                            <div className="flex items-center gap-0.5 rounded-md border border-[#e7e7ed] p-0.5">
                              {["left", "center", "right"].map((align) => {
                                const Icon = align === "left" ? AlignLeft : align === "center" ? AlignCenter : AlignRight;
                                return <button key={align} type="button" title={RECEIPT_ALIGN[align]} onClick={() => setSectionProp(section.id, "align", align)} className={`flex h-5 w-5 items-center justify-center rounded transition ${section.align === align ? "bg-[#f0efff] text-[#6957f5]" : "text-[#b3b4bf] hover:text-[#4f5059]"}`}><Icon size={12} /></button>;
                              })}
                            </div>
                            <Dropdown value={section.span} onChange={(v) => setSectionProp(section.id, "span", v)} triggerClass="h-6 rounded-md border border-[#e7e7ed] bg-white px-1 text-[9px] font-bold text-[#4f5059] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]" options={Object.entries(RECEIPT_SPAN).map(([value, label]) => ({ value, label }))} />
                            <input type="number" min="6" max="48" step="0.5" title="Font size (px)" value={section.fontSize} onChange={(event) => setSectionProp(section.id, "fontSize", Number(event.target.value) || BASE_FONT_SIZE)} className="h-6 w-12 rounded-md border border-[#e7e7ed] bg-white px-1 text-[9px] font-bold text-[#4f5059] outline-none focus:border-[#887bf3]" />
                            <Dropdown value={section.font} onChange={(v) => setSectionProp(section.id, "font", v)} triggerClass="h-6 rounded-md border border-[#e7e7ed] bg-white px-1 text-[9px] font-bold text-[#4f5059] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]" options={Object.entries(RECEIPT_FONTS).map(([value, label]) => ({ value, label }))} />
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-[#e9e9ef] p-4">
            <div className="flex items-center justify-between gap-3">
              <label className="flex items-center gap-2.5">
                <input type="checkbox" checked={showNote} onChange={(event) => setShowNote(event.target.checked)} className="h-4 w-4 accent-[#6957f5]" />
                <span className="text-xs font-extrabold text-[#303139]">Note</span>
              </label>
              <span className="text-[10px] text-[#92939d]">Shown at the bottom of the receipt</span>
            </div>
            <textarea value={form.receipt_note} disabled={!showNote} onChange={(event) => setForm({ ...form, receipt_note: event.target.value })} rows={3} placeholder="Thank you! See you again soon." className="mt-3 w-full resize-y rounded-xl border border-[#dfdfe8] bg-white px-3.5 py-2.5 text-sm text-[#22232a] outline-none placeholder:text-[#aaabb4] focus:border-[#887bf3] focus:ring-4 focus:ring-[#6957f5]/10 disabled:opacity-50" />
          </div>

          <div className="flex justify-end border-t border-[#eeeeF2] pt-5">
            <Button onClick={save} disabled={loading}>{loading ? "Saving..." : "Save receipt"} <Check size={14} /></Button>
          </div>
        </div>

        <div className="lg:sticky lg:top-5">
          <ReceiptLiveSheet
            workspace={workspace}
            draft={{
              ...form,
              receipt_templates: { [activeName]: layout },
              receipt_active_template: activeName,
              receipt_default_template: activeName,
              receipt_layout: layout,
            }}
          />
        </div>
      </div>
    </div>
  );
}

function ReceiptModal({ order, workspace, onClose, token, storeId, notify }) {
  const [emailing, setEmailing] = useState(false);
  if (!order) return null;
  const prefs = workspace?.store?.preferences || {};
  const receiptSize = prefs.receipt_size || "thermal";
  const receiptTemplate = prefs.receipt_size === "thermal" ? "classic" : prefs.receipt_template === "professional" ? "professional" : "classic";
  const canEmail = Boolean(order.customer?.email) && ["paid", "refunded"].includes(order.status);
  const emailReceipt = async () => {
    setEmailing(true);
    try {
      const result = await api.emailReceipt(token, storeId, order.id);
      notify(`Receipt emailed to ${result.email}`);
    } catch (requestError) {
      notify(requestError.message || "Could not email receipt");
    } finally {
      setEmailing(false);
    }
  };
  const actions = (
    <div className="receipt-screen-actions mt-4 space-y-2">
      {canEmail && <Button variant="soft" className="w-full" disabled={emailing} onClick={emailReceipt}>{emailing ? "Sending..." : "Email receipt to customer"} <Mail size={14} /></Button>}
      <div className="flex gap-2">
        <Button variant="outline" className="flex-1" onClick={onClose}>Close</Button>
        <Button className="flex-1" onClick={() => window.print()}><Download size={14} /> Print receipt</Button>
      </div>
    </div>
  );
  if (receiptTemplate === "professional") {
    return (
      <Modal open onClose={onClose} title="Receipt preview" description={`${order.order_number} · ${order.status.replaceAll("_", " ")} · Professional`} width="max-w-[520px]">
        <div className="receipt-print-area rounded-xl border border-[#e9e9ef] bg-white text-[#202128]" data-receipt-size={receiptSize} data-template="professional">
          <ReceiptProfessionalBody order={order} workspace={workspace} />
        </div>
        {actions}
      </Modal>
    );
  }
  return (
    <Modal open onClose={onClose} title="Receipt preview" description={`${order.order_number} · ${order.status.replaceAll("_", " ")}`} width="max-w-[420px]">
      <div className="receipt-print-area rounded-xl border border-[#e9e9ef] bg-white p-4 text-[#202128]" data-receipt-size={receiptSize} data-template={receiptTemplate}>
        <ReceiptClassicBody order={order} workspace={workspace} />
      </div>
      {actions}
    </Modal>
  );
}

export {
  buildReceiptDemo,
  RECEIPT_SECTIONS,
  RECEIPT_LANG,
  RECEIPT_TRANSLATIONS,
  tLabel,
  RECEIPT_ALIGN,
  RECEIPT_SIZE,
  RECEIPT_SPAN,
  RECEIPT_FONTS,
  RECEIPT_FONT_STACKS,
  RECEIPT_ZOOM,
  normalizeLayoutSection,
  getReceiptLayout,
  ReceiptSheetBody,
  ReceiptLiveSheet,
  LabelInput,
  ReceiptsPane,
  ProfessionalSection,
  ReceiptProfessionalBody,
  ClassicSection,
  ReceiptClassicBody,
  ReceiptModal,
};
