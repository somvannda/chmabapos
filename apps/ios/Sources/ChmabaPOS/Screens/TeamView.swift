import SwiftUI

/// Team — who can sign in, and what they may do. Ported from
/// `apps/android/.../screens/team/TeamScreen.kt`.
///
/// Reads `GET /team` -> `list[MembershipRead]`. The endpoint is company-scoped, so it needs
/// no store header, unlike almost every other screen here.
struct TeamView: View {
    let onBack: () -> Void

    @State private var members: [MembershipRead] = []
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 12) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Team")
                    .font(.system(size: 20, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("Who can sign in, and what they may do.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading the team…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if members.isEmpty {
            noticeLine("Nobody has been added to this company yet.")
        } else {
            PanelList {
                ForEach(Array(members.enumerated()), id: \.element.id) { index, member in
                    ListRow(showsDivider: index < members.count - 1) {
                        AnyView(row(member))
                    } trailing: {
                        badges(member)
                    } action: {
                        // Nothing to open: membership is edited in the web app.
                    }
                }
            }
        }
    }

    private func row(_ member: MembershipRead) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .fill(ChmabaColor.lavender)
                .frame(width: 36, height: 36)
                .overlay {
                    Text(Self.initials(member))
                        .font(.system(size: 11, weight: .heavy))
                        .foregroundStyle(ChmabaColor.purple)
                }

            VStack(alignment: .leading, spacing: 2) {
                Text(Self.name(member))
                    .font(.system(size: 12.5, weight: .bold))
                    .foregroundStyle(ChmabaColor.textPrimary)
                    .lineLimit(1)
                Text(member.user.email)
                    .font(.system(size: 10))
                    .foregroundStyle(ChmabaColor.faint)
                    .lineLimit(1)
                Text(Self.reach(member))
                    .font(.system(size: 10))
                    .foregroundStyle(ChmabaColor.faint)
            }
        }
    }

    private func badges(_ member: MembershipRead) -> some View {
        VStack(alignment: .trailing, spacing: 4) {
            // "Owner", not "owner": the API's key is lowercase and this is a label.
            ChmabaBadge(
                text: Self.roleLabel(member.role),
                tone: member.role == "owner" ? .blue : .neutral
            )
            ChmabaBadge(
                text: member.status == "active"
                    ? "Active"
                    : Self.roleLabel(member.status),
                tone: member.status == "active" ? .blue : .neutral
            )
        }
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    // MARK: Formatting

    private static func name(_ member: MembershipRead) -> String {
        let full = member.user.fullName.trimmingCharacters(in: .whitespacesAndNewlines)
        return full.isEmpty ? member.user.email : full
    }

    private static func roleLabel(_ role: String) -> String {
        let trimmed = role.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let first = trimmed.first else { return "—" }
        return String(first).uppercased() + trimmed.dropFirst()
    }

    /// Which stores this member reaches.
    ///
    /// The payload carries store ids, not names, and the app has no member-to-store lookup,
    /// so this counts them rather than naming one it cannot resolve.
    private static func reach(_ member: MembershipRead) -> String {
        switch member.storeIds.count {
        case 0: return "All stores"
        case 1: return "1 store"
        default: return "\(member.storeIds.count) stores"
        }
    }

    private static func initials(_ member: MembershipRead) -> String {
        let parts = name(member)
            .split(whereSeparator: { " .@_".contains($0) })
            .filter { !$0.isEmpty }
        let letters = parts.prefix(2).compactMap { $0.first }.map { String($0).uppercased() }
        return letters.isEmpty ? "?" : letters.joined()
    }

    private func load() async {
        if members.isEmpty { loading = true }
        error = nil
        do {
            members = try await APIClient.shared.get("team", as: [MembershipRead].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load the team."
            loading = false
        }
    }
}
