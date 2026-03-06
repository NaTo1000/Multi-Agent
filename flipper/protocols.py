"""
Flipper Zero protocol helpers.

Each class wraps a specific Flipper Zero subsystem and provides a clean
async API that delegates to :class:`~flipper.device.FlipperDevice` for the
actual serial communication.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .device import FlipperDevice, SubGHzSignal, NFCCard, FlipperCommandError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-GHz
# ---------------------------------------------------------------------------

#: Supported ISM bands and their canonical centre frequencies (Hz)
SUBGHZ_PRESETS: Dict[str, float] = {
    "433.92MHz": 433_920_000,
    "315MHz":    315_000_000,
    "868.35MHz": 868_350_000,
    "915MHz":    915_000_000,
}


class SubGHzProtocol:
    """
    Sub-GHz radio protocol handler.

    Supports receiving, transmitting, and replaying signals on common ISM
    bands.  Signal files use the standard Flipper ``.sub`` format.
    """

    def __init__(self, device: FlipperDevice):
        self._dev = device

    async def receive(
        self,
        frequency_hz: float = SUBGHZ_PRESETS["433.92MHz"],
        timeout_s: float = 5.0,
    ) -> Optional[SubGHzSignal]:
        """
        Listen on *frequency_hz* for up to *timeout_s* seconds.

        Returns a :class:`~flipper.device.SubGHzSignal` if a signal is
        captured, otherwise ``None``.
        """
        logger.info("SubGHz: listening on %.3f MHz (timeout=%ss)",
                    frequency_hz / 1e6, timeout_s)
        return await self._dev.subghz_receive(frequency_hz, timeout_s)

    async def transmit(self, signal: SubGHzSignal) -> bool:
        """Transmit a previously captured or synthesised signal."""
        logger.info("SubGHz: transmitting on %.3f MHz (%s)",
                    signal.frequency_hz / 1e6, signal.modulation)
        return await self._dev.subghz_transmit(signal)

    async def replay_file(self, path: str) -> bool:
        """Load a ``.sub`` file and replay it."""
        content = Path(path).read_text(encoding="utf-8")
        signal = self._parse_sub_file(content)
        return await self.transmit(signal)

    @staticmethod
    def _parse_sub_file(content: str) -> SubGHzSignal:
        """Parse Flipper ``.sub`` file content into a SubGHzSignal."""
        props: Dict[str, str] = {}
        raw_lines: List[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("RAW_Data:") or line.startswith("Data:"):
                raw_lines.append(line)
            elif ":" in line:
                key, _, val = line.partition(":")
                props[key.strip()] = val.strip()

        freq = float(props.get("Frequency", "433920000"))
        modulation = props.get("Protocol", "RAW")
        key_hex = props.get("Key", "")
        data = bytes(int(b, 16) for b in key_hex.split()) if key_hex else b""
        preset = props.get("Preset", "FuriHalSubGhzPresetOok270Async")

        return SubGHzSignal(
            frequency_hz=freq,
            modulation=modulation,
            data=data,
            preset=preset,
            raw_lines=raw_lines,
        )

    def build_signal(
        self,
        frequency_hz: float,
        modulation: str,
        data: bytes,
        preset: str = "FuriHalSubGhzPresetOok270Async",
    ) -> SubGHzSignal:
        """Create a SubGHzSignal from raw parameters."""
        return SubGHzSignal(
            frequency_hz=frequency_hz,
            modulation=modulation,
            data=data,
            preset=preset,
        )


# ---------------------------------------------------------------------------
# Infrared
# ---------------------------------------------------------------------------

#: Common IR protocols supported by Flipper Zero
IR_PROTOCOLS = {
    "NEC", "NECext", "Samsung32", "RC6", "RC5", "RC5X", "SIRC",
    "SIRC15", "SIRC20", "Kaseikyo", "RCA", "RAW",
}


class InfraredProtocol:
    """
    Infrared (IR) protocol handler.

    Allows transmitting IR commands using standard protocols (NEC, Samsung,
    RC5/6, SIRC, Kaseikyo …) as well as capturing raw waveforms.
    """

    def __init__(self, device: FlipperDevice):
        self._dev = device

    async def transmit(
        self, protocol: str, address: int, command: int
    ) -> bool:
        """
        Transmit an IR command.

        Parameters
        ----------
        protocol:
            One of the strings in :data:`IR_PROTOCOLS`.
        address:
            IR device address (e.g. 0x0000 for most TVs).
        command:
            IR command code (e.g. 0x0010 for volume up).
        """
        if protocol not in IR_PROTOCOLS:
            raise ValueError(
                f"Unknown IR protocol '{protocol}'. "
                f"Choose from: {sorted(IR_PROTOCOLS)}"
            )
        logger.info("IR: transmit %s address=0x%04x command=0x%04x",
                    protocol, address, command)
        return await self._dev.ir_transmit(protocol, address, command)

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Capture an IR signal and return the decoded data."""
        raw = await self._dev.run_command("ir rx")
        if "OK" in raw or "Received" in raw:
            return {"raw": raw, "captured": True}
        return None


# ---------------------------------------------------------------------------
# NFC / RFID
# ---------------------------------------------------------------------------

class NFCProtocol:
    """
    NFC / RFID protocol handler.

    Supports detecting nearby cards, reading their UIDs, and emulating
    saved card dumps.
    """

    def __init__(self, device: FlipperDevice):
        self._dev = device

    async def detect(self) -> Optional[NFCCard]:
        """Scan for a nearby NFC card and return its metadata."""
        logger.info("NFC: scanning for card")
        return await self._dev.nfc_detect()

    async def read_uid(self) -> Optional[str]:
        """Return only the UID of the first detected card."""
        card = await self.detect()
        return card.uid if card else None

    async def emulate(self, uid: str, technology: str = "Mifare Classic") -> bool:
        """Start card emulation (requires a supported Flipper firmware)."""
        raw = await self._dev.run_command(f"nfc emulate {technology} {uid}")
        return "OK" in raw


# ---------------------------------------------------------------------------
# Bad USB / Rubber Ducky
# ---------------------------------------------------------------------------

class BadUSBProtocol:
    """
    Bad USB / Rubber Ducky HID injection handler.

    Sends DuckyScript payloads to the connected host via the Flipper Zero's
    Bad USB application.

    .. warning::
        Only use on systems you own or have explicit permission to test.
    """

    DUCKY_DELAY_DEFAULT = 50  # ms between keystrokes

    def __init__(self, device: FlipperDevice):
        self._dev = device

    async def run_script(self, script: str) -> bool:
        """
        Execute a DuckyScript payload.

        Parameters
        ----------
        script:
            Multi-line DuckyScript string.
        """
        logger.info("BadUSB: injecting %d-line script", len(script.splitlines()))
        raw = await self._dev.run_command(f"bad_usb run_script {script[:64]!r}")
        return "OK" in raw

    async def type_string(self, text: str, delay_ms: int = DUCKY_DELAY_DEFAULT) -> bool:
        """Type an arbitrary string on the target host keyboard."""
        raw = await self._dev.run_command(f"bad_usb type {text!r} {delay_ms}")
        return "OK" in raw

    async def send_keys(self, keys: str) -> bool:
        """
        Send modifier + key combos (e.g. ``"CTRL ALT t"`` for a terminal).
        """
        raw = await self._dev.run_command(f"bad_usb keys {keys}")
        return "OK" in raw
