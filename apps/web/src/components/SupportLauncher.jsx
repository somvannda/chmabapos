import { useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { SupportChat } from "./SupportChat";
import { api } from "../api";

// A floating entry point to the same assistant that lives in the Knowledge base,
// so it is reachable from any workspace page. The full experience stays inline
// on the Knowledge base page; this is a quick-access panel.
function SupportLauncher({ token, storeId, onNavigate, onOpenGuide, onContactSupport }) {
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState(() => {
    try {
      return localStorage.getItem("chmaba.support.lang") || "en";
    } catch {
      return "en";
    }
  });
  const [prompts, setPrompts] = useState([]);

  useEffect(() => {
    if (!token || !open) return undefined;
    let active = true;
    api.supportStarterPrompts(token, language)
      .then((data) => { if (active) setPrompts(data?.prompts || []); })
      .catch(() => { if (active) setPrompts([]); });
    return () => { active = false; };
  }, [token, language, open]);

  const changeLanguage = (value) => {
    setLanguage(value);
    try {
      localStorage.setItem("chmaba.support.lang", value);
    } catch {
      /* ignore storage failures */
    }
  };

  return (
    <>
      {open && (
        <div className="fixed bottom-[84px] right-5 z-50 w-[390px] max-w-[calc(100vw-40px)]">
          <SupportChat
            token={token}
            storeId={storeId}
            language={language}
            onLanguageChange={changeLanguage}
            starterPrompts={prompts}
            onOpenGuide={onOpenGuide}
            onNavigate={onNavigate}
            onContactSupport={onContactSupport}
            className="shadow-[0_24px_80px_rgba(20,21,28,.28)]"
          />
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Close the assistant" : "Ask the assistant"}
        className="fixed bottom-5 right-5 z-50 inline-flex h-12 items-center gap-2 rounded-full bg-[#6957f5] px-4 text-xs font-bold text-white shadow-[0_12px_30px_rgba(105,87,245,.4)] transition hover:bg-[#5a48e0]"
      >
        {open ? <X size={16} /> : <Sparkles size={16} />}
        {open ? "Close" : "Ask Chmaba"}
      </button>
    </>
  );
}

export { SupportLauncher };
