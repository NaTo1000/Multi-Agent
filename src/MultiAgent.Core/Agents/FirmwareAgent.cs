using Microsoft.Extensions.Logging;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>Manages firmware generation, compilation and OTA deployment.</summary>
public sealed class FirmwareAgent : AgentBase
{
    public FirmwareAgent(ILogger<FirmwareAgent> logger) : base("firmware", logger) { }

    protected override Task<object?> ExecuteCoreAsync(string task,
                                                        IReadOnlyDictionary<string, object> parameters,
                                                        Device? device,
                                                        CancellationToken cancellationToken)
    {
        return task switch
        {
            "build" => Task.FromResult<object?>(new { status = "built", artifact = "firmware.bin" }),
            "flash" when device is not null
                => Task.FromResult<object?>(new { status = "flashed", device_id = device.DeviceId }),
            "flash" => throw new ArgumentException("A target device is required for 'flash'"),
            _ => throw new NotSupportedException($"Firmware task '{task}' not supported")
        };
    }
}
