namespace MultiAgent.Core;

/// <summary>
/// Core orchestration engine for the Multi-Agent system.
/// </summary>
public class AgentOrchestrator
{
    private readonly List<string> _agentIds = new();

    /// <summary>Gets the registered agent IDs.</summary>
    public IReadOnlyList<string> AgentIds => _agentIds.AsReadOnly();

    /// <summary>Registers an agent with the orchestrator.</summary>
    public void RegisterAgent(string agentId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(agentId);
        _agentIds.Add(agentId);
    }

    /// <summary>Returns the number of registered agents.</summary>
    public int AgentCount => _agentIds.Count;
}
