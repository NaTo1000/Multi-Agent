namespace MultiAgent.Core.Interfaces;

/// <summary>Contract for detecting faults in a stream of metric samples.</summary>
public interface IFaultDetector
{
    /// <summary>Feed a new metric sample; returns true when an anomaly is detected.</summary>
    bool RecordSample(double value);

    /// <summary>Reset the detector state.</summary>
    void Reset();
}

/// <summary>Contract for executing non-blocking rollback actions.</summary>
public interface IRollbackManager
{
    /// <summary>
    /// Registers a rollback action identified by <paramref name="operationId"/>.
    /// Earlier registrations are executed first.
    /// </summary>
    void Register(string operationId, Func<CancellationToken, Task> rollback);

    /// <summary>Fire-and-forget rollback of a specific operation.</summary>
    void TriggerRollback(string operationId);

    /// <summary>Fire-and-forget rollback of all registered operations (LIFO order).</summary>
    void TriggerAllRollbacks();
}
