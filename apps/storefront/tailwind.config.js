import uiPreset from "../../packages/ui/tailwind-preset.js";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [uiPreset],
  content: ["./app/**/*.{js,jsx}"],
};
