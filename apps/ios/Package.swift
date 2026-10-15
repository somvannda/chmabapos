// swift-tools-version: 6.0
//
// Chmaba Cloud POS — native iOS client.
//
// This is an xtool project: a plain SwiftPM library that xtool bundles into an
// iOS app. It builds on Windows/Linux via xtool + the Darwin Swift SDK; see
// apps/ios/README.md.
//
// Keep exactly ONE library product here — that is what xtool packages as the app.

import PackageDescription

let package = Package(
    name: "ChmabaPOS",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "ChmabaPOS",
            targets: ["ChmabaPOS"]
        ),
    ],
    targets: [
        .target(
            name: "ChmabaPOS",
            swiftSettings: [
                .enableUpcomingFeature("ExistentialAny"),
            ]
        ),
    ]
)
