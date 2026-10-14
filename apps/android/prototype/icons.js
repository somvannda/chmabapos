/* ============================================================================
   Chmaba POS · Android prototype — icon system
   ----------------------------------------------------------------------------
   The web app draws every icon from Lucide (24x24, stroke 2, round caps/joins).
   Emoji are NOT allowed in the Android design, so this file:
     1. injects a Lucide-compatible SVG sprite,
     2. replaces the emoji/glyph placeholders used in the prototype markup,
     3. fills any [data-i="name"] container.

   Add an icon only by adding a <symbol> here — never a new emoji.
   ========================================================================== */
(function () {
  'use strict';

  var ICONS = {
    /* ---- navigation ---- */
    home: '<path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    cart: '<circle cx="9" cy="20" r="1.4"/><circle cx="19" cy="20" r="1.4"/><path d="M2 3h2.2l2.4 12.2a2 2 0 0 0 2 1.6h9.6a2 2 0 0 0 2-1.6L21 7H5.6"/>',
    receipt: '<path d="M5 2h14v20l-3-2-2 2-2-2-2 2-3-2z"/><path d="M9 7h6M9 11h6M9 15h4"/>',
    more: '<circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/><circle cx="5" cy="12" r="1.4"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    /* ---- search / capture ---- */
    search: '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5 16.7 16.7"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"/>',
    /* ---- actions ---- */
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    chevronRight: '<path d="M9 6l6 6-6 6"/>',
    chevronLeft: '<path d="M15 6l-6 6 6 6"/>',
    chevronDown: '<path d="M6 9l6 6 6-6"/>',
    arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 4v5h-5"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    upload: '<path d="M12 21V9M7 14l5-5 5 5M4 3h16"/>',
    pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    share: '<path d="M12 3v12M8 7l4-4 4 4"/><path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
    /* ---- people ---- */
    userPlus: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 12-4.9"/><path d="M19 8v6M16 11h6"/>',
    users: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M17 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4.5-5.8"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    arrowUpRight: '<path d="M7 17 17 7M9 7h8v8"/>',
    signal: '<path d="M4 20v-4M9 20v-8M14 20v-12M19 20V4"/>',
    wifi: '<path d="M2 8.5a15 15 0 0 1 20 0"/><path d="M5.5 12.5a10 10 0 0 1 13 0"/><path d="M9 16.5a5 5 0 0 1 6 0"/>',
    battery: '<rect x="2" y="8" width="17" height="8" rx="2"/><path d="M21 11v2"/>',
    /* ---- commerce ---- */
    qr: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM19 14h2M14 19h2M19 19h2"/>',
    banknote: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.4"/><path d="M6 12h.01M18 12h.01"/>',
    printer: '<path d="M6 9V3h12v6"/><path d="M6 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-1"/><rect x="8" y="14" width="8" height="7" rx="1"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    dollar: '<circle cx="12" cy="12" r="9"/><path d="M12 7v10"/><path d="M15 9.5A3 3 0 0 0 12 8c-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2a3 3 0 0 1-3-1.5"/>',
    tag: '<path d="M20.6 13.4 12 22l-9-9V4h9z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    truck: '<path d="M3 7h11v9H3z"/><path d="M14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="1.7"/><circle cx="17.5" cy="18" r="1.7"/>',
    store: '<path d="M3 9l1.6-5h14.8L21 9"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/>',
    package: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    boxes: '<path d="M3 8.5 7.5 6 12 8.5V14l-4.5 2.5L3 14z"/><path d="M12 8.5 16.5 6 21 8.5V14l-4.5 2.5L12 14z"/>',
    barChart: '<path d="M3 21h18"/><path d="M7 21v-8M12 21V6M17 21v-12"/>',
    wallet: '<path d="M3 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M16 12h4"/><path d="M3 8l9-4 9 4"/>',
    /* ---- business types (identical to web's marketing icons) ---- */
    coffee: '<path d="M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M17 9h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M6 3v2M10 3v2M14 3v2"/>',
    utensils: '<path d="M5 3v7a2 2 0 0 0 4 0V3"/><path d="M7 10v11"/><path d="M16.5 3c-1.4 1.7-2 3.2-2 4.8 0 1.4.8 2.4 2 2.4s2-1 2-2.4c0-1.6-.6-3.1-2-4.8z"/><path d="M16.5 10.2V21"/>',
    smartphone: '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
    phone: '<path d="M6 3h3l2 5-2.5 1.5a12 12 0 0 0 5 5L15 12l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z"/>',
    layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    /* ---- account / security ---- */
    lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.5"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l8-8"/><path d="M17 4l3 3M14.5 6.5l2 2"/>',
    mail: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 6.3A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1"/><path d="M6.6 6.7A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 4.4-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    /* ---- misc / status ---- */
    sparkles: '<path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z"/>',
    bell: '<path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    message: '<path d="M21 11.5a8.4 8.4 0 0 1-12 7.5L3 21l2-5.4A8.4 8.4 0 1 1 21 11.5z"/>',
    moon: '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>',
    alert: '<path d="M12 3l9 16H3z"/><path d="M12 9v5M12 17h.01"/>',
    party: '<path d="M3 21l6-14 8 8z"/><path d="M14 4l1 1M19 9l1 1M14.5 9.5 16 8M18 6l1.5-1.5M20 11l2-.5M11 3l.5-2"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v8h14v-8M12 8v12"/><path d="M12 8S10 4 7.5 4a2 2 0 0 0 0 4M12 8s2-4 4.5-4a2 2 0 0 1 0 4"/>',
    cornerDownRight: '<path d="M15 10l5 5-5 5"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
    arrowLeftRight: '<path d="M8 7l-4 4 4 4M16 17l4-4-4-4M4 11h16"/>',
    monitor: '<rect x="2" y="4" width="20" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    sliders: '<path d="M3 6h9M16 6h5M3 12h5M12 12h9M3 18h13M20 18h1"/><circle cx="14" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    creditCard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    undo: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>'
  };

  /* Placeholder glyph -> icon name. These are the characters actually present
     in the prototype markup; they are swapped for real SVGs on load. */
  var GLYPH = {
    '\u{1F50D}': 'search',      // 🔍
    '\u{1F4F7}': 'camera',      // 📷
    '\u25A3': 'scan',           // ▣
    '\u25A4': 'archive',        // ▤  (hold order)
    '\u25A5': 'boxes',          // ▥  (adjust stock)
    '\u25A6': 'barChart',       // ▦  (reports)
    '\u25A7': 'package',        // ▧  (products / help)
    '\uFF0B': 'plus',           // ＋
    '\u{1F6D2}': 'cart',        // 🛒
    '\u{1F4B5}': 'banknote',    // 💵
    '\u25A9': 'qr',             // ▩
    '\u2399': 'printer',        // ⎙
    '\u27F3': 'refresh',        // ⟳
    '\u270E': 'pencil',         // ✎
    '\u2913': 'download',       // ⤓
    '\u2912': 'upload',         // ⤒
    '\u2630': 'menu',           // ☰
    '\u{1F514}': 'bell',        // 🔔
    '\u{1F4AC}': 'message',     // 💬
    '\u2709': 'mail',           // ✉
    '\u{1F512}': 'lock',        // 🔒
    '\u{1F6E1}': 'shield',      // 🛡
    '\u{1F389}': 'party',       // 🎉
    '\u{1F441}': 'eye',         // 👁
    '\u263E': 'moon',           // ☾
    '\u2726': 'sparkles',       // ✦
    '\u2212': 'minus',          // −
    '\u260E': 'phone',          // ☎
    '\u2190': 'chevronLeft',    // ←
    '\u2191': 'arrowUpRight',   // ↑ (trend)
    '\u2192': 'arrowRight',     // →
    '\u25BE': 'chevronDown',    // ▾
    '\u2713': 'check',          // ✓
    '\u2715': 'x',              // ✕
    '\u2699': 'settings',       // ⚙
    '\u{1F464}': 'user',        // 👤
    '\u203A': 'chevronRight',   // ›
    '\u21B3': 'cornerDownRight',// ↳
    '\u20AA': 'qr',             // ₪
    '\u21C4': 'arrowLeftRight', // ⇄
    '\u2302': 'home',           // ⌂
    '\u2261': 'receipt',        // ≡
    '\u22EF': 'more',           // ⋯
    '\u2615': 'coffee',         // ☕
    '\u{1F37D}': 'utensils',    // 🍽
    '\u{1F4F1}': 'smartphone',  // 📱
    '\u{1F3EC}': 'store',       // 🏬
    '\u{1F511}': 'key',         // 🔑
    '\u{1F9FE}': 'receipt'      // 🧾
  };

  // 'archive' is used by Hold; register it explicitly.
  ICONS.archive = '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/>';

  function svg(name, cls) {
    return '<svg class="' + (cls || 'ic') + '" aria-hidden="true"><use href="#i-' + name + '"/></svg>';
  }

  function injectSprite() {
    if (document.getElementById('chmaba-icons')) return;
    var parts = ['<svg id="chmaba-icons" width="0" height="0" style="position:absolute" aria-hidden="true">'];
    Object.keys(ICONS).forEach(function (name) {
      parts.push(
        '<symbol id="i-' + name + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICONS[name] + '</symbol>'
      );
    });
    parts.push('</svg>');
    var holder = document.createElement('div');
    holder.innerHTML = parts.join('');
    document.body.insertBefore(holder.firstChild, document.body.firstChild);
  }

  var PATTERN = new RegExp('[' + Object.keys(GLYPH).join('') + ']', 'gu');

  function swapTextNodes(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var text = node.nodeValue;
      if (!text) return;
      PATTERN.lastIndex = 0;
      if (!PATTERN.test(text)) return;

      var frag = document.createDocumentFragment();
      var last = 0;
      var m;
      PATTERN.lastIndex = 0;
      while ((m = PATTERN.exec(text)) !== null) {
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        var name = GLYPH[m[0]];
        if (name && ICONS[name]) {
          var span = document.createElement('span');
          span.className = 'ico';
          span.innerHTML = svg(name);
          frag.appendChild(span);
        } else {
          frag.appendChild(document.createTextNode(m[0]));
        }
        last = m.index + m[0].length;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  function fillDecorative(root) {
    root.querySelectorAll('[data-i]').forEach(function (el) {
      el.innerHTML = svg(el.getAttribute('data-i'));
    });
  }

  function run() {
    injectSprite();
    fillDecorative(document);
    swapTextNodes(document.body);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }

  window.ChmabaIcons = { svg: svg, names: Object.keys(ICONS) };
})();
