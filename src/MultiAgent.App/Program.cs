using MultiAgent.Core;

var orchestrator = new Orchestrator();

Console.WriteLine("Multi-Agent Orchestration System");
Console.WriteLine($"Registered agents: {orchestrator.Agents.Count}");
Console.WriteLine("Use 'dotnet run --project src/MultiAgent.App -- demo' to run a demo.");

