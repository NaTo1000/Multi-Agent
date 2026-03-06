namespace MultiAgent.Core.Models;

/// <summary>Hardware capabilities a device may expose.</summary>
[Flags]
public enum DeviceCapability
{
    None = 0,
    Wifi = 1,
    Ble = 2,
    Gps = 4,
    Gnss = 8,
    Lora = 16
}
