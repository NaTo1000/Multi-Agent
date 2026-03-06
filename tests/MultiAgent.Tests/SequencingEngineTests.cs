using Microsoft.Extensions.Logging.Abstractions;
using MultiAgent.Core.Orchestration;
using Xunit;

namespace MultiAgent.Tests;

public sealed class SequencingEngineTests
{
    private SequencingEngine CreateEngine(int maxConcurrent = 10)
        => new(NullLogger<SequencingEngine>.Instance, maxConcurrent);

    [Fact]
    public void PendingCount_StartsAtZero()
    {
        var engine = CreateEngine();
        Assert.Equal(0, engine.PendingCount);
    }

    [Fact]
    public void Enqueue_IncrementsPendingCount()
    {
        var engine = CreateEngine();
        engine.Enqueue(_ => Task.CompletedTask, "t1");
        engine.Enqueue(_ => Task.CompletedTask, "t2");
        Assert.Equal(2, engine.PendingCount);
    }

    [Fact]
    public void Clear_ResetsPendingCount()
    {
        var engine = CreateEngine();
        engine.Enqueue(_ => Task.CompletedTask, "t1");
        engine.Clear();
        Assert.Equal(0, engine.PendingCount);
    }

    [Fact]
    public async Task RunNextAsync_ExecutesHighestPriorityItem()
    {
        var engine = CreateEngine();
        var executed = new List<string>();

        engine.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("low"); }, "low", priority: 10);
        engine.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("high"); }, "high", priority: 1);

        // Only run one item — should be the highest priority (priority=1)
        await engine.RunNextAsync();

        Assert.Single(executed);
        Assert.Equal("high", executed[0]);
        Assert.Equal(1, engine.PendingCount);
    }

    [Fact]
    public async Task RunAllAsync_ExecutesAllItems()
    {
        var engine = CreateEngine();
        var executed = new List<string>();
        var locker = new object();

        for (int i = 0; i < 5; i++)
        {
            var id = $"t{i}";
            engine.Enqueue(async ct =>
            {
                await Task.Delay(5, ct);
                lock (locker) executed.Add(id);
            }, id);
        }

        await engine.RunAllAsync();

        Assert.Equal(0, engine.PendingCount);
        Assert.Equal(5, executed.Count);
    }

    [Fact]
    public async Task RunAllAsync_RespectsPriorityOrder()
    {
        var engine = CreateEngine(maxConcurrent: 1); // serial execution
        var executed = new List<string>();

        engine.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("C"); }, "C", priority: 3);
        engine.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("A"); }, "A", priority: 1);
        engine.Enqueue(async ct => { await Task.Delay(1, ct); executed.Add("B"); }, "B", priority: 2);

        await engine.RunAllAsync();

        Assert.Equal(["A", "B", "C"], executed);
    }

    [Fact]
    public async Task MaxConcurrency_IsRespected()
    {
        const int maxConcurrent = 3;
        var engine = CreateEngine(maxConcurrent);
        int concurrent = 0;
        int maxObserved = 0;
        var locker = new object();

        for (int i = 0; i < 9; i++)
        {
            engine.Enqueue(async ct =>
            {
                int current;
                lock (locker) { current = ++concurrent; maxObserved = Math.Max(maxObserved, current); }
                await Task.Delay(30, ct);
                lock (locker) { --concurrent; }
            }, $"t{i}");
        }

        await engine.RunAllAsync();
        Assert.True(maxObserved <= maxConcurrent,
            $"Max concurrent {maxObserved} exceeded limit {maxConcurrent}");
    }
}
