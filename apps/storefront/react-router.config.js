/** @type {import("@react-router/dev/config").Config} */
export default {
  // Server-rendered: the store page must be useful before hydration and must
  // unfurl correctly when a merchant shares it on Facebook or Telegram, which
  // read the raw HTML and never run JavaScript.
  ssr: true,
};
