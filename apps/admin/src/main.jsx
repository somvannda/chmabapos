import { useState, useEffect, useCallback } from "react";
import ReactDOM from "react-dom/client";
import { Eye, EyeOff } from "lucide-react";
import PlatformAdmin, { ThemeProvider } from "./App";
import { api } from "./api";
import "./styles.css";

const TOKEN_KEY = "chmaba.access_token";
const ADMIN_PAGES = new Set(["overview", "users", "companies", "stores", "subscriptions", "plans", "audit", "payments"]);

function pageFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  const segment = (parts[0] === "admin" ? parts[1] : parts[0]) || "";
  if (!segment) return "overview";
  return ADMIN_PAGES.has(segment) ? segment : "not-found";
}

function AdminNotFound({ onBack }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#17181c] p-6">
      <div className="w-full max-w-md rounded-2xl border border-[#33343a] bg-[#1f2025] p-9 text-center">
        <div className="flex items-center justify-center gap-2">
          <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#686970]">Chmaba</p>
          <span className="rounded-full bg-[#2a2b32] px-2.5 py-1 text-[9px] font-bold uppercase tracking-[.12em] text-[#c4f27c]">Admin</span>
        </div>
        <h1 className="mt-6 text-6xl font-extrabold leading-none tracking-[-.06em] text-[#6957f5]">404</h1>
        <p className="mt-4 text-base font-extrabold tracking-[-.02em] text-white">Page not found</p>
        <p className="mt-2 text-sm leading-6 text-[#92939d]">That admin page does not exist or has moved.</p>
        <div className="mt-7 flex flex-col gap-2">
          <button type="button" onClick={onBack} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#6957f5] text-sm font-bold text-white transition hover:bg-[#7b6bf7]">Back to overview</button>
          <button type="button" onClick={() => window.history.back()} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-[#363740] text-sm font-bold text-[#c8c9d0] transition hover:bg-[#232429]">Go back</button>
        </div>
      </div>
    </div>
  );
}

function AdminShell() {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
  const [toast, setToast] = useState(null);
  const [page, setPage] = useState(pageFromPath());

  const notify = useCallback((message) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    const sync = () => setPage(pageFromPath());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  useEffect(() => {
    let active = true;
    if (!token) {
      setStatus("signin");
      return () => { active = false; };
    }
    setStatus("loading");
    api.me(token)
      .then((me) => {
        if (!active) return;
        setUser(me);
        setStatus(me.platform_role ? "ready" : "denied");
      })
      .catch(() => {
        if (!active) return;
        window.localStorage.removeItem(TOKEN_KEY);
        setToken("");
        setUser(null);
        setStatus("signin");
      });
    return () => { active = false; };
  }, [token]);

  const signIn = async (event) => {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const result = await api.login({ email: email.trim(), password });
      window.localStorage.setItem(TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setUser(result.user);
      setStatus(result.user.platform_role ? "ready" : "denied");
      if (result.user.platform_role) notify("Signed in");
    } catch (requestError) {
      setAuthError(requestError.message || "Could not sign in");
    } finally {
      setAuthBusy(false);
    }
  };

  const signOut = () => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setStatus("signin");
  };

  const openUser = useCallback(() => {
    window.history.pushState({}, "", "/users");
  }, []);

  const navigate = useCallback((nextPage) => {
    setPage(nextPage);
    window.history.pushState({}, "", `/${nextPage}`);
  }, []);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#17181c] p-6">
        <div className="text-center text-white">
          <div className="mx-auto flex h-12 w-12 animate-pulse items-center justify-center rounded-2xl bg-[#c4f27c] text-[#17181c]">
            <span className="text-xl font-extrabold">c</span>
          </div>
          <p className="mt-5 text-sm font-bold">Checking admin access</p>
          <p className="mt-1 text-xs text-[#92939d]">Verifying platform session...</p>
        </div>
      </div>
    );
  }

  if (status === "signin" || status === "denied") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#17181c] p-4">
        <form onSubmit={signIn} className="w-full max-w-[380px] rounded-2xl border border-[#33343a] bg-[#1f2025] p-6">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#686970]">Chmaba</p>
            <span className="rounded-full bg-[#2a2b32] px-2.5 py-1 text-[9px] font-bold uppercase tracking-[.12em] text-[#c4f27c]">Admin</span>
          </div>
          <h1 className="mt-6 text-xl font-extrabold tracking-[-.03em] text-white">Platform control panel</h1>
          <p className="mt-1 text-xs text-[#92939d]">Sign in with a platform admin account.</p>
          <label className="mt-6 block">
            <span className="mb-1.5 block text-xs font-semibold text-[#a9aab2]">Email</span>
            <input type="email" required autoFocus value={email} onChange={(event) => setEmail(event.target.value)} className="h-11 w-full rounded-xl border border-[#363740] bg-[#17181c] px-3.5 text-sm text-white outline-none focus:border-[#6957f5]" />
          </label>
          <label className="mt-4 block">
            <span className="mb-1.5 block text-xs font-semibold text-[#a9aab2]">Password</span>
            <div className="relative">
              <input type={showPassword ? "text" : "password"} required value={password} onChange={(event) => setPassword(event.target.value)} className="h-11 w-full rounded-xl border border-[#363740] bg-[#17181c] px-3.5 pr-10 text-sm text-white outline-none focus:border-[#6957f5]" />
              <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((visible) => !visible)} className="absolute right-2.5 top-2.5 flex h-6 w-6 items-center justify-center rounded-md text-[#7f808a] transition hover:bg-[#2a2b32] hover:text-white">{showPassword ? <EyeOff size={15} /> : <Eye size={15} />}</button>
            </div>
          </label>
          {authError && <p className="mt-4 rounded-xl border border-[#5a2a2a] bg-[#3a1e1e] px-3 py-2.5 text-xs text-[#ffb4a8]">{authError}</p>}
          {status === "denied" && <p className="mt-4 rounded-xl border border-[#5a4a1e] bg-[#3a3018] px-3 py-2.5 text-xs text-[#ffe6a8]">This account is not a platform admin.</p>}
          <button type="submit" disabled={authBusy || !email.trim() || !password} className="mt-6 h-11 w-full rounded-xl bg-[#6957f5] text-sm font-bold text-white transition hover:bg-[#7b6bf7] disabled:opacity-40">
            {authBusy ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    );
  }

  if (page === "not-found") {
    return <AdminNotFound onBack={() => navigate("overview")} />;
  }

  return (
    <>
      {toast && (
        <div className="fixed left-1/2 top-4 z-50 -translate-x-1/2 rounded-xl border border-[#2c2d33] bg-[#232429] px-4 py-2.5 text-xs font-semibold text-white shadow-soft">{toast}</div>
      )}
      <PlatformAdmin token={token} user={user} onSignOut={signOut} onOpenUser={openUser} onNavigate={navigate} initialPage={page} notify={notify} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <ThemeProvider>
    <AdminShell />
  </ThemeProvider>
);
