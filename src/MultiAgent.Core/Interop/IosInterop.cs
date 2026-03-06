namespace MultiAgent.Core.Interop;

/// <summary>
/// iOS/Swift interop touchpoints (stubs).
///
/// In a real Xamarin.iOS or .NET MAUI project these would be replaced with
/// native bindings to Swift frameworks (e.g. CoreBluetooth, CoreLocation).
/// Exposed as a static façade so the stubs can be replaced at runtime via
/// <see cref="IIosInterop"/>.
/// </summary>
public static class IosInteropFacade
{
    private static IIosInterop _impl = new StubIosInterop();

    /// <summary>Replace the stub with a real implementation at start-up.</summary>
    public static void Register(IIosInterop impl) => _impl = impl;

    public static Task<bool> RequestBluetoothPermissionAsync() => _impl.RequestBluetoothPermissionAsync();
    public static Task<bool> RequestLocationPermissionAsync() => _impl.RequestLocationPermissionAsync();
    public static Task<(double Lat, double Lon)?> GetCurrentLocationAsync() => _impl.GetCurrentLocationAsync();
    public static Task<IReadOnlyList<string>> ScanBluetoothDevicesAsync(TimeSpan timeout) => _impl.ScanBluetoothDevicesAsync(timeout);
}

/// <summary>Contract for iOS native interop.</summary>
public interface IIosInterop
{
    Task<bool> RequestBluetoothPermissionAsync();
    Task<bool> RequestLocationPermissionAsync();
    Task<(double Lat, double Lon)?> GetCurrentLocationAsync();
    Task<IReadOnlyList<string>> ScanBluetoothDevicesAsync(TimeSpan timeout);
}

/// <summary>
/// No-op stub used on non-iOS platforms or during testing.
/// </summary>
public sealed class StubIosInterop : IIosInterop
{
    public Task<bool> RequestBluetoothPermissionAsync() => Task.FromResult(true);
    public Task<bool> RequestLocationPermissionAsync() => Task.FromResult(true);
    public Task<(double Lat, double Lon)?> GetCurrentLocationAsync() =>
        Task.FromResult<(double, double)?>(null);
    public Task<IReadOnlyList<string>> ScanBluetoothDevicesAsync(TimeSpan timeout) =>
        Task.FromResult<IReadOnlyList<string>>([]);
}
