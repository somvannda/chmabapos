#!/bin/bash
# Verifies the Lucide icon port in apps/ios without a Mac.
#
# Why this exists
# ---------------
# apps/ios has no SVG runtime, so ChmabaIcons.swift carries its own path-data parser, and
# SCREENS.md forbids changing the icon set. That makes the parser load-bearing and, until
# this script, completely untested: it could only be checked by building for a device and
# looking at the screen.
#
# How it works
# ------------
# The parser and the icon path data are the only parts of ChmabaIcons.swift that do not
# need SwiftUI -- they touch it solely through the `import` and the `Path` type. So this
# script takes the real source text up to the "// MARK: - Rendering" boundary, swaps the
# import for a Path that records the geometry calls, and compiles THAT with a host swiftc.
# It is the actual parser, not a reimplementation, so it cannot drift from the app.
#
# Then two independent checks:
#   1. Geometry assertions -- no NaN, nothing outside the 24x24 grid, all 71 icons present.
#   2. Differential pixel diff -- the same raw path data is drawn by rsvg (a reference SVG
#      implementation) and by this parser; both renders are rasterised and compared. The
#      path data itself is proven correct by construction (it is what the web and Android
#      draw), so a zero diff means the parser is faithful.
#
# Requirements: bash, python3, swiftc on PATH (or swiftly at the default location), and
# rsvg-convert. All are ordinary packages, so this can run in CI on Linux -- no Xcode.
#
# Usage: apps/ios/scripts/verify-icons.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "$HERE/.." && pwd)"
SWIFT_SRC="$IOS_DIR/Sources/ChmabaPOS/Design/ChmabaIcons.swift"

OUTDIR="${1:-$(mktemp -d)}"
BUILD="$OUTDIR/host"
mkdir -p "$BUILD"

for tool in python3 swiftc rsvg-convert; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "missing required tool: $tool" >&2
        echo "(swiftc may need to be added to PATH -- see the toolchain step in apps/ios/README)" >&2
        exit 2
    fi
done

echo "############ 1. reference render of the raw path data ############"
python3 "$HERE/icon-reference-sheet.py" "$SWIFT_SRC" "$OUTDIR/reference.svg"
rsvg-convert -w 1332 "$OUTDIR/reference.svg" -o "$OUTDIR/reference.png"

echo
echo "############ 2. host-compiled parser render ############"
# Find the end of the parser + icon data rather than hard-coding a line number: any edit to
# the parser shifts everything, and a hard-coded cut silently truncates the enum mid-switch.
CUT=$(grep -n '^// MARK: - Rendering' "$SWIFT_SRC" | head -1 | cut -d: -f1)
if [ -z "$CUT" ]; then
    echo "could not find the '// MARK: - Rendering' boundary in $SWIFT_SRC" >&2
    exit 1
fi
CUT=$((CUT - 1))
echo "extracting lines 1..$CUT (parser + icon data)"

{
cat <<'SHIM'
import Foundation

/// Records the geometry the real renderer would have drawn. Identical calls, so the
/// parser's arithmetic -- including the arc-to-bezier conversion -- is exercised in full.
struct Path {
    private(set) var d: [String] = []
    private var start = CGPoint.zero
    mutating func move(to p: CGPoint) { d.append("M \(f(p.x)) \(f(p.y))"); start = p }
    mutating func addLine(to p: CGPoint) { d.append("L \(f(p.x)) \(f(p.y))") }
    mutating func addCurve(to p: CGPoint, control1 c1: CGPoint, control2 c2: CGPoint) {
        d.append("C \(f(c1.x)) \(f(c1.y)) \(f(c2.x)) \(f(c2.y)) \(f(p.x)) \(f(p.y))")
    }
    mutating func closeSubpath() { d.append("Z") }
    private func f(_ v: Double) -> String { String(format: "%.4f", v) }
}
SHIM
# Drop the original `import SwiftUI`.
sed -n "2,${CUT}p" "$SWIFT_SRC"
} > "$BUILD/main.swift"

cat <<'MAIN' >> "$BUILD/main.swift"

// Regression: malformed input must terminate. A numeric argument after `Z` consumes no
// token, so without a guard the parse loop spins forever. A hang is silent and happens on
// the main thread, so it is asserted before anything else -- if the guard regresses this
// process never reaches the SVG step and the job fails loudly.
for hostile in ["M0 0 L1 1 Z 5 5", "M0 0Z1 1", "Z", "M0 0", "L5 5"] {
    let parsed = SVGPathParser.path(from: hostile)
    print("hostile \(hostile.debugDescription) -> \(parsed.d.count) commands, terminated")
}

// Emit a proof sheet laid out identically to icon-reference-sheet.py so the two renders
// are comparable pixel for pixel.
let cols = 9, cell = 74.0, iconBox = 48.0, pad = 8.0
let icons = ChmabaIcon.allCases
let rows = (icons.count + cols - 1) / cols
let w = Double(cols) * cell, h = Double(rows) * cell
let scale = iconBox / 24.0

var svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="\(Int(w))" height="\(Int(h))" viewBox="0 0 \(Int(w)) \(Int(h))">
<rect width="100%" height="100%" fill="#ffffff"/>
"""

for (i, icon) in icons.enumerated() {
    let cx = Double(i % cols) * cell
    let cy = Double(i / cols) * cell
    svg += "<rect x=\"\(Int(cx))\" y=\"\(Int(cy))\" width=\"\(Int(cell))\" height=\"\(Int(cell))\" fill=\"none\" stroke=\"#dddddd\" stroke-width=\"1\"/>\n"
    svg += "<g transform=\"translate(\(cx + pad),\(cy + pad)) scale(\(scale))\">"
    for d in icon.paths {
        let path = SVGPathParser.path(from: d)
        svg += "<path d=\"\(path.d.joined(separator: " "))\" fill=\"none\" stroke=\"#16171d\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n"
    }
    svg += "</g>\n"
    let name = icon.rawValue
    let size = name.count <= 11 ? 9 : 7
    svg += "<text x=\"\(Int(cx + cell / 2))\" y=\"\(Int(cy + cell - 3))\" font-family=\"DejaVu Sans, sans-serif\" font-size=\"\(size)\" fill=\"#666666\" text-anchor=\"middle\">\(name)</text>\n"
}
svg += "</svg>\n"
try! svg.write(toFile: CommandLine.arguments[1], atomically: true, encoding: .utf8)
print("wrote \(icons.count) icons")
MAIN

swiftc -O -o "$BUILD/icontest" "$BUILD/main.swift"
"$BUILD/icontest" "$OUTDIR/parser.svg"
rsvg-convert -w 1332 "$OUTDIR/parser.svg" -o "$OUTDIR/parser.png"

echo
echo "############ 3. verification ############"
python3 "$HERE/verify-icons.py" "$OUTDIR/parser.svg" "$OUTDIR/reference.png" "$OUTDIR/parser.png"

echo
echo "proof sheets left in $OUTDIR"
