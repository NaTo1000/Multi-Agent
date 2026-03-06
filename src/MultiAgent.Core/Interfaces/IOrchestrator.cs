using MultiAgent.Core.Models;

namespace MultiAgent.Core.Interfaces;

/// <summary>Contract for the central orchestrator.</summary>
public interface IOrchestrator
{
    // --- Device management ---
    string RegisterDevice(Device device);
    bool UnregisterDevice(string deviceId);
    Device? GetDevice(string deviceId);
    IReadOnlyList<Device> ListDevices();

    // --- Agent management ---
    string RegisterAgent(IAgent agent);
    IAgent? GetAgent(string agentId);
    IReadOnlyList<IAgent> ListAgents();
    IReadOnlyList<IAgent> GetAgentsByType(string agentType);

    // --- Task dispatch ---
    Task<string> DispatchTaskAsync(string agentId, string task,
                                   IReadOnlyDictionary<string, object>? parameters = null,
                                   string? deviceId = null,
                                   CancellationToken cancellationToken = default);

    Task<IReadOnlyList<string>> BroadcastTaskAsync(string agentType, string task,
                                                    IReadOnlyDictionary<string, object>? parameters = null,
                                                    CancellationToken cancellationToken = default);

    TaskResult? GetTaskResult(string taskId);

    // --- Lifecycle ---
    Task StartAsync(CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);

    // --- Events ---
    event EventHandler<OrchestratorEventArgs> OrchestratorEvent;
}

/// <summary>Payload for orchestrator-level events.</summary>
public sealed class OrchestratorEventArgs(string eventName, object? data) : EventArgs
{
    public string EventName { get; } = eventName;
    public object? Data { get; } = data;
}
