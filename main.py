"""
Multi-Agent ESP32 Orchestration System — main entry point.

Usage:
    python main.py                    # Run API server (default)
    python main.py --mode server      # Same as above
    python main.py --mode cli         # Interactive CLI
    python main.py --mode demo        # Run built-in demo
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from logging_system.logger import setup_logging

logger = logging.getLogger(__name__)


def build_orchestrator(config: dict):
    """Instantiate and wire up the full orchestrator."""
    from orchestrator import Orchestrator
    from agents import (
        AIAgent,
        CommsAgent,
        FirmwareAgent,
        FrequencyAgent,
        ModulationAgent,
    )

    orch = Orchestrator(config)

    # Register all agents
    orch.register_agent(FrequencyAgent(config.get("frequency_agent", {})))
    orch.register_agent(ModulationAgent(config.get("modulation_agent", {})))
    orch.register_agent(FirmwareAgent(config.get("firmware_agent", {})))
    orch.register_agent(CommsAgent(config.get("comms_agent", {})))
    orch.register_agent(AIAgent(config.get("ai_agent", {})))

    return orch


def load_config(config_path: str) -> dict:
    """Load YAML config if available, else return empty dict."""
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.info("Config file not found at %s — using defaults", config_path)
        return {}
    except ImportError:
        logger.warning("PyYAML not installed — using defaults")
        return {}


# ------------------------------------------------------------------
# Server mode
# ------------------------------------------------------------------

def run_server(orchestrator, host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI/uvicorn server."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Install with: pip install uvicorn[standard]")
        sys.exit(1)

    from api import create_app
    app = create_app(orchestrator)

    logger.info("Starting API server on http://%s:%d", host, port)
    logger.info("  Docs: http://%s:%d/docs", host, port)
    logger.info("  WS:   ws://%s:%d/ws/telemetry", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


# ------------------------------------------------------------------
# Demo mode
# ------------------------------------------------------------------

async def run_demo(orchestrator):
    """
    Demonstrate the orchestrator without real hardware.
    Creates a simulated device and exercises each agent type.
    """
    from orchestrator.device import ESP32Device, DeviceCapability, DeviceStatus

    print("\n=== Multi-Agent ESP32 Demo ===\n")

    # Create a fake device
    device = ESP32Device(
        device_id="demo-001",
        name="DemoESP32",
        ip_address="192.168.1.100",
        capabilities=[
            DeviceCapability.WIFI,
            DeviceCapability.BLE,
            DeviceCapability.GPS,
        ],
    )
    device.status = DeviceStatus.ONLINE
    orchestrator.register_device(device)
    print(f"  Registered device: {device.name} ({device.device_id})")

    # Start orchestrator
    await orchestrator.start()
    print("  Orchestrator started")
    print(f"  Agents: {[a.agent_type for a in orchestrator.list_agents()]}")

    # Show status
    status = orchestrator.get_status()
    print(f"\n  Orchestrator status:")
    print(f"    Running: {status['running']}")
    print(f"    Agents:  {len(status['agents'])}")
    print(f"    Devices: {len(status['devices'])}")

    # Demo: frequency agent
    freq_agents = orchestrator.get_agents_by_type("frequency_agent")
    if freq_agents:
        task_id = await orchestrator.dispatch_task(
            freq_agents[0].agent_id,
            "get_frequency",
            {},
            device.device_id,
        )
        result = orchestrator.get_task_result(task_id)
        print(f"\n  FrequencyAgent get_frequency → {result}")

    # Demo: AI recommendation
    ai_agents = orchestrator.get_agents_by_type("ai_agent")
    if ai_agents:
        task_id = await orchestrator.dispatch_task(
            ai_agents[0].agent_id,
            "research",
            {"query": "Best modulation for long-range ESP32"},
        )
        result = orchestrator.get_task_result(task_id)
        if result:
            print(f"\n  AIAgent research response:")
            print(f"    {result.get('result', {}).get('response', '')[:200]}")

    # Demo: firmware build
    fw_agents = orchestrator.get_agents_by_type("firmware_agent")
    if fw_agents:
        task_id = await orchestrator.dispatch_task(
            fw_agents[0].agent_id,
            "build",
            {"template": "base", "features": ["wifi", "ble"], "version": "demo-1.0.0"},
        )
        result = orchestrator.get_task_result(task_id)
        if result:
            build_info = result.get("result", {})
            print(f"\n  FirmwareAgent build:")
            print(f"    build_id:  {build_info.get('build_id')}")
            print(f"    version:   {build_info.get('version')}")
            print(f"    compiled:  {build_info.get('compiled')}")

    await orchestrator.stop()
    print("\n  Orchestrator stopped — demo complete.\n")


# ------------------------------------------------------------------
# CLI mode
# ------------------------------------------------------------------

async def run_cli(orchestrator):
    """Simple interactive CLI for manual control."""
    await orchestrator.start()
    print("Multi-Agent ESP32 CLI. Type 'help' for commands, 'exit' to quit.")

    while True:
        try:
            line = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not line:
            continue
        if line == "exit":
            break
        if line == "help":
            print("  status         - Show orchestrator status")
            print("  devices        - List registered devices")
            print("  agents         - List registered agents")
            continue
        if line == "status":
            import json
            print(json.dumps(orchestrator.get_status(), indent=2))
        elif line == "devices":
            for d in orchestrator.list_devices():
                print(f"  {d.device_id}: {d.name} [{d.status.value}]")
        elif line == "agents":
            for a in orchestrator.list_agents():
                print(f"  {a.agent_id[:8]}: {a.agent_type} [{a.status.value}]")
        else:
            print(f"  Unknown command: {line}")

    await orchestrator.stop()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent ESP32 Orchestration System"
    )
    parser.add_argument(
        "--mode", choices=["server", "demo", "cli"], default="server",
        help="Execution mode (default: server)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="API server bind host")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument(
        "--config", default="config/default.yaml", help="Path to YAML config file"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--log-dir", default=None, help="Directory for log files")
    args = parser.parse_args()

    setup_logging(level=args.log_level, log_dir=args.log_dir)

    config = load_config(args.config)
    orchestrator = build_orchestrator(config)

    if args.mode == "server":
        run_server(orchestrator, host=args.host, port=args.port)
    elif args.mode == "demo":
        asyncio.run(run_demo(orchestrator))
    elif args.mode == "cli":
        asyncio.run(run_cli(orchestrator))


if __name__ == "__main__":
    main()
