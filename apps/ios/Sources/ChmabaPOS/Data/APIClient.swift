import Foundation
import os

// MARK: - Configuration

/// Base URL of the Chmaba API, editable at runtime.
///
/// This is deliberately NOT a compile-time constant any more. The dev server's address
/// depends on which network the phone is on, and this machine has two candidate
/// addresses on different subnets (a LAN and an iPhone-hotspot subnet), so pinning one
/// meant a rebuild every time the answer changed. The value is persisted, and the
/// sign-in screen exposes it with a connection test.
enum APIConfig {
    private static let key = "api_base_url"

    /// LAN, as a default. Overridable from the app.
    static let fallbackString = "http://192.168.100.136/api/v1/"

    static var baseURLString: String {
        get { UserDefaults.standard.string(forKey: key) ?? fallbackString }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static var baseURL: URL {
        URL(string: baseURLString) ?? URL(string: fallbackString)!
    }

    /// The host:port an operator would recognise, for error messages.
    static var hostDescription: String {
        guard let url = URL(string: baseURLString), let host = url.host else { return baseURLString }
        return url.port.map { "\(host):\($0)" } ?? host
    }

    static func reset() {
        UserDefaults.standard.removeObject(forKey: key)
    }
}

// MARK: - Errors

enum APIError: Error, LocalizedError {
    case http(status: Int, detail: String?)
    case transport(any Error)
    case decoding(any Error)
    case missingToken

    /// A short heading, so the UI can present a proper error card rather than one
    /// run-on sentence.
    var title: String {
        switch self {
        case .http(let status, _):
            switch status {
            case 401: return "Sign-in failed"
            case 403: return "Not allowed"
            case 404: return "Not found"
            case 422: return "Check your details"
            case 429: return "Too many attempts"
            case 500...599: return "Server problem"
            default: return "Something went wrong"
            }
        case .transport: return "Can't reach the server"
        case .decoding: return "Unexpected response"
        case .missingToken: return "Not signed in"
        }
    }

    /// The actionable second line. Only the transport case really has one, because
    /// that is the case an operator can actually do something about.
    var recoverySuggestion: String? {
        switch self {
        case .transport:
            return "Check the tablet is on the same Wi-Fi as the till, then try again. If the address is wrong, change it below."
        case .http(429, _):
            return "Wait a minute, then try again."
        case .http(500...599, _):
            return "Nothing you did caused this. Try again, and tell support if it keeps happening."
        case .decoding:
            return "The app and the server may be different versions."
        default:
            return nil
        }
    }

    var errorDescription: String? {
        switch self {
        case let .http(status, detail):
            if let detail, !detail.isEmpty { return detail }
            switch status {
            case 401: return "The email or password is incorrect."
            case 403: return "You do not have access to that."
            case 404: return "That could not be found."
            case 422: return "Some of those details were rejected."
            case 429: return "Too many attempts. Please wait a moment."
            case 500...599: return "The server could not complete the request."
            default: return "The request failed (\(status))."
            }
        case .transport:
            // Naming the host is the difference between "it is broken" and "it is
            // pointed at the wrong machine".
            return "Nothing answered at \(APIConfig.hostDescription)."
        case .decoding:
            return "The server sent something this version of the app could not read."
        case .missingToken:
            return "Your session has ended. Please sign in again."
        }
    }
}

// MARK: - Client

/// Talks to the Chmaba API.
///
/// Two behaviours matter and are easy to get wrong:
///
///  1. **The refresh cookie is rotated by the server.** `POST /auth/refresh` issues
///     a new cookie and invalidates the old one, so concurrent refreshes would
///     race and one would lose. Refreshes are therefore coalesced behind a single
///     in-flight task.
///  2. **Cookies live in `HTTPCookieStorage`.** `URLSession` then sends the refresh
///     cookie automatically, which is the iOS equivalent of the Android client's
///     custom persistent cookie jar.
final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    /// Read per request rather than captured at init, so changing the server in the
    /// UI takes effect immediately with no rebuild.
    private var baseURL: URL { APIConfig.baseURL }
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    /// Mutable state behind a scoped lock.
    ///
    /// `NSLock.lock()`/`unlock()` is `NS_SWIFT_UNAVAILABLE_FROM_ASYNC` under Swift 6,
    /// so this uses `OSAllocatedUnfairLock`'s scoped `withLock` instead. The critical
    /// sections contain no `await`, which is what makes that safe.
    private struct State {
        var accessToken: String?
        var storeId: String?
        var refreshInFlight: Task<String, any Error>?
    }
    private let state = OSAllocatedUnfairLock(initialState: State())

    init() {
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = .shared
        config.httpShouldSetCookies = true
        config.httpCookieAcceptPolicy = .always
        // Deliberately short. This talks to a LAN dev server, and a 30s wait on an
        // unreachable host makes the whole app look frozen -- a tap does nothing
        // until the timeout expires, so it reads as a dead button. Better to fail in
        // a few seconds with a clear message than to hang.
        config.timeoutIntervalForRequest = 12
        config.timeoutIntervalForResource = 30
        config.waitsForConnectivity = false
        session = URLSession(configuration: config)

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom(Self.decodeDate)
        self.decoder = decoder

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        self.encoder = encoder
    }

    func setAccessToken(_ token: String?) {
        state.withLock { $0.accessToken = token }
    }

    func currentAccessToken() -> String? {
        state.withLock { $0.accessToken }
    }

    /// The store every store-scoped endpoint is scoped to.
    ///
    /// The Android client sends `X-Store-ID` on catalog, orders and reports calls. The
    /// header is optional server-side (a default store is resolved), but reports and
    /// order creation are the endpoints where resolving the wrong store would be
    /// silently wrong rather than an error, so it is set explicitly.
    func setStoreId(_ id: String?) {
        state.withLock { $0.storeId = id }
    }

    func currentStoreId() -> String? {
        state.withLock { $0.storeId }
    }

    // MARK: Requests

    func get<T: Decodable>(_ path: String, as _: T.Type) async throws -> T {
        try await send(path, method: "GET", body: Optional<Never>.none, as: T.self)
    }

    func post<B: Encodable, T: Decodable>(_ path: String, body: B, as type: T.Type) async throws -> T {
        try await send(path, method: "POST", body: body, as: type)
    }

    @discardableResult
    func post<B: Encodable>(_ path: String, body: B) async throws -> Data {
        try await sendRaw(path, method: "POST", body: body, allowRefresh: true)
    }

    private func send<B: Encodable, T: Decodable>(
        _ path: String,
        method: String,
        body: B?,
        as type: T.Type,
        allowRefresh: Bool = true
    ) async throws -> T {
        let data = try await sendRaw(path, method: method, body: body, allowRefresh: allowRefresh)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    private func sendRaw<B: Encodable>(
        _ path: String,
        method: String,
        body: B?,
        allowRefresh: Bool
    ) async throws -> Data {
        let request = try makeRequest(path, method: method, body: body)
        let (data, response) = try await perform(request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0

        if status == 401, allowRefresh, shouldAttemptRefresh(path) {
            _ = try await refreshAccessToken()
            let retried = try makeRequest(path, method: method, body: body)
            let (retryData, retryResponse) = try await perform(retried)
            let retryStatus = (retryResponse as? HTTPURLResponse)?.statusCode ?? 0
            guard (200..<300).contains(retryStatus) else {
                throw APIError.http(status: retryStatus, detail: Self.detail(from: retryData))
            }
            return retryData
        }

        guard (200..<300).contains(status) else {
            throw APIError.http(status: status, detail: Self.detail(from: data))
        }
        return data
    }

    private func makeRequest<B: Encodable>(_ path: String, method: String, body: B?) throws -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = currentAccessToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let storeId = currentStoreId() {
            request.setValue(storeId, forHTTPHeaderField: "X-Store-ID")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try encoder.encode(body)
        }
        return request
    }

    private func perform(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch {
            throw APIError.transport(error)
        }
    }

    /// Never try to refresh in response to the auth endpoints themselves --
    /// that is how you get an infinite loop on a bad password.
    private func shouldAttemptRefresh(_ path: String) -> Bool {
        !path.hasPrefix("auth/login")
            && !path.hasPrefix("auth/refresh")
            && !path.hasPrefix("auth/register")
    }

    // MARK: Token refresh

    /// Coalesced: concurrent callers share one refresh, because the server rotates
    /// the refresh cookie and a second concurrent refresh would invalidate the first.
    @discardableResult
    func refreshAccessToken() async throws -> String {
        // Check-and-set atomically, so two callers cannot both mint a refresh.
        let task: Task<String, any Error> = state.withLock { state in
            if let existing = state.refreshInFlight { return existing }
            let task = Task<String, any Error> { [weak self] in
                guard let self else { throw APIError.missingToken }
                defer { self.state.withLock { $0.refreshInFlight = nil } }
                let res: TokenResponse = try await self.send(
                    "auth/refresh", method: "POST", body: Optional<Never>.none,
                    as: TokenResponse.self, allowRefresh: false
                )
                self.setAccessToken(res.accessToken)
                return res.accessToken
            }
            state.refreshInFlight = task
            return task
        }
        return try await task.value
    }

    // MARK: Decoding helpers

    private static func detail(from data: Data) -> String? {
        guard let body = try? JSONDecoder().decode(APIErrorBody.self, from: data) else { return nil }
        return body.detail
    }

    /// FastAPI emits ISO-8601, sometimes with fractional seconds and sometimes
    /// without. `ISO8601DateFormatter` alone rejects one of those, which would fail
    /// the whole payload, so try the realistic shapes in order.
    private static func decodeDate(_ decoder: any Decoder) throws -> Date {
        let container = try decoder.singleValueContainer()
        let raw = try container.decode(String.self)

        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = withFraction.date(from: raw) { return date }

        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        if let date = plain.date(from: raw) { return date }

        throw DecodingError.dataCorruptedError(
            in: container,
            debugDescription: "Unrecognised date format: \(raw)"
        )
    }
}
