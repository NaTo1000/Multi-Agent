using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;

namespace MultiAgent.Core.FaultTolerance;

/// <summary>
/// Façade that combines fault detection with automatic rollback triggering.
/// </summary>
public sealed class FaultTolerantSequencer
{
    private readonly IFaultDetector _detector;
    private readonly IRollbackManager _rollback;
    private readonly ISequencingEngine _engine;
    private readonly ILogger<FaultTolerantSequencer> _logger;

    public FaultTolerantSequencer(
        IFaultDetector detector,
        IRollbackManager rollback,
        ISequencingEngine engine,
        ILogger<FaultTolerantSequencer> logger)
    {
        _detector = detector;
        _rollback = rollback;
        _engine = engine;
        _logger = logger;
    }

    /// <summary>
    /// Enqueue a work item; if the health metric indicates a fault, trigger all rollbacks
    /// before enqueuing.
    /// </summary>
    public void Enqueue(Func<CancellationToken, Task> work, string taskId,
                        int priority = 5, double? healthMetric = null)
    {
        if (healthMetric.HasValue && _detector.RecordSample(healthMetric.Value))
        {
            _logger.LogWarning("Fault detected for task {TaskId}; triggering rollbacks", taskId);
            _rollback.TriggerAllRollbacks();
        }

        _engine.Enqueue(work, taskId, priority);
    }

    public Task RunAllAsync(CancellationToken cancellationToken = default)
        => _engine.RunAllAsync(cancellationToken);

    public int PendingCount => _engine.PendingCount;
}
