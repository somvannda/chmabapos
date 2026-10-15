import Foundation
import Security

// MARK: - Keychain

/// Minimal Keychain wrapper for the access token.
///
/// The Android client keeps its token in `SharedPreferences`. On iOS the equivalent
/// should be the **Keychain**, not `UserDefaults`: it is the platform's encrypted
/// secret store, and a POS device is exactly the kind of thing that gets lost.
enum Keychain {
    private static let service = "com.chmaba.pos"

    static func set(_ value: String, for key: String) {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)

        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(attributes as CFDictionary, nil)
    }

    static func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data
        else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

// MARK: - Session

/// Owns the signed-in state for the whole app.
///
/// Drives the root view: `.checking` on launch while we try a silent restore,
/// then `.signedOut` (login) or `.signedIn` (the shell).
@MainActor
final class Session: ObservableObject {
    enum State: Equatable {
        case checking
        case signedOut
        case signedIn
    }

    @Published private(set) var state: State = .checking
    @Published private(set) var user: UserRead?
    @Published private(set) var storeId: UUID?
    @Published private(set) var workspaceName: String?
    @Published private(set) var companyName: String?
    @Published private(set) var currencyCode: String = "USD"
    @Published var signInError: String?
    @Published private(set) var isSigningIn = false

    private let api = APIClient.shared
    private static let tokenKey = "access_token"

    /// Called once on launch. A stored token that no longer works is *not* an
    /// error worth showing -- we just fall back to the login screen.
    func restore() async {
        guard let token = Keychain.get(Self.tokenKey) else {
            state = .signedOut
            return
        }
        api.setAccessToken(token)
        do {
            let me: UserRead = try await api.get("auth/me", as: UserRead.self)
            user = me
            await loadWorkspace()
            state = .signedIn
        } catch {
            // The access token may simply be expired; the refresh cookie can
            // still rescue it.
            do {
                let refreshed = try await api.refreshAccessToken()
                Keychain.set(refreshed, for: Self.tokenKey)
                user = try await api.get("auth/me", as: UserRead.self)
                await loadWorkspace()
                state = .signedIn
            } catch {
                clearLocalSession()
                state = .signedOut
            }
        }
    }

    /// The store/company the till belongs to.
    ///
    /// Store-scoped endpoints need `X-Store-ID`, and the nav shows the store name, so
    /// this runs once per sign-in rather than per screen. A failure here is not fatal
    /// -- the shell still renders, it just shows fallbacks -- so it never blocks the
    /// signed-in state.
    private func loadWorkspace() async {
        do {
            let workspace: WorkspaceRead = try await api.get("workspaces/current", as: WorkspaceRead.self)
            storeId = workspace.store.id
            workspaceName = workspace.store.name
            companyName = workspace.company.name
            currencyCode = workspace.store.currencyCode
            // Store-scoped endpoints read this header.
            api.setStoreId(workspace.store.id.uuidString)
        } catch {
            storeId = nil
            workspaceName = nil
            companyName = nil
            api.setStoreId(nil)
        }
    }

    func signIn(email: String, password: String, remember: Bool) async {
        signInError = nil
        isSigningIn = true
        defer { isSigningIn = false }

        do {
            let body = LoginRequest(
                email: email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased(),
                password: password,
                rememberMe: remember
            )
            let res: TokenResponse = try await api.post("auth/login", body: body, as: TokenResponse.self)
            api.setAccessToken(res.accessToken)
            Keychain.set(res.accessToken, for: Self.tokenKey)
            user = res.user
            await loadWorkspace()
            state = .signedIn
        } catch let error as APIError {
            signInError = error.errorDescription
        } catch {
            signInError = "Something went wrong signing in."
        }
    }

    func signOut() async {
        // Best effort -- a failed logout must still clear the device.
        _ = try? await api.post("auth/logout", body: EmptyBody())
        clearLocalSession()
        state = .signedOut
    }

    private func clearLocalSession() {
        api.setAccessToken(nil)
        Keychain.delete(Self.tokenKey)
        // Drop the rotated refresh cookie too, or the next sign-in inherits it.
        if let storage = HTTPCookieStorage.shared.cookies {
            for cookie in storage { HTTPCookieStorage.shared.deleteCookie(cookie) }
        }
        user = nil
    }
}

/// For endpoints that take no body but are still POSTs (logout, refresh).
struct EmptyBody: Codable {}
