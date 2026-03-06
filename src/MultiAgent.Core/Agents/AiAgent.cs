using Microsoft.Extensions.Logging;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>AI-driven agent for adaptive optimisation and research queries.</summary>
public sealed class AiAgent : AgentBase
{
    public AiAgent(ILogger<AiAgent> logger) : base("ai", logger) { }

    protected override Task<object?> ExecuteCoreAsync(string task,
                                                        IReadOnlyDictionary<string, object> parameters,
                                                        Device? device,
                                                        CancellationToken cancellationToken)
    {
        return task switch
        {
            "optimise" => Task.FromResult<object?>(new
            {
                status = "ok",
                recommendation = "Switch to GFSK at 915 MHz for lower interference",
                device_id = device?.DeviceId
            }),
            "research" when parameters.TryGetValue("query", out var q)
                => Task.FromResult<object?>(new { status = "ok", answer = $"AI answer for: {q}" }),
            _ => throw new NotSupportedException($"AI task '{task}' not supported")
        };
    }
}
