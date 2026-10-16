// The storefront has no icon package on purpose, so the few icons it needs are drawn
// here. Keeping them together means the store page does not grow a second copy of the
// same paths, and they inherit `currentColor` like any other inline SVG.
//
// The social marks are simplified rather than official brand assets: they are drawn from
// simple shapes so they sit at the same optical weight as the rest, and swapping in a
// licensed brand set later means replacing these four paths and nothing else.

export function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

export function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.6a2 2 0 0 1-.5 2.1L8.1 9.5a16 16 0 0 0 6 6l1.1-1.1a2 2 0 0 1 2.1-.5c.8.3 1.7.5 2.6.6a2 2 0 0 1 1.7 2Z" />
    </svg>
  );
}

function TelegramIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M21.6 4.1 2.9 11.3c-.9.3-.9 1.5 0 1.8l4.6 1.5 1.7 5.3c.2.7 1.1.9 1.6.3l2.4-2.6 4.4 3.2c.6.4 1.4.1 1.6-.6l3.2-14.6c.2-.9-.7-1.6-1.6-1.2Zm-3.3 3.6-7.4 6.6c-.2.2-.3.4-.4.6l-.4 2.4-1.1-3.4 9-6.6c.3-.2.5.1.3.4Z" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.7-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12Z" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M7.5 2h9A5.5 5.5 0 0 1 22 7.5v9A5.5 5.5 0 0 1 16.5 22h-9A5.5 5.5 0 0 1 2 16.5v-9A5.5 5.5 0 0 1 7.5 2Zm0 2A3.5 3.5 0 0 0 4 7.5v9A3.5 3.5 0 0 0 7.5 20h9a3.5 3.5 0 0 0 3.5-3.5v-9A3.5 3.5 0 0 0 16.5 4h-9Zm10.75 1.5a1.25 1.25 0 1 1 0 2.5 1.25 1.25 0 0 1 0-2.5ZM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
    </svg>
  );
}

function TikTokIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M16.5 2h-3v13.1a2.9 2.9 0 1 1-2.3-2.8V9.2a6 6 0 1 0 5.3 6V8.6a6.6 6.6 0 0 0 3.5 1V6.4a3.6 3.6 0 0 1-3.5-3.6V2Z" />
    </svg>
  );
}

/** The mark for a network, or nothing when we do not have one. */
export function SocialIcon({ network }) {
  if (network === "telegram") return <TelegramIcon />;
  if (network === "facebook") return <FacebookIcon />;
  if (network === "instagram") return <InstagramIcon />;
  if (network === "tiktok") return <TikTokIcon />;
  return null;
}
