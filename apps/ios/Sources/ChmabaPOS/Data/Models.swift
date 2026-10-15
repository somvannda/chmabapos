import Foundation

// MARK: - Money
//
// The API serialises Python `Decimal` as a JSON **string** (Pydantic v2's default
// for Decimal; `APIModel` in chmabapos_api/app/schemas.py sets no custom
// serialiser). So `price` arrives as `"4.50"`, not `4.50`.
//
// This type accepts either form, because a stricter decoder fails the whole
// product list on one field -- which is exactly the kind of bug that looks like
// a networking failure.

struct APIDecimal: Codable, Hashable, Sendable, Comparable {
    var value: Decimal

    init(_ value: Decimal) { self.value = value }

    init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let text = try? container.decode(String.self) {
            guard let parsed = Decimal(string: text) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Expected a decimal string, got \"\(text)\""
                )
            }
            value = parsed
        } else {
            value = try container.decode(Decimal.self)
        }
    }

    func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        // Send strings back, matching the API's own representation.
        try container.encode("\(value)")
    }

    static func < (lhs: APIDecimal, rhs: APIDecimal) -> Bool { lhs.value < rhs.value }
}

// MARK: - Auth

struct UserRead: Codable, Hashable, Sendable, Identifiable {
    let id: UUID
    let email: String
    let fullName: String
    let isActive: Bool
    let isEmailVerified: Bool
    let platformRole: String?
    let createdAt: Date
}

struct TokenResponse: Codable, Sendable {
    let accessToken: String
    let tokenType: String
    let expiresIn: Int
    let user: UserRead
}

struct LoginRequest: Codable, Sendable {
    let email: String
    let password: String
    let rememberMe: Bool
}

struct RegisterRequest: Codable, Sendable {
    let email: String
    let fullName: String
    let password: String
}

struct RegisterResponse: Codable, Sendable {
    let user: UserRead
    let message: String
    /// Dev convenience: the API returns the verification token directly when mail
    /// is not configured, so sign-up can be completed without a mail catcher.
    let devVerificationToken: String?
    let mailhogUrl: String?
}

struct VerifyEmailRequest: Codable, Sendable {
    let token: String
}

// MARK: - Catalog

struct CategoryRead: Codable, Hashable, Sendable, Identifiable {
    let id: UUID
    let name: String
    let parentId: UUID?
}

struct ProductRead: Codable, Hashable, Sendable, Identifiable {
    let id: UUID
    let companyId: UUID
    let categoryId: UUID?
    let name: String
    let sku: String
    let description: String?
    let image: String?
    let barcode: String?
    let brand: String?
    let unit: String
    let trackInventory: Bool
    let trackSerials: Bool
    let isSample: Bool
    let price: APIDecimal
    let costPrice: APIDecimal?
    let taxRate: APIDecimal?
    let isActive: Bool
    let category: CategoryRead?
    let onHand: Double
    let reorderPoint: Int
}

// MARK: - Errors

/// An error the API reported in a structured way (`{"detail": "..."}`).
struct APIErrorBody: Codable, Sendable {
    let detail: String?
}

struct PasswordResetRequest: Codable, Sendable {
    let email: String
}

struct PasswordResetConfirmRequest: Codable, Sendable {
    let token: String
    let password: String
}
