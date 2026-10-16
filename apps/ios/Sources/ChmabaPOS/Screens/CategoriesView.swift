import SwiftUI

/// Categories, ported from `apps/android/.../screens/categories/CategoriesScreen.kt` and
/// the prototype's `data-screen="categories"`.
///
/// Reads `GET /categories`; creates with `POST /categories`; renames with
/// `PATCH /categories/{id}`. The create payload is `CategoryCreateRequest { name,
/// parent_id }`, and a duplicate name comes back as 409, which is surfaced rather than
/// swallowed.
///
/// `CategoryRead` carries no product count, so none is shown -- the same limitation the
/// Android client documents in place of a count.
struct CategoriesView: View {
    let onBack: () -> Void

    @State private var categories: [CategoryRead] = []
    @State private var loading = true
    @State private var error: String?
    @State private var editor: EditorTarget?
    @State private var saving = false
    @State private var saveError: String?

    /// Which editor is open. `categoryId == nil` means create.
    private struct EditorTarget: Identifiable {
        let id: String
        let title: String
        let initial: String
        let categoryId: UUID?
    }

    private var parents: [CategoryRead] { categories.filter { !$0.isSubcategory } }
    private var subs: [CategoryRead] { categories.filter(\.isSubcategory) }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
        .sheet(item: $editor) { target in
            CategoryEditorSheet(
                title: target.title,
                initial: target.initial,
                saving: saving,
                error: saveError,
                onCancel: {
                    saveError = nil
                    editor = nil
                },
                onSave: { name in
                    Task { await save(name: name, editing: target.categoryId) }
                }
            )
        }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Categories")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Organize products into categories and subcategories.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer(minLength: 0)
                ChmabaButton(
                    text: "Add",
                    variant: .primary,
                    size: .small,
                    leadingIcon: .plus
                ) {
                    saveError = nil
                    editor = EditorTarget(id: "new", title: "Add category", initial: "", categoryId: nil)
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        StatGrid(columns: 3) {
            StatTile(label: "Categories", value: "\(categories.count)", tone: .violet, compact: true)
            StatTile(label: "Top-level", value: "\(parents.count)", tone: .green, compact: true)
            // `StatTile.neutralPanel` exists for exactly this tile.
            StatTile(
                label: "Subcategories",
                value: "\(subs.count)",
                tone: .neutral,
                compact: true,
                neutralPanel: true
            )
        }
        .padding(.bottom, 14)

        if loading {
            noticeLine("Loading categories…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else {
            PanelList {
                if categories.isEmpty {
                    noticeLine("No categories yet.")
                        .padding(16)
                } else {
                    ForEach(Array(categories.enumerated()), id: \.element.id) { index, category in
                        ListRow(showsDivider: index < categories.count - 1) {
                            AnyView(
                                HStack(spacing: 12) {
                                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                                        .fill(category.isSubcategory
                                              ? ChmabaColor.backgroundAlt
                                              : ChmabaColor.lavender)
                                        .frame(width: 34, height: 34)
                                        .overlay {
                                            ChmabaIconView(
                                                icon: category.isSubcategory ? .cornerDownRight : .tag,
                                                size: 17,
                                                color: category.isSubcategory
                                                    ? ChmabaColor.muted
                                                    : ChmabaColor.purple
                                            )
                                        }
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(category.name)
                                            .font(.system(size: 12.5, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                            .lineLimit(1)
                                        Text(category.isSubcategory ? "Subcategory" : "Category")
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                    }
                                }
                            )
                        } trailing: {
                            // Nil means the endpoint did not report it, which is not the
                            // same as "inactive", so it reads as active.
                            ChmabaBadge(
                                text: (category.isActive ?? true) ? "Active" : "Inactive",
                                tone: (category.isActive ?? true) ? .green : .neutral
                            )
                        } action: {
                            saveError = nil
                            editor = EditorTarget(
                                id: category.id.uuidString,
                                title: "Rename category",
                                initial: category.name,
                                categoryId: category.id
                            )
                        }
                    }
                }
            }
            .padding(.bottom, 8)
        }
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    // MARK: Actions

    private struct CategoryPayload: Encodable {
        let name: String
    }

    private func load() async {
        if categories.isEmpty { loading = true }
        error = nil
        do {
            categories = try await APIClient.shared.get("categories", as: [CategoryRead].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load categories."
            loading = false
        }
    }

    /// `editing` nil creates; otherwise renames. On success the list is reloaded rather
    /// than patched locally, so the row always reflects what the server holds.
    private func save(name: String, editing categoryId: UUID?) async {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            saveError = "Give the category a name."
            return
        }
        saving = true
        saveError = nil
        do {
            if let categoryId {
                let updated = try await APIClient.shared.patch(
                    "categories/\(categoryId.uuidString)",
                    body: CategoryPayload(name: trimmed),
                    as: CategoryRead.self
                )
                if let index = categories.firstIndex(where: { $0.id == updated.id }) {
                    categories[index] = updated
                }
            } else {
                let created = try await APIClient.shared.post(
                    "categories",
                    body: CategoryPayload(name: trimmed),
                    as: CategoryRead.self
                )
                categories.append(created)
            }
            editor = nil
        } catch let apiError as APIError {
            saveError = apiError.errorDescription
        } catch {
            saveError = "Could not save the category."
        }
        saving = false
    }
}

/// The prototype's `CategoryDialog`: one field, Cancel and Save, with the API's own
/// message shown in place rather than a generic failure.
private struct CategoryEditorSheet: View {
    let title: String
    let initial: String
    let saving: Bool
    let error: String?
    let onCancel: () -> Void
    let onSave: (String) -> Void

    @State private var name: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title)
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)

            TextField("Name", text: $name)
                .font(.system(size: 13))
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.backgroundAlt, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
                .padding(.top, 14)

            if let error {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundStyle(BadgeTone.red.foreground)
                    .padding(.top, 8)
            }

            HStack(spacing: 10) {
                ChmabaButton(text: "Cancel", variant: .outline, size: .medium, enabled: !saving) {
                    onCancel()
                }
                ChmabaButton(
                    text: saving ? "Saving…" : "Save",
                    variant: .primary,
                    size: .medium,
                    enabled: !saving && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                    loading: saving
                ) {
                    onSave(name)
                }
            }
            .padding(.top, 18)

            Spacer(minLength: 0)
        }
        .padding(20)
        .presentationDetents([.height(260)])
        .presentationDragIndicator(.visible)
        .onAppear { name = initial }
    }
}
