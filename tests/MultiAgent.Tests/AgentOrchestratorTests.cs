using MultiAgent.Core;

namespace MultiAgent.Tests;

public class AgentOrchestratorTests
{
    [Fact]
    public void RegisterAgent_AddsAgentToList()
    {
        var orchestrator = new AgentOrchestrator();
        orchestrator.RegisterAgent("test-agent");
        Assert.Single(orchestrator.AgentIds);
        Assert.Equal("test-agent", orchestrator.AgentIds[0]);
    }

    [Fact]
    public void AgentCount_ReflectsNumberOfRegisteredAgents()
    {
        var orchestrator = new AgentOrchestrator();
        orchestrator.RegisterAgent("agent-1");
        orchestrator.RegisterAgent("agent-2");
        Assert.Equal(2, orchestrator.AgentCount);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void RegisterAgent_ThrowsOnInvalidId(string? agentId)
    {
        var orchestrator = new AgentOrchestrator();
        Assert.ThrowsAny<ArgumentException>(() => orchestrator.RegisterAgent(agentId!));
    }
}