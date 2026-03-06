using Microsoft.Extensions.Logging.Abstractions;
using MultiAgent.Core.FaultTolerance;
using Xunit;

namespace MultiAgent.Tests;

public sealed class RollbackManagerTests
{
    private RollbackManager CreateManager()
        => new(NullLogger<RollbackManager>.Instance);

    [Fact]
    public async Task TriggerRollback_ExecutesRegisteredAction()
    {
        var manager = CreateManager();
        var executed = false;
        manager.Register("op-1", async ct => { await Task.Delay(1, ct); executed = true; });

        manager.TriggerRollback("op-1");
        await Task.Delay(200); // allow fire-and-forget to complete

        Assert.True(executed);
    }

    [Fact]
    public async Task TriggerAllRollbacks_ExecutesAllRegisteredActions()
    {
        var manager = CreateManager();
        var order = new List<string>();
        var locker = new object();

        manager.Register("op-1", async ct => { await Task.Delay(10, ct); lock (locker) order.Add("op-1"); });
        manager.Register("op-2", async ct => { await Task.Delay(10, ct); lock (locker) order.Add("op-2"); });
        manager.Register("op-3", async ct => { await Task.Delay(10, ct); lock (locker) order.Add("op-3"); });

        manager.TriggerAllRollbacks();
        await Task.Delay(300); // allow fire-and-forget tasks

        // All three rollbacks must have executed; exact completion order is non-deterministic
        // because tasks run concurrently (fire-and-forget).
        Assert.Equal(3, order.Count);
        Assert.Contains("op-1", order);
        Assert.Contains("op-2", order);
        Assert.Contains("op-3", order);
    }

    [Fact]
    public void TriggerRollback_UnknownId_DoesNotThrow()
    {
        var manager = CreateManager();
        var ex = Record.Exception(() => manager.TriggerRollback("nonexistent"));
        Assert.Null(ex);
    }

    [Fact]
    public async Task RegisterSameId_OverwritesPreviousAction()
    {
        var manager = CreateManager();
        var firstCalled = false;
        var secondCalled = false;

        manager.Register("op-1", async ct => { await Task.Delay(1, ct); firstCalled = true; });
        manager.Register("op-1", async ct => { await Task.Delay(1, ct); secondCalled = true; });

        manager.TriggerRollback("op-1");
        await Task.Delay(200);

        Assert.False(firstCalled);
        Assert.True(secondCalled);
    }
}
