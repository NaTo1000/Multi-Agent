using Microsoft.Extensions.Logging.Abstractions;
using MultiAgent.Core.FaultTolerance;
using Xunit;

namespace MultiAgent.Tests;

public sealed class EwmaFaultDetectorTests
{
    private EwmaFaultDetector CreateDetector(double alpha = 0.3, double threshold = 3.0)
        => new(NullLogger<EwmaFaultDetector>.Instance, alpha, threshold);

    [Fact]
    public void FirstSample_NeverTriggersAnomaly()
    {
        var d = CreateDetector();
        Assert.False(d.RecordSample(100));
    }

    [Fact]
    public void StableSamples_DoNotTriggerAnomaly()
    {
        var d = CreateDetector();
        double[] samples = [10, 10.1, 9.9, 10.0, 10.05, 9.98];
        foreach (var s in samples)
            Assert.False(d.RecordSample(s));
    }

    [Fact]
    public void LargeSpike_TriggersAnomaly()
    {
        var d = CreateDetector();
        // Warm up with stable samples
        foreach (var s in new double[] { 10, 10, 10, 10, 10 })
            d.RecordSample(s);

        // A value 10× the baseline should trigger the detector
        Assert.True(d.RecordSample(100));
    }

    [Fact]
    public void Reset_ClearsState()
    {
        var d = CreateDetector();
        foreach (var s in new double[] { 10, 10, 10, 10, 10 })
            d.RecordSample(s);

        d.Reset();
        // After reset the first sample never triggers
        Assert.False(d.RecordSample(100));
    }

    [Theory]
    [InlineData(0.1)]
    [InlineData(0.5)]
    [InlineData(0.9)]
    public void DifferentAlpha_StillDetectsSpike(double alpha)
    {
        var d = CreateDetector(alpha: alpha, threshold: 2.0);
        foreach (var s in new double[] { 5, 5, 5, 5, 5 })
            d.RecordSample(s);
        Assert.True(d.RecordSample(500));
    }
}
