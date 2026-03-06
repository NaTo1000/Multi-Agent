using Microsoft.Extensions.Logging;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>Manages cloud and device communications (WiFi, BLE, LoRa).</summary>
public sealed class CommsAgent : AgentBase
{
    public CommsAgent(ILogger<CommsAgent> logger) : base("comms", logger) { }

    protected override Task<object?> ExecuteCoreAsync(string task,
                                                        IReadOnlyDictionary<string, object> parameters,
                                                        Device? device,
                                                        CancellationToken cancellationToken)
    {
        return task switch
        {
            "cloud_push" => Task.FromResult<object?>(new { status = "pushed" }),
            "ble_advertise" => Task.FromResult<object?>(new { status = "advertising" }),
            "ping" when device is not null
                => Task.FromResult<object?>(new { status = "pong", device_id = device.DeviceId }),
            _ => throw new NotSupportedException($"Comms task '{task}' not supported")
        };
    }
}
