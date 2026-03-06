using Microsoft.Extensions.Logging;
using MultiAgent.Core.Interfaces;

namespace MultiAgent.Core.Orchestration;

/// <summary>
/// Priority-based async task sequencing engine.
/// Lower priority value = higher urgency (processed first).
/// Mirrors the Python <c>TaskScheduler</c>.
/// </summary>
public sealed class SequencingEngine : ISequencingEngine
{
    private readonly ILogger<SequencingEngine> _logger;
    private readonly int _maxConcurrent;
    private readonly SemaphoreSlim _semaphore;

    private readonly object _lock = new();
    private readonly List<QueuedWork> _queue = [];

    public int PendingCount
    {
        get { lock (_lock) return _queue.Count; }
    }

    public SequencingEngine(ILogger<SequencingEngine> logger, int maxConcurrent = 10)
    {
        _logger = logger;
        _maxConcurrent = maxConcurrent;
        _semaphore = new SemaphoreSlim(maxConcurrent, maxConcurrent);
    }

    public void Enqueue(Func<CancellationToken, Task> work, string taskId, int priority = 5)
    {
        lock (_lock)
        {
            _queue.Add(new QueuedWork(taskId, priority, work));
            _queue.Sort((a, b) => a.Priority.CompareTo(b.Priority));
        }
        _logger.LogDebug("Enqueued task {TaskId} (priority={Priority})", taskId, priority);
    }

    public async Task RunNextAsync(CancellationToken cancellationToken = default)
    {
        QueuedWork? item;
        lock (_lock)
        {
            if (_queue.Count == 0) return;
            item = _queue[0];
            _queue.RemoveAt(0);
        }

        await _semaphore.WaitAsync(cancellationToken);
        try
        {
            await item.Work(cancellationToken);
        }
        finally
        {
            _semaphore.Release();
        }
    }

    public async Task RunAllAsync(CancellationToken cancellationToken = default)
    {
        while (true)
        {
            List<QueuedWork> batch;
            lock (_lock)
            {
                if (_queue.Count == 0) break;
                var take = Math.Min(_maxConcurrent, _queue.Count);
                batch = _queue.GetRange(0, take);
                _queue.RemoveRange(0, take);
            }

            await Task.WhenAll(batch.Select(item => RunWithSemaphoreAsync(item, cancellationToken)));
        }
    }

    private async Task RunWithSemaphoreAsync(QueuedWork item, CancellationToken cancellationToken)
    {
        await _semaphore.WaitAsync(cancellationToken);
        try
        {
            await item.Work(cancellationToken);
        }
        finally
        {
            _semaphore.Release();
        }
    }

    public void Clear()
    {
        lock (_lock) _queue.Clear();
    }

    private sealed record QueuedWork(string TaskId, int Priority, Func<CancellationToken, Task> Work);
}
