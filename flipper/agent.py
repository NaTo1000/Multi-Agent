"""
FlipperAgent — orchestrator-integrated agent for the Flipper Zero.

This agent follows the same :class:`~orchestrator.agent.AgentBase` interface as
all other agents in the system so it can be registered with the central
orchestrator.  It also exposes a ``run_standalone()`` coroutine so the module
can operate without any orchestrator when the main system is not available.
"""

import logging
from typing import Any, Dict, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

from .device import FlipperDevice, FlipperConnectionError
from .protocols import SubGHzProtocol, InfraredProtocol, NFCProtocol, BadUSBProtocol

logger = logging.getLogger(__name__)


class FlipperAgent(AgentBase):
    """
    Agent that bridges the Flipper Zero into the multi-agent orchestrator.

    Supported tasks
    ---------------
    ``status``
        Return current Flipper Zero device info and status.
    ``subghz_receive``
        Listen on a Sub-GHz frequency and return the first captured signal.
        Params: ``frequency_hz`` (float, default 433920000).
    ``subghz_transmit``
        Transmit a Sub-GHz signal.
        Params: ``frequency_hz``, ``modulation``, ``data`` (hex string or list of ints).
    ``nfc_detect``
        Scan for a nearby NFC card.
    ``nfc_emulate``
        Emulate an NFC card.
        Params: ``uid``, ``technology`` (optional).
    ``ir_transmit``
        Transmit an IR command.
        Params: ``protocol``, ``address``, ``command``.
    ``bad_usb_type``
        Type a string on the target host.
        Params: ``text``, ``delay_ms`` (optional).
    ``run_command``
        Execute an arbitrary Flipper CLI command.
        Params: ``command`` (string).
    """

    TASKS = {
        "status",
        "subghz_receive",
        "subghz_transmit",
        "nfc_detect",
        "nfc_emulate",
        "ir_transmit",
        "bad_usb_type",
        "run_command",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("flipper_agent", config)
        port = self.config.get("port", None)  # None → simulated
        baud = int(self.config.get("baud_rate", FlipperDevice.DEFAULT_BAUD))
        timeout = float(self.config.get("timeout", 5.0))
        self._flipper = FlipperDevice(port=port, baud_rate=baud, timeout=timeout)
        self._subghz = SubGHzProtocol(self._flipper)
        self._ir = InfraredProtocol(self._flipper)
        self._nfc = NFCProtocol(self._flipper)
        self._bad_usb = BadUSBProtocol(self._flipper)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _on_start(self) -> None:
        try:
            await self._flipper.connect()
        except FlipperConnectionError as exc:
            logger.warning("FlipperAgent: could not connect — %s", exc)

    async def _on_stop(self) -> None:
        await self._flipper.disconnect()

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],  # ESP32 device (not used by this agent)
    ) -> Any:
        if task == "status":
            return await self._get_status()
        if task == "subghz_receive":
            return await self._subghz_receive(params)
        if task == "subghz_transmit":
            return await self._subghz_transmit(params)
        if task == "nfc_detect":
            return await self._nfc_detect()
        if task == "nfc_emulate":
            return await self._nfc_emulate(params)
        if task == "ir_transmit":
            return await self._ir_transmit(params)
        if task == "bad_usb_type":
            return await self._bad_usb_type(params)
        if task == "run_command":
            return await self._run_command(params)
        raise ValueError(f"Unknown FlipperAgent task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _get_status(self) -> Dict[str, Any]:
        info = await self._flipper.get_info()
        return {
            "device": self._flipper.to_dict(),
            "firmware": info.software_version,
            "hardware": info.hardware_version,
            "serial": info.serial_number,
        }

    async def _subghz_receive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        freq = float(params.get("frequency_hz", 433_920_000))
        timeout = float(params.get("timeout_s", 5.0))
        signal = await self._subghz.receive(frequency_hz=freq, timeout_s=timeout)
        if signal is None:
            return {"captured": False, "frequency_hz": freq}
        return {
            "captured": True,
            "frequency_hz": signal.frequency_hz,
            "modulation": signal.modulation,
            "data": list(signal.data),
            "raw_lines": signal.raw_lines,
        }

    async def _subghz_transmit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from .device import SubGHzSignal
        freq = float(params.get("frequency_hz", 433_920_000))
        modulation = str(params.get("modulation", "RAW"))
        raw_data = params.get("data", [])
        if isinstance(raw_data, str):
            data = bytes(int(b, 16) for b in raw_data.split())
        else:
            data = bytes(raw_data)
        signal = SubGHzSignal(frequency_hz=freq, modulation=modulation, data=data)
        ok = await self._subghz.transmit(signal)
        return {"ok": ok, "frequency_hz": freq, "modulation": modulation}

    async def _nfc_detect(self) -> Dict[str, Any]:
        card = await self._nfc.detect()
        if card is None:
            return {"detected": False}
        return {
            "detected": True,
            "uid": card.uid,
            "technology": card.technology,
            "atqa": card.atqa,
            "sak": card.sak,
        }

    async def _nfc_emulate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uid = str(params.get("uid", ""))
        tech = str(params.get("technology", "Mifare Classic"))
        ok = await self._nfc.emulate(uid, tech)
        return {"ok": ok, "uid": uid, "technology": tech}

    async def _ir_transmit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        protocol = str(params.get("protocol", "NEC"))
        address = int(params.get("address", 0))
        command = int(params.get("command", 0))
        ok = await self._ir.transmit(protocol, address, command)
        return {"ok": ok, "protocol": protocol, "address": address, "command": command}

    async def _bad_usb_type(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = str(params.get("text", ""))
        delay_ms = int(params.get("delay_ms", BadUSBProtocol.DUCKY_DELAY_DEFAULT))
        ok = await self._bad_usb.type_string(text, delay_ms)
        return {"ok": ok, "text_length": len(text)}

    async def _run_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = str(params.get("command", "help"))
        output = await self._flipper.run_command(command)
        return {"command": command, "output": output}

    # ------------------------------------------------------------------
    # Standalone operation
    # ------------------------------------------------------------------

    async def run_standalone(self, tasks: list) -> list:
        """
        Run this agent independently from the orchestrator.

        Parameters
        ----------
        tasks:
            List of ``{"task": str, "params": dict}`` dicts to execute in
            sequence.

        Returns
        -------
        list
            Results in the same order as *tasks*.
        """
        await self._on_start()
        results = []
        for item in tasks:
            task_name = item.get("task", "status")
            task_params = item.get("params", {})
            try:
                result = await self.execute(task_name, task_params, None)
            except Exception as exc:  # pylint: disable=broad-except
                result = {"error": str(exc)}
            results.append({"task": task_name, "result": result})
        await self._on_stop()
        return results
