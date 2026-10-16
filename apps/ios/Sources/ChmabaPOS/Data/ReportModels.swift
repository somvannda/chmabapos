import Foundation

// Reporting DTOs, mirroring apps/android/.../data/reports/Reports.kt, which in turn
// mirrors ReportSummary in chmabapos_api/app/schemas.py.
//
// NOTE the breakdown lists (top_products, daily_sales, category_sales,
// payment_methods) are UNTYPED dicts server-side -- their keys are only documented in
// the Android DTO and the web helpers. Reading that file before writing this one is
// what surfaced the real field names.

// MARK: - Periods

/// Reporting windows. Mirrors `ReportPeriod` in the Android client, which mirrors the
/// web presets: apps/web/src/lib/dashboard.js and features/reports.jsx.
enum ReportPeriod: String, CaseIterable, Hashable {
    case today, last7, last30, thisMonth, allTime

    var label: String {
        switch self {
        case .today: return "Today"
        case .last7: return "Last 7 days"
        case .last30: return "Last 30 days"
        case .thisMonth: return "This month"
        case .allTime: return "All time"
        }
    }

    var from: String {
        switch self {
        case .today: return Self.dayISO(daysAgo: 0)
        case .last7: return Self.dayISO(daysAgo: 6)
        case .last30: return Self.dayISO(daysAgo: 29)
        case .thisMonth: return Self.monthStartISO()
        case .allTime: return "1970-01-01"
        }
    }

    /// All time sends no upper bound, matching the Android client.
    var to: String? {
        switch self {
        case .allTime: return nil
        default: return Self.dayISO(daysAgo: 0)
        }
    }

    private static func dayISO(daysAgo: Int) -> String {
        let calendar = Calendar.current
        let date = calendar.date(byAdding: .day, value: -daysAgo, to: Date()) ?? Date()
        return isoFormatter.string(from: date)
    }

    private static func monthStartISO() -> String {
        let calendar = Calendar.current
        let components = calendar.dateComponents([.year, .month], from: Date())
        let first = calendar.date(from: components) ?? Date()
        return isoFormatter.string(from: first)
    }

    private static let isoFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter
    }()
}

/// The Dashboard's own three presets, narrower than the Reports screen's five.
enum DashboardPeriod: String, CaseIterable, Hashable {
    case today, week, thisMonth

    var title: String {
        switch self {
        case .today: return "Today"
        case .week: return "Last 7 days"
        case .thisMonth: return "This month"
        }
    }

    var reportPeriod: ReportPeriod {
        switch self {
        case .today: return .today
        case .week: return .last7
        case .thisMonth: return .thisMonth
        }
    }
}

// MARK: - Payload

struct TopProduct: Codable, Sendable {
    let name: String?
    let quantity: Double
    let amount: String?

    /// `amount` is a decimal string like every other money field.
    var value: Double { amount.flatMap(Double.init) ?? 0 }
    var units: Int { Int(quantity.rounded()) }
    var displayName: String { name ?? "Unnamed" }
}

struct MixRow: Codable, Sendable {
    let method: String?
    let category: String?
    let name: String?
    let amount: String?

    /// The web labels a mix row `method ?? category ?? name`.
    var label: String { method ?? category ?? name ?? "Other" }
    var value: Double { amount.flatMap(Double.init) ?? 0 }
}

struct DailySale: Codable, Sendable {
    let date: String?
    let amount: String?
    var value: Double { amount.flatMap(Double.init) ?? 0 }
}

struct ReportTransaction: Codable, Sendable {
    let id: String?
    let orderNumber: String?
    let status: String?
    let customerName: String?
    let currencyCode: String?
    let total: String?
    let itemsCount: Int
    let unitsCount: Int
    let paymentMethod: String?
    let createdAt: String?

    var totalValue: Double { total.flatMap(Double.init) ?? 0 }

    /// "10:42 AM". `created_at` is UTC; the Android client also parses it as UTC and
    /// renders in the device zone, because the store's zone is not available
    /// client-side. Same behaviour here, same caveat.
    var timeLabel: String {
        guard let createdAt, createdAt.count >= 19 else { return "—" }
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        guard let date = parser.date(from: String(createdAt.prefix(19))) else { return "—" }
        let clock = DateFormatter()
        clock.dateFormat = "h:mm a"
        clock.locale = Locale(identifier: "en_US_POSIX")
        return clock.string(from: date)
    }

    var badgeTone: BadgeTone {
        switch paymentMethod?.lowercased() {
        case "khqr": return .violet
        case "cash": return .green
        default: return .neutral
        }
    }

    var methodLabel: String { paymentMethod?.uppercased() ?? "—" }
}

struct ReportSummary: Codable, Sendable {
    let fromDate: String?
    let toDate: String?
    let grossSales: String?
    let netSales: String?
    let netAfterRefunds: String?
    let tax: String?
    let discounts: String?
    let refunds: String?
    let refundsCount: Int
    let transactions: Int
    let averageOrder: String?
    let itemsSold: Double
    let daysInPeriod: Int
    let averageDailyNet: String?
    let projectedNext30Days: String?
    let topProducts: [TopProduct]
    let dailySales: [DailySale]
    let categorySales: [MixRow]
    let paymentMethods: [MixRow]
    let transactionsDetail: [ReportTransaction]

    /// The headline the web uses first: net after refunds, falling back to net sales
    /// (`net_after_refunds ?? net_sales`). Reading Reports.kt is what surfaced that.
    var effectiveNet: Decimal {
        decimal(netAfterRefunds ?? netSales ?? "0.00")
    }

    /// Taken from the payload rather than assumed, so a non-USD store is right.
    var currency: String { transactionsDetail.first?.currencyCode ?? "USD" }

    var averagePerDay: Double {
        daysInPeriod > 0 ? Double(transactions) / Double(daysInPeriod) : 0
    }

    private func decimal(_ raw: String) -> Decimal { Decimal(string: raw) ?? 0 }
}

/// One ranked row of a breakdown, carrying its share of the total.
struct MixShare: Identifiable, Hashable {
    let label: String
    let amount: Double
    let percent: Int
    var id: String { label }
}

/// Mirrors the web's `salesMix`: drop zero rows, rank descending, keep `limit`, and
/// express each as a share of the *kept* rows rather than of everything.
func salesMix(_ rows: [MixRow], limit: Int = 5) -> [MixShare] {
    let clean = rows
        .map { ($0.label, $0.value) }
        .filter { $0.1 > 0 }
        .sorted { $0.1 > $1.1 }
    let total = clean.reduce(0) { $0 + $1.1 }
    return clean.prefix(limit).map { label, amount in
        MixShare(
            label: label,
            amount: amount,
            percent: total > 0 ? Int(((amount / total) * 100).rounded()) : 0
        )
    }
}
