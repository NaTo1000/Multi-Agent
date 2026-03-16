// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "IOSIntegration",
    platforms: [
        .iOS(.v17),
        .watchOS(.v10),
        .macOS(.v14)
    ],
    products: [
        .library(name: "IOSIntegration",  targets: ["IOSIntegration"]),
        .library(name: "FlipperBridge",   targets: ["FlipperBridge"]),
        .library(name: "PineappleKit",    targets: ["PineappleKit"]),
        .library(name: "AssetPackManager",targets: ["AssetPackManager"]),
    ],
    dependencies: [
        // WebSocket client — latest stable (4.0.6)
        .package(url: "https://github.com/daltoniam/Starscream.git", from: "4.0.6"),
        // Keychain wrapper — latest stable (4.2.2)
        .package(url: "https://github.com/kishikawakatsumi/KeychainAccess.git", from: "4.2.2"),
        // Protobuf runtime for Flipper RPC — latest stable (1.29.0)
        .package(url: "https://github.com/apple/swift-protobuf.git", from: "1.29.0"),
        // Swift async algorithms — latest stable (1.0.2)
        .package(url: "https://github.com/apple/swift-algorithms.git", from: "1.2.0"),
    ],
    targets: [
        .target(
            name: "IOSIntegration",
            dependencies: [
                "FlipperBridge",
                "PineappleKit",
                "AssetPackManager",
                .product(name: "Starscream",   package: "Starscream"),
                .product(name: "KeychainAccess", package: "KeychainAccess"),
                .product(name: "Algorithms",   package: "swift-algorithms"),
            ],
            path: "Sources/IOSIntegration",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .target(
            name: "FlipperBridge",
            dependencies: [
                .product(name: "SwiftProtobuf", package: "swift-protobuf"),
            ],
            path: "Sources/FlipperBridge",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .target(
            name: "PineappleKit",
            dependencies: [],
            path: "Sources/PineappleKit",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .target(
            name: "AssetPackManager",
            dependencies: [],
            path: "Sources/AssetPackManager",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "IOSIntegrationTests",
            dependencies: ["IOSIntegration"],
            path: "Tests/IOSIntegrationTests"
        ),
        .testTarget(
            name: "FlipperBridgeTests",
            dependencies: ["FlipperBridge"],
            path: "Tests/FlipperBridgeTests"
        ),
        .testTarget(
            name: "PineappleKitTests",
            dependencies: ["PineappleKit"],
            path: "Tests/PineappleKitTests"
        ),
    ]
)
