import uiPreset from "../../packages/ui/tailwind-preset.js";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [uiPreset],
  // Without this the shared marketing chrome's dark: utilities follow the operating
  // system instead of a class, so a shopper on a dark-preference machine got a black
  // header above a light page. The storefront has no dark mode, and setting it to
  // "class" (which nothing ever adds) keeps those utilities dormant. apps/web and
  // apps/admin already do this.
  darkMode: "class",
  content: ["./app/**/*.{js,jsx}", "../../packages/ui/**/*.{js,jsx}"],
};
