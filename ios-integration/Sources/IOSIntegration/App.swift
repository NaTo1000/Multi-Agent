import SwiftUI

/// Entry point for the iOS Integration module.
///
/// When running as a standalone app, `@main` bootstraps the SwiftUI lifecycle.
/// When embedded as a library target the `App` type is imported directly by
/// the host application.
@main
struct IOSIntegrationApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
