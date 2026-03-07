using MultiAgent.Core;

namespace MultiAgent.Tests;

public class OrchestratorTests
{
    [Fact]
    public void Register_AddsAgentToList()
    {
        var orchestrator = new Orchestrator();
        var agent = new StubAgent("agent-1", "Stub");

        orchestrator.Register(agent);

        Assert.Single(orchestrator.Agents);
        Assert.Equal("agent-1", orchestrator.Agents[0].Id);
    }

    [Fact]
    public void Register_NullAgent_ThrowsArgumentNullException()
    {
        var orchestrator = new Orchestrator();

        Assert.Throws<ArgumentNullException>(() => orchestrator.Register(null!));
    }

    [Fact]
    public async Task DispatchAsync_RouteToMatchingAgent_ReturnsResult()
    {
        var orchestrator = new Orchestrator();
        orchestrator.Register(new StubAgent("agent-1", "Stub", handledTask: "scan"));

        var results = await orchestrator.DispatchAsync("scan");

        Assert.Single(results);
        Assert.True(results[0].Success);
        Assert.Equal("agent-1", results[0].AgentId);
        Assert.Equal("scan", results[0].TaskName);
    }

    [Fact]
    public async Task DispatchAsync_NoMatchingAgent_ReturnsEmpty()
    {
        var orchestrator = new Orchestrator();
        orchestrator.Register(new StubAgent("agent-1", "Stub", handledTask: "scan"));

        var results = await orchestrator.DispatchAsync("unknown-task");

        Assert.Empty(results);
    }

    [Fact]
    public async Task DispatchAsync_EmptyTaskName_ThrowsArgumentException()
    {
        var orchestrator = new Orchestrator();

        await Assert.ThrowsAsync<ArgumentException>(() => orchestrator.DispatchAsync(""));
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private sealed class StubAgent(string id, string name, string handledTask = "*") : IAgent
    {
        public string Id { get; } = id;
        public string Name { get; } = name;

        public bool CanHandle(string taskName) =>
            handledTask == "*" || handledTask.Equals(taskName, StringComparison.Ordinal);

        public Task<AgentResult> ExecuteAsync(string taskName, CancellationToken cancellationToken = default) =>
            Task.FromResult(new AgentResult(Id, taskName, Success: true, "ok"));
    }
}
