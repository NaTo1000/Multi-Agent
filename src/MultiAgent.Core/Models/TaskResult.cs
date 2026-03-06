namespace MultiAgent.Core.Models;

/// <summary>Immutable snapshot of a dispatched task and its outcome.</summary>
public sealed record TaskResult(
    string TaskId,
    string AgentId,
    string TaskName,
    object? Result,
    DateTimeOffset CompletedAt,
    bool Success,
    string? ErrorMessage = null);
