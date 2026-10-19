// Add-ons on a cart line.
//
// The cart stores quantities only, keyed by a line key. To let two selections of
// the same product be two lines, the key carries the chosen add-on *names* - never
// prices: the API reprices every add-on from the catalogue on submit, so a price
// cached in the browser could only ever be a lie.
//
// A line key is therefore `<product-or-variant key>~m:<encoded names>`. A key
// without the marker is a plain line, which is what every cart written before
// add-ons existed already holds.

const MARKER = "~m:";

/** The key a line with this selection is stored under. No add-ons means the base key. */
export function addModifiersToLineKey(baseKey, names = []) {
  const chosen = (names || []).map((name) => String(name)).filter(Boolean);
  if (!chosen.length) return baseKey;
  // Sorted, so the same selection is the same line whichever order it was picked,
  // and JSON-encoded so a name containing the separator cannot split another line.
  const signature = encodeURIComponent(JSON.stringify([...chosen].sort()));
  return `${baseKey}${MARKER}${signature}`;
}

/** Split a line key back into its product/variant key and its add-on names. */
export function splitLineKey(lineKey) {
  const value = String(lineKey || "");
  const at = value.indexOf(MARKER);
  if (at === -1) return { baseKey: value, modifierNames: [] };
  let modifierNames = [];
  try {
    const parsed = JSON.parse(decodeURIComponent(value.slice(at + MARKER.length)));
    if (Array.isArray(parsed)) modifierNames = parsed.map(String);
  } catch {
    // A hand-edited or corrupted key resolves to a plain line rather than throwing.
  }
  return { baseKey: value.slice(0, at), modifierNames };
}

/**
 * The price one selection adds, looked up from the menu's own groups. A name that
 * is not on the menu (or a group the product no longer has) adds nothing here; the
 * API is the authority and refuses it outright.
 */
export function modifierDelta(modifierGroups, names) {
  const wanted = new Set((names || []).map(String));
  let delta = 0;
  for (const group of modifierGroups || []) {
    for (const modifier of group.modifiers || []) {
      if (wanted.has(String(modifier.name))) delta += Number(modifier.price_delta) || 0;
    }
  }
  return delta;
}

/**
 * Whether a selection satisfies a group's own rule. ``min_select`` is only
 * enforced when the group is required, which is how the catalogue models it.
 */
export function groupSatisfied(group, selectedNames) {
  const selected = (selectedNames || []).filter((name) => (group.modifiers || []).some((modifier) => String(modifier.name) === String(name)));
  const minimum = group.is_required ? Math.max(1, Number(group.min_select) || 0) : Number(group.min_select) || 0;
  const maximum = Number(group.max_select) || 1;
  return selected.length >= minimum && selected.length <= maximum;
}

/** Whether every group on the product is satisfied by the selection. */
export function selectionComplete(modifierGroups, selectedByGroup) {
  return (modifierGroups || []).every((group) => groupSatisfied(group, selectedByGroup?.[group.id] || []));
}
