// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "Pawble",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "Pawble", targets: ["Pawble"])
    ],
    targets: [
        .executableTarget(name: "Pawble")
    ]
)
