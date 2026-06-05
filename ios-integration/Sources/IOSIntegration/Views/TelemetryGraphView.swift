import SwiftUI
import Charts

/// Real-time line graph for named telemetry metrics using the Swift Charts framework.
public struct TelemetryGraphView: View {
    public let data: [TelemetryData]
    public let metric: String

    public init(data: [TelemetryData], metric: String) {
        self.data = data
        self.metric = metric
    }

    private var chartPoints: [(date: Date, value: Double)] {
        data.compactMap { frame in
            guard let value = frame.metrics[metric] else { return nil }
            return (date: frame.timestamp, value: value)
        }
    }

    private var yRange: ClosedRange<Double>? {
        let values = chartPoints.map(\.value)
        guard let min = values.min(), let max = values.max() else { return nil }
        let pad = max(1, (max - min) * 0.1)
        return (min - pad)...(max + pad)
    }

    public var body: some View {
        if chartPoints.isEmpty {
            Text("No \(metric) data")
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            Chart(chartPoints.indices, id: \.self) { i in
                let point = chartPoints[i]
                LineMark(
                    x: .value("Time", point.date),
                    y: .value(metric, point.value)
                )
                .interpolationMethod(.catmullRom)
                .foregroundStyle(Color.accentColor)

                AreaMark(
                    x: .value("Time", point.date),
                    y: .value(metric, point.value)
                )
                .interpolationMethod(.catmullRom)
                .foregroundStyle(
                    LinearGradient(
                        colors: [Color.accentColor.opacity(0.3), Color.accentColor.opacity(0.0)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
            }
            .chartXAxis {
                AxisMarks(values: .stride(by: 30)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.second())
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisGridLine()
                    AxisValueLabel()
                }
            }
            .chartYScale(domain: yRange ?? 0...100)
            .chartLegend(.hidden)
        }
    }
}

#Preview {
    let now = Date()
    let mockData = (0..<50).map { i in
        TelemetryData(
            timestamp: now.addingTimeInterval(Double(i) * -2),
            deviceId: "esp32-01",
            metrics: ["cpu": Double(20 + arc4random_uniform(60))],
            signalStrength: nil,
            eventType: "heartbeat"
        )
    }
    .reversed()
    .map { $0 }

    return TelemetryGraphView(data: mockData, metric: "cpu")
        .frame(height: 200)
        .padding()
}
