using Microsoft.Extensions.Logging;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>Handles frequency scanning, locking and fleet synchronisation.</summary>
public sealed class FrequencyAgent : AgentBase
{
    public FrequencyAgent(ILogger<FrequencyAgent> logger) : base("frequency", logger) { }

    protected override Task<object?> ExecuteCoreAsync(string task,
                                                        IReadOnlyDictionary<string, object> parameters,
                                                        Device? device,
                                                        CancellationToken cancellationToken)
    {
        return task switch
        {
            "scan" => Task.FromResult<object?>(new { bands = new[] { "2.4GHz", "5GHz" }, status = "scanned" }),
            "lock" when parameters.TryGetValue("frequency_hz", out var freq)
                => Task.FromResult<object?>(new { status = "locked", frequency_hz = freq }),
            "sync" => Task.FromResult<object?>(new { status = "synced", device_id = device?.DeviceId }),
            _ => throw new NotSupportedException($"Frequency task '{task}' not supported")
        };
    }
}
