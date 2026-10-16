import SwiftUI

/// Help & support — the guides, grouped by section, one article open at a time. Ported from
/// `apps/android/.../screens/help/HelpScreen.kt`.
///
/// Everything shown comes from `GET /support/articles`, which has already narrowed the
/// corpus to this company's vertical and this member's role. Nothing is summarised or
/// rewritten: the steps are the API's own copy, and they describe the POS rather than one
/// client of it, so a step may mention the web's sidebar.
///
/// Not here: the AI assistant. `POST /support/chat` and the starter prompts are real
/// endpoints and are unwired, so the screen says "Guides" rather than promising a
/// conversation it does not hold.
struct HelpView: View {
    let onBack: () -> Void

    @State private var sections: [SupportSectionRead] = []
    @State private var loading = true
    @State private var error: String?
    /// The article the reader opened, so only one set of steps is on screen at a time.
    @State private var openArticle: String?

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
                Text("Help & support")
                    .font(.system(size: 20, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("Guides for this workspace.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading the guides…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if sections.isEmpty {
            noticeLine("No guides are available for this workspace yet.")
        } else {
            VStack(spacing: 10) {
                ForEach(sections) { section in
                    sectionCard(section)
                }
            }
        }
    }

    private func sectionCard(_ section: SupportSectionRead) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(section.title)
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)
            Text(section.blurb)
                .font(.system(size: 11))
                .lineSpacing(1.5)
                .foregroundStyle(ChmabaColor.muted)
                .padding(.top, 2)

            ForEach(section.articles) { article in
                let isOpen = openArticle == article.id

                Button {
                    openArticle = isOpen ? nil : article.id
                } label: {
                    HStack(spacing: 8) {
                        Text(article.title)
                            .font(.system(size: 12, weight: isOpen ? .bold : .regular))
                            .foregroundStyle(isOpen ? ChmabaColor.textPrimary : ChmabaColor.purple)
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(isOpen ? "−" : "+")
                            .font(.system(size: 13))
                            .foregroundStyle(ChmabaColor.faint)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.top, 8)

                if isOpen {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(article.steps.enumerated()), id: \.offset) { index, step in
                            Text("\(index + 1).  \(step)")
                                .font(.system(size: 11.5))
                                .lineSpacing(2)
                                .foregroundStyle(ChmabaColor.textPrimary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        if let tip = article.tip, !tip.trimmingCharacters(in: .whitespaces).isEmpty {
                            Text("Tip: \(tip)")
                                .font(.system(size: 11))
                                .lineSpacing(1.5)
                                .foregroundStyle(ChmabaColor.muted)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding(.top, 6)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func load() async {
        if sections.isEmpty { loading = true }
        error = nil
        do {
            sections = try await APIClient.shared.get("support/articles", as: [SupportSectionRead].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load the guides."
            loading = false
        }
    }
}
