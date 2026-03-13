import SwiftUI

/// Root navigation container that routes to the five main tabs.
public struct ContentView: View {
    @EnvironmentObject private var orchestratorEnv: OrchestratorServiceEnv
    @EnvironmentObject private var socketEnv: TelemetrySocketEnv

    public init() {}

    public var body: some View {
        TabView {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "square.grid.2x2.fill")
                }

            DeviceListView()
                .tabItem {
                    Label("Devices", systemImage: "cpu.fill")
                }

            FlipperView()
                .tabItem {
                    Label("Flipper", systemImage: "flipphone")
                }

            PineappleView()
                .tabItem {
                    Label("Pineapple", systemImage: "wifi.router")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(OrchestratorServiceEnv())
        .environmentObject(TelemetrySocketEnv())
}
