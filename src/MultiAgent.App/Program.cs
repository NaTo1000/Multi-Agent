using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using MultiAgent.Core.Agents;
using MultiAgent.Core.FaultTolerance;
using MultiAgent.Core.FlipperZero;
using MultiAgent.Core.Interop;
using MultiAgent.Core.Models;
using MultiAgent.Core.Orchestration;

// ─── Logging ───────────────────────────────────────────────────────────────
var services = new ServiceCollection()
    .AddLogging(b => b.AddConsole().SetMinimumLevel(LogLevel.Information))
    .BuildServiceProvider();

var logFactory = services.GetRequiredService<ILoggerFactory>();

// ─── Mode selection ─────────────────────────────────────────────────────────
var mode = args.Length > 0 ? args[0].ToLowerInvariant() : "demo";

Console.WriteLine("╔══════════════════════════════════════════════════╗");
Console.WriteLine("║        MultiAgent C# Orchestration System        ║");
Console.WriteLine($"║  Mode: {mode,-41}║");
Console.WriteLine("╚══════════════════════════════════════════════════╝");
Console.WriteLine();

switch (mode)
{
    case "demo":
        await RunDemoAsync(logFactory);
        break;
    case "status":
        await RunStatusAsync(logFactory);
        break;
    default:
        Console.Error.WriteLine($"Unknown mode '{mode}'. Available: demo, status");
        Environment.Exit(1);
        break;
}

// ─── Demo ────────────────────────────────────────────────────────────────────
static async Task RunDemoAsync(ILoggerFactory logFactory)
{
    Console.WriteLine("=== Demo Mode ===");

    // Build orchestrator
    var orch = new Orchestrator(logFactory.CreateLogger<Orchestrator>(),
                                healthCheckInterval: TimeSpan.FromSeconds(30));

    // Register agents
    orch.RegisterAgent(new FrequencyAgent(logFactory.CreateLogger<FrequencyAgent>()));
    orch.RegisterAgent(new ModulationAgent(logFactory.CreateLogger<ModulationAgent>()));
    orch.RegisterAgent(new FirmwareAgent(logFactory.CreateLogger<FirmwareAgent>()));
    orch.RegisterAgent(new CommsAgent(logFactory.CreateLogger<CommsAgent>()));
    orch.RegisterAgent(new AiAgent(logFactory.CreateLogger<AiAgent>()));

    // Register a demo device
    var device = new Device("device-001", "ESP32-Demo", ipAddress: "192.168.1.100");
    orch.RegisterDevice(device);

    // Subscribe to events
    orch.OrchestratorEvent += (_, e) =>
        Console.WriteLine($"  [EVENT] {e.EventName}");

    await orch.StartAsync();

    // --- Sequencing engine demo ---
    Console.WriteLine("\n>>> Sequencing engine demo <<<");
    var seqEngine = new SequencingEngine(logFactory.CreateLogger<SequencingEngine>());
    seqEngine.Enqueue(async ct => { await Task.Delay(10, ct); Console.WriteLine("  Task B (priority=2) executed"); }, "task-b", priority: 2);
    seqEngine.Enqueue(async ct => { await Task.Delay(10, ct); Console.WriteLine("  Task A (priority=1) executed"); }, "task-a", priority: 1);
    seqEngine.Enqueue(async ct => { await Task.Delay(10, ct); Console.WriteLine("  Task C (priority=5) executed"); }, "task-c", priority: 5);
    Console.WriteLine($"  Pending: {seqEngine.PendingCount}");
    await seqEngine.RunAllAsync();

    // --- Fault detection demo ---
    Console.WriteLine("\n>>> Fault detection demo <<<");
    var detector = new EwmaFaultDetector(logFactory.CreateLogger<EwmaFaultDetector>());
    double[] samples = [10, 10.1, 9.9, 10.0, 10.05, 50.0 /* spike */];
    foreach (var s in samples)
    {
        var fault = detector.RecordSample(s);
        Console.WriteLine($"  sample={s,5:F1}  fault={fault}");
    }

    // --- Rollback demo ---
    Console.WriteLine("\n>>> Rollback demo <<<");
    var rollback = new RollbackManager(logFactory.CreateLogger<RollbackManager>());
    rollback.Register("op-1", async ct => { await Task.Delay(10, ct); Console.WriteLine("  Rollback op-1 executed"); });
    rollback.Register("op-2", async ct => { await Task.Delay(10, ct); Console.WriteLine("  Rollback op-2 executed"); });
    rollback.TriggerAllRollbacks();
    await Task.Delay(200); // let fire-and-forget tasks finish

    // --- Flipper Zero shim demo ---
    Console.WriteLine("\n>>> Flipper Zero shim demo <<<");
    var flipper = new FlipperZeroShim(logFactory.CreateLogger<FlipperZeroShim>());
    await flipper.ConnectAsync("/dev/ttyUSB0");
    var capture = await flipper.CaptureSubGhzAsync(433_920_000);
    Console.WriteLine($"  Capture bytes: {capture.Length}");
    await flipper.DisconnectAsync();

    // --- iOS interop stubs demo ---
    Console.WriteLine("\n>>> iOS interop stubs demo <<<");
    var btPerm = await IosInteropFacade.RequestBluetoothPermissionAsync();
    Console.WriteLine($"  Bluetooth permission granted (stub): {btPerm}");

    // --- Dispatch tasks ---
    Console.WriteLine("\n>>> Dispatching tasks <<<");
    var agents = orch.ListAgents();
    var freqAgent = orch.GetAgentsByType("frequency").First();
    var taskId = await orch.DispatchTaskAsync(freqAgent.AgentId, "scan");
    var result = orch.GetTaskResult(taskId);
    Console.WriteLine($"  Task {taskId[..8]}... success={result?.Success}");

    await orch.StopAsync();
    Console.WriteLine("\nDemo complete.");
}

// ─── Status ───────────────────────────────────────────────────────────────────
static async Task RunStatusAsync(ILoggerFactory logFactory)
{
    Console.WriteLine("=== Status Mode ===");
    var orch = new Orchestrator(logFactory.CreateLogger<Orchestrator>());
    orch.RegisterAgent(new FrequencyAgent(logFactory.CreateLogger<FrequencyAgent>()));
    await orch.StartAsync();

    var agents = orch.ListAgents();
    Console.WriteLine($"Agents: {agents.Count}");
    foreach (var a in agents)
        Console.WriteLine($"  {a.AgentType,-15} {a.Status}  ({a.AgentId[..8]}...)");

    await orch.StopAsync();
}
