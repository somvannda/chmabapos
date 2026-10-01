import { useEffect, useState } from "react";
import { api } from "../api";
import { CAPABILITY_KEYS, CAPABILITY_PACKS, allowsCapability } from "./capabilityPacks";

// Re-exported so existing `from "../lib/capabilities"` imports keep working; the
// catalog and helpers themselves live in the dependency-free capabilityPacks
// module so they can be unit-tested without the API client.
export { CAPABILITY_KEYS, CAPABILITY_PACKS, allowsCapability };

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
