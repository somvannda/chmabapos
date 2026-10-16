import SwiftUI

/// Activity — what the team changed, newest first. Ported from
/// `apps/android/.../screens/activity/ActivityScreen.kt`.
///
/// Reads `GET /audit-logs`, which returns the same entries the web Activity page shows and
/// requires an owner or manager role. The endpoint declares no response model, so
/// `AuditEntry` mirrors the dict it actually sends.
///
/// `details` is rendered as the key/value pairs the API sent rather than mapped onto fixed
/// columns, because the keys differ per action: an inventory adjustment carries a product
/// and a quantity, a settings change carries rules. Fixed columns would be blank for most
/// actions.
struct ActivityView: View {
    let onBack: () -> Void

    @State private var entries: [AuditEntry] = []
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar {
            VStack(alignment: .leading, spacing: 2) {
                Text("Activity")
                    .font(.system(size: 20, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("Recent changes made by your team across the workspace.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading activity…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if entries.isEmpty {
            noticeLine("Nothing has been changed yet.")
        } else {
            VStack(spacing: 8) {
                ForEach(entries) { entry in
                    row(entry)
                }
            }
            .padding(.top, 4)
        }
    }

    private func row(_ entry: AuditEntry) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                ChmabaBadge(text: entry.action, tone: .blue)
                Text(entry.entityType ?? "")
                    .font(.system(size: 10))
                    .foregroundStyle(ChmabaColor.faint)
                    .lineLimit(1)
            }

            Text("\(entry.actor ?? "System")  ·  \(ActivityView.localStamp(entry.createdAt))")
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.muted)
                .padding(.top, 6)

            let details = Self.detailLine(entry.details)
            if !details.isEmpty {
                Text(details)
                    .font(.system(size: 11.5))
                    .lineSpacing(2)
                    .foregroundStyle(ChmabaColor.textPrimary)
                    .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 14))
    }

    /// `product: Milk  ·  quantity: 2`, in the API's own key order.
    private static func detailLine(_ details: [String: JSONValue]?) -> String {
        guard let details, !details.isEmpty else { return "" }
        return details.keys.sorted()
            .map { "\($0): \(details[$0]?.displayText ?? "")" }
            .joined(separator: "  ·  ")
    }

    /// The API's instant rendered in the reader's own zone.
    ///
    /// The payload carries an offset, so slicing the string would show UTC on a phone that
    /// is not in it — a sale rung up at 11:35 in Phnom Penh reading as 04:35. A value that
    /// cannot be parsed is returned as it came rather than replaced with a guess, which is
    /// what the Android client does too.
    static func localStamp(_ iso: String?, timeZone: TimeZone = .current) -> String {
        guard let iso, !iso.isEmpty else { return "" }

        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]

        guard let date = withFraction.date(from: iso) ?? plain.date(from: iso) else {
            return iso
        }

        let display = DateFormatter()
        display.locale = Locale(identifier: "en_US_POSIX")
        display.timeZone = timeZone
        display.dateFormat = "d MMM yyyy, HH:mm"
        return display.string(from: date)
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func load() async {
        if entries.isEmpty { loading = true }
        error = nil
        do {
            entries = try await APIClient.shared.get("audit-logs", as: [AuditEntry].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load activity."
            loading = false
        }
    }
}
