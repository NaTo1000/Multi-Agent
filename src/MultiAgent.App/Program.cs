using MultiAgent.Core;

var orchestrator = new AgentOrchestrator();
orchestrator.RegisterAgent("frequency-agent");
orchestrator.RegisterAgent("modulation-agent");
orchestrator.RegisterAgent("firmware-agent");

Console.WriteLine($"Multi-Agent Orchestration System — {orchestrator.AgentCount} agent(s) registered.");
foreach (var id in orchestrator.AgentIds)
    Console.WriteLine($"  • {id}");

