using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Orchestration;

/// <summary>
/// Central orchestrator.  Manages a fleet of devices, dispatches agents, and
/// coordinates tasks — mirroring the Python <c>Orchestrator</c> class.
/// </summary>
public sealed class Orchestrator : IOrchestrator
{
    private readonly ILogger<Orchestrator> _logger;
    private readonly ConcurrentDictionary<string, Device> _devices = new();
    private readonly ConcurrentDictionary<string, IAgent> _agents = new();
    private readonly ConcurrentDictionary<string, TaskResult> _results = new();
    private readonly TimeSpan _healthCheckInterval;
    private CancellationTokenSource? _cts;
    private bool _running;

    public event EventHandler<OrchestratorEventArgs>? OrchestratorEvent;

    public Orchestrator(ILogger<Orchestrator> logger, TimeSpan? healthCheckInterval = null)
    {
        _logger = logger;
        _healthCheckInterval = healthCheckInterval ?? TimeSpan.FromSeconds(10);
        _logger.LogInformation("Orchestrator initialised");
    }

    // -----------------------------------------------------------------------
    // Device management
    // -----------------------------------------------------------------------

    public string RegisterDevice(Device device)
    {
        if (_devices.TryAdd(device.DeviceId, device))
        {
            Emit("device_registered", new { device_id = device.DeviceId });
            _logger.LogInformation("Registered device: {Name} ({DeviceId})", device.Name, device.DeviceId);
        }
        else
        {
            _logger.LogWarning("Device {DeviceId} already registered", device.DeviceId);
        }
        return device.DeviceId;
    }

    public bool UnregisterDevice(string deviceId)
    {
        if (!_devices.TryRemove(deviceId, out _)) return false;
        Emit("device_unregistered", new { device_id = deviceId });
        _logger.LogInformation("Unregistered device: {DeviceId}", deviceId);
        return true;
    }

    public Device? GetDevice(string deviceId) => _devices.GetValueOrDefault(deviceId);
    public IReadOnlyList<Device> ListDevices() => _devices.Values.ToList();

    // -----------------------------------------------------------------------
    // Agent management
    // -----------------------------------------------------------------------

    public string RegisterAgent(IAgent agent)
    {
        if (_agents.TryAdd(agent.AgentId, agent))
        {
            Emit("agent_registered", new { agent_id = agent.AgentId, agent_type = agent.AgentType });
            _logger.LogInformation("Registered agent: {AgentType} ({AgentId})", agent.AgentType, agent.AgentId);
        }
        else
        {
            _logger.LogWarning("Agent {AgentId} already registered", agent.AgentId);
        }
        return agent.AgentId;
    }

    public IAgent? GetAgent(string agentId) => _agents.GetValueOrDefault(agentId);
    public IReadOnlyList<IAgent> ListAgents() => _agents.Values.ToList();
    public IReadOnlyList<IAgent> GetAgentsByType(string agentType) =>
        _agents.Values.Where(a => a.AgentType == agentType).ToList();

    // -----------------------------------------------------------------------
    // Task dispatch
    // -----------------------------------------------------------------------

    public async Task<string> DispatchTaskAsync(string agentId, string task,
                                                  IReadOnlyDictionary<string, object>? parameters = null,
                                                  string? deviceId = null,
                                                  CancellationToken cancellationToken = default)
    {
        if (!_agents.TryGetValue(agentId, out var agent))
            throw new KeyNotFoundException($"Unknown agent: {agentId}");

        var taskId = Guid.NewGuid().ToString();
        var device = deviceId is not null ? _devices.GetValueOrDefault(deviceId) : null;

        _logger.LogInformation("Dispatching task {Task} → agent {AgentId} (device={DeviceId})",
                                task, agentId, deviceId);
        Emit("task_dispatched", new { task_id = taskId, agent_id = agentId, task, device_id = deviceId });

        try
        {
            var result = await agent.ExecuteAsync(task, parameters, device, cancellationToken);
            var record = new TaskResult(taskId, agentId, task, result, DateTimeOffset.UtcNow, Success: true);
            _results[taskId] = record;
            Emit("task_completed", record);
            return taskId;
        }
        catch (Exception ex)
        {
            var record = new TaskResult(taskId, agentId, task, null, DateTimeOffset.UtcNow,
                                        Success: false, ErrorMessage: ex.Message);
            _results[taskId] = record;
            Emit("task_failed", record);
            throw;
        }
    }

    public async Task<IReadOnlyList<string>> BroadcastTaskAsync(string agentType, string task,
                                                                  IReadOnlyDictionary<string, object>? parameters = null,
                                                                  CancellationToken cancellationToken = default)
    {
        var agents = GetAgentsByType(agentType);
        if (agents.Count == 0)
        {
            _logger.LogWarning("No agents of type {AgentType} found", agentType);
            return [];
        }

        var taskIds = await Task.WhenAll(
            agents.Select(a => DispatchTaskAsync(a.AgentId, task, parameters, null, cancellationToken)));
        return taskIds;
    }

    public TaskResult? GetTaskResult(string taskId) => _results.GetValueOrDefault(taskId);

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_running) return;
        _running = true;
        _cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

        _logger.LogInformation("Starting orchestrator with {AgentCount} agent(s) and {DeviceCount} device(s)",
                                _agents.Count, _devices.Count);

        await Task.WhenAll(_agents.Values.Select(a => a.StartAsync(_cts.Token)));
        _ = Task.Run(() => HealthCheckLoopAsync(_cts.Token), _cts.Token);

        Emit("orchestrator_started", new { timestamp = DateTimeOffset.UtcNow });
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!_running) return;
        _running = false;
        _cts?.Cancel();

        await Task.WhenAll(_agents.Values.Select(a => a.StopAsync(cancellationToken)));
        Emit("orchestrator_stopped", new { timestamp = DateTimeOffset.UtcNow });
        _logger.LogInformation("Orchestrator stopped");
    }

    private async Task HealthCheckLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try { await Task.Delay(_healthCheckInterval, ct); }
            catch (OperationCanceledException) { break; }

            foreach (var device in _devices.Values)
            {
                _logger.LogDebug("Health-check ping: {DeviceId}", device.DeviceId);
            }
        }
    }

    // -----------------------------------------------------------------------
    // Status / events
    // -----------------------------------------------------------------------

    private void Emit(string eventName, object? data) =>
        OrchestratorEvent?.Invoke(this, new OrchestratorEventArgs(eventName, data));
}
