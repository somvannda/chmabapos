// A printable sheet of table QR codes.
//
// One card per table: the code, the table's name, and the one instruction a guest
// needs. The QR encodes the stable legacy link (`/order/<qr_token>`), the address
// already on printed table tents, so a slug change never invalidates a sticker
// (docs/table-ordering-plan.md, D4).
//
// The SVGs are captured from the codes the settings page already renders rather
// than generated again, so the printed code and the on-screen code are the same
// drawing. This module only assembles and escapes the document, which is what
// makes it testable without a browser.

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape a value for HTML text or an attribute. */
export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

const STYLES = `
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #17181c; }
  header { margin-bottom: 16px; }
  h1 { margin: 0; font-size: 20px; }
  header p { margin: 4px 0 0; font-size: 12px; color: #6b6c76; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .card { border: 1px solid #d9d9e3; border-radius: 12px; padding: 16px; text-align: center; break-inside: avoid; }
  .qr { display: flex; justify-content: center; }
  .qr svg { width: 180px; height: 180px; }
  .table { margin: 10px 0 0; font-size: 15px; font-weight: 800; }
  .hint { margin: 2px 0 0; font-size: 11px; color: #6b6c76; }
  @media print { body { padding: 8px; } }
`;

/**
 * The full HTML document for a table QR sheet.
 *
 * ``tables`` is a list of ``{ id, name, qrSvg }``: ``qrSvg`` is the rendered SVG
 * markup for that table's code.
 */
export function tableQrSheetHtml({ storeName, tables = [], printedAt = "" } = {}) {
  const cards = (tables || [])
    .map((table) => {
      const name = escapeHtml(table?.name || "Table");
      const svg = table?.qrSvg || "";
      return `<article class="card"><div class="qr">${svg}</div><p class="table">${name}</p><p class="hint">Scan to order from your table</p></article>`;
    })
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${escapeHtml(storeName || "Store")} table QR codes</title>
<style>${STYLES}</style>
</head>
<body>
<header>
<h1>${escapeHtml(storeName || "")}</h1>
<p>Scan a code to open the menu for that table.</p>
${printedAt ? `<p>${escapeHtml(printedAt)}</p>` : ""}
</header>
<main class="grid">${cards}</main>
</body>
</html>
`;
}
