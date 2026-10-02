// Pure helpers for the "Suggested for you" knowledge-base nudges.
// Kept free of React/JSX so they can be unit-tested with node:test.

/**
 * Build the contextual nudges shown on the knowledge-base page from data we
 * already have. Each nudge carries an `href` (the workspace route to open) so
 * the pure function stays free of navigation callbacks.
 *
 * - the next incomplete setup step, when setup is unfinished
 * - a restock nudge, when one or more items are low on stock
 */
export function buildNudges(checklist, lowStock) {
  const list = [];

  if (checklist && checklist.completed < checklist.total) {
    const next = (checklist.steps || []).find((step) => !step.done);
    if (next) {
      list.push({
        id: "setup",
        label: next.title,
        description: next.description,
        href: next.href || "dashboard",
      });
    }
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
