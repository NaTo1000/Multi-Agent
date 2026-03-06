using Microsoft.Extensions.Logging.Abstractions;
using MultiAgent.Core.FaultTolerance;
using MultiAgent.Core.Orchestration;
using Xunit;

namespace MultiAgent.Tests;

public sealed class FaultTolerantSequencerTests
{
    private FaultTolerantSequencer CreateSequencer()
    {
        var detector = new EwmaFaultDetector(NullLogger<EwmaFaultDetector>.Instance);
        var rollback = new RollbackManager(NullLogger<RollbackManager>.Instance);
        var engine = new SequencingEngine(NullLogger<SequencingEngine>.Instance);
        return new FaultTolerantSequencer(detector, rollback, engine,
                                          NullLogger<FaultTolerantSequencer>.Instance);
    }

    [Fact]
    public async Task NormalMetrics_EnqueuesAndRunsWithoutRollback()
    {
        var seq = CreateSequencer();
        var executed = new List<string>();

        seq.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("t1"); }, "t1", healthMetric: 10.0);
        seq.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("t2"); }, "t2", healthMetric: 10.1);

        await seq.RunAllAsync();

        Assert.Equal(2, executed.Count);
    }

    [Fact]
    public async Task FaultMetric_TriggersRollbackBeforeEnqueue()
    {
        var detector = new EwmaFaultDetector(NullLogger<EwmaFaultDetector>.Instance);
        var rollback = new RollbackManager(NullLogger<RollbackManager>.Instance);
        var engine = new SequencingEngine(NullLogger<SequencingEngine>.Instance);
        var seq = new FaultTolerantSequencer(detector, rollback, engine,
                                              NullLogger<FaultTolerantSequencer>.Instance);

        var rollbackExecuted = false;
        rollback.Register("op-1", async ct => { await Task.Delay(10, ct); rollbackExecuted = true; });

        // Warm up detector
        for (int i = 0; i < 5; i++) seq.Enqueue(_ => Task.CompletedTask, $"warmup-{i}", healthMetric: 10.0);
        await seq.RunAllAsync();

        // Spike — should trigger rollback
        seq.Enqueue(_ => Task.CompletedTask, "spike", healthMetric: 5000.0);
        await seq.RunAllAsync();
        await Task.Delay(300); // let fire-and-forget finish

        Assert.True(rollbackExecuted);
    }

    [Fact]
    public void PendingCount_ReflectsEnqueuedItems()
    {
        var seq = CreateSequencer();
        seq.Enqueue(_ => Task.CompletedTask, "t1");
        seq.Enqueue(_ => Task.CompletedTask, "t2");
        Assert.Equal(2, seq.PendingCount);
    }
}
