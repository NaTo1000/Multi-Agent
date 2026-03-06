using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;

namespace MultiAgent.Core.FaultTolerance;

/// <summary>
/// Non-blocking rollback manager.
/// Rollback actions are fired as background tasks (fire-and-forget) so they
/// never block the caller — matching the Python <c>RollbackManager</c> which
/// uses <c>asyncio.ensure_future</c>.
/// </summary>
public sealed class RollbackManager : IRollbackManager
{
    private readonly ILogger<RollbackManager> _logger;
    private readonly ConcurrentDictionary<string, Func<CancellationToken, Task>> _rollbacks = new();
    private readonly List<string> _order = [];   // insertion order for LIFO replay
    private readonly object _orderLock = new();

    public RollbackManager(ILogger<RollbackManager> logger)
    {
        _logger = logger;
    }

    public void Register(string operationId, Func<CancellationToken, Task> rollback)
    {
        _rollbacks[operationId] = rollback;
        lock (_orderLock)
        {
            if (!_order.Contains(operationId))
                _order.Add(operationId);
        }
        _logger.LogDebug("Registered rollback for operation {OperationId}", operationId);
    }

    public void TriggerRollback(string operationId)
    {
        if (!_rollbacks.TryGetValue(operationId, out var rollback))
        {
            _logger.LogWarning("No rollback registered for {OperationId}", operationId);
            return;
        }

        _logger.LogInformation("Triggering non-blocking rollback for {OperationId}", operationId);
        _ = Task.Run(async () =>
        {
            try { await rollback(CancellationToken.None); }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Rollback failed for {OperationId}", operationId);
            }
        });
    }

    public void TriggerAllRollbacks()
    {
        List<string> ordered;
        lock (_orderLock)
        {
            ordered = new List<string>(_order);
            ordered.Reverse();   // LIFO
        }

        _logger.LogInformation("Triggering non-blocking rollback for all {Count} operation(s)", ordered.Count);
        foreach (var id in ordered)
            TriggerRollback(id);
    }
}
