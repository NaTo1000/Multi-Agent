using Microsoft.Extensions.Logging;
using MultiAgent.Core.Models;

namespace MultiAgent.Core.Agents;

/// <summary>Handles modulation selection and adaptive switching.</summary>
public sealed class ModulationAgent : AgentBase
{
    private static readonly string[] SupportedModes = ["AM", "FM", "FSK", "GFSK", "LoRa", "QPSK", "QAM16"];

    public ModulationAgent(ILogger<ModulationAgent> logger) : base("modulation", logger) { }

    protected override Task<object?> ExecuteCoreAsync(string task,
                                                        IReadOnlyDictionary<string, object> parameters,
                                                        Device? device,
                                                        CancellationToken cancellationToken)
    {
        return task switch
        {
            "list_modes" => Task.FromResult<object?>(SupportedModes),
            "set_mode" when parameters.TryGetValue("mode", out var mode)
                => Task.FromResult<object?>(new { status = "ok", mode }),
            "adaptive_select" => Task.FromResult<object?>(new { status = "ok", selected = "GFSK" }),
            _ => throw new NotSupportedException($"Modulation task '{task}' not supported")
        };
    }
}
