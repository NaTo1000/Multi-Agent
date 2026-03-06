using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;

namespace MultiAgent.Core.FaultTolerance;

/// <summary>
/// Exponentially Weighted Moving Average (EWMA) fault detector.
/// Flags an anomaly when a sample deviates more than <see cref="Threshold"/> standard
/// deviations from the running mean — matching the Python <c>FaultDetector</c>.
/// </summary>
public sealed class EwmaFaultDetector : IFaultDetector
{
    private readonly ILogger<EwmaFaultDetector> _logger;
    private readonly double _alpha;      // smoothing factor (0 < α ≤ 1)
    private readonly double _threshold;  // deviation multiplier

    private double _ewma;
    private double _variance;
    private bool _initialized;

    /// <param name="alpha">EWMA smoothing factor (default 0.3).</param>
    /// <param name="threshold">Anomaly threshold in σ units (default 3.0).</param>
    public EwmaFaultDetector(ILogger<EwmaFaultDetector> logger, double alpha = 0.3, double threshold = 3.0)
    {
        _logger = logger;
        _alpha = alpha;
        _threshold = threshold;
    }

    public bool RecordSample(double value)
    {
        if (!_initialized)
        {
            _ewma = value;
            _variance = 0;
            _initialized = true;
            return false;
        }

        var deviation = value - _ewma;
        var priorStdDev = Math.Sqrt(_variance);

        // When prior variance is non-zero, use the standard EWMA anomaly check.
        // When it is zero (e.g. a constant baseline), fall back to a relative
        // deviation check so we catch clear outliers without false-positives from noise.
        bool isAnomaly;
        if (priorStdDev > 0)
            isAnomaly = Math.Abs(deviation) > _threshold * priorStdDev;
        else if (Math.Abs(_ewma) > double.Epsilon)
            isAnomaly = Math.Abs(deviation) / Math.Abs(_ewma) > 0.5;  // >50% relative spike
        else
            isAnomaly = false;

        // Update variance and EWMA AFTER the check so the spike itself does not
        // inflate the variance and suppress detection in the same step.
        _variance = (1 - _alpha) * (_variance + _alpha * deviation * deviation);
        _ewma = _alpha * value + (1 - _alpha) * _ewma;

        if (isAnomaly)
            _logger.LogWarning("Fault detected: value={Value:F3} ewma={Ewma:F3} deviation={Deviation:F3}", value, _ewma, deviation);

        return isAnomaly;
    }

    public void Reset()
    {
        _initialized = false;
        _ewma = 0;
        _variance = 0;
    }
}
