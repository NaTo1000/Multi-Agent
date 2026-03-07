namespace MultiAgent.Core;

/// <summary>Represents a single autonomous agent.</summary>
public interface IAgent
{
    /// <summary>Unique identifier for this agent.</summary>
    string Id { get; }

    /// <summary>Human-readable agent name.</summary>
    string Name { get; }

    /// <summary>Returns <c>true</c> if this agent can handle the given task.</summary>
    bool CanHandle(string taskName);

    /// <summary>Executes the given task and returns a result.</summary>
    Task<AgentResult> ExecuteAsync(string taskName, CancellationToken cancellationToken = default);
}
