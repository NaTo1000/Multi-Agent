using MultiAgent.Core.Models;

namespace MultiAgent.Core.Interfaces;

/// <summary>Contract for all orchestrator agents.</summary>
public interface IAgent
{
    string AgentId { get; }
    string AgentType { get; }
    AgentStatus Status { get; }

    Task StartAsync(CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>Execute a named task with optional parameters and optional target device.</summary>
    Task<object?> ExecuteAsync(string task,
                               IReadOnlyDictionary<string, object>? parameters = null,
                               Device? device = null,
                               CancellationToken cancellationToken = default);

    IReadOnlyDictionary<string, object> GetMetrics();
}
