namespace MultiAgent.Core.Models;

/// <summary>
/// Represents a single physical device (e.g. an ESP32 module) managed by the orchestrator.
/// </summary>
public sealed class Device
{
    public string DeviceId { get; init; }
    public string Name { get; init; }
    public string? IpAddress { get; set; }
    public string? MacAddress { get; init; }
    public DeviceCapability Capabilities { get; init; }
    public DeviceStatus Status { get; set; } = DeviceStatus.Unknown;
    public string FirmwareVersion { get; set; } = "0.0.0";
    public double CurrentFrequencyHz { get; set; } = 2_400_000_000.0;
    public int? Rssi { get; set; }
    public DateTimeOffset? LastSeen { get; set; }
    public Dictionary<string, object> Telemetry { get; } = [];

    public Device(string deviceId, string name,
                  string? ipAddress = null, string? macAddress = null,
                  DeviceCapability capabilities = DeviceCapability.Wifi | DeviceCapability.Ble)
    {
        DeviceId = deviceId;
        Name = name;
        IpAddress = ipAddress;
        MacAddress = macAddress;
        Capabilities = capabilities;
    }

    public bool HasCapability(DeviceCapability cap) => (Capabilities & cap) == cap;

    public void UpdateTelemetry(IReadOnlyDictionary<string, object> data)
    {
        foreach (var kv in data)
            Telemetry[kv.Key] = kv.Value;
        LastSeen = DateTimeOffset.UtcNow;
        if (data.TryGetValue("rssi", out var rssi) && rssi is int r) Rssi = r;
        if (data.TryGetValue("frequency_hz", out var freq) && freq is double f) CurrentFrequencyHz = f;
    }
}
