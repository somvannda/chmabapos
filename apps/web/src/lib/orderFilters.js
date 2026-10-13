// Date presets and query building for the Orders filter bar.

export function orderRangeDates(range, now = new Date()) {
  const iso = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  if (range === "today") return { from: iso(now), to: iso(now) };
  if (range === "7d") { const start = new Date(now); start.setDate(start.getDate() - 6); return { from: iso(start), to: iso(now) }; }
  if (range === "30d") { const start = new Date(now); start.setDate(start.getDate() - 29); return { from: iso(start), to: iso(now) }; }
  if (range === "month") return { from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), to: iso(now) };
  return { from: null, to: null };
}

export function buildOrderQuery({ status = "all", search = "", range = "all", limit = 50 } = {}, now = new Date()) {
  const params = { limit };
  if (status && status !== "all") params.status = status;
  const term = String(search).trim();
  if (term) params.search = term;
  const { from, to } = orderRangeDates(range, now);
  if (from) params.from_date = from;
  if (to) params.to_date = to;
  return params;
}
