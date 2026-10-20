// Money entry and display, per currency.
//
// The riel has no subunit, so a KHR till must not ask for hundredths: prefilling
// "3666.00" into a cash field invites a cashier to type a decimal that cannot be
// counted out, and sends an amount the API has to quietly round. Everything that
// turns a number into an editable string goes through here.

export function currencyDecimals(code) {
  return String(code || "").toUpperCase() === "KHR" ? 0 : 2;
}

export function moneyInput(value, code) {
  const decimals = currencyDecimals(code);
  const number = Number(value);
  if (!Number.isFinite(number)) return decimals === 0 ? "0" : "0.00";
  return number.toFixed(decimals);
}
