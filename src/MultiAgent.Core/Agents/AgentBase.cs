using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>
/// Abstract base for all orchestrator agents.
/// Concrete agents override <see cref="ExecuteCoreAsync"/> to implement domain logic.
/// </summary>
public abstract class AgentBase : IAgent
{
    protected readonly ILogger Logger;

    private long _tasksCompleted;
    private long _tasksFailed;
    private DateTimeOffset? _lastTaskAt;

    public string AgentId { get; } = Guid.NewGuid().ToString();
    public string AgentType { get; }
    public AgentStatus Status { get; protected set; } = AgentStatus.Idle;

    protected AgentBase(string agentType, ILogger logger)
    {
        AgentType = agentType;
        Logger = logger;
        Logger.LogDebug("Agent created: {AgentType} ({AgentId})", AgentType, AgentId);
    }

    public virtual Task StartAsync(CancellationToken cancellationToken = default)
    {
        Status = AgentStatus.Idle;
        Logger.LogInformation("Agent started: {AgentType} ({AgentId})", AgentType, AgentId);
        return OnStartAsync(cancellationToken);
    }

    public virtual async Task StopAsync(CancellationToken cancellationToken = default)
    {
        Status = AgentStatus.Stopped;
        await OnStopAsync(cancellationToken);
        Logger.LogInformation("Agent stopped: {AgentType} ({AgentId})", AgentType, AgentId);
    }

    protected virtual Task OnStartAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    protected virtual Task OnStopAsync(CancellationToken cancellationToken) => Task.CompletedTask;

    public async Task<object?> ExecuteAsync(string task,
                                             IReadOnlyDictionary<string, object>? parameters = null,
                                             Device? device = null,
                                             CancellationToken cancellationToken = default)
    {
        Status = AgentStatus.Busy;
        _lastTaskAt = DateTimeOffset.UtcNow;
        try
        {
            var result = await ExecuteCoreAsync(task, parameters ?? new Dictionary<string, object>(), device, cancellationToken);
            Interlocked.Increment(ref _tasksCompleted);
            Status = AgentStatus.Idle;
            return result;
        }
        catch (Exception ex)
        {
            Interlocked.Increment(ref _tasksFailed);
            Status = AgentStatus.Error;
            Logger.LogError(ex, "Agent {AgentType} task '{Task}' failed", AgentType, task);
            throw;
        }
    }

    /// <summary>Override to implement domain-specific task logic.</summary>
    protected abstract Task<object?> ExecuteCoreAsync(string task,
                                                       IReadOnlyDictionary<string, object> parameters,
                                                       Device? device,
                                                       CancellationToken cancellationToken);

    public IReadOnlyDictionary<string, object> GetMetrics() => new Dictionary<string, object>
    {
        ["agent_id"] = AgentId,
        ["agent_type"] = AgentType,
        ["status"] = Status.ToString().ToLowerInvariant(),
        ["tasks_completed"] = _tasksCompleted,
        ["tasks_failed"] = _tasksFailed,
        ["last_task_at"] = (object?)_lastTaskAt ?? "never"
    };
}
