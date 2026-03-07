namespace MultiAgent.Core;

/// <summary>
/// Central orchestrator that manages a fleet of agents.
/// </summary>
public sealed class Orchestrator
{
    private readonly List<IAgent> _agents = new();

    /// <summary>Gets the registered agents.</summary>
    public IReadOnlyList<IAgent> Agents => _agents.AsReadOnly();

    /// <summary>Registers an agent with the orchestrator.</summary>
    public void Register(IAgent agent)
    {
        ArgumentNullException.ThrowIfNull(agent);
        _agents.Add(agent);
    }

    /// <summary>
    /// Dispatches a task to all agents that accept it and returns their results.
    /// </summary>
    public async Task<IReadOnlyList<AgentResult>> DispatchAsync(
        string taskName,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(taskName);

        var results = new List<AgentResult>();
        foreach (var agent in _agents)
        {
            if (agent.CanHandle(taskName))
            {
                var result = await agent.ExecuteAsync(taskName, cancellationToken);
                results.Add(result);
            }
        }

        return results.AsReadOnly();
    }
}
