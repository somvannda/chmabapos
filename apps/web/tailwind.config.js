/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 14px 40px rgba(28, 31, 42, .07)",
        panel: "0 28px 70px rgba(28, 31, 42, .12)",
      },
      animation: {
        "fade-up": "fadeUp .5s ease-out both",
        "fade-in": "fadeIn .35s ease-out both",
        "pulse-soft": "pulseSoft 2.3s ease-in-out infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: ".55" },
          "50%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
