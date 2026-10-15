import SwiftUI

// Lucide icon parity.
//
// The web app draws every icon from Lucide -- 24x24, stroke width 2, round caps and
// joins. `SCREENS.md` is explicit that the icon set must not change, and Material or SF
// Symbols look noticeably different. So the SAME path data the web and Android use is
// rendered here, ported from apps/android/.../ui/icons/ChmabaIcons.kt, which in turn
// mirrors apps/android/prototype/icons.js.
//
// iOS has no SVG support, so this includes a small path-data parser. It handles the
// commands Lucide actually uses, including elliptical arcs -- `a1.4 1.4 0 1 1-2.8 0`
// appears in the cart, more, sliders and several other icons, so arc support is not
// optional.

// MARK: - Path data parser

enum SVGPathParser {
    private enum Token {
        case command(Character)
        case number(Double)
    }

    static func path(from d: String) -> Path {
        var path = Path()
        let tokens = tokenize(d)

        var index = 0
        var current = CGPoint.zero
        var subpathStart = CGPoint.zero
        var lastControl: CGPoint?
        var command: Character = " "

        func number() -> Double {
            if index < tokens.count, case let .number(value) = tokens[index] {
                index += 1
                return value
            }
            return 0
        }

        func point(relative: Bool) -> CGPoint {
            let x = number(), y = number()
            return relative
                ? CGPoint(x: current.x + x, y: current.y + y)
                : CGPoint(x: x, y: y)
        }

        while index < tokens.count {
            if case let .command(c) = tokens[index] {
                command = c
                index += 1
            }

            let relative = command.isLowercase
            let upper = Character(command.uppercased())

            switch upper {
            case "M":
                let p = point(relative: relative)
                path.move(to: p)
                current = p
                subpathStart = p
                lastControl = nil
                // A moveto followed by more pairs is an implicit lineto.
                command = relative ? "l" : "L"

            case "L":
                let p = point(relative: relative)
                path.addLine(to: p)
                current = p
                lastControl = nil

            case "H":
                let x = number()
                let p = CGPoint(x: relative ? current.x + x : x, y: current.y)
                path.addLine(to: p)
                current = p
                lastControl = nil

            case "V":
                let y = number()
                let p = CGPoint(x: current.x, y: relative ? current.y + y : y)
                path.addLine(to: p)
                current = p
                lastControl = nil

            case "C":
                let c1 = point(relative: relative)
                let c2 = point(relative: relative)
                let end = point(relative: relative)
                path.addCurve(to: end, control1: c1, control2: c2)
                lastControl = c2
                current = end

            case "S":
                // Reflect the previous control point when the last command was a cubic.
                let reflected: CGPoint
                if let last = lastControl {
                    reflected = CGPoint(x: 2 * current.x - last.x, y: 2 * current.y - last.y)
                } else {
                    reflected = current
                }
                let c2 = point(relative: relative)
                let end = point(relative: relative)
                path.addCurve(to: end, control1: reflected, control2: c2)
                lastControl = c2
                current = end

            case "A":
                let rx = number(), ry = number()
                let rotation = number()
                let largeArc = number() != 0
                let sweep = number() != 0
                let end = point(relative: relative)
                appendArc(
                    to: &path, from: current, to: end,
                    rx: rx, ry: ry, rotation: rotation,
                    largeArc: largeArc, sweep: sweep
                )
                current = end
                lastControl = nil

            case "Z":
                path.closeSubpath()
                current = subpathStart
                lastControl = nil

            default:
                // Unknown command: skip its arguments rather than spin.
                index = tokens.count
            }
        }
        return path
    }

    /// Endpoint-parameterisation arc to cubic beziers, following the SVG spec F.6.
    private static func appendArc(
        to path: inout Path,
        from start: CGPoint,
        to end: CGPoint,
        rx: Double, ry: Double,
        rotation: Double,
        largeArc: Bool, sweep: Bool
    ) {
        var rx = abs(rx), ry = abs(ry)
        if rx == 0 || ry == 0 || (start == end) {
            path.addLine(to: end)
            return
        }

        let phi = rotation * .pi / 180
        let cosPhi = cos(phi), sinPhi = sin(phi)

        let dx2 = (start.x - end.x) / 2
        let dy2 = (start.y - end.y) / 2
        let x1p = cosPhi * dx2 + sinPhi * dy2
        let y1p = -sinPhi * dx2 + cosPhi * dy2

        // Scale the radii up if they are too small to span the endpoints.
        let lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
        if lambda > 1 {
            let scale = sqrt(lambda)
            rx *= scale
            ry *= scale
        }

        let rxSq = rx * rx, rySq = ry * ry
        let numerator = rxSq * rySq - rxSq * y1p * y1p - rySq * x1p * x1p
        let denominator = rxSq * y1p * y1p + rySq * x1p * x1p
        let factor = (largeArc != sweep ? 1.0 : -1.0)
            * sqrt(max(0, numerator / denominator))

        let cxp = factor * rx * y1p / ry
        let cyp = -factor * ry * x1p / rx
        let cx = cosPhi * cxp - sinPhi * cyp + (start.x + end.x) / 2
        let cy = sinPhi * cxp + cosPhi * cyp + (start.y + end.y) / 2

        func angle(_ ux: Double, _ uy: Double, _ vx: Double, _ vy: Double) -> Double {
            let dot = ux * vx + uy * vy
            let length = sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy))
            guard length > 0 else { return 0 }
            var result = acos(max(-1, min(1, dot / length)))
            if ux * vy - uy * vx < 0 { result = -result }
            return result
        }

        let ux = (x1p - cxp) / rx, uy = (y1p - cyp) / ry
        let vx = (-x1p - cxp) / rx, vy = (-y1p - cyp) / ry

        let theta1 = angle(1, 0, ux, uy)
        var deltaTheta = angle(ux, uy, vx, vy)
        if !sweep && deltaTheta > 0 { deltaTheta -= 2 * .pi }
        if sweep && deltaTheta < 0 { deltaTheta += 2 * .pi }

        // Split into segments of at most 90 degrees.
        let segments = max(1, Int(ceil(abs(deltaTheta) / (.pi / 2))))
        let delta = deltaTheta / Double(segments)
        let handle = 4.0 / 3.0 * tan(delta / 4)

        func pointOnArc(_ a: Double) -> CGPoint {
            CGPoint(
                x: cx + rx * cos(a) * cosPhi - ry * sin(a) * sinPhi,
                y: cy + rx * cos(a) * sinPhi + ry * sin(a) * cosPhi
            )
        }

        func derivative(_ a: Double) -> CGPoint {
            CGPoint(
                x: -rx * sin(a) * cosPhi - ry * cos(a) * sinPhi,
                y: -rx * sin(a) * sinPhi + ry * cos(a) * cosPhi
            )
        }

        var segmentStart = start
        var angleStart = theta1
        for _ in 0..<segments {
            let angleEnd = angleStart + delta
            let endPoint = pointOnArc(angleEnd)
            let d1 = derivative(angleStart)
            let d2 = derivative(angleEnd)
            path.addCurve(
                to: endPoint,
                control1: CGPoint(x: segmentStart.x + handle * d1.x, y: segmentStart.y + handle * d1.y),
                control2: CGPoint(x: endPoint.x - handle * d2.x, y: endPoint.y - handle * d2.y)
            )
            segmentStart = endPoint
            angleStart = angleEnd
        }
    }

    private static func tokenize(_ d: String) -> [Token] {
        var tokens: [Token] = []
        var buffer = ""
        var previous: Character?

        func flush() {
            if !buffer.isEmpty, let value = Double(buffer) { tokens.append(.number(value)) }
            buffer = ""
        }

        for character in d {
            if character.isLetter, character != "e", character != "E" {
                flush()
                tokens.append(.command(character))
            } else if character == "e" || character == "E" {
                // Exponent, not a command -- only valid straight after a digit.
                if let p = previous, p.isNumber { buffer.append(character) }
            } else if character == " " || character == "," || character == "\n" || character == "\t" {
                flush()
            } else if (character == "-" || character == "+"), !buffer.isEmpty,
                      !buffer.hasSuffix("e"), !buffer.hasSuffix("E") {
                // A sign after a value starts a new number, not part of this one.
                flush()
                buffer.append(character)
            } else if character == "." && buffer.contains(".") {
                flush()
                buffer.append(character)
            } else {
                buffer.append(character)
            }
            previous = character
        }
        flush()
        return tokens
    }
}

// MARK: - The icon set

/// One Lucide icon. `paths` are the exact strings used by the web and Android clients.
enum ChmabaIcon: String, CaseIterable {
    // navigation
    case home, cart, receipt, more, menu, sliders
    // search / capture
    case search, scan, camera
    // actions
    case plus, minus, close, check, chevronRight, chevronLeft, chevronDown
    case arrowRight, arrowUpRight, refresh, download, upload, pencil, trash
    case copy, share, undo, filter, percent
    // people
    case user, userPlus, users
    // commerce
    case qr, banknote, printer, creditCard, dollar, tag, truck, store, package
    case archive, boxes, barChart, wallet, layers, coffee, utensils, smartphone
    case phone, monitor, calendar, image, clock
    // account / security
    case lock, key, mail, shield, eye, eyeOff
    // misc / status
    case sparkles, bell, message, moon, alert, party, gift
    case cornerDownRight, arrowLeftRight, signal, wifi, battery

    var paths: [String] {
        switch self {
        case .home: return ["M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"]
        case .cart: return [
            "M10.4 20a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
            "M20.4 20a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
            "M2 3h2.2l2.4 12.2a2 2 0 0 0 2 1.6h9.6a2 2 0 0 0 2-1.6L21 7H5.6",
        ]
        case .receipt: return ["M5 2h14v20l-3-2-2 2-2-2-2 2-3-2z", "M9 7h6M9 11h6M9 15h4"]
        case .more: return [
            "M13.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
            "M20.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
            "M6.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
        ]
        case .menu: return ["M4 6h16M4 12h16M4 18h16"]
        case .sliders: return [
            "M3 6h9M16 6h5M3 12h5M12 12h9M3 18h13M20 18h1",
            "M16 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
            "M11 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
            "M20 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
        ]
        case .search: return ["M18 11a7 7 0 1 1-14 0 7 7 0 0 1 14 0z", "M20.5 20.5 16.7 16.7"]
        case .scan: return ["M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"]
        case .camera: return [
            "M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z",
            "M15 13a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
        ]
        case .plus: return ["M12 5v14M5 12h14"]
        case .minus: return ["M5 12h14"]
        case .close: return ["M6 6l12 12M18 6 6 18"]
        case .check: return ["M20 6 9 17l-5-5"]
        case .chevronRight: return ["M9 6l6 6-6 6"]
        case .chevronLeft: return ["M15 6l-6 6 6 6"]
        case .chevronDown: return ["M6 9l6 6 6-6"]
        case .arrowRight: return ["M5 12h14M13 6l6 6-6 6"]
        case .arrowUpRight: return ["M7 17 17 7M9 7h8v8"]
        case .refresh: return ["M21 12a9 9 0 1 1-2.6-6.4", "M21 4v5h-5"]
        case .download: return ["M12 3v12M7 10l5 5 5-5M4 21h16"]
        case .upload: return ["M12 21V9M7 14l5-5 5 5M4 3h16"]
        case .pencil: return ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"]
        case .trash: return ["M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"]
        case .copy: return [
            "M11 9h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H11a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2z",
            "M5 15V5a2 2 0 0 1 2-2h10",
        ]
        case .share: return ["M12 3v12M8 7l4-4 4 4", "M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"]
        case .undo: return ["M3 12a9 9 0 1 0 3-6.7", "M3 4v5h5"]
        case .filter: return ["M3 5h18l-7 8v6l-4-2v-4z"]
        case .percent: return [
            "M19 5 5 19",
            "M9 6.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z",
            "M20 17.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z",
        ]
        case .user: return ["M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z", "M4 21a8 8 0 0 1 16 0"]
        case .userPlus: return [
            "M13 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
            "M2 21a7 7 0 0 1 12-4.9",
            "M19 8v6M16 11h6",
        ]
        case .users: return [
            "M13 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
            "M2 21a7 7 0 0 1 14 0",
            "M17 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4.5-5.8",
        ]
        case .qr: return [
            "M4 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z",
            "M15 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z",
            "M4 14h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z",
            "M14 14h3v3h-3zM19 14h2M14 19h2M19 19h2",
        ]
        case .banknote: return [
            "M4 6h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
            "M14.4 12a2.4 2.4 0 1 1-4.8 0 2.4 2.4 0 0 1 4.8 0z",
            "M6 12h.01M18 12h.01",
        ]
        case .printer: return [
            "M6 9V3h12v6",
            "M6 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-1",
            "M9 14h6a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z",
        ]
        case .creditCard: return [
            "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
            "M2 10h20",
        ]
        case .dollar: return [
            "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
            "M12 7v10",
            "M15 9.5A3 3 0 0 0 12 8c-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2a3 3 0 0 1-3-1.5",
        ]
        case .tag: return [
            "M20.6 13.4 12 22l-9-9V4h9z",
            "M8.8 7.5a1.3 1.3 0 1 1-2.6 0 1.3 1.3 0 0 1 2.6 0z",
        ]
        case .truck: return [
            "M3 7h11v9H3z",
            "M14 10h4l3 3v3h-7z",
            "M8.7 18a1.7 1.7 0 1 1-3.4 0 1.7 1.7 0 0 1 3.4 0z",
            "M19.2 18a1.7 1.7 0 1 1-3.4 0 1.7 1.7 0 0 1 3.4 0z",
        ]
        case .store: return ["M3 9l1.6-5h14.8L21 9", "M4 9v11h16V9", "M9 20v-6h6v6"]
        case .package: return ["M21 8 12 3 3 8v8l9 5 9-5z", "M3 8l9 5 9-5M12 13v8"]
        case .archive: return [
            "M4 4h16a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z",
            "M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8",
            "M10 12h4",
        ]
        case .boxes: return [
            "M3 8.5 7.5 6 12 8.5V14l-4.5 2.5L3 14z",
            "M12 8.5 16.5 6 21 8.5V14l-4.5 2.5L12 14z",
        ]
        case .barChart: return ["M3 21h18", "M7 21v-8M12 21V6M17 21v-12"]
        case .wallet: return [
            "M5 6h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
            "M16 12h4",
            "M3 8l9-4 9 4",
        ]
        case .layers: return ["M12 3l9 5-9 5-9-5z", "M3 13l9 5 9-5"]
        case .coffee: return [
            "M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z",
            "M17 9h1.5a2.5 2.5 0 0 1 0 5H17",
            "M6 3v2M10 3v2M14 3v2",
        ]
        case .utensils: return [
            "M5 3v7a2 2 0 0 0 4 0V3",
            "M7 10v11",
            "M16.5 3c-1.4 1.7-2 3.2-2 4.8 0 1.4.8 2.4 2 2.4s2-1 2-2.4c0-1.6-.6-3.1-2-4.8z",
            "M16.5 10.2V21",
        ]
        case .smartphone: return [
            "M8 2h8a2.5 2.5 0 0 1 2.5 2.5v15A2.5 2.5 0 0 1 16 22H8a2.5 2.5 0 0 1-2.5-2.5v-15A2.5 2.5 0 0 1 8 2z",
            "M11 18h2",
        ]
        case .phone: return ["M6 3h3l2 5-2.5 1.5a12 12 0 0 0 5 5L15 12l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z"]
        case .monitor: return [
            "M4 4h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
            "M8 20h8M12 16v4",
        ]
        case .calendar: return [
            "M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
            "M8 3v4M16 3v4M3 11h18",
        ]
        case .image: return [
            "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z",
            "M10 8.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z",
            "M21 15l-5-5L5 21",
        ]
        case .clock: return ["M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z", "M12 7v5l3 2"]
        case .lock: return [
            "M6 10h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z",
            "M8 10V7a4 4 0 0 1 8 0v3",
            "M13.5 15.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z",
        ]
        case .key: return ["M12 15a4 4 0 1 1-8 0 4 4 0 0 1 8 0z", "M11 12l8-8", "M17 4l3 3M14.5 6.5l2 2"]
        case .mail: return [
            "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
            "M3 7l9 6 9-6",
        ]
        case .shield: return ["M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z", "M9 12l2 2 4-4"]
        case .eye: return [
            "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z",
            "M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
        ]
        case .eyeOff: return [
            "M3 3l18 18",
            "M10.6 6.3A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1",
            "M6.6 6.7A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 4.4-1",
            "M9.9 9.9a3 3 0 0 0 4.2 4.2",
        ]
        case .sparkles: return [
            "M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z",
            "M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z",
        ]
        case .bell: return ["M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6", "M10 20a2 2 0 0 0 4 0"]
        case .message: return ["M21 11.5a8.4 8.4 0 0 1-12 7.5L3 21l2-5.4A8.4 8.4 0 1 1 21 11.5z"]
        case .moon: return ["M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"]
        case .alert: return ["M12 3l9 16H3z", "M12 9v5M12 17h.01"]
        case .party: return [
            "M3 21l6-14 8 8z",
            "M14 4l1 1M19 9l1 1M14.5 9.5 16 8M18 6l1.5-1.5M20 11l2-.5M11 3l.5-2",
        ]
        case .gift: return [
            "M4 8h16a1 1 0 0 1 1 1v3H3V9a1 1 0 0 1 1-1z",
            "M5 12v8h14v-8M12 8v12",
            "M12 8S10 4 7.5 4a2 2 0 0 0 0 4M12 8s2-4 4.5-4a2 2 0 0 1 0 4",
        ]
        case .cornerDownRight: return ["M15 10l5 5-5 5", "M4 4v7a4 4 0 0 0 4 4h12"]
        case .arrowLeftRight: return ["M8 7l-4 4 4 4M16 17l4-4-4-4M4 11h16"]
        case .signal: return ["M4 20v-4M9 20v-8M14 20v-12M19 20V4"]
        case .wifi: return [
            "M2 8.5a15 15 0 0 1 20 0",
            "M5.5 12.5a10 10 0 0 1 13 0",
            "M9 16.5a5 5 0 0 1 6 0",
        ]
        case .battery: return [
            "M4 8h13a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z",
            "M21 11v2",
        ]
        }
    }
}

// MARK: - Rendering

/// Renders a Lucide icon with the web's stroke treatment: 24x24 viewport, stroke 2,
/// round caps and joins, no fill.
struct ChmabaIconView: View {
    let icon: ChmabaIcon
    var size: CGFloat = 24
    var color: Color = ChmabaColor.textPrimary
    /// Stroke width in viewport units (the prototype always uses 2).
    var lineWidth: CGFloat = 2

    var body: some View {
        Canvas { context, canvasSize in
            let scale = min(canvasSize.width, canvasSize.height) / 24
            let transform = CGAffineTransform(scaleX: scale, y: scale)
            var combined = Path()
            for d in icon.paths {
                combined.addPath(SVGPathParser.path(from: d))
            }
            context.stroke(
                combined.applying(transform),
                with: .color(color),
                style: StrokeStyle(
                    lineWidth: lineWidth * scale,
                    lineCap: .round,
                    lineJoin: .round
                )
            )
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

/// Convenience so a call site reads like the rest of the app.
struct ChmabaIconLabel: View {
    let icon: ChmabaIcon
    var size: CGFloat = 20
    var color: Color = ChmabaColor.textPrimary

    var body: some View {
        ChmabaIconView(icon: icon, size: size, color: color)
    }
}
