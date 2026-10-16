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
    /// `GET /categories` returns this, but `/products` embeds a slimmer category, so it is
    /// optional and nil is treated as active rather than as inactive.
    var isActive: Bool? = nil

    var isSubcategory: Bool { parentId != nil }
}

/// A JSON value whose shape is not known ahead of time.
///
/// `AuditEntry.details` differs per action -- an inventory adjustment carries a product and
/// a quantity, a settings change carries rules -- so it is rendered as the key/value pairs
/// the API actually sent, rather than mapped onto columns that would be blank for most
/// actions. `[String: Any]` is not `Codable`, hence this.
enum JSONValue: Codable, Hashable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case null
    case array([JSONValue])
    case object([String: JSONValue])

    init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Unsupported JSON value"
            )
        }
    }

    func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .null: try container.encodeNil()
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        }
    }

    /// Whole numbers print without a trailing ".0", matching what the API sent.
    var displayText: String {
        switch self {
        case .string(let value):
            return value
        case .bool(let value):
            return value ? "true" : "false"
        case .null:
            return "—"
        case .number(let value):
            guard value == value.rounded(), abs(value) < 1e15 else { return String(value) }
            return String(Int64(value))
        case .array(let value):
            return value.map(\.displayText).joined(separator: ", ")
        case .object(let value):
            return value.keys.sorted()
                .map { "\($0): \(value[$0]?.displayText ?? "")" }
                .joined(separator: ", ")
        }
    }
}

/// One recorded change, from `GET /audit-logs`.
///
/// That endpoint declares no response model (`v1.py:9071`), so this mirrors the dict the API
/// sends. `createdAt` is deliberately a String rather than a Date: the client's decoder
/// throws on an unrecognised date shape, which would fail the entire payload, and the
/// Android client keeps it as a string for the same reason.
struct AuditEntry: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let action: String
    let entityType: String?
    let entityId: String?
    /// The person's display name. Absent where the system made the change.
    let actor: String?
    let details: [String: JSONValue]?
    let createdAt: String?
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

// MARK: - Workspace
//
// Only the fields the app actually shows are declared; Codable ignores the rest of
// the payload, so this does not need to track WorkspaceRead in full.

struct CompanyRead: Codable, Sendable {
    let id: UUID
    let name: String
}

struct StoreRead: Codable, Sendable {
    let id: UUID
    let name: String
    /// The store's own currency. Threaded through so money() stops guessing USD.
    let currencyCode: String
}

struct WorkspaceRead: Codable, Sendable {
    let company: CompanyRead
    let store: StoreRead
    /// The effective plan's enabled feature keys (`app/features.py`), so the POS can list
    /// what the plan includes rather than keeping a second copy of the catalogue.
    var planFeatures: [String] = []
}
