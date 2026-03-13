// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "IOSIntegration",
    platforms: [
        .iOS(.v17),
        .watchOS(.v10),
        .macOS(.v14)
    ],
    products: [
        .library(name: "IOSIntegration", targets: ["IOSIntegration"]),
        .library(name: "FlipperBridge", targets: ["FlipperBridge"]),
        .library(name: "PineappleKit", targets: ["PineappleKit"]),
        .library(name: "AssetPackManager", targets: ["AssetPackManager"]),
    ],
    dependencies: [
        .package(url: "https://github.com/daltoniam/Starscream.git", from: "4.0.0"),
        .package(url: "https://github.com/kishikawakatsumi/KeychainAccess.git", from: "4.2.2"),
        .package(url: "https://github.com/apple/swift-protobuf.git", from: "1.25.0"),
    ],
    targets: [
        .target(
            name: "IOSIntegration",
            dependencies: [
                "FlipperBridge",
                "PineappleKit",
                "AssetPackManager",
                .product(name: "Starscream", package: "Starscream"),
                .product(name: "KeychainAccess", package: "KeychainAccess"),
            ],
            path: "Sources/IOSIntegration"
        ),
        .target(
            name: "FlipperBridge",
            dependencies: [
                .product(name: "SwiftProtobuf", package: "swift-protobuf"),
            ],
            path: "Sources/FlipperBridge"
        ),
        .target(
            name: "PineappleKit",
            dependencies: [],
            path: "Sources/PineappleKit"
        ),
        .target(
            name: "AssetPackManager",
            dependencies: [],
            path: "Sources/AssetPackManager"
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
