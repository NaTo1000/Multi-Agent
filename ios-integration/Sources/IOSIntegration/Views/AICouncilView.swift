import SwiftUI

/// AI Council view — displays recommendations from HuggingFace and WatsonX
/// based on live fleet telemetry metrics.
public struct AICouncilView: View {
    @StateObject private var viewModel = AICouncilViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            Group {
                if let analysis = viewModel.analysis {
                    analysisContent(analysis)
                } else if viewModel.isAnalysing {
                    analysingPlaceholder
                } else {
                    emptyState
                }
            }
            .navigationTitle("AI Council")
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    if viewModel.isAnalysing {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                    Button {
                        Task { await viewModel.runAnalysis() }
                    } label: {
                        Image(systemName: "wand.and.stars")
                    }
                    .disabled(viewModel.isAnalysing)
                    .accessibilityLabel("Run AI Analysis")
                }
            }
            .alert("Analysis Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "Unknown error")
            }
            .task {
                await viewModel.runAnalysis()
            }
        }
    }

    // MARK: - Analysis content

    @ViewBuilder
    private func analysisContent(_ analysis: AICouncilAnalysis) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                summaryCard(analysis)
                severityBadges(analysis)
                recommendationsList(analysis)
                metricsSnapshot(analysis)
                Spacer(minLength: 24)
            }
            .padding()
        }
    }

    private func summaryCard(_ analysis: AICouncilAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Summary", systemImage: "text.bubble.fill")
                .font(.headline)
            Text(analysis.summaryText)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("Updated \(analysis.timestamp.formatted(date: .omitted, time: .shortened))")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private func severityBadges(_ analysis: AICouncilAnalysis) -> some View {
        HStack(spacing: 12) {
            SeverityBadge(count: analysis.criticalCount, label: "Critical", color: .red)
            SeverityBadge(count: analysis.warningCount,  label: "Warning",  color: .orange)
            SeverityBadge(count: analysis.infoCount,     label: "Info",     color: .blue)
        }
    }

    private func recommendationsList(_ analysis: AICouncilAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recommendations")
                .font(.headline)

            if analysis.recommendations.isEmpty {
                Label("No issues detected", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green)
                    .padding(.vertical, 4)
            } else {
                ForEach(analysis.sortedRecommendations) { rec in
                    RecommendationCard(recommendation: rec)
                }
            }
        }
    }

    private func metricsSnapshot(_ analysis: AICouncilAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Metrics Snapshot")
                .font(.headline)
            if analysis.metricsSnapshot.isEmpty {
                Text("No metrics data available.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                LazyVGrid(
                    columns: [GridItem(.flexible()), GridItem(.flexible())],
                    spacing: 8
                ) {
                    ForEach(analysis.metricsSnapshot.sorted(by: { $0.key < $1.key }), id: \.key) { key, value in
                        MetricTile(key: key, value: value)
                    }
                }
            }
        }
    }

    // MARK: - Empty / loading states

    private var analysingPlaceholder: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.4)
            Text("AI Council is analysing your fleet…")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        ContentUnavailableView(
            "Run AI Analysis",
            systemImage: "brain.head.profile",
            description: Text("Tap ✦ to let the AI council analyse your fleet metrics.")
        )
    }
}

// MARK: - Supporting views

private struct SeverityBadge: View {
    let count: Int
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text("\(count)")
                .font(.title2.bold())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
    }
}

private struct RecommendationCard: View {
    let recommendation: AIRecommendation

    var severityColor: Color {
        switch recommendation.severity {
        case .critical: return .red
        case .warning:  return .orange
        case .info:     return .blue
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle()
                    .fill(severityColor)
                    .frame(width: 8, height: 8)
                Text(recommendation.title)
                    .font(.subheadline.bold())
                Spacer()
                Text(recommendation.source.rawValue)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(.quaternary, in: Capsule())
            }
            if !recommendation.body.isEmpty {
                Text(recommendation.body)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(4)
            }
        }
        .padding(12)
        .background(severityColor.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(severityColor.opacity(0.25), lineWidth: 1)
        )
    }
}

private struct MetricTile: View {
    let key: String
    let value: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(key)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Text(String(format: "%.2f", value))
                .font(.subheadline.monospacedDigit())
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }
}

#Preview {
    AICouncilView()
}
