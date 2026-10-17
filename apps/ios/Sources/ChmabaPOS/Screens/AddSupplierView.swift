import SwiftUI

/// Add a supplier. Writes `POST /suppliers`, which takes and returns a plain dict rather than a
/// Pydantic model, so the field names below are the handler's own (`v1.py:9387`):
/// `name` is required; `contact_name`, `phone` and `email` are optional and blank means null.
///
/// **This endpoint is plan-gated.** It calls `require_plan_feature(..., "purchasing")`, and the
/// free plan does not include it: verified against the live API, where `GET /suppliers` answers
/// 200 and `POST /suppliers` answers **403 with an empty body**. A generic failure message would
/// therefore tell a free-plan merchant nothing at all, so a 403 is reported as what it is.
struct AddSupplierView: View {
    let onDone: (Supplier) -> Void
    let onBack: () -> Void

    @State private var name = ""
    @State private var contactName = ""
    @State private var phone = ""
    @State private var email = ""
    @State private var saving = false
    @State private var error: String?

    private var canSave: Bool {
        guard !saving else { return false }
        return !name.trimmingCharacters(in: .whitespaces).isEmpty
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
                Text("Add supplier")
                    .font(.system(size: 18, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("Where stock comes from.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var form: some View {
        field("Name", $name, placeholder: "Required")
        field("Contact name", $contactName, placeholder: "Optional")
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
            text: "Add supplier",
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
        let contactName: String?
        let phone: String?
        let email: String?
    }

    private func save() async {
        saving = true
        error = nil

        func trimmed(_ value: String) -> String? {
            let text = value.trimmingCharacters(in: .whitespaces)
            return text.isEmpty ? nil : text
        }

        let payload = Payload(
            name: name.trimmingCharacters(in: .whitespaces),
            contactName: trimmed(contactName),
            phone: trimmed(phone),
            email: trimmed(email)
        )

        do {
            let created = try await APIClient.shared.post(
                "suppliers", body: payload, as: Supplier.self
            )
            onDone(created)
        } catch let apiError as APIError {
            if case .http(let status, _) = apiError, status == 403 {
                // The endpoint is gated on the "purchasing" plan feature and answers 403 with
                // an empty body, so there is nothing to relay. Naming the feature is the only
                // useful thing to say.
                error = "Suppliers need the Purchasing feature. This workspace's plan does not "
                    + "include it — upgrade, or add suppliers in the web app."
            } else {
                error = apiError.errorDescription
            }
        } catch {
            self.error = "Could not add the supplier."
        }
        saving = false
    }
}
