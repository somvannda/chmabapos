import { useEffect, useState } from "react";
import { api } from "../api";

// Mirrors CAPABILITY_LABELS in chmabapos_api/app/verticals.py. Keep the two in
// sync; the backend is the source of truth and validates the store override.
export const CAPABILITY_PACKS = [
  { key: "barcode", label: "Barcode scanning", detail: "Scan or type a UPC to add a product fast." },
  { key: "brand", label: "Brand / model", detail: "Track the maker or model on each product." },
  { key: "unit_of_measure", label: "Unit of measure", detail: "Sell by weight or volume (kg, g, l, ml, pack)." },
  { key: "variants", label: "Variants", detail: "Sizes, colours and packs that share one product." },
  { key: "modifiers", label: "Modifiers / add-ons", detail: "Extras like milk, shots or sides." },
  { key: "tables", label: "Tables & floor plan", detail: "Seat guests at tables and manage the dining room." },
  { key: "serials", label: "Serial / IMEI & warranty", detail: "Track individual units, IMEI and warranty." },
  { key: "batches", label: "Batches & expiry", detail: "Track stock by batch and expiry date." },
];

export const CAPABILITY_KEYS = CAPABILITY_PACKS.map((pack) => pack.key);

// Fetch the store's effective capability packs. Returns `null` while loading and
// whenever the API does not report capabilities, which callers treat as "show
// everything" so a rollout mismatch never hides data a store already has.
export function useCapabilities(token, storeId) {
  const [capabilities, setCapabilities] = useState(null);
  useEffect(() => {
    let active = true;
    if (!token) return () => { active = false; };
    api.currentWorkspace(token, storeId)
      .then((workspace) => {
        if (active) setCapabilities(Array.isArray(workspace?.capabilities) ? workspace.capabilities : null);
      })
      .catch(() => { if (active) setCapabilities(null); });
    return () => { active = false; };
  }, [token, storeId]);
  return capabilities;
}

// True when a pack should be surfaced. `null` (unknown) means show it.
export function allowsCapability(capabilities, key) {
  return capabilities === null || capabilities.includes(key);
}
