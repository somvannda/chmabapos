import Foundation
import os

// MARK: - Configuration

enum APIConfig {
    /// Base URL of the Chmaba API.
    ///
    /// The Android client deliberately targets `http://localhost:5173/api/v1/` --
    /// the Vite dev-server origin -- because Google sign-in needs the CSRF cookie
    /// and the registered redirect URI to share a host. A native iOS build has no
    /// such constraint while we use email/password sign-in, so this points
    /// straight at the API through nginx.
    ///
    /// Change this one constant to move between the LAN dev server and a deployed
    /// environment. nginx proxies `/api/` to the API container on port 8000.
    static let baseURL = URL(string: "http://192.168.100.136/api/v1/")!
}

// MARK: - Errors

enum APIError: Error, LocalizedError {
    case http(status: Int, detail: String?)
    case transport(any Error)
    case decoding(any Error)
    case missingToken

    var errorDescription: String? {
        switch self {
        case let .http(status, detail):
            if let detail, !detail.isEmpty { return detail }
            switch status {
            case 401: return "Your session has expired. Please sign in again."
            case 403: return "You do not have access to that."
            case 404: return "Not found."
            case 429: return "Too many attempts. Please wait and try again."
            case 500...599: return "The server had a problem. Please try again."
            default: return "Request failed (\(status))."
            }
        case .transport:
            return "Cannot reach the server. Check that the API is running and that the phone is on the same network."
        case .decoding:
            return "The server sent something we could not read."
        case .missingToken:
            return "Not signed in."
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

    private let baseURL: URL
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
        var refreshInFlight: Task<String, any Error>?
    }
    private let state = OSAllocatedUnfairLock(initialState: State())

    init(baseURL: URL = APIConfig.baseURL) {
        self.baseURL = baseURL

        let config = URLSessionConfiguration.default
        config.httpCookieStorage = .shared
        config.httpShouldSetCookies = true
        config.httpCookieAcceptPolicy = .always
        config.timeoutIntervalForRequest = 30
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
