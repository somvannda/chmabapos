// The marketing chrome shared by chmaba.com and the storefront host.
//
// It depends on nothing but React and Tailwind classes, and takes everything
// host-specific as props. That is deliberate: the three apps are separate npm
// projects that already read packages/ui by relative path (the Tailwind preset and
// tokens.css arrive the same way), so importing app code from here would create a
// cycle between apps. Anything the two hosts disagree about - where the logo links,
// which nav items exist, what the main button does - is passed in.
//
// The storefront has no dark mode, so the dark: classes below stay dormant there;
// chmaba.com opts into them with darkMode: "class".

const NAV_LINK = "transition hover:text-[#17181c] dark:text-[#9a9aa4] dark:hover:text-[#e4e4e8]";

// The brand mark, matching the lockup the apps already render.
export function ChmabaLogo({ light = false }) {
  const chip = light ? "bg-[#c4f27c]" : "bg-[#17181c] dark:bg-[#c4f27c]";
  const ring = light ? "border-[#17181c]" : "border-white dark:border-[#17181c]";
  const word = light ? "text-white" : "text-[#17181c] dark:text-white";
  return (
    <div className="flex items-center gap-2.5">
      <div className={`relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-[10px] ${chip}`}>
        <span className={`absolute h-3 w-3 rounded-full border-[2.5px] ${ring}`} />
        <span className={`absolute -right-0.5 top-1.5 h-3 w-3 rounded-full border-[2.5px] ${ring}`} />
      </div>
      <span className={`text-[19px] font-extrabold tracking-[-.04em] ${word}`}>chmaba</span>
    </div>
  );
}

// Header buttons mirror the app Button's sizes and tones without importing it.
// A link when given an href, a button when given a handler.
function HeaderAction({ primary = false, href, onClick, children }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all duration-200";
  const look = primary
    ? "h-9 bg-[#6957f5] px-3 text-xs text-white shadow-[0_7px_16px_rgba(105,87,245,.2)] hover:bg-[#5845e7]"
    : "px-3 py-2 text-sm text-[#60616c] hover:text-[#17181c] dark:text-[#9a9aa4] dark:hover:text-[#e4e4e8]";
  const className = `${base} ${look}`;
  if (href) {
    return <a href={href} className={className} onClick={onClick}>{children}</a>;
  }
  return <button type="button" className={className} onClick={onClick}>{children}</button>;
}

// nav items: { label, href, external? }. `actions` holds host-specific extras such as
// the theme toggle, which would otherwise drag app state into this package.
export function ChmabaHeader({ homeHref = "/", onHomeClick, nav = [], onNavClick, actions = null, signIn, cta }) {
  return (
    <header className="sticky top-0 z-40 border-b border-[#e9e9ef]/70 bg-[#fafafd]/85 backdrop-blur-xl dark:border-[#2a2b30]/80 dark:bg-[#111114]/85">
      <div className="mx-auto flex h-[76px] max-w-[1240px] items-center justify-between gap-4 px-5 lg:px-8">
        <a href={homeHref} aria-label="Chmaba home" className="transition hover:opacity-80" onClick={onHomeClick}>
          <ChmabaLogo />
        </a>
        <nav className="hidden items-center gap-8 text-sm font-medium text-[#6f707a] md:flex">
          {nav.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={NAV_LINK}
              {...(item.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              onClick={(event) => onNavClick?.(event, item)}
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2.5">
          {actions}
          {signIn ? <span className="hidden sm:block"><HeaderAction href={signIn.href} onClick={signIn.onClick}>{signIn.label}</HeaderAction></span> : null}
          {cta ? <HeaderAction primary href={cta.href} onClick={cta.onClick}>{cta.label}</HeaderAction> : null}
        </div>
      </div>
    </header>
  );
}

// links: { label, href, onClick? }. `note` overrides the copyright line.
export function ChmabaFooter({ homeHref = "/", onHomeClick, links = [], note }) {
  return (
    <footer className="border-t border-[#eaeaef] px-5 py-7 lg:px-8 dark:border-[#2a2b30]">
      <div className="mx-auto flex max-w-[1240px] flex-col gap-4 text-xs text-[#92939d] sm:flex-row sm:items-center sm:justify-between">
        <a href={homeHref} aria-label="Chmaba home" className="transition hover:opacity-80" onClick={onHomeClick}>
          <ChmabaLogo />
        </a>
        <span>{note || <>&copy; {new Date().getFullYear()} Chmaba Technologies. Built with &#10084;&#65039; for better days.</>}</span>
        <div className="flex gap-5">
          {links.map(({ label, href, onClick, external, strong }) => <a key={label} href={href} className={strong ? `font-semibold ${NAV_LINK}` : NAV_LINK} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})} onClick={onClick}>{label}</a>)}
        </div>
      </div>
    </footer>
  );
}
