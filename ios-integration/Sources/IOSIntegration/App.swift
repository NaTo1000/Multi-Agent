import SwiftUI

@main
public struct MultiAgentApp: App {

    @StateObject private var orchestratorService = OrchestratorServiceEnv()
    @StateObject private var socketEnv = TelemetrySocketEnv()

    public init() {}

    public var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(orchestratorService)
                .environmentObject(socketEnv)
        }
    }
}

// MARK: - Environment wrappers
// These ObservableObject wrappers allow the actor-based services to be
// injected into the SwiftUI environment without direct actor conformance.

public final class OrchestratorServiceEnv: ObservableObject {
    public let service = OrchestratorService()
    public init() {}
}

public final class TelemetrySocketEnv: ObservableObject {
    public let socket = TelemetrySocket()
    public init() {}
}
