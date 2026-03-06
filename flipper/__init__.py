"""
Flipper Zero module — standalone and orchestrator-integrated interface.

This module can be used in two ways:

  1. **Standalone** — run as a script/CLI:
         python -m flipper --port /dev/ttyACM0 subghz transmit --file signal.sub

  2. **Orchestrated** — register the FlipperAgent with the main orchestrator:
         from flipper import FlipperAgent
         orchestrator.register_agent(FlipperAgent({"port": "/dev/ttyACM0"}))
"""

from .device import FlipperDevice, FlipperConnectionError, FlipperCommandError
from .protocols import SubGHzProtocol, InfraredProtocol, NFCProtocol, BadUSBProtocol
from .agent import FlipperAgent

__all__ = [
    "FlipperDevice",
    "FlipperConnectionError",
    "FlipperCommandError",
    "SubGHzProtocol",
    "InfraredProtocol",
    "NFCProtocol",
    "BadUSBProtocol",
    "FlipperAgent",
]
