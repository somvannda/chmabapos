# @chmaba/ui

Shared design tokens and the Tailwind preset for Chmaba apps (`web`, `admin`,
and the public storefront).

## What it is

- `tokens.css` — the palette as CSS custom properties. Colours are stored as
  space-separated RGB channels so Tailwind can build opacity variants
  (`bg-brand/10`). Light values live on `:root`, dark values on `.dark`.
- `tailwind-preset.js` — maps colour utilities (`bg-brand`, `text-ink-soft`,
  `border-line-strong`, `bg-surface-muted`, `bg-page`, …) onto those variables.

## Why variables rather than hex

A stored RGB channel can be re-pointed at runtime, which is what makes
per-merchant branding possible without forking a component:

```jsx
// A storefront subtree wearing the merchant's accent.
<div style={{ "--color-brand": "220 38 38", "--color-brand-soft": "254 226 226" }}>
  …
</div>
```

The POS shell keeps the Chmaba palette because it never sets these overrides,
so merchant colours can never leak into the cashier UI.

## Using it

`tokens.css` must be loaded once per app, before the components render:

```css
/* src/styles.css */
@import "../../packages/ui/tokens.css";
```

```js
/* tailwind.config.js */
import uiPreset from "../../packages/ui/tailwind-preset.js";

export default {
  presets: [uiPreset],
  darkMode: "class",
  // …
};
```

## Adoption

Adoption is deliberately incremental. Adding the preset only *adds* utilities;
it does not change any existing class. A component can therefore move from a
hard-coded hex to a token one at a time, keeping the rendered colour identical
until someone actually wants it to change.

## Adding a token

Add the channel triplet to `:root` in `tokens.css`, add the dark value under
`.dark` if it differs, then expose it in `tailwind-preset.js`. Keep the light
value equal to whatever the apps currently hard-code, so adoption stays a no-op
visually.
