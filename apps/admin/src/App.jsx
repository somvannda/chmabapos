import { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback } from "react";
import {  AlignCenter,  AlignLeft,  AlignRight,  AlertTriangle,  ArrowDownRight,  ArrowLeft,  ArrowRight,  ArrowRightLeft,  ArrowUpRight,  Archive,  Banknote,  BarChart3,  Bell,  Boxes,  Building2,  CalendarDays,  Check,  CheckCircle2,  ChevronDown,  ChevronLeft,  ChevronRight,  CircleHelp,  CircleDollarSign,  Clock3,  Copy,  Download,  Edit3,  ExternalLink,  Eye,  EyeOff,  Filter,  Grid2X2,  GripVertical,  Landmark,  LayoutDashboard,  List,  LockKeyhole,  LogOut,  Mail,  MapPin,  Menu,  Minus,  MoreHorizontal,  Package,  Percent,  Plus,  QrCode,  Receipt,  RefreshCw,  RotateCcw,  Search,  ScanLine,  Settings2,  ShieldCheck,  ShoppingCart,  Smartphone,  SunMedium,  Moon,  Sparkles,  Store,  Tag,  ToggleLeft,  ToggleRight,  Trash2,  TrendingUp,  Truck,  UserPlus,  UserRound,  Users,  WalletCards,  X,} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { api, APIError } from "./api";
import { adminPath, parseRoute, userPath, usernameFor, viewFromPath } from "./routing";
import { Listbox, Transition } from "@headlessui/react";
const STORAGE_KEY = "chmaba-theme";
const SELECT_TRIGGER = "h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm text-[#292a31] dark:border-[#363740] dark:bg-[#1f2025] dark:text-[#e4e4e8]";
function Dropdown({ value, onChange, options = [], placeholder = "Select", disabled = false, triggerClass = SELECT_TRIGGER, chevron = true, panel = "", align = "left" }) {
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
              <Listbox.Options className={`absolute ${align === "right" ? "right-0" : "left-0"} top-full z-40 mt-1.5 max-h-64 w-max min-w-[180px] max-w-[min(92vw,340px)] overflow-auto rounded-xl border border-[#e6e6ed] bg-white p-1 shadow-[0_18px_44px_rgba(20,21,28,.16)] dark:border-[#363740] dark:bg-[#232429] ${panel}`}>
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
const ThemeContext = createContext({ theme: "light", toggleTheme: () => {}, applyUserTheme: () => {} });const useTheme = () => useContext(ThemeContext);

function ThemeProvider({ children }) {  const [theme, setTheme] = useState(() => {    try {      const stored = localStorage.getItem(STORAGE_KEY);      if (stored === "dark" || stored === "light") return stored;    } catch { /* ignore */ }    return "light";  });  const applyUserTheme = useCallback((value) => {    if (value !== "dark" && value !== "light") return;    setTheme(value);    try { localStorage.setItem(STORAGE_KEY, value); } catch { /* ignore */ }  }, []);  const persistUserTheme = useCallback((next) => {    try {      const storedToken = window.localStorage.getItem("chmaba.access_token");      if (storedToken) api.updatePreferences(storedToken, { theme: next }).catch(() => { /* ignore */ });    } catch { /* ignore */ }  }, []);  const toggleTheme = useCallback(() => {    const next = theme === "dark" ? "light" : "dark";    setTheme(next);    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }    persistUserTheme(next);  }, [theme, persistUserTheme]);  useEffect(() => {    const root = document.documentElement;    if (theme === "dark") {      root.classList.add("dark");    } else {      root.classList.remove("dark");    }  }, [theme]);  const value = useMemo(() => ({ theme, toggleTheme, applyUserTheme }), [theme, toggleTheme, applyUserTheme]);  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;}function ThemeToggle() {  const { theme, toggleTheme } = useTheme();  return <button type="button" aria-label="Toggle dark mode" title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleTheme} className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0f0f5] hover:text-[#272831] dark:text-[#9a9aa4] dark:hover:bg-[#2a2b32] dark:hover:text-[#e4e4e8]">{theme === "dark" ? <SunMedium size={17} /> : <Moon size={17} />}</button>;}



const ADMIN_NAV_ITEMS = [  { id: "overview", label: "Overview", icon: LayoutDashboard },  { id: "funnel", label: "Funnel", icon: TrendingUp },  { id: "analytics", label: "Sales analytics", icon: BarChart3 },  { id: "retention", label: "Retention", icon: Clock3 },  { id: "attention", label: "Needs attention", icon: AlertTriangle },  { id: "search", label: "Search", icon: Search },  { id: "users", label: "Users", icon: Users },  { id: "companies", label: "Companies", icon: Building2 },  { id: "stores", label: "Stores", icon: Store },  { id: "subscriptions", label: "Subscriptions", icon: WalletCards },  { id: "billing-payments", label: "Billing payments", icon: Receipt },    { id: "plans", label: "Plans", icon: Package }, { id: "payments", label: "Payment links", icon: QrCode }, { id: "mailing", label: "Mailing", icon: Mail }, { id: "settings", label: "Settings", icon: Settings2 }, { id: "audit", label: "Activity", icon: ShieldCheck }, { id: "support", label: "Support", icon: CircleHelp }, { id: "help", label: "Help content", icon: CircleHelp },];const money = (value, currency = "USD") => {  if (currency === "KHR") return `${Math.round(value * 4000).toLocaleString()}áŸ›`;  return `$${value.toFixed(2)}`;};

function Button({ children, variant = "primary", size = "md", className = "", ...props }) {  const variants = {    primary: "bg-[#6957f5] text-white shadow-[0_7px_16px_rgba(105,87,245,.2)] hover:bg-[#5845e7]",    dark: "bg-[#17181c] text-white hover:bg-[#2d2e34]",    soft: "bg-[#f0efff] text-[#5b4be3] hover:bg-[#e7e4ff]",    outline: "border border-[#dedee7] bg-white text-[#282930] hover:border-[#bdbbc9] hover:bg-[#fafafd]",    "outline-dark": "border border-[#4a4b51] bg-transparent text-white hover:border-[#5c5d66] hover:bg-[#303137]",    ghost: "text-[#696a74] hover:bg-[#f2f2f6] hover:text-[#24252b]",    danger: "bg-[#fff0ee] text-[#d0574b] hover:bg-[#ffe5e2]",    lime: "bg-[#c4f27c] text-[#1b2715] hover:bg-[#b8ea6d]",  };const sizes = {    xs: "h-8 rounded-lg px-2.5 text-xs",    sm: "h-9 rounded-lg px-3 text-xs",    md: "h-10 rounded-xl px-4 text-sm",    lg: "h-12 rounded-xl px-5 text-sm",  };  return (    <button className={`inline-flex items-center justify-center gap-2 font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`} {...props}>      {children}    </button>  );}function IconButton({ label, children, className = "", ...props }) {  return (    <button aria-label={label} title={label} className={`inline-flex h-9 w-9 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0eff5] hover:text-[#272831] ${className}`} {...props}>      {children}    </button>  );}function Badge({ children, tone = "neutral", dot = false }) {  const tones = {    neutral: "bg-[#f1f1f5] text-[#686974]",    green: "bg-[#edf9e4] text-[#4f8b32]",    yellow: "bg-[#fff6df] text-[#ad7d1c]",    red: "bg-[#fff0ee] text-[#c2564b]",    violet: "bg-[#f0efff] text-[#6555df]",    blue: "bg-[#eaf4ff] text-[#3579b8]",  };const dots = { green: "bg-[#77bb4b]", yellow: "bg-[#dca93c]", red: "bg-[#dc6b60]", violet: "bg-[#7969ec]", blue: "bg-[#63a2d8]", neutral: "bg-[#9899a4]" };  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-semibold ${tones[tone]}`}>{dot && <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} />}{children}</span>;}function Field({ label, hint, ...props }) {  return (    <label className="block">      <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">{label}</span>      <input className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm text-[#22232a] outline-none transition placeholder:text-[#aaabb4] focus:border-[#887bf3] focus:ring-4 focus:ring-[#6957f5]/10" {...props} />      {hint && <span className="mt-1.5 block text-[11px] text-[#92939d]">{hint}</span>}    </label>  );}function Modal({ open, title, description, onClose, children, width = "max-w-lg" }) {  if (!open) return null;  return (    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#17181c]/45 p-4 backdrop-blur-[3px]" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>      <div className={`max-h-[92vh] w-full overflow-y-auto rounded-2xl bg-white shadow-[0_24px_80px_rgba(20,21,28,.22)] ${width}`}>        <div className="flex items-start justify-between border-b border-[#eeeeF2] px-5 py-4">          <div>            <h2 className="text-base font-bold text-[#202128]">{title}</h2>            {description && <p className="mt-1 text-xs text-[#898a95]">{description}</p>}          </div>          <IconButton label="Close" onClick={onClose}><X size={17} /></IconButton>        </div>        <div className="p-5">{children}</div>      </div>    </div>  );}function Logo({ light = false }) {  return (    <div className="flex items-center gap-2.5">      <div className={`relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-[10px] ${light ? "bg-[#c4f27c]" : "bg-[#17181c]"}`}>        <span className={`absolute h-3 w-3 rounded-full border-[2.5px] ${light ? "border-[#17181c]" : "border-white"}`} />        <span className={`absolute -right-0.5 top-1.5 h-3 w-3 rounded-full border-[2.5px] ${light ? "border-[#17181c]" : "border-white"}`} />      </div>      <span className={`text-[19px] font-extrabold tracking-[-.04em] ${light ? "text-white" : "text-[#17181c]"}`}>chmaba</span>    </div>  );}







function AdminSidebar({ active, onNavigate, onSignOut, user }) {  return <aside className="fixed inset-y-0 left-0 z-20 hidden w-[252px] flex-col bg-[#17181c] px-3.5 py-5 text-white lg:flex"><div className="px-3"><Logo light /></div><div className="mt-9 px-2"><p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[.15em] text-[#686970]">Platform</p><nav className="space-y-1">{ADMIN_NAV_ITEMS.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => onNavigate(id)} className={`flex h-10 w-full items-center gap-3 rounded-xl px-3 text-left text-[12px] font-semibold transition ${active === id ? "bg-[#6957f5] text-white shadow-[0_7px_18px_rgba(105,87,245,.25)]" : "text-[#8b8c95] hover:bg-[#292a30] hover:text-white"}`}><Icon size={16} /><span>{label}</span>{active === id && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#c4f27c]" />}</button>)}</nav></div><div className="mt-auto"><div className="mb-3 rounded-xl border border-[#33343a] bg-[#202126] p-3"><div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#c4f27c] text-[10px] font-extrabold text-[#1d2817]">PA</div><div><p className="text-[11px] font-bold">Platform admin</p><p className="mt-0.5 text-[9px] text-[#85868e]">{user?.email}</p></div></div></div><button onClick={onSignOut} className="flex w-full items-center gap-2 px-2 text-[11px] font-semibold text-[#777880] hover:text-white"><LogOut size={15} /> Sign out</button><p className="mt-3 px-2 text-[9px] leading-4 text-[#55565e]">build {__APP_VERSION__} · {new Date(__BUILD_TIME__).toLocaleString()}</p></div></aside>;}function AdminHeader({ active, onMenu, onSignOut, user }) {  const current = ADMIN_NAV_ITEMS.find((item) => item.id === active);  return <header className="flex min-h-[74px] items-center justify-between border-b border-[#e9e9ef] bg-[#fafafd]/90 px-5 backdrop-blur dark:border-[#2a2b30] dark:bg-[#1a1b1f]/90 lg:px-8"><div className="flex items-center gap-3"><IconButton label="Open admin menu" onClick={onMenu} className="lg:hidden"><Menu size={19} /></IconButton><div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#6957f5]">Chmaba control room</p><h1 className="mt-1 text-[18px] font-extrabold tracking-[-.04em]">{current?.label || "Overview"}</h1></div></div><div className="flex items-center gap-2"><ThemeToggle /><Badge tone="violet">SUPER ADMIN</Badge><div className="hidden h-8 w-8 items-center justify-center rounded-full bg-[#ded9fb] text-[10px] font-bold text-[#5144c7] sm:flex">{user?.full_name?.slice(0, 2).toUpperCase() || "PA"}</div><IconButton label="Sign out" onClick={onSignOut} className="lg:hidden"><LogOut size={16} /></IconButton></div></header>;}function AdminMobileMenu({ active, open, onClose, onNavigate }) {  return <><div className={`fixed inset-0 z-30 bg-[#17181c]/35 transition lg:hidden ${open ? "visible opacity-100" : "invisible opacity-0"}`} onClick={onClose} /><aside className={`fixed inset-y-0 left-0 z-40 flex w-[252px] flex-col bg-[#17181c] px-3.5 py-5 text-white transition-transform duration-300 lg:hidden ${open ? "translate-x-0" : "-translate-x-full"}`}><div className="flex items-center justify-between px-3"><Logo light /><IconButton label="Close admin menu" onClick={onClose} className="text-[#898a94] hover:bg-[#292a30] hover:text-white"><X size={17} /></IconButton></div><div className="mt-9 px-2 space-y-1">{ADMIN_NAV_ITEMS.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { onNavigate(id); onClose(); }} className={`flex h-10 w-full items-center gap-3 rounded-xl px-3 text-left text-[12px] font-semibold ${active === id ? "bg-[#6957f5] text-white" : "text-[#8b8c95]"}`}><Icon size={16} />{label}</button>)}</div></aside></>;}function AdminMetric({ label, value, detail, icon: Icon, tone = "violet" }) {  const tones = { violet: "bg-[#f0efff] text-[#6957f5]", green: "bg-[#eff9e5] text-[#67a53c]", peach: "bg-[#fff1e9] text-[#cb784d]", yellow: "bg-[#fff5dc] text-[#b18020]" };  return <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5 shadow-[0_8px_24px_rgba(28,31,42,.04)]"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold text-[#858690]">{label}</p><p className="mt-2 text-[25px] font-extrabold tracking-[-.055em]">{value}</p></div><div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div></div><p className="mt-3 text-[10px] text-[#a4a5ad]">{detail}</p></div>;}function AdminOverview({ overview, companies, activities, attention, onNavigate, loading }) {  const latest = (activities || []).slice(0, 8);  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="flex items-center gap-2 text-xs text-[#92939d]"><span className="h-2 w-2 rounded-full bg-[#6957f5]" /> Platform-wide visibility</div><h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em]">Good morning, platform team</h2><p className="mt-1 text-sm text-[#898a95]">Keep Chmaba healthy across every tenant and store.</p></div><Badge tone="green" dot>All systems operational</Badge></div>{attention && attention.items.some((item) => item.count > 0) && <div className="mt-5 rounded-2xl border border-[#f3c9c3] bg-[#fff8f7] p-4"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2 text-xs font-bold text-[#c2564b]"><AlertTriangle size={14} /> Needs attention</div><button onClick={() => onNavigate("attention")} className="text-[11px] font-bold text-[#6957f5]">Open</button></div><div className="mt-3 flex flex-wrap gap-2">{attention.items.filter((item) => item.count > 0).map((item) => <span key={item.kind} className="inline-flex items-center gap-2 rounded-xl border border-[#f3d3cf] bg-white px-3 py-1.5 text-[11px]"><span className="text-[#5b5c66]">{item.label}</span><span className="font-bold text-[#c2564b]">{item.count}</span></span>)}</div></div>}<div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><AdminMetric label="Total users" value={overview?.users ?? "-"} detail={`${overview?.active_users ?? 0} active users`} icon={Users} /><AdminMetric label="Companies" value={overview?.companies ?? "-"} detail={`${overview?.active_companies ?? 0} active tenants`} icon={Building2} tone="green" /><AdminMetric label="Stores" value={overview?.stores ?? "-"} detail={`${overview?.active_stores ?? 0} active locations`} icon={Store} tone="peach" /><AdminMetric label="Paid subscriptions" value={overview?.paid_subscriptions ?? "-"} detail={`${overview?.pending_subscriptions ?? 0} pending payment`} icon={WalletCards} tone="yellow" /></div><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><AdminMetric label="Sales (30d)" value={overview ? money(Number(overview.gmv_30d || 0), overview.gmv_currency) : "-"} detail={`${overview?.orders_30d ?? 0} orders · ${overview?.orders_total ?? 0} all time`} icon={TrendingUp} tone="green" /><AdminMetric label="Plan revenue (30d)" value={overview ? money(Number(overview.platform_revenue_30d || 0), "USD") : "-"} detail={`${overview ? money(Number(overview.platform_revenue_total || 0), "USD") : "-"} all time`} icon={CircleDollarSign} tone="violet" /><AdminMetric label="Recurring (MRR)" value={overview ? money(Number(overview.mrr || 0), "USD") : "-"} detail="Active paid plans, list price" icon={BarChart3} tone="peach" /><AdminMetric label="Active users (30d)" value={overview?.active_users_30d ?? "-"} detail={`${overview?.new_users_30d ?? 0} new signups this month`} icon={Users} tone="yellow" /></div><div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_.9fr]"><section className="rounded-2xl border border-[#e9e9ef] bg-white p-5 sm:p-6"><div className="flex items-center justify-between"><div><h3 className="text-sm font-extrabold">Latest companies</h3><p className="mt-1 text-[11px] text-[#999aa4]">Newest tenant workspaces</p></div><button onClick={() => onNavigate("companies")} className="text-[11px] font-bold text-[#6957f5]">View all</button></div><div className="mt-5 space-y-2">{companies.slice(0, 5).map((company) => <div key={company.id} className="flex items-center gap-3 rounded-xl bg-[#fafafd] px-3 py-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#ded9fb] text-[10px] font-extrabold text-[#5144c7]">{company.name.slice(0, 2).toUpperCase()}</div><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold">{company.name}</p><p className="mt-1 text-[10px] text-[#999aa4]">{company.store_count} store(s) · {company.member_count} member(s)</p></div><Badge tone={company.is_active ? "green" : "red"} dot>{company.is_active ? "Active" : "Suspended"}</Badge></div>)}{companies.length === 0 && <p className="py-10 text-center text-xs text-[#999aa4]">No companies yet.</p>}</div></section><section className="rounded-2xl border border-[#e9e9ef] bg-white p-5 sm:p-6"><div className="flex items-center justify-between"><div><h3 className="text-sm font-extrabold">Recent activity</h3><p className="mt-1 text-[11px] text-[#999aa4]">Platform events and admin actions</p></div><button onClick={() => onNavigate("audit")} className="text-[11px] font-bold text-[#6957f5]">View all</button></div><div className="mt-5 space-y-4">{latest.map((item) => <div key={`${item.source}-${item.id}`} className="flex gap-3"><div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.source === "admin" ? "bg-[#dc6b60]" : "bg-[#6957f5]"}`} /><div className="min-w-0"><p className="truncate text-xs font-bold">{item.title}</p><p className="mt-1 text-[10px] text-[#999aa4]">{item.actor_email || "system"} · {new Date(item.created_at).toLocaleString()}</p></div></div>)}{latest.length === 0 && <p className="py-10 text-center text-xs text-[#999aa4]">No activity yet.</p>}</div></section></div>{loading && <p className="mt-5 text-xs text-[#999aa4]">Refreshing platform data...</p>}</div>;}function AdminUsers({ users, onUpdate, loading, token }) {  const [search, setSearch] = useState("");  const [selected, setSelected] = useState(null);  const [detail, setDetail] = useState(null);  const [detailLoading, setDetailLoading] = useState(false);  const [detailError, setDetailError] = useState("");  const filtered = users.filter((user) => `${user.full_name} ${user.email}`.toLowerCase().includes(search.toLowerCase()));  const openDetail = async (user) => { setSelected(user); setDetail(null); setDetailError(""); setDetailLoading(true); try { setDetail(await api.adminUserDetail(token, user.id)); } catch (requestError) { setDetailError(requestError.message || "Could not load user"); } finally { setDetailLoading(false); } };  const exportCsv = async () => { try { downloadCsv("users.csv", await api.adminExportUsersCsv(token)); } catch (requestError) { setDetailError(requestError.message || "Could not export users"); } };  return <><AdminTablePage title="Users" description="All accounts across Chmaba." extra={<Button variant="outline" size="sm" onClick={exportCsv}>Export CSV</Button>} search={search} setSearch={setSearch} loading={loading} gridTemplate="1.6fr .5fr .8fr .7fr .8fr .7fr" minWidth={860} columns={<> <span>User</span><span>Companies</span><span>Role</span><span>Last login</span><span>Status</span><span>Action</span></>} rows={filtered.map((user) => <div key={user.id} className="grid min-w-[860px] grid-cols-[1.6fr_.5fr_.8fr_.7fr_.8fr_.7fr] items-center gap-3 border-t border-[#f0f0f3] px-4 py-4 text-xs"><button type="button" onClick={() => openDetail(user)} className="flex items-center gap-3 text-left"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#ded9fb] text-[10px] font-bold text-[#5144c7]">{user.full_name.slice(0, 2).toUpperCase()}</div><div><p className="font-bold hover:text-[#6957f5]">{user.full_name}</p><p className="mt-1 text-[10px] text-[#999aa4]">{user.email}</p></div></button><span className="text-[#777883]">{user.company_count}</span><span>{user.platform_role ? <Badge tone="violet">{user.platform_role}</Badge> : <span className="text-[#999aa4]">Tenant user</span>}</span><span className="text-[#777883]">{user.last_login ? new Date(user.last_login).toLocaleString() : <span className="text-[#c0c1c9]">never</span>}</span><Badge tone={user.is_active ? "green" : "red"} dot>{user.is_active ? "Active" : "Suspended"}</Badge><div className="flex gap-2"><Button variant="outline" size="xs" onClick={() => openDetail(user)}>View</Button><Button variant={user.is_active ? "danger" : "soft"} size="xs" disabled={user.platform_role === "super_admin"} onClick={() => onUpdate(user.id, { is_active: !user.is_active })}>{user.is_active ? "Suspend" : "Restore"}</Button></div></div>)} />{selected && <Modal open title={selected.full_name || "User"} description={selected.email} onClose={() => setSelected(null)} width="max-w-[760px]"><div className="space-y-5 p-5">{detailError && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{detailError}</p>}{detailLoading ? <p className="py-8 text-center text-xs text-[#999aa4]">Loading profile...</p> : detail && <><div className="grid gap-3 sm:grid-cols-4"><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Companies</p><p className="mt-1 text-lg font-extrabold">{detail.company_count}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Status</p><p className="mt-1 text-xs font-bold">{detail.is_active ? "Active" : "Suspended"}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Email</p><p className="mt-1 text-xs font-bold">{detail.is_email_verified ? "Verified" : "Unverified"}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Last login</p><p className="mt-1 text-xs font-bold">{detail.last_login ? new Date(detail.last_login).toLocaleString() : "never"}</p></div></div><div><p className="text-sm font-extrabold">Companies &amp; roles</p>{detail.memberships.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No workspace memberships.</p> : <div className="mt-2 space-y-2">{detail.memberships.map((membership) => <div key={membership.company_id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><div className="min-w-0"><p className="truncate font-bold text-[#4d4e57]">{membership.company_name}</p><p className="mt-0.5 text-[10px] text-[#999aa4]">joined {new Date(membership.created_at).toLocaleDateString()}</p></div><div className="flex items-center gap-2"><Badge tone="violet">{membership.role}</Badge><Badge tone={membership.status === "active" ? "green" : "neutral"}>{membership.status}</Badge></div></div>)}</div>}</div><div><p className="text-sm font-extrabold">Sessions</p>{detail.sessions.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No sign-ins recorded.</p> : <div className="mt-2 space-y-2">{detail.sessions.map((session) => <div key={session.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><div className="min-w-0"><p className="truncate text-[#4d4e57]">{session.user_agent || "Unknown device"}</p><p className="mt-0.5 text-[10px] text-[#999aa4]">{session.ip_address || "no ip"} · last used {new Date(session.last_used_at).toLocaleString()}</p></div><Badge tone={session.active ? "green" : "neutral"}>{session.active ? "active" : session.revoked_at ? "revoked" : "expired"}</Badge></div>)}</div>}</div><div><p className="text-sm font-extrabold">Recent activity</p>{detail.recent_activity.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No activity recorded.</p> : <div className="mt-2 space-y-2">{detail.recent_activity.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{item.title}</span><span className="shrink-0 text-[10px] text-[#999aa4]">{new Date(item.created_at).toLocaleString()}</span></div>)}</div>}</div></>}</div></Modal>}</>;}function AdminCompanies({ companies, onUpdate, loading, token }) {  const [search, setSearch] = useState("");  const [selected, setSelected] = useState(null);  const [detail, setDetail] = useState(null);  const [detailLoading, setDetailLoading] = useState(false);  const [detailError, setDetailError] = useState("");  const filtered = companies.filter((company) => company.name.toLowerCase().includes(search.toLowerCase()));  const openDetail = async (company) => { setSelected(company); setDetail(null); setDetailError(""); setDetailLoading(true); try { setDetail(await api.adminCompanyDetail(token, company.id)); } catch (requestError) { setDetailError(requestError.message || "Could not load company"); } finally { setDetailLoading(false); } };  const exportCsv = async () => { try { downloadCsv("companies.csv", await api.adminExportCompaniesCsv(token)); } catch (requestError) { setDetailError(requestError.message || "Could not export companies"); } };  return <><AdminTablePage title="Companies" description="Tenant workspaces and plan state." extra={<Button variant="outline" size="sm" onClick={exportCsv}>Export CSV</Button>} search={search} setSearch={setSearch} loading={loading} gridTemplate="1.5fr .6fr .7fr .8fr .8fr .7fr" minWidth={850} columns={<><span>Company</span><span>Stores</span><span>Members</span><span>Plan</span><span>Status</span><span>Action</span></>} rows={filtered.map((company) => <div key={company.id} className="grid min-w-[850px] grid-cols-[1.5fr_.6fr_.7fr_.8fr_.8fr_.7fr] items-center gap-3 border-t border-[#f0f0f3] px-4 py-4 text-xs"><button type="button" onClick={() => openDetail(company)} className="text-left"><p className="font-bold hover:text-[#6957f5]">{company.name}</p><p className="mt-1 text-[10px] text-[#999aa4]">{company.country} · {company.default_currency_code}</p></button><span>{company.store_count}</span><span>{company.member_count}</span><span className="capitalize">{company.plan_code || "-"}</span><Badge tone={company.is_active ? "green" : "red"} dot>{company.is_active ? "Active" : "Suspended"}</Badge><div className="flex gap-2"><Button variant="outline" size="xs" onClick={() => openDetail(company)}>View</Button><Button variant={company.is_active ? "danger" : "soft"} size="xs" onClick={() => onUpdate(company.id, { is_active: !company.is_active })}>{company.is_active ? "Suspend" : "Restore"}</Button></div></div>)} />{selected && <Modal open title={selected.name || "Company"} description={`${selected.country} · ${selected.default_currency_code}`} onClose={() => setSelected(null)} width="max-w-[780px]"><div className="space-y-5 p-5">{detailError && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{detailError}</p>}{detailLoading ? <p className="py-8 text-center text-xs text-[#999aa4]">Loading health...</p> : detail && <><div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-5"><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Stores</p><p className="mt-1 text-lg font-extrabold">{detail.store_count}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Members</p><p className="mt-1 text-lg font-extrabold">{detail.member_count}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Customers</p><p className="mt-1 text-lg font-extrabold">{detail.customer_count}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Sales</p><p className="mt-1 text-lg font-extrabold">{money(Number(detail.gmv_total || 0), detail.gmv_currency)}</p></div><div className="rounded-xl bg-[#fafafd] p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Plan fees</p><p className="mt-1 text-lg font-extrabold">{money(Number(detail.revenue_total || 0), "USD")}</p></div></div><div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2.5 text-xs"><Badge tone={detail.is_active ? "green" : "red"} dot>{detail.is_active ? "Active" : "Suspended"}</Badge><span className="text-[#777883]">Plan <strong className="capitalize text-[#4d4e57]">{detail.plan_code || "-"}</strong>{detail.billing_cycle ? ` / ${detail.billing_cycle}` : ""}</span><Badge tone={detail.subscription_status === "active" ? "green" : detail.subscription_status === "pending" ? "yellow" : "neutral"}>{detail.subscription_status || "no subscription"}</Badge><span className="text-[#777883]">{detail.orders_total} paid orders</span><span className="text-[#999aa4]">Last activity {detail.last_activity ? new Date(detail.last_activity).toLocaleString() : "never"}</span></div><div><p className="text-sm font-extrabold">Stores</p>{detail.stores.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No stores.</p> : <div className="mt-2 space-y-2">{detail.stores.map((store) => <div key={store.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><div className="min-w-0"><p className="truncate font-bold text-[#4d4e57]">{store.name}</p><p className="mt-0.5 text-[10px] text-[#999aa4]">{store.currency_code} · opened {new Date(store.created_at).toLocaleDateString()}</p></div><Badge tone={store.is_active ? "green" : "red"}>{store.is_active ? "active" : "paused"}</Badge></div>)}</div>}</div><div><p className="text-sm font-extrabold">Members &amp; roles</p>{detail.members.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No members.</p> : <div className="mt-2 space-y-2">{detail.members.map((member) => <div key={member.user_id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><div className="min-w-0"><p className="truncate font-bold text-[#4d4e57]">{member.full_name}</p><p className="mt-0.5 truncate text-[10px] text-[#999aa4]">{member.email}</p></div><div className="flex items-center gap-2"><Badge tone="violet">{member.role}</Badge><Badge tone={member.status === "active" ? "green" : "neutral"}>{member.status}</Badge></div></div>)}</div>}</div><div><p className="text-sm font-extrabold">Recent activity</p>{detail.recent_activity.length === 0 ? <p className="mt-2 text-xs text-[#999aa4]">No activity recorded.</p> : <div className="mt-2 space-y-2">{detail.recent_activity.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{item.title}</span><span className="shrink-0 text-[10px] text-[#999aa4]">{new Date(item.created_at).toLocaleString()}</span></div>)}</div>}</div></>}</div></Modal>}</>;}function AdminStores({ stores, onUpdate, loading }) {  const [search, setSearch] = useState("");  const filtered = stores.filter((store) => `${store.name} ${store.company_name}`.toLowerCase().includes(search.toLowerCase()));  return <AdminTablePage title="Stores" description="Every location across tenant workspaces." search={search} setSearch={setSearch} loading={loading} gridTemplate="1.4fr 1.3fr .7fr .8fr .7fr" minWidth={720} columns={<><span>Store</span><span>Company</span><span>Currency</span><span>Status</span><span>Action</span></>} rows={filtered.map((store) => <div key={store.id} className="grid min-w-[720px] grid-cols-[1.4fr_1.3fr_.7fr_.8fr_.7fr] items-center gap-3 border-t border-[#f0f0f3] px-4 py-4 text-xs"><div><p className="font-bold">{store.name}</p><p className="mt-1 text-[10px] text-[#999aa4]">{store.address || "No address"}</p></div><span className="text-[#777883]">{store.company_name}</span><span className="font-bold">{store.currency_code}</span><Badge tone={store.is_active ? "green" : "red"} dot>{store.is_active ? "Active" : "Suspended"}</Badge><Button variant={store.is_active ? "danger" : "soft"} size="xs" onClick={() => onUpdate(store.id, { is_active: !store.is_active })}>{store.is_active ? "Suspend" : "Restore"}</Button></div>)} />;}function AdminSubscriptions({ subscriptions, loading }) {  const [filter, setFilter] = useState("all");  const [cancelTarget, setCancelTarget] = useState(null);  const [memberRemoveTarget, setMemberRemoveTarget] = useState(null);  const filtered = filter === "all" ? subscriptions : subscriptions.filter((subscription) => subscription.status === filter);  return <AdminTablePage title="Subscriptions" description="Plan status across all companies." loading={loading} gridTemplate="1.5fr .7fr .8fr 1fr 1fr" minWidth={720} extra={<div className="flex rounded-lg bg-[#f5f5f8] p-1">{["all", "active", "pending", "canceled"].map((value) => <button key={value} onClick={() => setFilter(value)} className={`rounded-md px-3 py-1.5 text-[10px] font-bold capitalize ${filter === value ? "bg-white text-[#4d4e57] shadow-sm" : "text-[#9697a0]"}`}>{value}</button>)}</div>} columns={<><span>Company</span><span>Plan</span><span>Status</span><span>Starts</span><span>Ends</span></>} rows={filtered.map((subscription) => <div key={subscription.id} className="grid min-w-[720px] grid-cols-[1.5fr_.7fr_.8fr_1fr_1fr] items-center gap-3 border-t border-[#f0f0f3] px-4 py-4 text-xs"><span className="font-bold">{subscription.company_name}</span><span className="capitalize">{subscription.plan_code}</span><Badge tone={subscription.status === "active" ? "green" : subscription.status === "pending" ? "yellow" : "neutral"} dot>{subscription.status}</Badge><span className="text-[#777883]">{new Date(subscription.starts_at).toLocaleDateString()}</span><span className="text-[#777883]">{subscription.ends_at ? new Date(subscription.ends_at).toLocaleDateString() : "-"}</span></div>)} />;}function AdminAudit({ token }) {  const [rows, setRows] = useState([]);  const [source, setSource] = useState("all");  const [search, setSearch] = useState("");  const [loading, setLoading] = useState(true);  const [error, setError] = useState("");  useEffect(() => { let active = true; setLoading(true); const timer = setTimeout(async () => { try { const params = { limit: 150 }; if (source !== "all") params.source = source; if (search.trim()) params.search = search.trim(); const data = await api.adminActivity(token, params); if (active) { setRows(data); setError(""); } } catch (requestError) { if (active) setError(requestError.message || "Could not load activity"); } finally { if (active) setLoading(false); } }, search ? 300 : 0); return () => { active = false; clearTimeout(timer); }; }, [token, source, search]);  const TABS = [["all", "Everything"], ["platform", "Platform events"], ["admin", "Admin actions"]];  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Activity</h2><p className="mt-1 text-sm text-[#898a95]">Every event on the platform — signups, logins, sales, refunds, team changes — alongside platform-admin actions.</p></div></div><div className="mt-6 flex flex-wrap items-center gap-3"><div className="inline-flex rounded-xl border border-[#e4e4eb] bg-[#f5f5f8] p-1">{TABS.map(([id, label]) => <button key={id} type="button" onClick={() => setSource(id)} className={`rounded-lg px-3.5 py-2 text-xs font-bold transition ${source === id ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}>{label}</button>)}</div><div className="relative w-full max-w-[320px]"><Search size={15} className="absolute left-3.5 top-3 text-[#a1a2ab]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search email, action or type..." className="h-10 w-full rounded-xl border border-[#e3e3ea] bg-[#fcfcfd] pl-10 pr-3 text-xs outline-none focus:border-[#887bf3]" /></div>{loading && <span className="text-[10px] font-semibold text-[#999aa4]">Refreshing...</span>}</div>{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-5 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white"><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-[#eeeeF2] text-[10px] uppercase tracking-[.12em] text-[#92939d]"><th className="px-4 py-3">Event</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Who</th><th className="px-4 py-3">Details</th><th className="px-4 py-3">Time</th></tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={5} className="px-4 py-8 text-center text-[#999aa4]">{loading ? "Loading..." : "No activity found."}</td></tr> : rows.map((row) => <tr key={`${row.source}-${row.id}`} className="border-b border-[#f0f0f3] last:border-0"><td className="px-4 py-3"><p className="font-bold text-[#3d3e47]">{row.title}</p><p className="mt-0.5 text-[10px] text-[#a1a2ab]">{row.event_type}</p></td><td className="px-4 py-3"><Badge tone={row.source === "admin" ? "red" : "violet"}>{row.source === "admin" ? "Admin" : "Platform"}</Badge></td><td className="px-4 py-3 text-[#777883]">{row.actor_email || (row.entity_type ? `entity: ${row.entity_type}` : "system")}</td><td className="max-w-[320px] truncate px-4 py-3 text-[#999aa4]">{row.details ? JSON.stringify(row.details) : "-"}</td><td className="whitespace-nowrap px-4 py-3 text-[#777883]">{new Date(row.created_at).toLocaleString()}</td></tr>)}</tbody></table></div></div></div>;}

function AdminHelpContent({ token, notify }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [previewVertical, setPreviewVertical] = useState("general");
  const [previewLanguage, setPreviewLanguage] = useState("en");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api.adminHelpArticles(token));
    } catch (requestError) {
      setError(requestError.message || "Could not load help content");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token]);

  const newDraft = () => setDraft({
    is_new: true, id: "", section_id: "general", section_title: "General", section_title_km: "",
    section_blurb: "", section_blurb_km: "", title: "", title_km: "", steps: "", steps_km: "",
    tip: "", tip_km: "", verticals: "general", roles: "owner,manager", position: 0, is_active: true,
  });
  const editDraft = (row) => setDraft({
    ...row, is_new: false,
    section_title_km: row.section_title_km || "", section_blurb_km: row.section_blurb_km || "",
    title_km: row.title_km || "", steps_km: (row.steps_km || []).join("\n"), tip_km: row.tip_km || "",
    steps: (row.steps || []).join("\n"), verticals: (row.verticals || []).join(", "), roles: (row.roles || []).join(", "),
  });

  const set = (field) => (event) => setDraft((current) => ({ ...current, [field]: event.target.value }));
  const splitList = (value) => value.split(",").map((item) => item.trim()).filter(Boolean);
  const splitLines = (value) => value.split("\n").map((item) => item.trim()).filter(Boolean);

  const save = async () => {
    const steps = splitLines(draft.steps);
    if (!draft.title.trim() || steps.length === 0) {
      setError("A title and at least one step are required");
      return;
    }
    const stepsKm = splitLines(draft.steps_km);
    const body = {
      section_id: draft.section_id.trim() || "general",
      section_title: draft.section_title.trim() || "General",
      section_title_km: draft.section_title_km.trim() || null,
      section_blurb: draft.section_blurb.trim() || " ",
      section_blurb_km: draft.section_blurb_km.trim() || null,
      title: draft.title.trim(),
      title_km: draft.title_km.trim() || null,
      steps,
      steps_km: stepsKm.length ? stepsKm : null,
      tip: draft.tip.trim() || null,
      tip_km: draft.tip_km.trim() || null,
      verticals: splitList(draft.verticals),
      roles: splitList(draft.roles),
      position: Number(draft.position) || 0,
      is_active: draft.is_active !== false,
    };
    setSaving(true);
    setError("");
    try {
      if (draft.is_new) {
        await api.adminCreateHelpArticle(token, { id: draft.id.trim(), ...body });
        notify?.("Help article created");
      } else {
        await api.adminUpdateHelpArticle(token, draft.id, body);
        notify?.("Help article updated");
      }
      setDraft(null);
      await load();
    } catch (requestError) {
      setError(requestError.message || "Could not save the article");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (row) => {
    try {
      await api.adminUpdateHelpArticle(token, row.id, { is_active: !row.is_active });
      notify?.(row.is_active ? "Help article deactivated" : "Help article restored");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Could not update status");
    }
  };

  const inputClass = "h-10 w-full rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs text-[#303139] outline-none";
  const textareaClass = "w-full rounded-xl border border-[#e4e4eb] bg-white p-3 text-xs text-[#303139] outline-none";
  const labelClass = "mb-1 block text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]";

  return <div className="mx-auto max-w-[1200px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Help content</h2>
        <p className="mt-1 text-sm text-[#898a95]">Edit the in-app guides. Changes apply to the help center and the assistant immediately.</p>
      </div>
      <Button onClick={newDraft}>New article</Button>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}

    {draft && <section className="mt-6 rounded-2xl border border-[#e9e9ef] bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-extrabold">{draft.is_new ? "New article" : `Edit ${draft.id}`}</h3>
        <button onClick={() => setDraft(null)} className="text-[11px] font-bold text-[#777883] hover:text-[#303139]">Cancel</button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {draft.is_new && <label><span className={labelClass}>Id (slug)</span><input className={inputClass} value={draft.id} onChange={set("id")} placeholder="inventory.restock" /></label>}
        <label><span className={labelClass}>Section id</span><input className={inputClass} value={draft.section_id} onChange={set("section_id")} /></label>
        <label><span className={labelClass}>Section title</span><input className={inputClass} value={draft.section_title} onChange={set("section_title")} /></label>
        <label><span className={labelClass}>Section title (Khmer)</span><input className={inputClass} value={draft.section_title_km} onChange={set("section_title_km")} /></label>
        <label><span className={labelClass}>Section blurb</span><input className={inputClass} value={draft.section_blurb} onChange={set("section_blurb")} /></label>
        <label><span className={labelClass}>Section blurb (Khmer)</span><input className={inputClass} value={draft.section_blurb_km} onChange={set("section_blurb_km")} /></label>
        <label><span className={labelClass}>Title</span><input className={inputClass} value={draft.title} onChange={set("title")} /></label>
        <label><span className={labelClass}>Title (Khmer)</span><input className={inputClass} value={draft.title_km} onChange={set("title_km")} /></label>
        <label className="sm:col-span-2"><span className={labelClass}>Steps (one per line)</span><textarea rows={5} className={textareaClass} value={draft.steps} onChange={set("steps")} /></label>
        <label className="sm:col-span-2"><span className={labelClass}>Steps (Khmer, one per line)</span><textarea rows={4} className={textareaClass} value={draft.steps_km} onChange={set("steps_km")} /></label>
        <label><span className={labelClass}>Tip</span><input className={inputClass} value={draft.tip} onChange={set("tip")} /></label>
        <label><span className={labelClass}>Tip (Khmer)</span><input className={inputClass} value={draft.tip_km} onChange={set("tip_km")} /></label>
        <label><span className={labelClass}>Verticals (comma-separated)</span><input className={inputClass} value={draft.verticals} onChange={set("verticals")} /></label>
        <label><span className={labelClass}>Roles (comma-separated)</span><input className={inputClass} value={draft.roles} onChange={set("roles")} /></label>
        <label><span className={labelClass}>Position</span><input className={inputClass} value={draft.position} onChange={set("position")} /></label>
        <label className="flex items-center gap-2 pt-5 text-xs font-semibold"><input type="checkbox" checked={draft.is_active !== false} onChange={(event) => setDraft((current) => ({ ...current, is_active: event.target.checked }))} /> Active</label>
      </div>
      {(() => {
        const km = previewLanguage === "km";
        const previewTitle = (km ? draft.title_km : "") || draft.title || "(untitled)";
        const previewSteps = splitLines(km ? (draft.steps_km || "") : (draft.steps || ""));
        const previewTip = (km ? draft.tip_km : "") || draft.tip;
        const applies = splitList(draft.verticals).includes(previewVertical);
        return (
          <div className="mt-4 rounded-xl border border-[#e9e9ef] bg-[#fafafd] p-4">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Preview</p>
              <select value={previewVertical} onChange={(event) => setPreviewVertical(event.target.value)} className="h-8 rounded-lg border border-[#e4e4eb] bg-white px-2 text-[10px] font-semibold text-[#4f5059]">
                {["general", "coffee", "restaurant", "mart", "electronics", "shop"].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
              <select value={previewLanguage} onChange={(event) => setPreviewLanguage(event.target.value)} className="h-8 rounded-lg border border-[#e4e4eb] bg-white px-2 text-[10px] font-semibold text-[#4f5059]">
                <option value="en">EN</option>
                <option value="km">ខ្មែរ</option>
              </select>
              <span className={`text-[10px] font-semibold ${applies ? "text-[#4f8b32]" : "text-[#c2564b]"}`}>{applies ? "Shown for this business type" : "Hidden for this business type"}</span>
            </div>
            <div className="mt-3 rounded-2xl border border-[#e9e9ef] bg-white p-4">
              <p className="text-sm font-extrabold text-[#202128]">{previewTitle}</p>
              <ol className="mt-3 space-y-1.5">
                {previewSteps.map((step, index) => (
                  <li key={index} className="flex gap-2 text-[11px] leading-5 text-[#5d5e68]">
                    <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#ece9ff] text-[9px] font-extrabold text-[#6957f5]">{index + 1}</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
              {previewTip && <p className="mt-3 rounded-lg border border-[#e6e5f3] bg-[#faf9ff] p-2 text-[10px] leading-4 text-[#696a76]">Tip: {previewTip}</p>}
            </div>
          </div>
        );
      })()}
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
        <span className="text-[10px] text-[#92939d]">Title and at least one step are required. Khmer fields fall back to English when empty.</span>
      </div>
    </section>}

    <div className="mt-6 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
      <div className="flex items-center justify-between border-b border-[#eeeeF2] px-4 py-3">
        <p className="text-sm font-extrabold">Articles</p>
        <p className="text-[10px] text-[#92939d]">{rows.length} total</p>
      </div>
      {loading ? <p className="p-6 text-sm text-[#92939d]">Loading...</p> : rows.map((row) => <div key={row.id} className="flex items-center gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
        <span className={`h-2 w-2 shrink-0 rounded-full ${row.is_active ? "bg-[#76bc4b]" : "bg-[#c8c9d0]"}`} />
        <span className="w-40 shrink-0 truncate font-mono text-[10px] text-[#777883]" title={row.id}>{row.id}</span>
        <span className="min-w-0 flex-1 truncate font-bold" title={row.title}>{row.title}</span>
        <span className="hidden shrink-0 text-[#92939d] sm:block">{row.section_id}</span>
        <button onClick={() => editDraft(row)} className="shrink-0 rounded-lg border border-[#e4e4eb] px-2 py-1 text-[10px] font-bold text-[#62636d] hover:border-[#bdb9ee] hover:text-[#6957f5]">Edit</button>
        <button onClick={() => toggleActive(row)} className="shrink-0 rounded-lg border border-[#e4e4eb] px-2 py-1 text-[10px] font-bold text-[#62636d] hover:border-[#bdb9ee] hover:text-[#6957f5]">{row.is_active ? "Deactivate" : "Restore"}</button>
      </div>)}
    </div>
  </div>;
}

function AdminSupportInsights({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [windowDays, setWindowDays] = useState(30);
  const [tickets, setTickets] = useState([]);
  const [ticketBusy, setTicketBusy] = useState(false);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [insights, ticketRows] = await Promise.all([
        api.adminSupportInsights(token, windowDays),
        api.adminSupportTickets(token),
      ]);
      setData(insights);
      setTickets(ticketRows);
    } catch (requestError) {
      setError(requestError.message || "Could not load support insights");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, windowDays]);
  const resolveTicket = async (ticket, status) => {
    setTicketBusy(true);
    setError("");
    try {
      await api.adminUpdateSupportTicket(token, ticket.id, { status });
      await load();
    } catch (requestError) {
      setError(requestError.message || "Could not update the request");
    } finally {
      setTicketBusy(false);
    }
  };
  const rate = data?.satisfaction_rate;
  const stat = (label, value, detail) => (
    <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
      <p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">{label}</p>
      <p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{value}</p>
      {detail && <p className="mt-1 text-[11px] text-[#92939d]">{detail}</p>}
    </div>
  );
  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Support insights</h2>
        <p className="mt-1 text-sm text-[#898a95]">How the in-app assistant answers questions, and where it falls short.</p>
      </div>
      <select value={windowDays} onChange={(event) => setWindowDays(Number(event.target.value))} className="h-10 rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs font-semibold text-[#4f5059]">
        {[7, 30, 90, 365].map((days) => <option key={days} value={days}>Last {days} days</option>)}
      </select>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading ? <p className="mt-6 text-sm text-[#92939d]">Loading...</p> : data && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stat("Helpful", data.feedback_up)}
        {stat("Not helpful", data.feedback_down)}
        {stat("Satisfaction", rate == null ? "-" : `${Math.round(rate * 100)}%`, `${data.feedback_up + data.feedback_down} rated`)}
        {stat("Escalations", data.escalations, "Talk to a human")}
      </div>
      <div className="mt-6 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
        <div className="flex items-center justify-between border-b border-[#eeeeF2] px-4 py-3">
          <div>
            <p className="text-sm font-extrabold">AI usage</p>
            <p className="text-[10px] text-[#92939d]">Tokens the assistant consumed in this window.</p>
          </div>
          <p className="text-[10px] text-[#92939d]">{data.ai_calls} calls · {data.ai_prompt_tokens + data.ai_completion_tokens} tokens · ~${Number(data.ai_estimated_cost_usd || 0).toFixed(4)}</p>
        </div>
        {(data.ai_by_model || []).length === 0
          ? <p className="p-6 text-xs text-[#92939d]">No usage in this window.</p>
          : data.ai_by_model.map((row) => (
            <div key={`${row.provider}-${row.model}`} className="flex items-center gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
              <span className="shrink-0 font-mono text-[10px] text-[#777883]">{row.provider}</span>
              <span className="min-w-0 flex-1 truncate" title={row.model}>{row.model}</span>
              <span className="shrink-0 text-[#92939d]">{row.calls} calls</span>
              <span className="shrink-0 font-bold text-[#777883]">{row.prompt_tokens + row.completion_tokens} tok</span>
            </div>
          ))}
      </div>
      <div className="mt-6 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
        <div className="flex items-center justify-between border-b border-[#eeeeF2] px-4 py-3">
          <p className="text-sm font-extrabold">Open support requests</p>
          <p className="text-[10px] text-[#92939d]">{tickets.filter((row) => row.status === "open").length} open</p>
        </div>
        {tickets.filter((row) => row.status === "open").length === 0
          ? <p className="p-6 text-xs text-[#92939d]">No open requests.</p>
          : tickets.filter((row) => row.status === "open").map((ticket) => (
            <div key={ticket.id} className="flex items-center gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
              <span className="shrink-0 font-mono text-[10px] text-[#777883]">{ticket.reference}</span>
              <span className="min-w-0 flex-1 truncate" title={ticket.question}>{ticket.question}</span>
              <span className="hidden shrink-0 text-[#b0b1ba] sm:block">{new Date(ticket.created_at).toLocaleDateString()}</span>
              <button disabled={ticketBusy} onClick={() => resolveTicket(ticket, "resolved")} className="shrink-0 rounded-lg bg-[#6957f5] px-2.5 py-1 text-[10px] font-bold text-white disabled:opacity-50">Resolve</button>
            </div>
          ))}
      </div>
      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <div className="overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
          <div className="border-b border-[#eeeeF2] px-4 py-3">
            <p className="text-sm font-extrabold">Questions needing attention</p>
            <p className="text-[10px] text-[#92939d]">Ranked by down-votes, then volume.</p>
          </div>
          {data.top_questions.length === 0
            ? <p className="p-6 text-xs text-[#92939d]">No feedback yet in this window.</p>
            : data.top_questions.map((row) => (
              <div key={row.question} className="flex items-center justify-between gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
                <span className="min-w-0 flex-1 truncate" title={row.question}>{row.question}</span>
                <span className="shrink-0 text-[#777883]">{row.total} asked</span>
                <span className={`shrink-0 font-bold ${row.down > 0 ? "text-[#c2564b]" : "text-[#92939d]"}`}>{row.down} down</span>
              </div>
            ))}
        </div>
        <div className="overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
          <div className="border-b border-[#eeeeF2] px-4 py-3">
            <p className="text-sm font-extrabold">Not covered</p>
            <p className="text-[10px] text-[#92939d]">Questions no guide matched — content to add.</p>
          </div>
          {(data.uncovered_questions || []).length === 0
            ? <p className="p-6 text-xs text-[#92939d]">Nothing uncovered in this window.</p>
            : data.uncovered_questions.map((row) => (
              <div key={row.question} className="flex items-center justify-between gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
                <span className="min-w-0 flex-1 truncate" title={row.question}>{row.question}</span>
                <span className="shrink-0 font-bold text-[#c2564b]">×{row.total}</span>
              </div>
            ))}
        </div>
        <div className="overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
          <div className="border-b border-[#eeeeF2] px-4 py-3">
            <p className="text-sm font-extrabold">Recent feedback</p>
            <p className="text-[10px] text-[#92939d]">Latest ratings across all workspaces.</p>
          </div>
          {data.recent_feedback.length === 0
            ? <p className="p-6 text-xs text-[#92939d]">No feedback yet.</p>
            : data.recent_feedback.map((row, index) => (
              <div key={index} className="flex items-center gap-3 border-t border-[#f0f0f3] px-4 py-3 text-xs">
                <span className={`shrink-0 font-bold ${row.rating === "up" ? "text-[#6daf43]" : "text-[#c2564b]"}`}>{row.rating === "up" ? "Helpful" : "Not helpful"}</span>
                <span className="min-w-0 flex-1 truncate" title={row.question}>{row.question}</span>
                <span className="shrink-0 text-[#b0b1ba]">{new Date(row.created_at).toLocaleDateString()}</span>
              </div>
            ))}
        </div>
      </div>
    </>}
  </div>;
}

function AdminChmabaPaySettings({ token, notify }) {  const [settings, setSettings] = useState(null);  const [form, setForm] = useState({ mode: "mock", api_url: "", platform_store_id: "", api_key: "", webhook_secret: "" });  const [loading, setLoading] = useState(true);  const [saving, setSaving] = useState(false);  const [reveal, setReveal] = useState({ api_key: false, webhook_secret: false });  const load = async (silent = false) => {    if (!silent) setLoading(true);    try {      const data = await api.chamabapaySettings(token);      setSettings(data);      setForm((current) => ({ ...current, mode: data.mode, api_url: data.api_url, platform_store_id: data.platform_store_id || "" }));    } catch (error) { notify(error.message || "Could not load ChmabaPay settings"); } finally { if (!silent) setLoading(false); }  };  useEffect(() => { load(); }, [token]);  const setField = (name, value) => setForm((current) => ({ ...current, [name]: value }));  const save = async () => {    if (!settings) return;    setSaving(true);    const body = { mode: form.mode, api_url: form.api_url.trim(), platform_store_id: form.platform_store_id.trim() };    if (form.api_key.trim()) body.api_key = form.api_key.trim();    if (form.webhook_secret.trim()) body.webhook_secret = form.webhook_secret.trim();    try {      await api.updateChamabapaySettings(token, body);      notify("ChmabaPay integration settings saved");      setForm((current) => ({ ...current, api_key: "", webhook_secret: "" }));      await load(true);    } catch (error) { notify(error.message || "Could not save ChmabaPay settings"); } finally { setSaving(false); }  };  const revealStoredSecret = async (secretKey, fieldName) => {    if (typeof window !== "undefined" && !window.confirm("Reveal the stored secret? It will be shown in the field.")) return;    try {      const res = await api.revealChamabapaySecret(token, fieldName);      setForm((current) => ({ ...current, [secretKey]: res.value || "" }));      setReveal((current) => ({ ...current, [secretKey]: true }));      notify("Secret revealed");    } catch (error) { notify(error.message || "Could not reveal secret"); }  };  const removeField = async (name, key) => {    setSaving(true);    try {      await api.updateChamabapaySettings(token, { [key]: "" });      await load(true);      notify("Field cleared");    } catch (error) { notify(error.message || "Could not update field"); } finally { setSaving(false); }  };  if (loading && !settings) return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex h-64 items-center justify-center text-xs text-[#999aa4]">Loading ChmabaPay settings...</div></div>;  const secretField = (label, key, secretKey, value, setValue, existing, placeholder, hint) => {    const shown = existing;    return <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">{label}</span><div className="flex gap-2"><div className="relative min-w-0 flex-1"><input type={reveal[secretKey] ? "text" : "password"} value={value} onChange={(event) => setValue(event.target.value)} placeholder={shown ? placeholder : "Enter the secret to store it in the platform database"} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 pr-12 text-sm outline-none focus:border-[#887bf3]" autoComplete="new-password" /></div><Button variant="outline" type="button" onClick={() => setReveal((current) => ({ ...current, [secretKey]: !current[secretKey] }))}>{reveal[secretKey] ? <Eye size={14} /> : <EyeOff size={14} />}</Button></div>{hint && <span className="mt-1.5 block text-[10px] leading-4 text-[#999aa4]">{hint}</span>}</label><div className="mt-3 flex items-center gap-2"><span className="text-[10px] font-semibold">{existing ? "Currently set (stored in database)." : "Not set - falling back to environment config."}</span>{existing && <button className="text-[10px] font-bold text-[#5b4be3] hover:underline" onClick={() => revealStoredSecret(secretKey, key)}>Reveal</button>}{existing && <button className="text-[10px] font-bold text-[#c2564b] hover:underline" onClick={() => removeField(label, key)}>Remove override</button>}</div></div>;  };  const textRow = (label, name, placeholder, hint) => <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">{label}</span><input value={form[name]} onChange={(event) => setField(name, event.target.value)} placeholder={placeholder} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />{hint && <span className="mt-1.5 block text-[10px] leading-4 text-[#999aa4]">{hint}</span>}</label>;  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">ChmabaPay integration</h2><p className="mt-1 text-sm text-[#898a95]">Platform-level ChmabaPay account used to collect Chmaba plan payments and to broker merchant KHQR.</p></div><div className="flex items-center gap-2"><Badge tone={settings.mode === "live" ? "green" : "yellow"} dot>{settings.mode === "live" ? "Live mode" : "Test mode"}</Badge>{settings.environment === "production" && <Badge tone="red">Production</Badge>}</div></div><div className="mt-5 rounded-2xl border border-[#e3e8dc] bg-[#f8fcf4] px-4 py-3 text-xs leading-5 text-[#465142]"><p><span className="font-extrabold">How this is used:</span> plan billing and merchant KHQR go through ChmabaPay at <span className="font-mono text-[11px]">{settings.api_url}</span>. Register the webhook endpoint below in the ChmabaPay dashboard so Chmaba is notified when a payment settles (webhook POST with <span className="font-mono text-[11px]">X-ChmabaPay-Signature</span>).</p></div><div className="mt-5 grid gap-5 lg:grid-cols-2"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Mode</span><Dropdown value={form.mode} onChange={(v) => setField("mode", v)} options={[{ value: "mock", label: "Test mode (no real charges)" }, { value: "live", label: "Live (real ChmabaPay)" }]} /></label>{textRow("API URL", "api_url", "https://pay.chmaba.com", "ChmabaPay base URL.")}<div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">{secretField("API key", "api_key", "api_key", form.api_key, (value) => setField("api_key", value), settings.api_key_set, (settings.api_key_preview || "(stored)"), "Server-side key (ck_live_...). Authenticates every store on the ChmabaPay account.")}</div><div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">{secretField("Webhook signing secret", "webhook_secret", "webhook_secret", form.webhook_secret, (value) => setField("webhook_secret", value), settings.webhook_secret_set, (settings.webhook_secret_preview || "(stored)"), "Used to verify X-ChmabaPay-Signature on incoming webhooks.")}</div>{textRow("Platform store id", "platform_store_id", "st_...", "Optional. Auto-detected from the ChmabaPay internal store that collects Chmaba plan fees.")}{settings.resolved_platform_store_id && <p className="mt-1 text-[10px] text-[#84907e]">Effective (used for plan fees): {settings.resolved_platform_store_id}</p>}</div><div className="mt-5 grid gap-5 lg:grid-cols-2"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Current webhook endpoint</span><div className="flex items-center gap-2"><code className="min-w-0 flex-1 truncate rounded-xl border border-[#e3e3ea] bg-[#fcfcfd] px-3.5 py-2.5 text-xs text-[#4d4e57]">{`${api.baseUrl}/webhooks/chamabapay`}</code><Button variant="outline" size="sm" onClick={() => { if (typeof navigator !== "undefined") navigator.clipboard?.writeText(`${api.baseUrl}/webhooks/chamabapay`).then(() => notify("Webhook URL copied")).catch(() => {}); }}><Copy size={13} /></Button></div><span className="mt-1.5 block text-[10px] leading-4 text-[#999aa4]">Register this URL in the ChmabaPay dashboard. Use your public API domain in production.</span></label></div><div className="mt-6 flex gap-2"><Button onClick={save} disabled={saving}><Check size={15} /> Save integration settings</Button></div></div>;}function AdminPayments({ token, notify }) {  const [tab, setTab] = useState("links");  return <div><div className="mx-auto max-w-[1460px] px-5 pt-6 lg:px-8"><div className="inline-flex rounded-xl border border-[#e4e4eb] bg-[#f5f5f8] p-1"><button onClick={() => setTab("links")} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition ${tab === "links" ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}><QrCode size={14} /> Merchant KHQR links</button><button onClick={() => setTab("chamabapay")} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition ${tab === "chamabapay" ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}><Landmark size={14} /> ChmabaPay integration</button></div></div>{tab === "chamabapay" ? <AdminChmabaPaySettings token={token} notify={notify} /> : <AdminPaymentLinkManager token={token} notify={notify} />}</div>;}function AdminPaymentLinkManager({ token, notify }) {  const [companies, setCompanies] = useState([]);  const [stores, setStores] = useState([]);  const [filter, setFilter] = useState("all");  const [search, setSearch] = useState("");  const [busyId, setBusyId] = useState("");  const [loading, setLoading] = useState(true);  const load = async (silent = false) => {    if (!silent) setLoading(true);    try {      const data = await api.adminPaymentLinks(token, { ...(filter !== "all" ? { status: filter } : {}), ...(search.trim() ? { search: search.trim() } : {}) });      setCompanies(data.companies || []);      setStores(data.stores || []);    } catch (error) { notify(error.message || "Could not load payment links"); } finally { if (!silent) setLoading(false); }  };  useEffect(() => { const timer = window.setTimeout(() => load(), 350); return () => window.clearTimeout(timer); }, [filter, search, token]);  const setStatus = async (scope, id, status, name) => {    setBusyId(`${scope}:${id}`);    try {      await api.adminUpdatePaymentLink(token, scope, id, { aba_payway_status: status });      notify(status === "active" ? `${name} approved — KHQR checkout enabled` : `${name} moved back to pending review`);      await load(true);    } catch (error) { notify(error.message || "Could not update payment link"); } finally { setBusyId(""); }  };  const tone = (status) => status === "active" ? "green" : status === "pending" ? "yellow" : "neutral";  const label = (status) => status === "active" ? "Active" : status === "pending" ? "Pending review" : "Not connected";  const pendingCount = [...companies, ...stores].filter((item) => item.aba_payway_status === "pending").length;  const activeCount = [...companies, ...stores].filter((item) => item.aba_payway_status === "active").length;  const rowActions = (scope, id, status, name) => <div className="flex items-center justify-end gap-1.5">{status === "pending" ? <Button size="xs" disabled={busyId === `${scope}:${id}`} onClick={() => setStatus(scope, id, "active", name)}><Check size={13} /> Approve</Button> : <Button size="xs" variant="outline" disabled={busyId === `${scope}:${id}`} onClick={() => setStatus(scope, id, "pending", name)}><RefreshCw size={13} /> Set pending</Button>}</div>;  const linkCell = (link) => link ? <div className="min-w-0"><p className="truncate font-mono text-[11px] text-[#4d4e57]" title={link}>{link}</p><a href={link} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold text-[#6957f5] hover:underline">Open link <ExternalLink size={10} /></a></div> : <span className="text-[#999aa4]">—</span>;  const group = (title, blurb, rows, cols) => <div className="rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div><h3 className="text-sm font-extrabold">{title}</h3><p className="mt-1 text-[11px] text-[#999aa4]">{blurb}</p></div><div className="app-scrollbar mt-4 overflow-x-auto"><div className="min-w-[760px]">{rows.length === 0 ? <div className="flex h-28 items-center justify-center text-xs text-[#999aa4]">No links {filter === "all" ? "submitted yet" : `with status "${filter}"`}.</div> : rows.map((row) => <div key={row.id} className="grid items-center gap-3 border-t border-[#f0f0f3] px-1 py-3.5 text-xs" style={{ gridTemplateColumns: cols }}><div className="min-w-0"><p className="truncate font-bold">{row.scope === "company" ? row.name : `${row.company_name} / ${row.name}`}</p>{row.scope === "store" ? <p className="mt-0.5 text-[10px] text-[#999aa4]">Store-level connection</p> : <p className="mt-0.5 text-[10px] text-[#999aa4]">Company-wide · {row.store_count} store(s)</p>}</div>{linkCell(row.aba_payway_link)}<span><Badge tone={tone(row.aba_payway_status)} dot>{label(row.aba_payway_status)}</Badge></span>{rowActions(row.scope, row.id, row.aba_payway_status, row.scope === "company" ? row.name : `${row.company_name} / ${row.name}`)}</div>)}</div></div></div>;  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Payment links</h2><p className="mt-1 text-sm text-[#898a95]">Merchant ABA PayWay links submitted for ChmabaPay KHQR checkout.</p></div><div className="flex items-center gap-2">{activeCount > 0 && <Badge tone="green" dot>{activeCount} active</Badge>}{pendingCount > 0 && <Badge tone="yellow" dot>{pendingCount} pending</Badge>}</div></div><div className="mt-5 rounded-2xl border border-[#e3e8dc] bg-[#f8fcf4] px-4 py-3 text-xs leading-5 text-[#465142]"><p><span className="font-extrabold">How to enable a merchant's KHQR:</span> the merchant submits their ABA PayWay link in Settings → Bank &amp; KHQR and it is registered with ChmabaPay automatically. Review it and click <span className="font-semibold">Approve</span> here so their POS checkout starts generating KHQR payments into their ABA account (usually within 24 hours).</p></div><div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="flex rounded-lg bg-[#f2f2f5] p-1">{["all", "pending", "active"].map((value) => <button key={value} onClick={() => setFilter(value)} className={`rounded-md px-3 py-1.5 text-[10px] font-bold capitalize ${filter === value ? "bg-white text-[#4d4e57] shadow-sm" : "text-[#9697a0]"}`}>{value === "all" ? "All" : value}</button>)}</div><div className="relative w-full sm:max-w-[340px]"><Search size={15} className="absolute left-3.5 top-3 text-[#a1a2ab]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search company or store..." className="h-10 w-full rounded-xl border border-[#e3e3ea] bg-[#fcfcfd] pl-10 pr-3 text-xs outline-none focus:border-[#887bf3]" /></div></div>{loading ? <p className="mt-8 text-center text-xs text-[#999aa4]">Loading payment links...</p> : <div className="mt-5 space-y-5">{group("Company-wide links", "One ABA account shared by every store in the workspace.", companies.map((item) => ({ ...item, scope: "company" })), "1.2fr 1.6fr .8fr .9fr")}{group("Store-level links", "Per-store ABA accounts that override the company-wide link.", stores.map((item) => ({ ...item, scope: "store" })), "1.2fr 1.6fr .8fr .9fr")}</div>}</div>;}function AdminBillingPayments({ token }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analytics, setAnalytics] = useState(null);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [data, summary] = await Promise.all([
        api.adminBillingPayments(token, status ? { status } : {}),
        api.adminBillingAnalytics(token),
      ]);
      setRows(data);
      setAnalytics(summary);
    } catch (requestError) {
      setError(requestError.message || "Could not load billing payments");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, status]);
  const statuses = ["", "pending", "paid", "failed", "expired", "canceled"];
  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Billing payments</h2><p className="mt-1 text-sm text-[#898a95]">Plan-fee KHQR payments, for support. Read-only.</p></div><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs font-semibold text-[#4f5059]">{statuses.map((value) => <option key={value || "all"} value={value}>{value || "All statuses"}</option>)}</select></div>{analytics && <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="rounded-2xl border border-[#e9e9ef] bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">MRR</p><p className="mt-1.5 text-xl font-extrabold tracking-[-.04em]">{money(Number(analytics.mrr || 0), "USD")}</p><p className="mt-1 text-[10px] text-[#92939d]">Active paid plans, list price</p></div><div className="rounded-2xl border border-[#e9e9ef] bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Plan revenue (30d)</p><p className="mt-1.5 text-xl font-extrabold tracking-[-.04em]">{money(Number(analytics.revenue_30d || 0), "USD")}</p><p className="mt-1 text-[10px] text-[#92939d]">{money(Number(analytics.revenue_total || 0), "USD")} all time</p></div><div className="rounded-2xl border border-[#e9e9ef] bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Payment success</p><p className="mt-1.5 text-xl font-extrabold tracking-[-.04em]">{analytics.payment_success_rate == null ? "-" : `${Math.round(analytics.payment_success_rate * 100)}%`}</p><p className="mt-1 text-[10px] text-[#92939d]">{analytics.payments_paid}/{analytics.payments_total} paid · {analytics.payments_pending} pending</p></div><div className="rounded-2xl border border-[#e9e9ef] bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Refunds</p><p className="mt-1.5 text-xl font-extrabold tracking-[-.04em]">{money(Number(analytics.refunds_total || 0), "USD")}</p><p className="mt-1 text-[10px] text-[#92939d]">{analytics.active_subscriptions} active subs</p></div></div>}{analytics && analytics.plan_mix.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{analytics.plan_mix.map((plan) => <span key={plan.plan_code} className="inline-flex items-center gap-2 rounded-xl border border-[#e9e9ef] bg-white px-3 py-2 text-xs"><span className="font-bold capitalize text-[#4d4e57]">{plan.plan_code}</span><span className="text-[#92939d]">{plan.subscriptions} subs</span><span className="font-semibold text-[#6957f5]">{money(Number(plan.mrr || 0), "USD")}</span></span>)}</div>}{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-6 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white"><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-[#eeeeF2] text-[10px] uppercase tracking-[.12em] text-[#92939d]"><th className="px-4 py-3">Company</th><th className="px-4 py-3">Plan</th><th className="px-4 py-3">Amount</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Fulfilled</th><th className="px-4 py-3">Created</th></tr></thead><tbody>{loading ? <tr><td colSpan={6} className="px-4 py-6 text-center text-[#999aa4]">Loading...</td></tr> : rows.length === 0 ? <tr><td colSpan={6} className="px-4 py-6 text-center text-[#999aa4]">No payments.</td></tr> : rows.map((row) => <tr key={row.id} className="border-b border-[#f0f0f3] last:border-0"><td className="px-4 py-3 font-bold text-[#4d4e57]">{row.company_name || row.company_id || "-"}</td><td className="px-4 py-3">{row.plan_code || "-"}{row.billing_cycle ? ` / ${row.billing_cycle}` : ""}</td><td className="px-4 py-3">{money(Number(row.amount), row.currency_code)}</td><td className="px-4 py-3"><Badge tone={row.status === "paid" ? "green" : row.status === "pending" ? "yellow" : "neutral"}>{row.status}</Badge></td><td className="px-4 py-3">{row.fulfilled_at ? new Date(row.fulfilled_at).toLocaleString() : "-"}</td><td className="px-4 py-3">{new Date(row.created_at).toLocaleString()}</td></tr>)}</tbody></table></div></div></div>;
}
function AdminTablePage({ title, description, search, setSearch, columns, rows, extra, loading, gridTemplate = "repeat(5, minmax(0, 1fr))", minWidth = 720 }) {  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">{title}</h2><p className="mt-1 text-sm text-[#898a95]">{description}</p></div>{extra}</div><div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">{setSearch && <div className="relative w-full max-w-[380px]"><Search size={15} className="absolute left-3.5 top-3 text-[#a1a2ab]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`Search ${title.toLowerCase()}...`} className="h-10 w-full rounded-xl border border-[#e3e3ea] bg-[#fcfcfd] pl-10 pr-3 text-xs outline-none focus:border-[#887bf3]" />{}</div>}{loading && <span className="text-[10px] font-semibold text-[#999aa4]">Refreshing...</span>}</div><div className="app-scrollbar mt-5 overflow-x-auto"><div className="grid gap-3 bg-[#fafafd] px-4 py-3 text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]" style={{ gridTemplateColumns: gridTemplate, minWidth }}>{columns}</div>{rows}{rows.length === 0 && <p className="py-14 text-center text-xs text-[#999aa4]">No records found.</p>}</div></div></div>;}function AdminPlans({ plans, onSave, loading }) {  const FEATURE_OPTIONS = [["inventory_management", "Inventory management"], ["purchasing", "Suppliers & purchase orders"], ["khqr_payments", "KHQR / online payments"], ["multi_currency", "Multi-currency & exchange rates"], ["advanced_reports", "Advanced reports & GDT export"], ["loyalty", "Customer loyalty points"], ["barcode_scanning", "Barcode scanning"], ["shift_management", "Shift management"], ["email_receipts", "Email receipts"], ["held_orders", "Hold & resume orders"], ["refunds", "Refunds"], ["receipt_customization", "Custom receipt templates"], ["roles_permissions", "Roles & permissions"], ["priority_support", "Priority support"]];  const empty = { code: "", name: "", description: "", monthly_price: 0, max_stores: 1, max_members: 1, transaction_limit: 0, capabilities: {}, is_active: true };  const [editing, setEditing] = useState(null);  const [draft, setDraft] = useState(empty);  const [isNew, setIsNew] = useState(false);  const [saving, setSaving] = useState(false);  const marketingBullets = (plan) => { const features = []; features.push(Number(plan.max_stores) > 1 ? `Up to ${plan.max_stores} stores` : "1 store"); features.push(Number(plan.max_members) > 1 ? `Up to ${plan.max_members} team members` : "1 owner account"); if (Number(plan.transaction_limit) > 0) features.push(`${Number(plan.transaction_limit).toLocaleString()} transactions per month`); if (Number(plan.monthly_price) <= 0) features.push("Basic POS with cash", "Weekly sales reports", "Customer management"); FEATURE_OPTIONS.forEach(([key, label]) => { if (plan.capabilities[key]) features.push(label); }); return features; };  const openCreate = () => { setDraft(empty); setIsNew(true); setEditing({ code: "" }); };  const openEdit = (plan) => { setDraft({ code: plan.code, name: plan.name || "", description: plan.description || "", monthly_price: Number(plan.monthly_price || 0), max_stores: plan.max_stores, max_members: plan.max_members, transaction_limit: plan.transaction_limit, capabilities: { ...(plan.capabilities || {}) }, is_active: plan.is_active }); setIsNew(false); setEditing({ code: plan.code }); };  const setCap = (key, value) => setDraft((current) => ({ ...current, capabilities: { ...current.capabilities, [key]: value } }));  const save = async () => { if (!draft.name.trim()) return; setSaving(true); try { const body = { name: draft.name.trim(), description: draft.description.trim() || null, monthly_price: Number(draft.monthly_price) || 0, max_stores: Number(draft.max_stores) || 1, max_members: Number(draft.max_members) || 1, transaction_limit: Number(draft.transaction_limit) || 0, capabilities: draft.capabilities, is_active: draft.is_active }; await onSave(isNew ? { create: true, ...body } : { code: draft.code, ...body }); setEditing(null); } catch (requestError) { /* surface via parent */ } finally { setSaving(false); } };  const bullets = marketingBullets(draft);
  const BILLING_CYCLES = [
    { key: "monthly", label: "Monthly", multiplier: 1, discount: 0, badge: null, billedLabel: "billed monthly" },
    { key: "semi_annual", label: "Semi-annual", multiplier: 6, discount: 0.15, badge: "Save 15%", billedLabel: "billed every 6 months" },
    { key: "annual", label: "Annual", multiplier: 12, discount: 0.2, badge: "Save 20%", billedLabel: "billed annually" },
  ];
  const [billingCycle, setBillingCycle] = useState("monthly");
  const cycle = BILLING_CYCLES.find((item) => item.key === billingCycle) || BILLING_CYCLES[0];
  const moneyUsd = (value) => `$${value.toFixed(2)}`;
  const perMonth = (plan) => (Number(plan?.monthly_price) || 0) * (1 - cycle.discount);
  const planPriceText = (plan) => Number(plan?.monthly_price) > 0 ? moneyUsd(perMonth(plan)) : "$0.00";
  const planTotalText = (plan) => Number(plan?.monthly_price) > 0 ? `${moneyUsd(perMonth(plan) * cycle.multiplier)} ${cycle.billedLabel}` : "Free forever";  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Plans & features</h2><p className="mt-1 text-sm text-[#898a95]">Pricing, limits, and included features for every tier.</p></div><Button size="sm" onClick={openCreate}><Plus size={15} /> New plan</Button></div>{loading && <p className="mt-4 text-xs text-[#999aa4]">Refreshing...</p>}<div className="mt-6 flex flex-wrap items-center justify-center gap-3">
  <div className="inline-flex rounded-xl border border-[#e4e4eb] bg-[#f5f5f8] p-1">
    {BILLING_CYCLES.map((item) => (
      <button key={item.key} type="button" onClick={() => setBillingCycle(item.key)} className={`relative rounded-lg px-4 py-2 text-xs font-bold transition ${billingCycle === item.key ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}>
        {item.label}
        {item.badge && <span className={`ml-1.5 text-[9px] ${billingCycle === item.key ? "text-[#c4f27c]" : "text-[#6957f5]"}`}>{item.badge}</span>}
      </button>
    ))}
  </div>
</div>
<div className="mt-7 grid gap-4 lg:grid-cols-3">
  {plans.map((plan) => {
    const enabled = plan.is_active !== false;
    const features = (plan.marketing_features && plan.marketing_features.length) ? plan.marketing_features : marketingBullets(plan);
    const subtitle = plan.description || (Number(plan.transaction_limit || 0) > 0 ? `${Number(plan.transaction_limit).toLocaleString()} transactions / month` : "");
    return (
      <div key={plan.code} className={`flex flex-col rounded-2xl border p-5 ${enabled ? "border-[#e8e8ee] bg-white" : "border-[#e7e0da] bg-[#faf6f2]"}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-extrabold">{plan.name}</p>
              {!enabled && <Badge tone="neutral">archived</Badge>}
            </div>
            <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#a1a2ab]">{plan.code}</p>
            {subtitle && <p className="mt-1.5 text-xs leading-5 text-[#6d6e78]">{subtitle}</p>}
          </div>
          <div className="shrink-0 text-right">
            <p className="text-2xl font-extrabold tracking-[-.05em] text-[#202128]">{planPriceText(plan)}<span className="ml-1 text-[11px] font-medium text-[#92939d]">/mo</span></p>
            <p className="mt-1 text-[10px] text-[#92939d]">{planTotalText(plan)}</p>
          </div>
        </div>
        <div className="my-5 h-px bg-[#eeeeF2]" />
        <div className="flex-1 space-y-2.5">
          {features.map((feature) => (
            <p key={feature} className={`flex items-start gap-2 text-xs ${enabled ? "text-[#6c6d77]" : "text-[#a29b94]"}`}><Check size={13} className="mt-0.5 shrink-0 text-[#65a33c]" />{feature}</p>
          ))}
        </div>
        <div className="mt-6 flex gap-2 border-t border-[#f0f0f3] pt-4">
          <Button variant="outline" size="sm" className="flex-1" onClick={() => openEdit(plan)}><Edit3 size={13} /> Edit</Button>
          <Button variant={enabled ? "ghost" : "soft"} size="sm" className="flex-1" onClick={() => onSave({ code: plan.code, is_active: !enabled })}>{enabled ? "Archive" : "Restore"}</Button>
        </div>
      </div>
    );
  })}
</div><Modal open={Boolean(editing)} title={isNew ? "Create plan" : `Edit ${editing?.code} plan`} description="Set pricing, limits, and capabilities - marketing bullets update automatically." onClose={() => setEditing(null)} width="max-w-[680px]"><div className="space-y-4 p-5"><div className="grid gap-3 sm:grid-cols-[.7fr_1.3fr]">{isNew && <Field label="Code" required placeholder="e.g. enterprise" value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value.toLowerCase().trim() })} />}<Field label="Name" required placeholder="e.g. Enterprise" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></div><div className="grid gap-3 sm:grid-cols-4"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Price / month</span><input type="number" min="0" step="0.01" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" value={draft.monthly_price} onChange={(event) => setDraft({ ...draft, monthly_price: Number(event.target.value) })} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Max stores</span><input type="number" min="1" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" value={draft.max_stores} onChange={(event) => setDraft({ ...draft, max_stores: Number(event.target.value) })} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Max members</span><input type="number" min="1" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" value={draft.max_members} onChange={(event) => setDraft({ ...draft, max_members: Number(event.target.value) })} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Tx limit / mo</span><input type="number" min="0" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" value={draft.transaction_limit} onChange={(event) => setDraft({ ...draft, transaction_limit: Number(event.target.value) })} /></label></div><Field label="Tagline (optional)" placeholder="A short one-liner shown on pricing." value={draft.description || ""} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /><div><p className="mb-2 text-xs font-semibold text-[#4f5059]">Included capabilities</p><div className="grid gap-1.5 sm:grid-cols-2">{FEATURE_OPTIONS.map(([key, label]) => { const on = Boolean(draft.capabilities[key]); return <button key={key} type="button" onClick={() => setCap(key, !on)} className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-left text-xs transition ${on ? "border-[#bcdc9f] bg-[#f4fbee]" : "border-[#e4e4eb] bg-[#fafafd] text-[#8b8c96]"}`}><span className="font-medium">{label}</span>{on ? <ToggleRight size={18} className="text-[#68a83d]" /> : <ToggleLeft size={18} className="text-[#b9bac2]" />}</button>; })}</div></div><div><p className="mb-2 text-xs font-semibold text-[#4f5059]">Marketing bullets (auto-generated)</p><div className="rounded-xl border border-[#e9e9ef] bg-[#fafafd] px-3.5 py-3">{bullets.map((feature) => <p key={feature} className="flex items-center gap-2 py-0.5 text-xs text-[#4f5059]"><Check size={13} className="text-[#68a83d]" />{feature}</p>)}{bullets.length === 0 && <p className="text-[11px] text-[#a3a4ac]">Nothing to advertise yet.</p>}</div></div><div className="flex items-center gap-2"><input id="plan-active" type="checkbox" checked={draft.is_active !== false} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })} className="h-4 w-4 accent-[#6957f5]" /><label htmlFor="plan-active" className="text-xs font-semibold text-[#4f5059]">Plan is active & available for signup</label></div><div className="flex justify-end gap-2 border-t border-[#eeeeF2] pt-4"><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button onClick={save} disabled={saving || !draft.name.trim()}><Check size={15} /> {saving ? "Saving..." : isNew ? "Create plan" : "Save changes"}</Button></div></div></Modal></div>;}
const MAILING_ALLOWED_TAGS = new Set(["P", "BR", "STRONG", "B", "EM", "I", "U", "A", "UL", "OL", "LI", "H2", "H3", "BLOCKQUOTE", "IMG"]);
const MAILING_ALLOWED_ATTRS = { A: new Set(["href"]), IMG: new Set(["src", "alt"]) };

function escapeHtmlText(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function plainTextToHtml(text) {
  return text
    .split(/\n{2,}/)
    .map((block) => `<p>${escapeHtmlText(block).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

/* Roughly what a text-only mail client shows, for the pre-send preview. */
function htmlToPlainText(html) {
  const doc = new DOMParser().parseFromString(html || "", "text/html");
  doc.querySelectorAll("br").forEach((node) => node.replaceWith("\n"));
  doc.querySelectorAll("p, li, h2, h3, blockquote").forEach((node) => node.append("\n"));
  return (doc.body.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}

/* Keep pasted content to the small, email-safe tag set the sender expects. */
function sanitizeRichHtml(html) {
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  const root = doc.body.firstElementChild;
  if (!root) return "";
  const clean = (node) => {
    [...node.childNodes].forEach((child) => {
      if (child.nodeType === 3) return;
      if (child.nodeType !== 1) { node.removeChild(child); return; }
      clean(child);
      if (!MAILING_ALLOWED_TAGS.has(child.tagName)) {
        while (child.firstChild) node.insertBefore(child.firstChild, child);
        node.removeChild(child);
        return;
      }
      [...child.attributes].forEach((attribute) => {
        const allowed = MAILING_ALLOWED_ATTRS[child.tagName];
        if (!allowed || !allowed.has(attribute.name)) child.removeAttribute(attribute.name);
      });
      if (child.tagName === "A") {
        const href = child.getAttribute("href") || "";
        if (!/^(https?:|mailto:)/i.test(href)) child.removeAttribute("href");
      }
      if (child.tagName === "IMG") {
        const src = child.getAttribute("src") || "";
        if (!/^https?:\/\//i.test(src)) {
          node.removeChild(child);
          return;
        }
        if (!child.getAttribute("alt")) child.setAttribute("alt", "");
        child.setAttribute("style", "max-width:100%;height:auto;border:0");
      }
    });
  };
  clean(root);
  return root.innerHTML;
}

const EDITOR_BUTTON = "flex h-8 min-w-[2rem] items-center justify-center rounded-lg px-2 text-xs font-bold text-[#5b5c66] transition hover:bg-[#eeeef5] hover:text-[#272831]";

function RichTextEditor({ value, onChange, apiRef, onUploadImage }) {
  const ref = useRef(null);
  const lastValue = useRef(null);
  const [focused, setFocused] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    const next = value || "";
    if (next !== lastValue.current) {
      ref.current.innerHTML = next;
      lastValue.current = next;
    }
  }, [value]);

  const emit = () => {
    if (!ref.current) return;
    const html = ref.current.innerHTML;
    lastValue.current = html;
    onChange(html);
  };

  const insertToken = (text) => {
    ref.current?.focus();
    document.execCommand("insertText", false, text);
    emit();
  };

  useEffect(() => {
    if (apiRef) apiRef.current = { insertToken };
  });

  const pickImage = () => fileRef.current?.click();

  const handleImageChosen = async (event) => {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";
    if (!file || !onUploadImage) return;
    setUploading(true);
    try {
      const result = await onUploadImage(file);
      if (result && result.url) {
        ref.current?.focus();
        document.execCommand("insertHTML", false, `<img src="${result.url}" alt="" style="max-width:100%;height:auto;border:0">`);
        emit();
      }
    } finally {
      setUploading(false);
    }
  };

  const exec = (command, argument = null) => {
    ref.current?.focus();
    document.execCommand(command, false, argument);
    emit();
  };

  const setBlock = (tag) => {
    ref.current?.focus();
    document.execCommand("formatBlock", false, tag);
    emit();
  };

  const addLink = () => {
    const url = window.prompt("Link URL", "https://");
    if (!url) return;
    exec("createLink", url);
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const clipboard = event.clipboardData;
    const pastedHtml = clipboard.getData("text/html");
    const pastedText = clipboard.getData("text/plain");
    const safe = pastedHtml ? sanitizeRichHtml(pastedHtml) : plainTextToHtml(pastedText);
    document.execCommand("insertHTML", false, safe);
    emit();
  };

  const tools = [
    { label: "Bold", text: <strong>B</strong>, run: () => exec("bold") },
    { label: "Italic", text: <em>I</em>, run: () => exec("italic") },
    { label: "Underline", text: <span className="underline">U</span>, run: () => exec("underline") },
    { divider: true },
    { label: "Heading", text: "H2", run: () => setBlock("<h2>") },
    { label: "Subheading", text: "H3", run: () => setBlock("<h3>") },
    { label: "Paragraph", text: "Text", run: () => setBlock("<p>") },
    { divider: true },
    { label: "Bulleted list", text: "\u2022 List", run: () => exec("insertUnorderedList") },
    { label: "Numbered list", text: "1. List", run: () => exec("insertOrderedList") },
    { divider: true },
    { label: "Insert image", text: uploading ? "..." : "Image", run: pickImage },
    { label: "Add link", text: "Link", run: addLink },
    { label: "Clear formatting", text: "Clear", run: () => exec("removeFormat") },
  ];

  return (
    <div className={`overflow-hidden rounded-xl border bg-white transition ${focused ? "border-[#887bf3]" : "border-[#dfdfe8]"}`}>
      <div className="flex flex-wrap items-center gap-0.5 border-b border-[#eeeef2] bg-[#fafafd] px-1.5 py-1.5">
        {tools.map((tool, index) =>
          tool.divider ? (
            <span key={`divider-${index}`} className="mx-1 h-5 w-px bg-[#e4e4eb]" />
          ) : (
            <button key={tool.label} type="button" title={tool.label} aria-label={tool.label} className={EDITOR_BUTTON} onMouseDown={(event) => event.preventDefault()} onClick={tool.run}>
              {tool.text}
            </button>
          )
        )}
      </div>
      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" onChange={handleImageChosen} />
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        data-placeholder="Write your email here..."
        onInput={emit}
        onFocus={() => setFocused(true)}
        onBlur={() => { setFocused(false); emit(); }}
        onPaste={handlePaste}
        className="mailing-editor max-h-[420px] min-h-[220px] overflow-auto px-3.5 py-3 text-sm leading-6 text-[#2b2c33] outline-none"
      />
    </div>
  );
}

function useRunner() {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const run = useCallback(async (label, action) => {
    setBusy(label);
    setError("");
    try {
      return await action();
    } catch (requestError) {
      setError(requestError.message || "Something went wrong");
      return null;
    } finally {
      setBusy("");
    }
  }, []);
  return { busy, error, run, setError };
}

function SettingsCard({ title, description, badge, children }) {
  return (
    <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-extrabold">{title}</p>
          <p className="mt-0.5 text-xs text-[#898a95]">{description}</p>
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

const SETTINGS_ERROR = "mt-3 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]";
const SETTINGS_LABEL = "mb-1.5 block text-xs font-semibold text-[#4f5059]";
const SETTINGS_INPUT = "h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]";

function MailSettingsPanel({ token, user, notify }) {
  const { busy, error, run } = useRunner();
  const canManage = user?.platform_role === "super_admin";
  const [mail, setMail] = useState(null);
  const [draft, setDraft] = useState({ provider: "smtp", resend_api_key: "", resend_webhook_secret: "", from_address: "", from_name: "", reply_to: "" });
  const [testTo, setTestTo] = useState("");

  const applyRow = useCallback((row) => {
    setMail(row);
    setDraft((current) => ({ provider: row.provider || "smtp", from_address: row.from_address || "", from_name: row.from_name || "", reply_to: row.reply_to || "", resend_api_key: current.resend_api_key, resend_webhook_secret: current.resend_webhook_secret }));
  }, []);

  useEffect(() => {
    let active = true;
    run("load", () => api.adminMailSettings(token)).then((row) => { if (active && row) applyRow(row); });
    return () => { active = false; };
  }, [token, run, applyRow]);

  const save = async () => {
    const body = { provider: draft.provider };
    if (draft.from_address) body.from_address = draft.from_address;
    if (draft.from_name !== "") body.from_name = draft.from_name;
    if (draft.reply_to !== "") body.reply_to = draft.reply_to;
    if (draft.resend_api_key) body.resend_api_key = draft.resend_api_key;
    if (draft.resend_webhook_secret) body.resend_webhook_secret = draft.resend_webhook_secret;
    const saved = await run("save", () => api.adminUpdateMailSettings(token, body));
    if (saved) { applyRow(saved); notify("Sending settings saved"); }
  };

  const reveal = async (field) => {
    const result = await run(`reveal-${field}`, () => api.adminRevealMailSecret(token, field));
    if (result && result.value) setDraft((current) => ({ ...current, [field === "webhook_secret" ? "resend_webhook_secret" : "resend_api_key"]: result.value }));
  };

  const sendTest = async () => {
    if (!testTo.trim()) return;
    const result = await run("test", () => api.adminTestMail(token, testTo.trim()));
    if (result) notify(result.sent ? `Test email sent via ${result.provider}` : `Test failed (${result.provider}): ${result.detail || "unknown error"}`);
  };

  return (
    <SettingsCard
      title="Email sending"
      description="How Chmaba delivers mail. Resend uses its API; SMTP uses the server relay."
      badge={mail ? <Badge tone={mail.provider === "resend" ? "violet" : "neutral"}>{mail.provider === "resend" ? "Resend" : "SMTP"}</Badge> : null}
    >
      {error && <p className={SETTINGS_ERROR}>{error}</p>}
      {!mail ? (
        <p className="mt-4 text-xs text-[#999aa4]">Loading...</p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block">
              <span className={SETTINGS_LABEL}>Provider</span>
              <Dropdown value={draft.provider} onChange={(value) => setDraft({ ...draft, provider: value })} options={(mail.providers || []).map((provider) => ({ value: provider.code, label: provider.label }))} placeholder="Choose a provider" />
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>From address</span>
              <input value={draft.from_address} onChange={(event) => setDraft({ ...draft, from_address: event.target.value })} placeholder="no-reply@chmaba.com" className={SETTINGS_INPUT} />
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>From name</span>
              <input value={draft.from_name} onChange={(event) => setDraft({ ...draft, from_name: event.target.value })} placeholder="Chmaba" className={SETTINGS_INPUT} />
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>Reply-to</span>
              <input value={draft.reply_to} onChange={(event) => setDraft({ ...draft, reply_to: event.target.value })} placeholder="support@chmaba.com" className={SETTINGS_INPUT} />
            </label>
          </div>
          {draft.provider === "resend" && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className={SETTINGS_LABEL}>Resend API key</span>
                <div className="flex gap-2">
                  <input value={draft.resend_api_key} onChange={(event) => setDraft({ ...draft, resend_api_key: event.target.value })} placeholder={mail.api_key_preview || "re_..."} className={SETTINGS_INPUT} />
                  {mail.api_key_set && <Button variant="outline" size="sm" disabled={busy === "reveal-api_key" || !canManage} onClick={() => reveal("api_key")}><Eye size={14} /> Reveal</Button>}
                </div>
                <span className="mt-1.5 block text-[11px] text-[#92939d]">{mail.api_key_set ? "Stored. Paste a new key to replace it." : "No key stored yet."}</span>
              </label>
              <label className="block">
                <span className={SETTINGS_LABEL}>Resend webhook secret</span>
                <div className="flex gap-2">
                  <input value={draft.resend_webhook_secret} onChange={(event) => setDraft({ ...draft, resend_webhook_secret: event.target.value })} placeholder={mail.webhook_secret_preview || "whsec_..."} className={SETTINGS_INPUT} />
                  {mail.webhook_secret_set && <Button variant="outline" size="sm" disabled={busy === "reveal-webhook_secret" || !canManage} onClick={() => reveal("webhook_secret")}><Eye size={14} /> Reveal</Button>}
                </div>
                <span className="mt-1.5 block text-[11px] text-[#92939d]">Bounces and spam complaints suppress the address automatically.</span>
              </label>
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button size="sm" disabled={busy === "save" || !canManage} onClick={save}>Save</Button>
            <span className="text-[11px] text-[#92939d]">
              {draft.provider === "resend" ? "Delivered through api.resend.com" : `Relay ${mail.smtp_host}:${mail.smtp_port}${mail.smtp_use_ssl ? " (TLS)" : mail.smtp_use_tls ? " (STARTTLS)" : ""}`}
            </span>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-[#f0f0f3] pt-4">
            <label className="block min-w-[240px] flex-1">
              <span className={SETTINGS_LABEL}>Send a test email to</span>
              <input value={testTo} onChange={(event) => setTestTo(event.target.value)} placeholder="you@example.com" className={SETTINGS_INPUT} />
            </label>
            <Button variant="outline" size="sm" disabled={busy === "test" || !canManage} onClick={sendTest}>{busy === "test" ? "Sending..." : "Send test"}</Button>
          </div>
          {!canManage && <p className="mt-2 text-[11px] text-[#ad7d1c]">Changing sending settings is limited to super admins.</p>}
        </>
      )}
    </SettingsCard>
  );
}

function AiWritingPanel({ token, user, notify }) {
  const { busy, error, run } = useRunner();
  const canManage = user?.platform_role === "super_admin";
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({ provider: "", model: "", base_url: "", api_key: "" });

  const applyRow = useCallback((row) => {
    setSettings(row);
    setDraft((current) => ({ provider: row.provider || "", model: row.model || "", base_url: row.base_url || "", api_key: current.api_key }));
  }, []);

  useEffect(() => {
    let active = true;
    run("load", () => api.adminAiSettings(token)).then((row) => { if (active && row) applyRow(row); });
    return () => { active = false; };
  }, [token, run, applyRow]);

  const save = async () => {
    const body = {};
    if (draft.provider) body.provider = draft.provider;
    if (draft.model) body.model = draft.model;
    if (draft.base_url) body.base_url = draft.base_url;
    if (draft.api_key) body.api_key = draft.api_key;
    const saved = await run("save", () => api.adminUpdateAiSettings(token, body));
    if (saved) { applyRow(saved); notify("AI settings saved"); }
  };

  const reveal = async () => {
    const result = await run("reveal", () => api.adminRevealAiSecret(token));
    if (result && result.value) setDraft((current) => ({ ...current, api_key: result.value }));
  };

  const testConnection = async () => {
    const result = await run("test", () => api.adminTestAi(token));
    if (result) notify(result.ok ? `AI OK: ${result.provider}${result.model ? ` / ${result.model}` : ""}` : `AI test failed: ${result.detail || "unknown error"}`);
  };

  return (
    <SettingsCard
      title="AI writing"
      description="Powers the 'Draft with AI' button in Mailing. The key is stored server-side and only used to draft copy."
      badge={settings?.api_key_set ? <Badge tone="green">configured</Badge> : <Badge tone="yellow">not configured</Badge>}
    >
      {error && <p className={SETTINGS_ERROR}>{error}</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block">
          <span className={SETTINGS_LABEL}>Provider</span>
          <Dropdown value={draft.provider} onChange={(value) => setDraft({ ...draft, provider: value })} options={(settings?.providers || []).map((provider) => ({ value: provider.code, label: provider.label }))} placeholder="Choose a provider" />
        </label>
        <label className="block">
          <span className={SETTINGS_LABEL}>Model</span>
          <input value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} placeholder="Provider default" className={SETTINGS_INPUT} />
        </label>
        <label className="block lg:col-span-2">
          <span className={SETTINGS_LABEL}>API key</span>
          <div className="flex gap-2">
            <input value={draft.api_key} onChange={(event) => setDraft({ ...draft, api_key: event.target.value })} placeholder={settings?.api_key_preview || "Paste the provider key"} className={SETTINGS_INPUT} />
            {settings?.api_key_set && <Button variant="outline" size="sm" disabled={busy === "reveal" || !canManage} onClick={reveal}><Eye size={14} /> Reveal</Button>}
          </div>
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={busy === "save" || !canManage} onClick={save}>Save</Button>
        <Button variant="outline" size="sm" disabled={busy === "test"} onClick={testConnection}>{busy === "test" ? "Testing..." : "Test AI"}</Button>
        <span className="text-[11px] text-[#92939d]">Supports ChatGPT (OpenAI), DeepSeek and Claude (Anthropic).</span>
      </div>
      {!canManage && <p className="mt-2 text-[11px] text-[#ad7d1c]">Changing AI settings is limited to super admins.</p>}
    </SettingsCard>
  );
}

function PaymentSettingsPanel({ token, notify }) {
  const { busy, error, run } = useRunner();
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({ mode: "mock", api_url: "", api_key: "", webhook_secret: "", platform_store_id: "" });

  const applyRow = useCallback((row) => {
    setSettings(row);
    setDraft((current) => ({ mode: row.mode || "mock", api_url: row.api_url || "", platform_store_id: row.platform_store_id || "", api_key: current.api_key, webhook_secret: current.webhook_secret }));
  }, []);

  useEffect(() => {
    let active = true;
    run("load", () => api.chamabapaySettings(token)).then((row) => { if (active && row) applyRow(row); });
    return () => { active = false; };
  }, [token, run, applyRow]);

  const save = async () => {
    const body = { mode: draft.mode };
    if (draft.api_url) body.api_url = draft.api_url;
    if (draft.platform_store_id !== "") body.platform_store_id = draft.platform_store_id;
    if (draft.api_key) body.api_key = draft.api_key;
    if (draft.webhook_secret) body.webhook_secret = draft.webhook_secret;
    const saved = await run("save", () => api.updateChamabapaySettings(token, body));
    if (saved) { applyRow(saved); notify("Payment settings saved"); }
  };

  const reveal = async (field) => {
    const result = await run(`reveal-${field}`, () => api.revealChamabapaySecret(token, field));
    if (result && result.value) setDraft((current) => ({ ...current, [field]: result.value }));
  };

  return (
    <SettingsCard
      title="ChmabaPay"
      description="Payment gateway used for plan fees and KHQR checkout."
      badge={settings ? <Badge tone={settings.mode === "live" ? "green" : "yellow"}>{settings.mode === "live" ? "live" : "mock"}</Badge> : null}
    >
      {error && <p className={SETTINGS_ERROR}>{error}</p>}
      {!settings ? (
        <p className="mt-4 text-xs text-[#999aa4]">Loading...</p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="block">
              <span className={SETTINGS_LABEL}>Mode</span>
              <Dropdown value={draft.mode} onChange={(value) => setDraft({ ...draft, mode: value })} options={[{ value: "mock", label: "Mock (local)" }, { value: "live", label: "Live" }]} placeholder="Choose a mode" />
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>API URL</span>
              <input value={draft.api_url} onChange={(event) => setDraft({ ...draft, api_url: event.target.value })} placeholder="https://pay.chmaba.com" className={SETTINGS_INPUT} />
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>Platform store ID</span>
              <input value={draft.platform_store_id} onChange={(event) => setDraft({ ...draft, platform_store_id: event.target.value })} placeholder="Chmaba's own store" className={SETTINGS_INPUT} />
            </label>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className={SETTINGS_LABEL}>API key</span>
              <div className="flex gap-2">
                <input value={draft.api_key} onChange={(event) => setDraft({ ...draft, api_key: event.target.value })} placeholder={settings.api_key_preview || "ck_live_..."} className={SETTINGS_INPUT} />
                {settings.api_key_set && <Button variant="outline" size="sm" disabled={busy === "reveal-api_key"} onClick={() => reveal("api_key")}><Eye size={14} /> Reveal</Button>}
              </div>
            </label>
            <label className="block">
              <span className={SETTINGS_LABEL}>Webhook secret</span>
              <div className="flex gap-2">
                <input value={draft.webhook_secret} onChange={(event) => setDraft({ ...draft, webhook_secret: event.target.value })} placeholder={settings.webhook_secret_preview || "whsec_..."} className={SETTINGS_INPUT} />
                {settings.webhook_secret_set && <Button variant="outline" size="sm" disabled={busy === "reveal-webhook_secret"} onClick={() => reveal("webhook_secret")}><Eye size={14} /> Reveal</Button>}
              </div>
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button size="sm" disabled={busy === "save"} onClick={save}>Save</Button>
            <span className="text-[11px] text-[#92939d]">Environment: {settings.environment}</span>
          </div>
        </>
      )}
    </SettingsCard>
  );
}

function SessionSettingsPanel({ token, user, notify }) {
  const { busy, error, run } = useRunner();
  const canManage = user?.platform_role === "super_admin";
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({ default_ttl_minutes: "", max_ttl_minutes: "" });

  const applyRow = useCallback((row) => {
    setSettings(row);
    setDraft({ default_ttl_minutes: String(row.default_ttl_minutes), max_ttl_minutes: String(row.max_ttl_minutes) });
  }, []);

  useEffect(() => {
    let active = true;
    run("load", () => api.adminSessionSettings(token)).then((row) => { if (active && row) applyRow(row); });
    return () => { active = false; };
  }, [token, run, applyRow]);

  const save = async () => {
    const body = {};
    if (draft.default_ttl_minutes !== "") body.default_ttl_minutes = Number(draft.default_ttl_minutes);
    if (draft.max_ttl_minutes !== "") body.max_ttl_minutes = Number(draft.max_ttl_minutes);
    const row = await run("save", () => api.adminUpdateSessionSettings(token, body));
    if (row) { applyRow(row); notify("Session settings saved"); }
  };

  const asHours = (minutes) => Math.round((Number(minutes) || 0) / 60 * 10) / 10;
  const asDays = (minutes) => Math.round((Number(minutes) || 0) / 1440 * 10) / 10;

  return (
    <SettingsCard
      title="Sign-in session length"
      description="Default and maximum length of a normal sign-in. Company owners can set their own value within the maximum."
      badge={settings ? <Badge tone="violet">{asHours(settings.default_ttl_minutes)}h default</Badge> : null}
    >
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className={SETTINGS_LABEL}>Default session length (minutes)</span>
          <input
            type="number"
            min="1"
            max={settings?.absolute_max_ttl_minutes || undefined}
            value={draft.default_ttl_minutes}
            disabled={!canManage || busy !== ""}
            onChange={(event) => setDraft({ ...draft, default_ttl_minutes: event.target.value })}
            className={SETTINGS_INPUT}
          />
          <span className="mt-1 block text-[10px] text-[#92939d]">{asHours(draft.default_ttl_minutes)} hours</span>
        </label>
        <label className="block">
          <span className={SETTINGS_LABEL}>Maximum session length (minutes)</span>
          <input
            type="number"
            min="1"
            max={settings?.absolute_max_ttl_minutes || undefined}
            value={draft.max_ttl_minutes}
            disabled={!canManage || busy !== ""}
            onChange={(event) => setDraft({ ...draft, max_ttl_minutes: event.target.value })}
            className={SETTINGS_INPUT}
          />
          <span className="mt-1 block text-[10px] text-[#92939d]">{asDays(draft.max_ttl_minutes)} days · platform ceiling {asDays(settings?.absolute_max_ttl_minutes)} days</span>
        </label>
      </div>
      {error && <p className={SETTINGS_ERROR}>{error}</p>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-[11px] text-[#92939d]">A normal sign-in lasts the default; "Remember me" stays longer.</p>
        <Button disabled={!canManage || busy !== "" || !settings} onClick={save}>
          {busy === "save" ? "Saving..." : "Save session settings"}
        </Button>
      </div>
      {!canManage && <p className="mt-2 text-[11px] text-[#ad7d1c]">Changing session settings is limited to super admins.</p>}
    </SettingsCard>
  );
}

function AdminSettings({ token, user, notify }) {
  return (
    <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Settings</h2>
        <p className="mt-1 text-sm text-[#898a95]">Platform integrations and API keys. Secrets are stored server-side and shown masked.</p>
      </div>
      <div className="mt-6 space-y-5">
        <MailSettingsPanel token={token} user={user} notify={notify} />
        <AiWritingPanel token={token} user={user} notify={notify} />
        <SessionSettingsPanel token={token} user={user} notify={notify} />
        <PaymentSettingsPanel token={token} notify={notify} />
      </div>
    </div>
  );
}

const MAILING_STATUS_TONE = { sent: "green", queued: "yellow", failed: "red", skipped: "neutral" };

function AdminMailing({ token, user, notify, onNavigate }) {
  const [instruction, setInstruction] = useState("");
  const [audience, setAudience] = useState("no_workspace");
  const [minAgeHours, setMinAgeHours] = useState("24");
  const [maxAgeDays, setMaxAgeDays] = useState("");
  const [preview, setPreview] = useState({ segments: [], recipients: [] });
  const [templates, setTemplates] = useState([]);
  const [sends, setSends] = useState([]);
  const [suppressions, setSuppressions] = useState([]);
  const [compose, setCompose] = useState({ subject: "", body_html: "", template_id: null, name: "" });
  const [tab, setTab] = useState("compose");
  const [htmlMode, setHtmlMode] = useState(false);
  const [previewMode, setPreviewMode] = useState("html");
  const [mergeTokens, setMergeTokens] = useState([]);
  const [drip, setDrip] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const editorApi = useRef(null);
  const dripEditors = useRef({});
  const canSend = user?.platform_role === "super_admin";

  const loadAudience = useCallback(async () => {
    try {
      const params = { audience };
      if (minAgeHours !== "") params.min_age_hours = minAgeHours;
      if (maxAgeDays !== "") params.max_age_days = maxAgeDays;
      setPreview(await api.adminMailingAudience(token, params));
    } catch (requestError) {
      setError(requestError.message || "Could not load the audience");
    }
  }, [token, audience, minAgeHours, maxAgeDays]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [templateRows, sendRows, suppressionRows, tokenRows, dripRow] = await Promise.all([
          api.adminMailingTemplates(token),
          api.adminMailingSends(token, 25),
          api.adminMailingSuppressions(token, 100),
          api.adminMailingTokens(token),
          api.adminMailingDrip(token),
        ]);
        if (!active) return;
        setTemplates(templateRows);
        setSends(sendRows);
        setSuppressions(suppressionRows);
        setMergeTokens(tokenRows);
        setDrip(dripRow);
      } catch (requestError) {
        if (active) setError(requestError.message || "Could not load mailing data");
      }
    })();
    return () => { active = false; };
  }, [token]);

  useEffect(() => { loadAudience(); }, [loadAudience]);

  const run = async (label, action, successMessage) => {
    setBusy(label);
    setError("");
    try {
      const result = await action();
      if (successMessage) notify(successMessage);
      return result;
    } catch (requestError) {
      setError(requestError.message || "Something went wrong");
      return null;
    } finally {
      setBusy("");
    }
  };

  const refreshTemplates = async () => setTemplates(await api.adminMailingTemplates(token));
  const refreshSends = async () => setSends(await api.adminMailingSends(token, 25));
  const refreshSuppressions = async () => setSuppressions(await api.adminMailingSuppressions(token, 100));

  const draftWithAi = async () => {
    if (!instruction.trim()) { setError("Tell the AI what the email should say."); return; }
    const result = await run("draft", () => api.adminMailingDraft(token, { instruction, audience }));
    if (result) setCompose((current) => ({ ...current, subject: result.subject, body_html: result.body_html }));
  };

  const saveTemplate = async () => {
    if (!compose.subject.trim() || !compose.body_html.trim()) { setError("Subject and body are required to save a template."); return; }
    const body = { name: compose.name.trim() || compose.subject.trim().slice(0, 60), subject: compose.subject, body_html: compose.body_html };
    const saved = compose.template_id
      ? await run("template", () => api.adminUpdateMailingTemplate(token, compose.template_id, body), "Template updated")
      : await run("template", () => api.adminCreateMailingTemplate(token, body), "Template saved");
    if (saved) { setCompose((current) => ({ ...current, template_id: saved.id, name: saved.name })); await refreshTemplates(); }
  };

  const deleteTemplate = async (id) => {
    const done = await run("template", () => api.adminDeleteMailingTemplate(token, id), "Template deleted");
    if (done !== null) { setCompose((current) => (current.template_id === id ? { ...current, template_id: null, name: "" } : current)); await refreshTemplates(); }
  };

  const sendMailing = async (testEmail) => {
    if (!compose.subject.trim() || !compose.body_html.trim()) { setError("Subject and body are required."); return; }
    const body = { subject: compose.subject, body_html: compose.body_html, audience, limit: 200 };
    if (compose.template_id) body.template_id = compose.template_id;
    if (minAgeHours !== "") body.min_age_hours = Number(minAgeHours);
    if (maxAgeDays !== "") body.max_age_days = Number(maxAgeDays);
    if (testEmail) body.test_email = testEmail;
    const result = await run("send", () => api.adminSendMailing(token, body));
    if (result) {
      if (testEmail) notify(`Test email ${result.sent ? "sent" : "failed"}`);
      else if (result.queued) notify(`Queued ${result.queued} email${result.queued === 1 ? "" : "s"} - sending now`);
      else notify("Nothing to send for this segment");
      await refreshSends();
      await loadAudience();
    }
  };

  const processQueue = async () => {
    const result = await run("queue", () => api.adminRunMailingQueue(token));
    if (result) {
      notify(`Queue: ${result.sent} sent, ${result.retried} retrying, ${result.failed} failed, ${result.remaining} remaining`);
      await refreshSends();
    }
  };

  const removeSuppression = async (id) => {
    const done = await run("suppress", () => api.adminDeleteMailingSuppression(token, id), "Address can be mailed again");
    if (done !== null) await refreshSuppressions();
  };

  const updateStep = (index, patch) => {
    setDrip((current) => ({ ...current, steps: current.steps.map((step, position) => (position === index ? { ...step, ...patch } : step)) }));
  };
  const updateWindow = (patch) => {
    setDrip((current) => ({ ...current, send_window: { ...(current.send_window || {}), ...patch } }));
  };
  const addStep = () => {
    setDrip((current) => ({
      ...current,
      steps: [
        ...(current.steps || []),
        { id: `step-${Date.now().toString(36)}`, day_offset: (current.steps?.length || 0) * 2 + 1, audience: "no_workspace", enabled: false, subject: "", body_html: "<p>Hi {{name}},</p>" },
      ],
    }));
  };
  const removeStep = (index) => {
    setDrip((current) => ({ ...current, steps: current.steps.filter((_, position) => position !== index) }));
  };
  const saveDrip = async () => {
    const saved = await run(
      "drip",
      () =>
        api.adminUpdateMailingDrip(token, {
          max_age_days: Number(drip.max_age_days) || 30,
          verified_only: Boolean(drip.verified_only),
          max_per_run: Number(drip.max_per_run) || 200,
          send_window: drip.send_window,
          steps: drip.steps,
        }),
      "Drip saved"
    );
    if (saved) setDrip(saved);
  };
  const runDripNow = async () => {
    const result = await run("drip-run", () => api.adminRunMailingDrip(token));
    if (result) {
      notify(`Drip run: ${result.sent} sent, ${result.failed} failed, ${result.skipped} skipped`);
      await refreshSends();
    }
  };

  const insertMergeToken = (token) => {
    if (htmlMode) {
      setCompose((current) => ({ ...current, body_html: `${current.body_html || ""}${token}` }));
      return;
    }
    editorApi.current?.insertToken(token);
  };

  const sampleForToken = (raw) => {
    const key = raw.replace(/[{}\s]/g, "").toLowerCase();
    const match = (mergeTokens || []).find((item) => item.token.replace(/[{}\s]/g, "").toLowerCase() === key);
    return match ? match.sample : raw;
  };
  const renderPreview = (html) => (html || "").replace(/\{\{[^}]*\}\}/g, sampleForToken);

  const preflight = useMemo(() => {
    const subject = (compose.subject || "").trim();
    const html = compose.body_html || "";
    const text = htmlToPlainText(html);
    const known = new Set((mergeTokens || []).map((item) => item.token.replace(/[{}\s]/g, "").toLowerCase()));
    const found = `${subject} ${html}`.match(/\{\{[^}]*\}\}/g) || [];
    const unknown = [...new Set(found.filter((raw) => !known.has(raw.replace(/[{}\s]/g, "").toLowerCase())))];
    const linkCount = (html.match(/<a\b[^>]*href=/gi) || []).length;
    const images = html.match(/<img\b[^>]*>/gi) || [];
    const missingAlt = images.filter((tag) => !/alt\s*=\s*["'][^"']+["']/i.test(tag)).length;
    const words = text.split(/\s+/).filter(Boolean).length;

    const checks = [];
    if (!subject) checks.push({ level: "error", text: "Add a subject line." });
    else if (subject.length > 70) checks.push({ level: "warn", text: `Subject is ${subject.length} characters - inboxes usually truncate around 60-70.` });
    if (!text.trim()) checks.push({ level: "error", text: "The email body is empty." });
    if (unknown.length) checks.push({ level: "warn", text: `Unknown placeholder${unknown.length === 1 ? "" : "s"}: ${unknown.join(", ")}. They are sent literally.` });
    if (!linkCount) checks.push({ level: "warn", text: "No link in the email, so there is no clear next step." });
    if (missingAlt) checks.push({ level: "warn", text: `${missingAlt} image${missingAlt === 1 ? "" : "s"} missing alt text.` });
    if (words > 0 && words < 20) checks.push({ level: "warn", text: "Very short - consider adding one concrete next step." });
    if (checks.length === 0) checks.push({ level: "ok", text: "Looks good - ready to send." });

    return { checks, words, linkCount, readSeconds: Math.max(5, Math.round((words / 200) * 60)) };
  }, [compose.subject, compose.body_html, mergeTokens]);

  const segmentOptions = (preview.segments || []).map((segment) => ({ value: segment.code, label: `${segment.label} (${segment.count})` }));
  const templateOptions = [{ value: "", label: "New draft" }, ...templates.map((template) => ({ value: template.id, label: template.name }))];
  const audienceCount = (preview.segments || []).find((segment) => segment.code === audience)?.count ?? 0;
  const recipients = preview.recipients || [];
  const TABS = [["compose", "Compose"], ["templates", `Templates (${templates.length})`], ["drip", "Automated drip"], ["log", "Delivery log"], ["suppressed", `Unsubscribed (${suppressions.length})`]];

  return (
    <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-2xl font-extrabold tracking-[-.05em]">Mailing</h2>
          <p className="mt-1 text-sm text-[#898a95]">Reach merchants who signed up but have not started selling.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => onNavigate?.("settings")}><Settings2 size={15} /> Settings</Button>
      </div>

      {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}

      <div className="mt-6 flex flex-wrap gap-2">
        {TABS.map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={`h-9 rounded-lg px-3.5 text-xs font-semibold transition ${tab === id ? "bg-[#6957f5] text-white" : "bg-white text-[#5b5c66] hover:bg-[#f2f2f6]"}`}>{label}</button>
        ))}
      </div>

      {tab === "compose" && (
        <div className="mt-5 grid gap-5 lg:grid-cols-[1.45fr_.95fr]">
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-[200px] flex-1">
                <Dropdown value={compose.template_id || ""} onChange={(value) => { const template = templates.find((item) => item.id === value); setCompose((current) => (value && template ? { ...current, template_id: value, name: template.name, subject: template.subject, body_html: template.body_html } : { ...current, template_id: null })); }} options={templateOptions} placeholder="Start a new draft" />
              </div>
              <input value={compose.name} onChange={(event) => setCompose({ ...compose, name: event.target.value })} placeholder="Template name (optional)" className="h-11 min-w-[180px] flex-1 rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
              <Button variant="outline" size="sm" disabled={busy === "template"} onClick={saveTemplate}><Plus size={14} /> Save</Button>
              {compose.template_id && <Button variant="danger" size="sm" disabled={busy === "template"} onClick={() => deleteTemplate(compose.template_id)}><Trash2 size={14} /></Button>}
            </div>

            <label className="mt-4 block">
              <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Subject</span>
              <input value={compose.subject} onChange={(event) => setCompose({ ...compose, subject: event.target.value })} placeholder="e.g. Your Chmaba store is ready when you are" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
            </label>

            <div className="mt-4 rounded-xl border border-[#e6e2ff] bg-[#f7f5ff] p-3">
              <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-[#6555df]"><Sparkles size={13} /> Draft with AI</div>
              <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={2} placeholder="e.g. Warm reminder to finish setup, mention the free plan and one-click help" className="mt-2 w-full resize-y rounded-lg border border-[#ded9f7] bg-white px-3 py-2 text-xs outline-none focus:border-[#887bf3]" />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button size="sm" disabled={busy === "draft"} onClick={draftWithAi}>{busy === "draft" ? "Drafting..." : "Draft email"}</Button>
                <span className="text-[11px] text-[#898a95]">Fills the subject and body below - review before sending.</span>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-semibold text-[#4f5059]">Body</span>
                <button type="button" onClick={() => setHtmlMode((mode) => !mode)} className="text-[11px] font-semibold text-[#6957f5] hover:underline">{htmlMode ? "Use visual editor" : "Edit HTML"}</button>
              </div>
              <div className="mb-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-[#898a95]">Insert:</span>
                {(mergeTokens || []).map((item) => (
                  <button key={item.token} type="button" title={`${item.label} - e.g. ${item.sample}`} onMouseDown={(event) => event.preventDefault()} onClick={() => insertMergeToken(item.token)} className="rounded-lg border border-[#e4e4eb] bg-white px-2 py-1 text-[11px] font-semibold text-[#5b5c66] transition hover:border-[#887bf3] hover:text-[#4a3bd8]">{item.label}</button>
                ))}
                <span className="text-[11px] text-[#92939d]">Filled in for each recipient when you send.</span>
              </div>
              {htmlMode ? (
                <textarea value={compose.body_html} onChange={(event) => setCompose({ ...compose, body_html: event.target.value })} rows={12} placeholder="<p>Hi {{name}},</p>" className="w-full resize-y rounded-xl border border-[#dfdfe8] bg-white px-3.5 py-2.5 font-mono text-xs outline-none focus:border-[#887bf3]" />
              ) : (
                <RichTextEditor value={compose.body_html} onChange={(html) => setCompose((current) => ({ ...current, body_html: html }))} apiRef={editorApi} onUploadImage={(file) => run("image", () => api.adminUploadMailingImage(token, file), "Image added")} />
              )}
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Preview</p>
                <div className="inline-flex rounded-lg border border-[#e4e4eb] bg-[#f5f5f8] p-0.5">
                  {[["html", "Inbox"], ["text", "Plain text"]].map(([id, label]) => (
                    <button key={id} type="button" onClick={() => setPreviewMode(id)} className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition ${previewMode === id ? "bg-white text-[#202128] shadow-sm" : "text-[#747580]"}`}>{label}</button>
                  ))}
                </div>
              </div>
              <p className="mt-0.5 text-[11px] text-[#898a95]">Sample values shown for tokens; each recipient sees their own.</p>
              {previewMode === "html" ? (
                <div className="mt-2 max-h-[260px] overflow-auto rounded-xl border border-[#e9e9ef] bg-[#fcfcfd] p-4 text-sm text-[#2b2c33]" dangerouslySetInnerHTML={{ __html: renderPreview(compose.body_html) || "<p style=\"color:#92939d\">Nothing to preview yet.</p>" }} />
              ) : (
                <pre className="mt-2 max-h-[260px] overflow-auto whitespace-pre-wrap rounded-xl border border-[#e9e9ef] bg-[#fcfcfd] p-4 font-sans text-sm text-[#2b2c33]">{htmlToPlainText(renderPreview(compose.body_html)) || "Nothing to preview yet."}</pre>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm font-extrabold">Audience</p>
                <IconButton label="Refresh audience" onClick={loadAudience}><RefreshCw size={15} /></IconButton>
              </div>
              <label className="mt-3 block">
                <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Segment</span>
                <Dropdown value={audience} onChange={setAudience} options={segmentOptions} placeholder="Choose a segment" />
              </label>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Min age (hours)</span>
                  <input type="number" min="0" value={minAgeHours} onChange={(event) => setMinAgeHours(event.target.value)} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Max age (days)</span>
                  <input type="number" min="0" value={maxAgeDays} onChange={(event) => setMaxAgeDays(event.target.value)} placeholder="Any" className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
                </label>
              </div>
              <p className="mt-3 text-xs text-[#4f5059]"><strong>{audienceCount}</strong> matching account{audienceCount === 1 ? "" : "s"}</p>
              <div className="mt-2 max-h-[150px] space-y-1 overflow-auto">
                {recipients.slice(0, 40).map((recipient) => (
                  <div key={recipient.id} className="flex items-center justify-between gap-2 rounded-lg bg-[#fafafd] px-2.5 py-1.5 text-[11px]">
                    <span className="truncate text-[#4f5059]">{recipient.email}</span>
                    {!recipient.is_email_verified && <Badge tone="yellow">unverified</Badge>}
                  </div>
                ))}
                {recipients.length === 0 && <p className="py-4 text-center text-[11px] text-[#999aa4]">No accounts match this segment.</p>}
              </div>
            </div>

            <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
              <p className="text-sm font-extrabold">Checks</p>
              <p className="mt-1 text-xs text-[#898a95]">A quick sanity pass before you send.</p>
              <ul className="mt-3 space-y-1.5">
                {preflight.checks.map((check) => (
                  <li key={check.text} className="flex items-start gap-2 text-xs">
                    <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${check.level === "ok" ? "bg-[#77bb4b]" : check.level === "error" ? "bg-[#dc6b60]" : "bg-[#dca93c]"}`} />
                    <span className="text-[#4f5059]">{check.text}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[11px] text-[#92939d]">{preflight.words} words · ~{preflight.readSeconds}s read · {preflight.linkCount} link{preflight.linkCount === 1 ? "" : "s"}</p>
            </div>

            <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
              <p className="text-sm font-extrabold">Send</p>
              <p className="mt-1 text-xs text-[#898a95]">Test to yourself first, then send to the segment. Unsubscribed addresses are always skipped.</p>
              {!canSend && <p className="mt-3 rounded-xl border border-[#ffe6a8] bg-[#fffaf0] px-3 py-2 text-[11px] text-[#ad7d1c]">Sending is limited to super admins.</p>}
              <div className="mt-4 flex flex-col gap-2">
                <Button variant="outline" size="sm" disabled={busy === "send" || !canSend} onClick={() => sendMailing(user?.email)}>Send test to myself</Button>
                <Button disabled={busy === "send" || !canSend || audienceCount === 0} onClick={() => sendMailing(null)}><Mail size={15} /> Send to {audienceCount} account{audienceCount === 1 ? "" : "s"}</Button>
                <Button variant="ghost" size="sm" disabled={busy === "queue" || !canSend} onClick={processQueue}>{busy === "queue" ? "Processing..." : "Process queue now"}</Button>
              </div>
              <p className="mt-3 text-[11px] leading-4 text-[#92939d]">Sends are queued (up to 200 per action) and go out within a minute; failures retry with backoff.</p>
            </div>
          </div>
        </div>
      )}

      {tab === "templates" && (
        <div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-extrabold">Saved templates</p>
            <Button variant="outline" size="sm" onClick={() => { setCompose({ subject: "", body_html: "", template_id: null, name: "" }); setTab("compose"); }}><Plus size={14} /> New draft</Button>
          </div>
          <div className="mt-4 space-y-2">
            {templates.map((template) => (
              <div key={template.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-[#3d3e47]">{template.name}</p>
                  <p className="truncate text-[11px] text-[#898a95]">{template.subject}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="xs" onClick={() => { setCompose({ subject: template.subject, body_html: template.body_html, template_id: template.id, name: template.name }); setTab("compose"); }}>Load</Button>
                  <Button variant="danger" size="xs" disabled={busy === "template"} onClick={() => deleteTemplate(template.id)}><Trash2 size={13} /></Button>
                </div>
              </div>
            ))}
            {templates.length === 0 && <p className="py-10 text-center text-xs text-[#999aa4]">No templates saved yet.</p>}
          </div>
        </div>
      )}

      {tab === "drip" && drip && (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-extrabold">Automated drip</p>
                <p className="mt-1 text-xs text-[#898a95]">Follow-ups sent automatically to stalled signups. Each person receives each step at most once.</p>
              </div>
              <div className="flex items-center gap-2">
                {!canSend && <span className="text-[11px] text-[#ad7d1c]">Super admin only</span>}
                <Button variant="outline" size="sm" disabled={busy === "drip-run" || !canSend} onClick={runDripNow}>{busy === "drip-run" ? "Running..." : "Run now"}</Button>
                <Button size="sm" disabled={busy === "drip" || !canSend} onClick={saveDrip}>Save changes</Button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Target signups from the last (days)</span>
                <input type="number" min="1" max="365" value={drip.max_age_days} onChange={(event) => setDrip({ ...drip, max_age_days: Number(event.target.value) })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Send between (hour)</span>
                <div className="flex items-center gap-2">
                  <input type="number" min="0" max="23" value={drip.send_window?.start_hour ?? 8} onChange={(event) => updateWindow({ start_hour: Number(event.target.value) })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
                  <span className="text-xs text-[#898a95]">to</span>
                  <input type="number" min="1" max="24" value={drip.send_window?.end_hour ?? 20} onChange={(event) => updateWindow({ end_hour: Number(event.target.value) })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
                </div>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Max sent per run</span>
                <input type="number" min="1" max="500" value={drip.max_per_run ?? 200} onChange={(event) => setDrip({ ...drip, max_per_run: Number(event.target.value) })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Timezone</span>
                <input value={drip.send_window?.timezone || ""} onChange={(event) => updateWindow({ timezone: event.target.value })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-5">
              <label className="flex items-center gap-2 text-xs font-semibold text-[#4f5059]">
                <input type="checkbox" checked={Boolean(drip.send_window?.weekdays_only)} onChange={(event) => updateWindow({ weekdays_only: event.target.checked })} />
                Weekdays only
              </label>
              <label className="flex items-center gap-2 text-xs font-semibold text-[#4f5059]">
                <input type="checkbox" checked={Boolean(drip.verified_only)} onChange={(event) => setDrip({ ...drip, verified_only: event.target.checked })} />
                Confirmed emails only
              </label>
            </div>
            <p className="mt-2 text-[11px] text-[#92939d]">Schedule it with cron: <code className="rounded bg-[#f5f5f8] px-1.5 py-0.5">python chmabapos_api/scripts/run_mailing_drip.py</code> - outside the window it does nothing. <strong>Run now</strong> ignores the window.</p>
          </div>

          {(drip.steps || []).map((step, index) => (
            <div key={step.id} className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-xs font-semibold text-[#4f5059]">
                  <input type="checkbox" checked={step.enabled} onChange={(event) => updateStep(index, { enabled: event.target.checked })} />
                  Enabled
                </label>
                <label className="flex items-center gap-2 text-xs text-[#4f5059]">
                  Send after
                  <input type="number" min="0" max="365" value={step.day_offset} onChange={(event) => updateStep(index, { day_offset: Number(event.target.value) })} className="h-9 w-20 rounded-lg border border-[#dfdfe8] bg-white px-2 text-xs outline-none focus:border-[#887bf3]" />
                  days
                </label>
                <div className="min-w-[220px] flex-1">
                  <Dropdown value={step.audience} onChange={(value) => updateStep(index, { audience: value })} options={segmentOptions} placeholder="Segment" />
                </div>
                <Button variant="danger" size="sm" onClick={() => removeStep(index)}><Trash2 size={13} /></Button>
              </div>
              <input value={step.subject} onChange={(event) => updateStep(index, { subject: event.target.value })} placeholder="Subject" className="mt-3 h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" />
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-[#898a95]">Insert:</span>
                {(mergeTokens || []).map((item) => (
                  <button key={item.token} type="button" title={item.label} onMouseDown={(event) => event.preventDefault()} onClick={() => dripEditors.current[step.id]?.current?.insertToken(item.token)} className="rounded-lg border border-[#e4e4eb] bg-white px-2 py-1 text-[11px] font-semibold text-[#5b5c66] transition hover:border-[#887bf3] hover:text-[#4a3bd8]">{item.label}</button>
                ))}
              </div>
              <div className="mt-2">
                <RichTextEditor value={step.body_html} onChange={(html) => updateStep(index, { body_html: html })} apiRef={dripEditors.current[step.id] || (dripEditors.current[step.id] = { current: null })} />
              </div>
            </div>
          ))}

          <Button variant="outline" size="sm" onClick={addStep}><Plus size={14} /> Add step</Button>
        </div>
      )}

      {tab === "log" && (
        <div className="mt-5 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#eeeef2] text-[10px] uppercase tracking-[.12em] text-[#92939d]">
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Attempts</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {sends.map((row) => (
                  <tr key={row.id} className="border-b border-[#f0f0f3] last:border-0">
                    <td className="px-4 py-3 font-bold text-[#4d4e57]">{row.recipient_email}</td>
                    <td className="px-4 py-3">{row.subject}</td>
                    <td className="px-4 py-3"><Badge tone={MAILING_STATUS_TONE[row.status] || "neutral"}>{row.status}</Badge></td>
                    <td className="px-4 py-3 text-[#898a95]">{row.attempts ?? 0}</td>
                    <td className="px-4 py-3 text-[#898a95]">{new Date(row.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {sends.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-[#999aa4]">Nothing sent yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "suppressed" && (
        <div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6">
          <p className="text-sm font-extrabold">Unsubscribed addresses</p>
          <p className="mt-1 text-xs text-[#898a95]">These accounts are permanently excluded from mailings until removed.</p>
          <div className="mt-4 space-y-2">
            {suppressions.map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-4 py-2.5 text-xs">
                <span className="truncate text-[#4d4e57]">{row.email}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-[#92939d]">{new Date(row.created_at).toLocaleDateString()}</span>
                  <Button variant="ghost" size="xs" disabled={busy === "suppress"} onClick={() => removeSuppression(row.id)}>Allow again</Button>
                </div>
              </div>
            ))}
            {suppressions.length === 0 && <p className="py-10 text-center text-xs text-[#999aa4]">Nobody has unsubscribed.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function downloadCsv(filename, content) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function AdminSearch({ token, onNavigate }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (query.trim().length < 2) { setResults(null); setLoading(false); return; }
    let active = true;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const data = await api.adminSearch(token, query.trim());
        if (active) { setResults(data); setError(""); }
      } catch (requestError) {
        if (active) setError(requestError.message || "Search failed");
      } finally {
        if (active) setLoading(false);
      }
    }, 300);
    return () => { active = false; clearTimeout(timer); };
  }, [token, query]);
  const total = results ? results.users.length + results.companies.length + results.stores.length : 0;
  return <div className="mx-auto max-w-[900px] p-5 lg:p-8">
    <div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Search</h2><p className="mt-1 text-sm text-[#898a95]">Find any user, company or store across the platform.</p></div>
    <div className="relative mt-6">
      <Search size={18} className="absolute left-4 top-3.5 text-[#a1a2ab]" />
      <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name or email..." className="h-12 w-full rounded-xl border border-[#e3e3ea] bg-white pl-12 pr-4 text-sm outline-none focus:border-[#887bf3]" />
    </div>
    {error && <p className="mt-4 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {query.trim().length < 2 ? <p className="mt-8 text-center text-xs text-[#999aa4]">Type at least two characters.</p> : loading ? <p className="mt-8 text-center text-xs text-[#999aa4]">Searching...</p> : results && <div>
      {total === 0 && <p className="mt-8 text-center text-xs text-[#999aa4]">No matches.</p>}
      {results.users.length > 0 && <section className="mt-6"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Users</p><div className="mt-2 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">{results.users.map((user) => <button key={user.id} type="button" onClick={() => onNavigate?.("users")} className="flex w-full items-center justify-between gap-3 border-b border-[#f0f0f3] px-4 py-3 text-left last:border-0 hover:bg-[#fafafd]"><div className="min-w-0"><p className="truncate text-xs font-bold text-[#3d3e47]">{user.full_name}</p><p className="mt-0.5 truncate text-[10px] text-[#999aa4]">{user.email}</p></div><div className="flex shrink-0 items-center gap-2">{user.platform_role && <Badge tone="violet">{user.platform_role}</Badge>}<Badge tone={user.is_active ? "green" : "red"} dot>{user.is_active ? "Active" : "Suspended"}</Badge></div></button>)}</div></section>}
      {results.companies.length > 0 && <section className="mt-6"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Companies</p><div className="mt-2 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">{results.companies.map((company) => <button key={company.id} type="button" onClick={() => onNavigate?.("companies")} className="flex w-full items-center justify-between gap-3 border-b border-[#f0f0f3] px-4 py-3 text-left last:border-0 hover:bg-[#fafafd]"><div className="min-w-0"><p className="truncate text-xs font-bold text-[#3d3e47]">{company.name}</p><p className="mt-0.5 text-[10px] text-[#999aa4]">{company.country}{company.plan_code ? ` · ${company.plan_code}` : ""}</p></div><Badge tone={company.is_active ? "green" : "red"} dot>{company.is_active ? "Active" : "Suspended"}</Badge></button>)}</div></section>}
      {results.stores.length > 0 && <section className="mt-6"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Stores</p><div className="mt-2 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">{results.stores.map((store) => <button key={store.id} type="button" onClick={() => onNavigate?.("stores")} className="flex w-full items-center justify-between gap-3 border-b border-[#f0f0f3] px-4 py-3 text-left last:border-0 hover:bg-[#fafafd]"><div className="min-w-0"><p className="truncate text-xs font-bold text-[#3d3e47]">{store.name}</p><p className="mt-0.5 truncate text-[10px] text-[#999aa4]">{store.company_name}</p></div><Badge tone={store.is_active ? "green" : "red"} dot>{store.is_active ? "Active" : "Paused"}</Badge></button>)}</div></section>}
    </div>}
  </div>;
}

function AdminSalesAnalytics({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState("30");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.adminSalesAnalytics(token, days || undefined));
    } catch (requestError) {
      setError(requestError.message || "Could not load sales analytics");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, days]);
  const usd = (value) => money(Number(value || 0), "USD");
  const cur = (value) => money(Number(value || 0), data?.summary?.gmv_currency || "USD");
  const tile = (label, value, detail) => (
    <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5">
      <p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">{label}</p>
      <p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{value}</p>
      {detail && <p className="mt-1 text-[11px] text-[#92939d]">{detail}</p>}
    </div>
  );
  const rank = (rows, valueKey) => (
    <div className="space-y-2">
      {rows.length === 0 ? <p className="py-4 text-center text-xs text-[#999aa4]">No data in this window.</p> : rows.map((row, index) => (
        <div key={`${row.id || row.name || row.product_name}-${index}`} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs">
          <div className="flex min-w-0 items-center gap-2"><span className="w-4 shrink-0 text-[#b0b1ba]">{index + 1}</span><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{row.name || row.product_name}</span></div>
          <span className="shrink-0 text-[#777883]">{row.orders != null ? `${row.orders} orders · ` : ""}<strong className="text-[#202128]">{cur(row[valueKey])}</strong></span>
        </div>
      ))}
    </div>
  );
  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Sales analytics</h2><p className="mt-1 text-sm text-[#898a95]">Platform-wide selling, payment mix and inventory health.</p></div>
      <select value={days} onChange={(event) => setDays(event.target.value)} className="h-10 rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs font-semibold text-[#4f5059]">{[7, 30, 90, 365].map((value) => <option key={value} value={value}>Last {value} days</option>)}</select>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading ? <p className="mt-6 text-sm text-[#92939d]">Loading...</p> : data && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {tile(`Sales (${data.window_days}d)`, cur(data.summary.gmv_window), `${data.summary.gmv_currency} · ${cur(data.summary.gmv_total)} all time`)}
        {tile(`Orders (${data.window_days}d)`, data.summary.orders_window, `${data.summary.orders_total} all time`)}
        {tile("Average order", cur(data.summary.average_order_value), "In this window")}
        {tile(`Refunds (${data.window_days}d)`, cur(data.summary.refunds_window), `${data.summary.refund_count_window} refund(s)`)}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {tile("Inventory value", usd(data.inventory.inventory_value), `${data.inventory.active_products} active products`)}
        {tile("Low stock", data.inventory.low_stock_count, "At or below reorder point")}
        {tile("Out of stock", data.inventory.out_of_stock_count, "Zero or negative on hand")}
        {tile("Top company", data.top_companies[0]?.name || "-", data.top_companies[0] ? cur(data.top_companies[0].gmv) : "No sales yet")}
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><h3 className="text-sm font-extrabold">Top companies</h3><p className="mt-1 text-[11px] text-[#999aa4]">By sales in this window</p><div className="mt-4">{rank(data.top_companies, "gmv")}</div></section>
        <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><h3 className="text-sm font-extrabold">Top stores</h3><p className="mt-1 text-[11px] text-[#999aa4]">By sales in this window</p><div className="mt-4">{rank(data.top_stores, "gmv")}</div></section>
        <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><h3 className="text-sm font-extrabold">Top products</h3><p className="mt-1 text-[11px] text-[#999aa4]">By revenue in this window</p><div className="mt-4">{rank(data.top_products, "revenue")}</div></section>
        <section className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><h3 className="text-sm font-extrabold">Payment methods</h3><p className="mt-1 text-[11px] text-[#999aa4]">Paid orders in this window</p><div className="mt-4">{data.payment_methods.length === 0 ? <p className="py-4 text-center text-xs text-[#999aa4]">No payments in this window.</p> : data.payment_methods.map((method) => <div key={method.method} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><span className="font-semibold capitalize text-[#4d4e57]">{method.method}</span><span className="text-[#777883]">{method.orders} orders · <strong className="text-[#202128]">{cur(method.amount)}</strong></span></div>)}</div></section>
      </div>
    </>}
  </div>;
}

function AdminRetention({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [weeks, setWeeks] = useState("8");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.adminRetention(token, weeks || undefined));
    } catch (requestError) {
      setError(requestError.message || "Could not load retention");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, weeks]);
  const pct = (value) => (value == null ? "-" : `${Math.round(value * 100)}%`);
  const maxStores = data?.weekly?.length ? Math.max(...data.weekly.map((row) => row.active_stores), 1) : 1;
  return <div className="mx-auto max-w-[1200px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Retention</h2><p className="mt-1 text-sm text-[#898a95]">Weekly engagement and how quickly new workspaces activate.</p></div>
      <select value={weeks} onChange={(event) => setWeeks(event.target.value)} className="h-10 rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs font-semibold text-[#4f5059]">{[4, 8, 12, 26].map((value) => <option key={value} value={value}>Last {value} weeks</option>)}</select>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading ? <p className="mt-6 text-sm text-[#92939d]">Loading...</p> : data && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Active companies</p><p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{data.active_companies}</p><p className="mt-1 text-[11px] text-[#92939d]">Ever recorded a paid sale</p></div>
        <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Repeat rate</p><p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{pct(data.repeat_rate)}</p><p className="mt-1 text-[11px] text-[#92939d]">Sold more than once</p></div>
        <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Orders / active company</p><p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{Number(data.average_orders_per_active_company || 0).toFixed(1)}</p><p className="mt-1 text-[11px] text-[#92939d]">All time</p></div>
      </div>
      <section className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-5">
        <h3 className="text-sm font-extrabold">Weekly engagement</h3>
        <p className="mt-1 text-[11px] text-[#999aa4]">Stores with a paid sale, active users and GMV per week</p>
        <div className="mt-4 space-y-3">
          {data.weekly.map((row) => <div key={row.week_start}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="font-semibold text-[#4d4e57]">Week of {new Date(row.week_start).toLocaleDateString()}</span><span className="text-[#777883]">{row.active_stores} stores · {row.active_users} users · {row.orders} orders · <strong className="text-[#202128]">{money(Number(row.gmv || 0), data.gmv_currency)}</strong></span></div>
            <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-[#f1f1f5]"><div className="h-full rounded-full bg-[#6957f5]" style={{ width: `${Math.max(2, Math.round((row.active_stores / maxStores) * 100))}%` }} /></div>
          </div>)}
        </div>
      </section>
      <section className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-5">
        <h3 className="text-sm font-extrabold">Signup cohorts</h3>
        <p className="mt-1 text-[11px] text-[#999aa4]">Workspaces created per week and how many sold within 28 days</p>
        <div className="mt-4 space-y-2">
          {data.cohorts.length === 0 ? <p className="py-4 text-center text-xs text-[#999aa4]">No new workspaces in this window.</p> : data.cohorts.map((cohort) => <div key={cohort.cohort_start} className="flex items-center justify-between gap-3 rounded-xl border border-[#f0f0f3] px-3 py-2 text-xs"><span className="font-semibold text-[#4d4e57]">Week of {new Date(cohort.cohort_start).toLocaleDateString()}</span><span className="text-[#777883]">{cohort.companies} workspaces · <strong className="text-[#202128]">{pct(cohort.activation_rate)}</strong> activated ({cohort.activated})</span></div>)}
        </div>
      </section>
    </>}
  </div>;
}

function AdminAttention({ token, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.adminAttention(token));
    } catch (requestError) {
      setError(requestError.message || "Could not load attention items");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token]);
  const actionable = data ? data.items.filter((item) => item.count > 0) : [];
  return <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Needs attention</h2><p className="mt-1 text-sm text-[#898a95]">Accounts, payments and subscriptions that may need the platform team.</p></div>
      <Button variant="outline" size="sm" onClick={load}><RefreshCw size={15} /> Refresh</Button>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading ? <p className="mt-6 text-sm text-[#92939d]">Loading...</p> : data && <>
      <p className="mt-4 text-xs text-[#898a95]">{actionable.length === 0 ? "Nothing needs attention right now." : `${actionable.length} item(s) need a look.`}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {data.items.map((item) => <div key={item.kind} className={`rounded-2xl border bg-white p-5 ${item.count > 0 && item.severity === "critical" ? "border-[#f3c9c3]" : "border-[#e9e9ef]"}`}>
          <div className="flex items-start justify-between gap-3">
            <div><p className="text-sm font-extrabold">{item.label}</p><p className={`mt-2 text-2xl font-extrabold tracking-[-.04em] ${item.count > 0 && item.severity === "critical" ? "text-[#c2564b]" : "text-[#202128]"}`}>{item.count}</p></div>
            <Badge tone={item.count === 0 ? "green" : item.severity === "critical" ? "red" : "yellow"} dot>{item.count === 0 ? "Clear" : item.severity === "critical" ? "Critical" : "Check"}</Badge>
          </div>
          {item.page && item.count > 0 && <Button variant="outline" size="xs" className="mt-3" onClick={() => onNavigate?.(item.page)}>View</Button>}
        </div>)}
      </div>
    </>}
  </div>;
}

function AdminFunnel({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState("");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.adminFunnel(token, days || undefined));
    } catch (requestError) {
      setError(requestError.message || "Could not load the funnel");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, days]);
  const pct = (value) => (value == null ? "-" : `${Math.round(value * 100)}%`);
  const max = data?.stages?.length ? Math.max(...data.stages.map((stage) => stage.count), 1) : 1;
  return <div className="mx-auto max-w-[1100px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Activation funnel</h2>
        <p className="mt-1 text-sm text-[#898a95]">Where merchants drop off between signing up and their first sale.</p>
      </div>
      <select value={days} onChange={(event) => setDays(event.target.value)} className="h-10 rounded-xl border border-[#e4e4eb] bg-white px-3 text-xs font-semibold text-[#4f5059]">
        <option value="">All time</option>
        {[7, 30, 90, 365].map((value) => <option key={value} value={value}>Last {value} days</option>)}
      </select>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading ? <p className="mt-6 text-sm text-[#92939d]">Loading...</p> : data && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Stalled signups</p><p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{data.stalled_signups}</p><p className="mt-1 text-[11px] text-[#92939d]">Registered but no workspace yet</p></div>
        <div className="rounded-2xl border border-[#e9e9ef] bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Stalled workspaces</p><p className="mt-2 text-2xl font-extrabold tracking-[-.04em]">{data.stalled_workspaces}</p><p className="mt-1 text-[11px] text-[#92939d]">Workspace created but never sold</p></div>
      </div>
      <div className="mt-5 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white">
        {data.stages.map((stage) => <div key={stage.key} className="border-b border-[#f0f0f3] px-4 py-4 last:border-0">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-bold text-[#3d3e47]">{stage.label}</span>
            <span className="text-[#777883]"><strong className="text-[#202128]">{stage.count}</strong> · {pct(stage.conversion_from_previous)} from previous · {pct(stage.conversion_from_start)} of signups</span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[#f1f1f5]"><div className="h-full rounded-full bg-[#6957f5]" style={{ width: `${Math.max(2, Math.round((stage.count / max) * 100))}%` }} /></div>
        </div>)}
      </div>
    </>}
  </div>;
}

function PlatformAdmin({ token, user, onSignOut, notify, initialPage = "overview", onNavigate }) {  const [active, setActive] = useState(initialPage);  const [mobileOpen, setMobileOpen] = useState(false);  const [overview, setOverview] = useState(null);  const [users, setUsers] = useState([]);  const [companies, setCompanies] = useState([]);  const [stores, setStores] = useState([]);  const [subscriptions, setSubscriptions] = useState([]);  const [plans, setPlans] = useState([]);  const [activities, setActivities] = useState([]);  const [attention, setAttention] = useState(null);  const [loading, setLoading] = useState(true);  const [error, setError] = useState("");  const load = async () => {    setLoading(true);    setError("");    try {      const [overviewRow, usersRows, companyRows, storeRows, subscriptionRows, planRows, activityRows, attentionRow] = await Promise.all([        api.adminOverview(token),        api.adminUsers(token),        api.adminCompanies(token),        api.adminStores(token),        api.adminSubscriptions(token),        api.adminPlans(token),        api.adminActivity(token, { limit: 100 }),
        api.adminAttention(token),      ]);      setOverview(overviewRow);      setUsers(usersRows);      setCompanies(companyRows);      setStores(storeRows);      setSubscriptions(subscriptionRows);      setPlans(planRows);      setActivities(activityRows);      setAttention(attentionRow);    } catch (requestError) {      setError(requestError.message || "Could not load admin data");    } finally {      setLoading(false);    }  };  useEffect(() => { load(); }, [token]);  const navigate = (page) => { setActive(page); onNavigate?.(page); };const updateUser = async (id, body) => { try { await api.adminUpdateUser(token, id, body); notify("User updated"); await load(); } catch (requestError) { setError(requestError.message); } };const updateCompany = async (id, body) => { try { await api.adminUpdateCompany(token, id, body); notify("Company status updated"); await load(); } catch (requestError) { setError(requestError.message); } };const updateStore = async (id, body) => { try { await api.adminUpdateStore(token, id, body); notify("Store status updated"); await load(); } catch (requestError) { setError(requestError.message); } };const savePlan = async (request) => { try { if (request.create) { await api.adminCreatePlan(token, request); notify("Plan created"); } else { await api.adminUpdatePlan(token, request.code, request); notify("Plan updated"); } await load(); } catch (requestError) { setError(requestError.message || "Could not save plan"); throw requestError; } };const content = { overview: <AdminOverview overview={overview} companies={companies} activities={activities} attention={attention} onNavigate={navigate} loading={loading} />, funnel: <AdminFunnel token={token} />, analytics: <AdminSalesAnalytics token={token} />, retention: <AdminRetention token={token} />, attention: <AdminAttention token={token} onNavigate={navigate} />, search: <AdminSearch token={token} onNavigate={navigate} />, users: <AdminUsers users={users} onUpdate={updateUser} loading={loading} token={token} />, companies: <AdminCompanies companies={companies} onUpdate={updateCompany} loading={loading} token={token} />, stores: <AdminStores stores={stores} onUpdate={updateStore} loading={loading} />, subscriptions: <AdminSubscriptions subscriptions={subscriptions} loading={loading} />, "billing-payments": <AdminBillingPayments token={token} />, plans: <AdminPlans plans={plans} onSave={savePlan} loading={loading} />, payments: <AdminPayments token={token} notify={notify} />, mailing: <AdminMailing token={token} user={user} notify={notify} onNavigate={navigate} />, settings: <AdminSettings token={token} user={user} notify={notify} />, audit: <AdminAudit token={token} />, support: <AdminSupportInsights token={token} />, help: <AdminHelpContent token={token} notify={notify} /> }[active] || <AdminOverview overview={overview} companies={companies} activities={activities} attention={attention} onNavigate={navigate} loading={loading} />;  return <div className="min-h-screen bg-[#fafafd] text-[#202128]"><AdminSidebar active={active} onNavigate={navigate} onSignOut={onSignOut} user={user} /><AdminMobileMenu active={active} open={mobileOpen} onClose={() => setMobileOpen(false)} onNavigate={navigate} /><div className="lg:pl-[252px]"><AdminHeader active={active} onMenu={() => setMobileOpen(true)} onSignOut={onSignOut} user={user} /><main>{error && <div className="mx-auto max-w-[1460px] px-5 pt-5 lg:px-8"><p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p></div>}{content}</main></div></div>;}

export { ThemeProvider, ThemeToggle };
export default PlatformAdmin;
