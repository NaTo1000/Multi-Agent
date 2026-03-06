// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "IOSIntegration",
    platforms: [
        .iOS(.v16)
    ],
    products: [
        .library(
            name: "IOSIntegration",
            targets: ["IOSIntegration"]
        )
    ],
    dependencies: [],
    targets: [
        .target(
            name: "IOSIntegration",
            dependencies: [],
            path: "Sources/IOSIntegration"
        ),
        .testTarget(
            name: "IOSIntegrationTests",
            dependencies: ["IOSIntegration"],
            path: "Tests/IOSIntegrationTests"
        )
    ]
)
