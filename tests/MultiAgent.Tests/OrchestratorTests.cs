using Microsoft.Extensions.Logging.Abstractions;
using MultiAgent.Core.Agents;
using MultiAgent.Core.Models;
using MultiAgent.Core.Orchestration;
using Xunit;

namespace MultiAgent.Tests;

public sealed class OrchestratorTests
{
    private Orchestrator CreateOrchestrator()
        => new(NullLogger<Orchestrator>.Instance);

    [Fact]
    public void RegisterDevice_AddsDevice()
    {
        var orch = CreateOrchestrator();
        var device = new Device("d1", "Test Device");
        orch.RegisterDevice(device);
        var device2 = Assert.Single(orch.ListDevices());
        Assert.Equal("d1", device2.DeviceId);
    }

    [Fact]
    public void UnregisterDevice_RemovesDevice()
    {
        var orch = CreateOrchestrator();
        orch.RegisterDevice(new Device("d1", "Test"));
        Assert.True(orch.UnregisterDevice("d1"));
        Assert.Null(orch.GetDevice("d1"));
    }

    [Fact]
    public void UnregisterDevice_UnknownId_ReturnsFalse()
    {
        var orch = CreateOrchestrator();
        Assert.False(orch.UnregisterDevice("nonexistent"));
    }

    [Fact]
    public void RegisterAgent_AddsAgent()
    {
        var orch = CreateOrchestrator();
        var agent = new FrequencyAgent(NullLogger<FrequencyAgent>.Instance);
        orch.RegisterAgent(agent);
        Assert.Single(orch.ListAgents());
    }

    [Fact]
    public void GetAgentsByType_FiltersCorrectly()
    {
        var orch = CreateOrchestrator();
        orch.RegisterAgent(new FrequencyAgent(NullLogger<FrequencyAgent>.Instance));
        orch.RegisterAgent(new FrequencyAgent(NullLogger<FrequencyAgent>.Instance));
        orch.RegisterAgent(new ModulationAgent(NullLogger<ModulationAgent>.Instance));

        Assert.Equal(2, orch.GetAgentsByType("frequency").Count);
        Assert.Single(orch.GetAgentsByType("modulation"));
    }

    [Fact]
    public async Task DispatchTaskAsync_ReturnsTaskId_AndStoresResult()
    {
        var orch = CreateOrchestrator();
        var agent = new FrequencyAgent(NullLogger<FrequencyAgent>.Instance);
        orch.RegisterAgent(agent);
        await orch.StartAsync();

        var taskId = await orch.DispatchTaskAsync(agent.AgentId, "scan");
        var result = orch.GetTaskResult(taskId);

        Assert.NotNull(result);
        Assert.True(result!.Success);
        Assert.Equal("scan", result.TaskName);

        await orch.StopAsync();
    }

    [Fact]
    public async Task DispatchTaskAsync_UnknownAgent_Throws()
    {
        var orch = CreateOrchestrator();
        await Assert.ThrowsAsync<KeyNotFoundException>(
            () => orch.DispatchTaskAsync("nonexistent", "scan"));
    }

    [Fact]
    public async Task BroadcastTaskAsync_DispatchesToAllAgentsOfType()
    {
        var orch = CreateOrchestrator();
        orch.RegisterAgent(new FrequencyAgent(NullLogger<FrequencyAgent>.Instance));
        orch.RegisterAgent(new FrequencyAgent(NullLogger<FrequencyAgent>.Instance));
        await orch.StartAsync();

        var taskIds = await orch.BroadcastTaskAsync("frequency", "scan");

        Assert.Equal(2, taskIds.Count);
        await orch.StopAsync();
    }

    [Fact]
    public async Task OrchestratorEvent_FiredOnTaskCompletion()
    {
        var orch = CreateOrchestrator();
        var agent = new FrequencyAgent(NullLogger<FrequencyAgent>.Instance);
        orch.RegisterAgent(agent);

        var events = new List<string>();
        orch.OrchestratorEvent += (_, e) => events.Add(e.EventName);

        await orch.StartAsync();
        await orch.DispatchTaskAsync(agent.AgentId, "scan");
        await orch.StopAsync();

        Assert.Contains("task_completed", events);
        Assert.Contains("orchestrator_started", events);
        Assert.Contains("orchestrator_stopped", events);
    }
}
