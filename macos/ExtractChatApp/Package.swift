// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "ExtractChatApp",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "ExtractChatApp", targets: ["ExtractChatApp"])],
    targets: [.executableTarget(name: "ExtractChatApp")]
)
