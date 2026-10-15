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
            // Brand artwork rendered from the source SVGs in apps/web/public by
            // scripts/75-render-brand-assets.sh. SwiftPM resources are copied into
            // the app bundle, so the logo is the real asset rather than geometry
            // re-derived in Swift.
            resources: [
                .copy("Resources/chmaba-mark.png"),
                .copy("Resources/chmaba-wordmark.png"),
                .copy("Resources/chmaba-wordmark-dark.png"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("ExistentialAny"),
            ]
        ),
    ]
)
