import { useState, useEffect, useContext, useMemo, useCallback, createContext } from "react";
import { Check, ChevronDown, SunMedium, Moon, X } from "lucide-react";
import { Listbox, Transition } from "@headlessui/react";
import { api } from "../api";

const STORAGE_KEY = "chmaba-theme";

const SELECT_TRIGGER = "h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm text-[#292a31] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]";

function Dropdown({ value, onChange, options = [], placeholder = "Select", disabled = false, triggerClass = SELECT_TRIGGER, chevron = true, panel = "" }) {
  const current = options.find((option) => String(option.value) === String(value));
  return (
    <div className="relative">
      <Listbox value={value} onChange={onChange} disabled={disabled}>
        {({ open }) => (
          <>
            <Listbox.Button className={`flex min-w-0 items-center justify-between gap-2 outline-none transition ${disabled ? "cursor-not-allowed opacity-50" : ""} ${triggerClass}`}>
              <span className={`${current ? "" : "opacity-60"} truncate`}>{current ? current.label : placeholder}</span>
              {chevron && <ChevronDown size={13} className={`shrink-0 text-[#92939d] transition-transform duration-150 ${open ? "rotate-180" : ""}`} />}
            </Listbox.Button>
            <Transition leave="transition ease-in duration-75" leaveFrom="opacity-100" leaveTo="opacity-0">
              <Listbox.Options className={`absolute left-0 top-full z-40 mt-1.5 max-h-64 w-max min-w-[180px] max-w-[min(92vw,340px)] overflow-auto rounded-xl border border-[#e6e6ed] bg-white p-1 shadow-[0_18px_44px_rgba(20,21,28,.16)] dark:border-[#363740] dark:bg-[#232429] ${panel}`}>
                {options.map((option) => (
                  <Listbox.Option key={String(option.value)} value={option.value} disabled={option.disabled} className={({ active }) => `flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-xs font-semibold ${active ? "bg-[#f3f1ff] text-[#4a3bd8] dark:bg-[#2c2b36] dark:text-[#b9afff]" : "text-[#4f5059] dark:text-[#c8c9d0]"} ${option.disabled ? "cursor-not-allowed opacity-40" : ""}`}>
                    {({ selected }) => (
                      <>
                        <span className="min-w-0">{option.label}</span>
                        {selected && <Check size={13} className="shrink-0 text-[#6957f5]" />}
                      </>
                    )}
                  </Listbox.Option>
                ))}
              </Listbox.Options>
            </Transition>
          </>
        )}
      </Listbox>
    </div>
  );
}

const ThemeContext = createContext({ theme: "light", toggleTheme: () => {}, applyUserTheme: () => {} });

const useTheme = () => useContext(ThemeContext);

function ThemeProvider({ children }) {  const [theme, setTheme] = useState(() => {    try {      const stored = localStorage.getItem(STORAGE_KEY);      if (stored === "dark" || stored === "light") return stored;    } catch { /* ignore */ }    return "light";  });  const applyUserTheme = useCallback((value) => {    if (value !== "dark" && value !== "light") return;    setTheme(value);    try { localStorage.setItem(STORAGE_KEY, value); } catch { /* ignore */ }  }, []);  const persistUserTheme = useCallback((next) => {    try {      const storedToken = window.localStorage.getItem("chmaba.access_token");      if (storedToken) api.updatePreferences(storedToken, { theme: next }).catch(() => { /* ignore */ });    } catch { /* ignore */ }  }, []);  const toggleTheme = useCallback(() => {    const next = theme === "dark" ? "light" : "dark";    setTheme(next);    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }    persistUserTheme(next);  }, [theme, persistUserTheme]);  useEffect(() => {    const root = document.documentElement;    if (theme === "dark") {      root.classList.add("dark");    } else {      root.classList.remove("dark");    }  }, [theme]);  const value = useMemo(() => ({ theme, toggleTheme, applyUserTheme }), [theme, toggleTheme, applyUserTheme]);  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;}

function ThemeToggle() {  const { theme, toggleTheme } = useTheme();  return <button type="button" aria-label="Toggle dark mode" title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleTheme} className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0f0f5] hover:text-[#272831] dark:text-[#9a9aa4] dark:hover:bg-[#2a2b32] dark:hover:text-[#e4e4e8]">{theme === "dark" ? <SunMedium size={17} /> : <Moon size={17} />}</button>;}

const money = (value, currency = "USD") => {  if (currency === "KHR") return `${Math.round(value * 4000).toLocaleString()}áŸ›`;  return `$${value.toFixed(2)}`;};

function formatCurrencyAmount(value, code = "USD") {  const amount = Number(value) || 0;  if (code === "KHR") return `${Math.round(amount).toLocaleString()}áŸ›`;  if (code === "THB") return `à¸¿${amount.toFixed(2)}`;  return `$${amount.toFixed(2)}`;}

function amountForCurrency(value, currencyCode, rates, baseCurrency = "USD") {  if (currencyCode === baseCurrency) return Number(value) || 0;  const direct = rates.find((item) => item.base_currency_code === baseCurrency && item.quote_currency_code === currencyCode && item.is_active);  if (direct) return (Number(value) || 0) * Number(direct.rate);  const inverse = rates.find((item) => item.base_currency_code === currencyCode && item.quote_currency_code === baseCurrency && item.is_active);  if (inverse) return (Number(value) || 0) / Number(inverse.rate);  return null;}

function amountToBaseCurrency(value, currencyCode, rates, baseCurrency = "USD") {  if (currencyCode === baseCurrency) return Number(value) || 0;  const direct = rates.find((item) => item.base_currency_code === baseCurrency && item.quote_currency_code === currencyCode && item.is_active);  if (direct) return (Number(value) || 0) / Number(direct.rate);  const inverse = rates.find((item) => item.base_currency_code === currencyCode && item.quote_currency_code === baseCurrency && item.is_active);  if (inverse) return (Number(value) || 0) * Number(inverse.rate);  return null;}

function adminStatusTone(active) {  return active ? "green" : "red";}

function Button({ children, variant = "primary", size = "md", className = "", ...props }) {  const variants = {    primary: "bg-[#6957f5] text-white shadow-[0_7px_16px_rgba(105,87,245,.2)] hover:bg-[#5845e7]",    dark: "bg-[#17181c] text-white hover:bg-[#2d2e34]",    soft: "bg-[#f0efff] text-[#5b4be3] hover:bg-[#e7e4ff]",    outline: "border border-[#dedee7] bg-white text-[#282930] hover:border-[#bdbbc9] hover:bg-[#fafafd]",    "outline-dark": "border border-[#4a4b51] bg-transparent text-white hover:border-[#5c5d66] hover:bg-[#303137]",    ghost: "text-[#696a74] hover:bg-[#f2f2f6] hover:text-[#24252b]",    danger: "bg-[#fff0ee] text-[#d0574b] hover:bg-[#ffe5e2]",    lime: "bg-[#c4f27c] text-[#1b2715] hover:bg-[#b8ea6d]",  };const sizes = {    xs: "h-8 rounded-lg px-2.5 text-xs",    sm: "h-9 rounded-lg px-3 text-xs",    md: "h-10 rounded-xl px-4 text-sm",    lg: "h-12 rounded-xl px-5 text-sm",  };  return (    <button className={`inline-flex items-center justify-center gap-2 font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`} {...props}>      {children}    </button>  );}

function IconButton({ label, children, className = "", ...props }) {  return (    <button aria-label={label} title={label} className={`inline-flex h-9 w-9 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0eff5] hover:text-[#272831] ${className}`} {...props}>      {children}    </button>  );}

function Badge({ children, tone = "neutral", dot = false }) {  const tones = {    neutral: "bg-[#f1f1f5] text-[#686974]",    green: "bg-[#edf9e4] text-[#4f8b32]",    yellow: "bg-[#fff6df] text-[#ad7d1c]",    red: "bg-[#fff0ee] text-[#c2564b]",    violet: "bg-[#f0efff] text-[#6555df]",    blue: "bg-[#eaf4ff] text-[#3579b8]",  };const dots = { green: "bg-[#77bb4b]", yellow: "bg-[#dca93c]", red: "bg-[#dc6b60]", violet: "bg-[#7969ec]", blue: "bg-[#63a2d8]", neutral: "bg-[#9899a4]" };  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-semibold ${tones[tone]}`}>{dot && <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} />}{children}</span>;}

function Field({ label, hint, ...props }) {  return (    <label className="block">      <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">{label}</span>      <input className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm text-[#22232a] outline-none transition placeholder:text-[#aaabb4] focus:border-[#887bf3] focus:ring-4 focus:ring-[#6957f5]/10" {...props} />      {hint && <span className="mt-1.5 block text-[11px] text-[#92939d]">{hint}</span>}    </label>  );}

function Modal({ open, title, description, onClose, children, width = "max-w-lg" }) {  if (!open) return null;  return (    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/45 p-4 backdrop-blur-[3px]" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>      <div className={`max-h-[92vh] w-full overflow-y-auto rounded-2xl bg-white shadow-[0_24px_80px_rgba(20,21,28,.22)] ${width}`}>        <div className="flex items-start justify-between border-b border-[#eeeeF2] px-5 py-4">          <div>            <h2 className="text-base font-bold text-[#202128]">{title}</h2>            {description && <p className="mt-1 text-xs text-[#898a95]">{description}</p>}          </div>          <IconButton label="Close" onClick={onClose}><X size={17} /></IconButton>        </div>        <div className="p-5">{children}</div>      </div>    </div>  );}

function Logo({ light = false, adaptive = false }) {  const chip = light ? "bg-[#c4f27c]" : adaptive ? "bg-[#17181c] dark:bg-[#c4f27c]" : "bg-[#17181c]";  const ring = light ? "border-[#17181c]" : adaptive ? "border-white dark:border-[#17181c]" : "border-white";  const word = light ? "text-white" : adaptive ? "text-[#17181c] dark:text-white" : "text-[#17181c]";  return (    <div className="flex items-center gap-2.5">      <div className={`relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-[10px] ${chip}`}>        <span className={`absolute h-3 w-3 rounded-full border-[2.5px] ${ring}`} />        <span className={`absolute -right-0.5 top-1.5 h-3 w-3 rounded-full border-[2.5px] ${ring}`} />      </div>      <span className={`text-[19px] font-extrabold tracking-[-.04em] ${word}`}>chmaba</span>    </div>  );}

function ProductMark({ product, size = "md" }) {  const sizes = { sm: "h-8 w-8 rounded-lg text-[9px]", md: "h-10 w-10 rounded-xl text-[10px]", lg: "h-14 w-14 rounded-2xl text-xs" };  if (product.image) return <img src={product.image} alt={product.name} className={`shrink-0 object-cover ${sizes[size]} overflow-hidden`} />;  return <div className={`flex shrink-0 items-center justify-center font-extrabold tracking-[-.04em] text-[#343039] ${sizes[size]}`} style={{ backgroundColor: product.color }}>{product.letter}</div>;}

export {
  STORAGE_KEY,
  SELECT_TRIGGER,
  Dropdown,
  ThemeContext,
  useTheme,
  ThemeProvider,
  ThemeToggle,
  money,
  formatCurrencyAmount,
  amountForCurrency,
  amountToBaseCurrency,
  adminStatusTone,
  Button,
  IconButton,
  Badge,
  Field,
  Modal,
  Logo,
  ProductMark,
};
