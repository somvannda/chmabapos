// Batch-expiry labelling. Pure so it can be unit-tested with node:test.
// `daysUntilExpiry` is the backend's day count: negative = already expired,
// 0 = expires today, positive = days remaining, null = no expiry date.
export function expiryStatus(daysUntilExpiry) {
  const days = Number(daysUntilExpiry);
  if (daysUntilExpiry == null || Number.isNaN(days)) return { label: "no expiry", tone: "neutral" };
  if (days < 0) return { label: `expired ${Math.abs(days)}d ago`, tone: "red" };
  if (days === 0) return { label: "expires today", tone: "yellow" };
  return { label: `in ${days}d`, tone: "yellow" };
}
