import SwiftUI

/// Grid browser for Flipper Zero / Momentum asset packs with preview images and install support.
public struct AssetPackBrowserView: View {
    @StateObject private var viewModel = AssetPackViewModel()

    private let columns = [GridItem(.adaptive(minimum: 160), spacing: 12)]

    public init() {}

    public var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.packs.isEmpty {
                    ProgressView("Fetching asset packs…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.packs.isEmpty {
                    ContentUnavailableView(
                        "No Packs Found",
                        systemImage: "photo.on.rectangle.angled",
                        description: Text("Could not reach the Momentum CDN.")
                    )
                } else {
                    ScrollView {
                        LazyVGrid(columns: columns, spacing: 12) {
                            ForEach(viewModel.filteredPacks) { pack in
                                AssetPackCard(
                                    pack: pack,
                                    progress: viewModel.downloadProgress[pack.id],
                                    isInstalled: viewModel.installedPackIds.contains(pack.id)
                                ) {
                                    Task { await viewModel.install(pack: pack) }
                                }
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Asset Packs")
            .searchable(text: $viewModel.searchText, prompt: "Search packs")
            .refreshable {
                await viewModel.fetchPacks()
            }
            .task {
                await viewModel.fetchPacks()
            }
            .alert("Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }
}

// MARK: - Card

private struct AssetPackCard: View {
    let pack: AssetPackSummary
    let progress: Double?
    let isInstalled: Bool
    let onInstall: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Preview image (async)
            AsyncImage(url: pack.previewURL) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(Color.secondary.opacity(0.2))
                    .overlay(Image(systemName: "photo").foregroundStyle(.secondary))
            }
            .frame(height: 100)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            Text(pack.name)
                .font(.subheadline.bold())
                .lineLimit(1)

            Text("by \(pack.author)")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            if let p = progress, p < 1.0 {
                ProgressView(value: p)
                    .tint(.accentColor)
            } else if isInstalled {
                Label("Installed", systemImage: "checkmark.circle.fill")
                    .font(.caption)
                    .foregroundStyle(.green)
            } else {
                Button("Install") { onInstall() }
                    .font(.caption.bold())
                    .buttonStyle(.borderedProminent)
                    .controlSize(.mini)
            }
        }
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

#Preview {
    AssetPackBrowserView()
}
