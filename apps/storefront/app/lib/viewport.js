// Mobile browsers draw their own chrome over the page: iOS Safari and Chrome
// both float an address bar at the bottom, and the on-screen keyboard covers
// whatever is beneath it. `position: fixed` is placed against the *layout*
// viewport, which ignores all of that - so a panel sized with `100vh` loses its
// composer behind the toolbar, and a launcher pinned to the bottom disappears
// behind it. The visual viewport is the part the shopper can actually see.
//
// Pure functions only, so `node --test` can cover them like the other helpers.

// Tailwind's `sm` breakpoint. Below it the widget is a full-screen sheet; above
// it the usual floating card.
export const MOBILE_QUERY = "(max-width: 639px)";

// How far above the layout viewport's bottom a phone launcher sits. The
// storefront's fixed cart bar is ~76px, so this clears it with a little air.
// iOS 26's floating browser bar overlays the layout viewport rather than
// resizing it, so the visual-viewport gap is added on top when it is larger.
export const MOBILE_LAUNCHER_BOTTOM = 96;
export const LAUNCHER_CLEARANCE = 24;

/**
 * Turn a `VisualViewport` into the box a fixed element must occupy so it is
 * fully visible, plus the height of any chrome drawn below that box.
 *
 * `offsetTop` is non-zero when the browser scrolled the layout viewport to
 * reveal a focused field, so it is part of the box rather than ignored.
 */
export function visibleViewportBox(viewport, layoutHeight) {
  if (!viewport) return null;
  const top = Math.max(0, Number(viewport.offsetTop) || 0);
  const height = Math.max(0, Number(viewport.height) || 0);
  if (height <= 0) return null;
  const layout = Math.max(top + height, Number(layoutHeight) || 0);
  return { top, height, bottomGap: Math.max(0, layout - (top + height)) };
}

/** Where to pin the mobile launcher, in px from the layout viewport's bottom. */
export function launcherBottom(bottomGap) {
  const gap = Math.max(0, Number(bottomGap) || 0);
  // `bottom` is measured from the layout viewport, whose last `gap` pixels are
  // covered by browser chrome. Keep the usual cart-bar clearance, but never
  // less than a finger's width of air above the visible edge.
  return Math.max(MOBILE_LAUNCHER_BOTTOM, gap + LAUNCHER_CLEARANCE);
}
