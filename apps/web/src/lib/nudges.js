// Pure helpers for the "Suggested for you" knowledge-base nudges.
// Kept free of React/JSX so they can be unit-tested with node:test.

/**
 * Build the contextual nudges shown on the knowledge-base page from data we
 * already have. Each nudge carries an `href` (the workspace route to open) so
 * the pure function stays free of navigation callbacks.
 *
 * - the next incomplete setup step, when setup is unfinished
 * - a "shift not open" nudge, when the store requires an open shift to sell
 * - a restock nudge, when one or more items are low on stock
 *
 * `shift` is `{ requireOpenShift, hasOpenShift }`; both default to a benign
 * state so callers that don't pass it never get a false shift nudge.
 */
export function buildNudges(checklist, lowStock, shift) {
  const list = [];
  let setupStepId = null;

  if (checklist && checklist.completed < checklist.total) {
    const next = (checklist.steps || []).find((step) => !step.done);
    if (next) {
      setupStepId = next.id;
      list.push({
        id: "setup",
        label: next.title,
        description: next.description,
        href: next.href || "dashboard",
      });
    }
  }

  // Skip when the setup nudge already points at opening a shift, so we don't
  // show the same action twice.
  if (shift?.requireOpenShift && !shift?.hasOpenShift && setupStepId !== "open-shift") {
    list.push({
      id: "shift",
      label: "Open a shift to start selling",
      description: "Your store requires an open shift before you can charge a sale.",
      href: "pos",
    });
  }

  if (lowStock && lowStock.length > 0) {
    list.push({
      id: "restock",
      label: `${lowStock.length} item${lowStock.length === 1 ? "" : "s"} low on stock`,
      description: "Restock before you run out.",
      href: "inventory",
    });
  }

  return list;
}
