#!/usr/bin/env python3
"""Render a proof sheet of the ChmabaIcon path data straight out of ChmabaIcons.swift.

This does NOT exercise the Swift parser -- it renders the raw path strings with a
reference SVG renderer. That isolates the ported DATA from the PARSER: if a glyph is
wrong here, the path string itself is wrong or missing; if every glyph is right here but
the app looks wrong, the parser is at fault. Those are different bugs with different
fixes, so it is worth being able to tell them apart.

Usage: python3 91-icon-proof-sheet.py <ChmabaIcons.swift> <out.svg>
"""
import re
import sys


def extract(swift_path):
    """Pull `case .name: return [ "..." , ... ]` blocks out of the paths switch."""
    src = open(swift_path, encoding="utf-8").read()

    # Only the `var paths: [String] { switch self { ... } }` body.
    start = src.find("var paths: [String] {")
    if start == -1:
        sys.exit("could not find `var paths: [String] {` in %s" % swift_path)
    body = src[start:]

    icons = []
    # case .home: return ["M3 10.5 ..."]
    # case .cart: return [\n  "M...",\n  "M...",\n]
    for m in re.finditer(r"case\s+\.(\w+)\s*:\s*return\s*\[(.*?)\]", body, re.S):
        name = m.group(1)
        paths = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))
        if paths:
            icons.append((name, paths))
    return icons


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(icons, cols=9, cell=74, icon_box=48, pad=8):
    rows = (len(icons) + cols - 1) // cols
    w = cols * cell
    h = rows * cell

    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">' % (w, h, w, h)
    )
    # NOTE: these are plain string literals, not %-formatted, so a literal percent must be
    # a single `%`. Writing `100%%` here yields an invalid rect and a transparent
    # background, which is exactly what silently broke the first differential diff.
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')

    scale = icon_box / 24.0
    for i, (name, paths) in enumerate(icons):
        cx = (i % cols) * cell
        cy = (i // cols) * cell
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" '
                     'stroke="#dddddd" stroke-width="1"/>' % (cx, cy, cell, cell))

        tx = cx + pad
        ty = cy + pad
        parts.append('<g transform="translate(%.3f,%.3f) scale(%.4f)">' % (tx, ty, scale))
        for d in paths:
            # Match the app's stroke treatment: 24x24 viewport, width 2, round caps/joins.
            parts.append(
                '<path d="%s" fill="none" stroke="#16171d" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/>' % esc(d)
            )
        parts.append('</g>')

        # Name label, shrunk so long names fit the cell.
        size = 9 if len(name) <= 11 else 7
        parts.append(
            '<text x="%d" y="%d" font-family="DejaVu Sans, sans-serif" font-size="%d" '
            'fill="#666666" text-anchor="middle">%s</text>'
            % (cx + cell // 2, cy + cell - 3, size, esc(name))
        )

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    icons = extract(sys.argv[1])
    if not icons:
        sys.exit("no icons extracted -- the Swift format may have changed")
    open(sys.argv[2], "w", encoding="utf-8").write(build_svg(icons))
    print("extracted %d icons" % len(icons))
    missing = [n for n, p in icons if not p or all(not s.strip() for s in p)]
    if missing:
        print("EMPTY PATH DATA: %s" % ", ".join(missing))
    names = [n for n, _ in icons]
    dups = {n for n in names if names.count(n) > 1}
    if dups:
        print("DUPLICATE CASES: %s" % ", ".join(sorted(dups)))


if __name__ == "__main__":
    main()
