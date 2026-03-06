import SwiftUI

/// Root view of the iOS Integration module.
///
/// Replace or extend this view to build out the full iOS UI that
/// communicates with the Multi-Agent ESP32 orchestration back-end.
struct ContentView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: "antenna.radiowaves.left.and.right")
                    .imageScale(.large)
                    .font(.system(size: 64))
                    .foregroundStyle(.tint)

                Text("Multi-Agent iOS Integration")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Swift iOS integration module for the\nMulti-Agent ESP32 orchestration system.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            .padding()
            .navigationTitle("Multi-Agent")
        }
    }
}

#Preview {
    ContentView()
}
