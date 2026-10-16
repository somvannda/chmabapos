import SwiftUI

/// Add a customer. Writes `POST /customers` -> `CustomerRead`.
///
/// Create only. The Android client's dialog is the same shape, and editing an existing
/// customer is a different concern — `PATCH /customers/{id}` exists, but nothing on iOS
/// offers it yet, and a create form that quietly became an edit form would need to say so.
struct AddCustomerView: View {
    let onDone: (Customer) -> Void
    let onBack: () -> Void

    @State private var name = ""
    @State private var phone = ""
    @State private var email = ""
    @State private var saving = false
    @State private var error: String?

    /// The API requires a name and validates the email as an `EmailStr`, so the button stays
    /// off rather than letting a round trip come back as a 422.
    private var canSave: Bool {
        guard !saving else { return false }
        guard !name.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        let trimmedEmail = email.trimmingCharacters(in: .whitespaces)
        return trimmedEmail.isEmpty || trimmedEmail.contains("@")
    }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { form }
        }
        .background(ChmabaColor.background)
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Add customer")
                    .font(.system(size: 18, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("Shared across your stores.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var form: some View {
        field("Name", $name, placeholder: "Sokha Lim")
        field("Phone", $phone, placeholder: "Optional", keyboard: .phonePad)
        field("Email", $email, placeholder: "Optional", keyboard: .emailAddress,
              autocapitalise: false)

        if let error {
            Text(error)
                .font(.system(size: 11))
                .lineSpacing(2)
                .foregroundStyle(BadgeTone.red.foreground)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 4)
        }

        ChmabaButton(
            text: "Add customer",
            variant: .primary,
            size: .large,
            enabled: canSave,
            fullWidth: true,
            loading: saving
        ) {
            Task { await save() }
        }
        .padding(.top, 16)
        .padding(.bottom, 8)
    }

    private func field(_ label: String, _ binding: Binding<String>,
                       placeholder: String,
                       keyboard: UIKeyboardType = .default,
                       autocapitalise: Bool = true) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField(placeholder, text: binding)
                .font(.system(size: 13))
                .keyboardType(keyboard)
                .textInputAutocapitalization(autocapitalise ? .words : .never)
                .autocorrectionDisabled(!autocapitalise)
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .padding(.bottom, 12)
    }

    private struct Payload: Encodable {
        let name: String
        let phone: String?
        let email: String?
    }

    private func save() async {
        saving = true
        error = nil

        let trimmedPhone = phone.trimmingCharacters(in: .whitespaces)
        let trimmedEmail = email.trimmingCharacters(in: .whitespaces)
        let payload = Payload(
            name: name.trimmingCharacters(in: .whitespaces),
            phone: trimmedPhone.isEmpty ? nil : trimmedPhone,
            email: trimmedEmail.isEmpty ? nil : trimmedEmail
        )

        do {
            let created = try await APIClient.shared.post(
                "customers", body: payload, as: Customer.self
            )
            onDone(created)
        } catch let apiError as APIError {
            // A rejected email address comes back with the API's own words, which name the
            // field; a generic message would not.
            error = apiError.errorDescription
        } catch {
            self.error = "Could not add the customer."
        }
        saving = false
    }
}
