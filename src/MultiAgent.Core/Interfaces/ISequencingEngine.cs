namespace MultiAgent.Core.Interfaces;

/// <summary>Contract for the priority-based task sequencing engine.</summary>
public interface ISequencingEngine
{
    /// <summary>Enqueue a work item with the given priority (lower = higher urgency).</summary>
    void Enqueue(Func<CancellationToken, Task> work, string taskId, int priority = 5);

    /// <summary>Execute the highest-priority queued item.</summary>
    Task RunNextAsync(CancellationToken cancellationToken = default);

    /// <summary>Drain the entire queue, respecting max-concurrency.</summary>
    Task RunAllAsync(CancellationToken cancellationToken = default);

    int PendingCount { get; }
    void Clear();
}
