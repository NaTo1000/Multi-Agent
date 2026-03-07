namespace MultiAgent.Core;

/// <summary>Encapsulates the outcome of an agent task execution.</summary>
public sealed record AgentResult(
    string AgentId,
    string TaskName,
    bool Success,
    string? Message = null,
    object? Payload = null);
