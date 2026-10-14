/**
 * Tailwind preset for every Chmaba surface.
 *
 * Maps colour utilities onto the CSS custom properties in `tokens.css`, so a
 * class name is a reference to a token rather than a literal hex:
 *
 *   bg-brand            text-ink-soft        border-line-strong
 *   bg-surface-muted    bg-page              bg-brand/10
 *
 * Because the values are variables, a scoped override rebrands a subtree. That
 * is how a merchant's storefront gets its own accent without forking the POS:
 *
 *   <div style={{ "--color-brand": "220 38 38" }}>
 *
 * Adoption is incremental: the existing hard-coded utilities keep working, so a
 * component can be moved onto tokens one at a time with no visual change.
 */
const channel = (name) => `rgb(var(--color-${name}) / <alpha-value>)`;

export default {
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: channel("brand"),
          hover: channel("brand-hover"),
          soft: channel("brand-soft"),
          tint: channel("brand-tint"),
        },
        ink: {
          DEFAULT: channel("ink"),
          soft: channel("ink-soft"),
        },
        muted: channel("muted"),
        surface: {
          DEFAULT: channel("surface"),
          muted: channel("surface-muted"),
          sunken: channel("surface-sunken"),
        },
        page: channel("page"),
        line: {
          DEFAULT: channel("line"),
          strong: channel("line-strong"),
        },
        success: {
          DEFAULT: channel("success"),
          soft: channel("success-soft"),
        },
        danger: {
          DEFAULT: channel("danger"),
          soft: channel("danger-soft"),
        },
      },
    },
  },
};
