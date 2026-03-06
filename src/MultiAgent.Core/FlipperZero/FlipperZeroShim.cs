using Microsoft.Extensions.Logging;

namespace MultiAgent.Core.FlipperZero;

/// <summary>
/// Placeholder shim for Flipper Zero hardware integration.
/// Replace stub implementations with real serial/USB protocol code
/// when running on a platform with Flipper Zero access.
/// </summary>
public sealed class FlipperZeroShim
{
    private readonly ILogger<FlipperZeroShim> _logger;
    private bool _connected;

    public bool IsConnected => _connected;
    public string? DevicePath { get; private set; }

    public FlipperZeroShim(ILogger<FlipperZeroShim> logger)
    {
        _logger = logger;
    }

    /// <summary>Open a connection to the Flipper Zero at <paramref name="path"/>.</summary>
    public Task<bool> ConnectAsync(string path, CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] Connecting to {Path}", path);
        DevicePath = path;
        _connected = true;          // Stub: always succeeds
        return Task.FromResult(true);
    }

    /// <summary>Disconnect from the Flipper Zero.</summary>
    public Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] Disconnecting from {Path}", DevicePath);
        _connected = false;
        DevicePath = null;
        return Task.CompletedTask;
    }

    /// <summary>
    /// Send a Sub-GHz raw capture command.  Returns a stub payload.
    /// </summary>
    public Task<byte[]> CaptureSubGhzAsync(double frequencyHz, int durationMs = 500,
                                            CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] Sub-GHz capture at {Freq:F0} Hz for {Duration} ms",
                                frequencyHz, durationMs);
        // Stub: return an empty capture
        return Task.FromResult(Array.Empty<byte>());
    }

    /// <summary>
    /// Transmit a raw Sub-GHz signal.  No-op in stub mode.
    /// </summary>
    public Task TransmitSubGhzAsync(double frequencyHz, byte[] data,
                                     CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] Sub-GHz transmit at {Freq:F0} Hz ({Bytes} bytes)",
                                frequencyHz, data.Length);
        return Task.CompletedTask;
    }

    /// <summary>
    /// Read NFC/RFID tag data.  Returns a stub payload.
    /// </summary>
    public Task<byte[]> ReadNfcAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] NFC read");
        return Task.FromResult(Array.Empty<byte>());
    }

    /// <summary>
    /// Run an infrared capture/replay operation.  No-op in stub mode.
    /// </summary>
    public Task InfraredReplayAsync(byte[] signal, CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[FlipperZero STUB] IR replay ({Bytes} bytes)", signal.Length);
        return Task.CompletedTask;
    }
}
