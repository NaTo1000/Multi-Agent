"""
FlipperDevice — low-level interface to a Flipper Zero over USB serial (CLI RPC).

The Flipper Zero exposes a text-based CLI over its USB serial port.  This
module abstracts that interface so higher-level protocol helpers and the
orchestrator agent can communicate with the device without worrying about
framing or reconnection logic.

When no physical device is available the class operates in *simulated* mode,
which is the default when ``port`` is ``None`` or ``"sim"``.  Simulated mode
is used for unit tests and dry-run demonstrations.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FlipperConnectionError(OSError):
    """Raised when the serial connection to a Flipper Zero cannot be established."""


class FlipperCommandError(RuntimeError):
    """Raised when a CLI command returns an error response from the device."""


# ---------------------------------------------------------------------------
# Device status / capabilities
# ---------------------------------------------------------------------------

class FlipperStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    BUSY = "busy"
    ERROR = "error"
    SIMULATED = "simulated"


class FlipperCapability(Enum):
    SUBGHZ = "subghz"
    NFC = "nfc"
    RFID = "rfid"
    INFRARED = "infrared"
    IBUTTON = "ibutton"
    BAD_USB = "bad_usb"
    GPIO = "gpio"
    BLE = "ble"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FlipperInfo:
    """Hardware / firmware information returned by the device."""
    hardware_version: str = "unknown"
    software_version: str = "unknown"
    build_date: str = "unknown"
    device_name: str = "Flipper Zero"
    serial_number: str = "unknown"
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class SubGHzSignal:
    """Captured or synthesised Sub-GHz signal."""
    frequency_hz: float
    modulation: str          # "AM270", "AM650", "FM238", "FM476", "RAW"
    data: bytes = field(default_factory=bytes)
    rssi: Optional[float] = None
    duration_us: Optional[int] = None
    preset: str = "FuriHalSubGhzPresetOok270Async"
    raw_lines: List[str] = field(default_factory=list)

    def to_sub_file(self) -> str:
        """Serialise to Flipper ``.sub`` file format."""
        lines = [
            "Filetype: Flipper SubGhz Key File",
            "Version: 1",
            f"Frequency: {int(self.frequency_hz)}",
            f"Preset: {self.preset}",
            f"Protocol: {self.modulation}",
        ]
        if self.data:
            lines.append(f"Key: {' '.join(f'{b:02X}' for b in self.data)}")
        if self.raw_lines:
            lines.extend(self.raw_lines)
        return "\n".join(lines) + "\n"


@dataclass
class NFCCard:
    """Captured NFC / RFID card data."""
    uid: str
    technology: str          # "Mifare Classic", "NTAG21x", "ISO14443-4" …
    atqa: Optional[str] = None
    sak: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FlipperDevice
# ---------------------------------------------------------------------------

class FlipperDevice:
    """
    High-level async interface to a Flipper Zero device.

    Parameters
    ----------
    port:
        Serial port path (e.g. ``/dev/ttyACM0``, ``COM3``) or ``"sim"`` /
        ``None`` for simulated mode.
    baud_rate:
        Serial baud rate.  The Flipper Zero uses 230400 by default.
    timeout:
        Read timeout in seconds.
    """

    DEFAULT_BAUD = 230400

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = DEFAULT_BAUD,
        timeout: float = 5.0,
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._simulated = port is None or port == "sim"
        self.status: FlipperStatus = (
            FlipperStatus.SIMULATED if self._simulated else FlipperStatus.DISCONNECTED
        )
        self._info: Optional[FlipperInfo] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()
        logger.debug(
            "FlipperDevice initialised (port=%s, simulated=%s)", port, self._simulated
        )

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the serial connection to the Flipper Zero."""
        if self._simulated:
            self.status = FlipperStatus.SIMULATED
            self._info = FlipperInfo(
                hardware_version="7.x",
                software_version="0.99.1-sim",
                build_date="2024-01-01",
                serial_number="SIM000001",
            )
            logger.info("FlipperDevice: simulated connection established")
            return

        try:
            import serial_asyncio  # type: ignore
        except ImportError as exc:
            raise FlipperConnectionError(
                "pyserial-asyncio is required for real device connections. "
                "Install with: pip install pyserial-asyncio"
            ) from exc

        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port,
                baudrate=self.baud_rate,
            )
            self.status = FlipperStatus.CONNECTED
            # Drain welcome banner
            await asyncio.wait_for(self._read_until_prompt(), timeout=self.timeout)
            logger.info("FlipperDevice connected on %s", self.port)
        except Exception as exc:
            self.status = FlipperStatus.ERROR
            raise FlipperConnectionError(
                f"Failed to connect to Flipper Zero on {self.port}: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """Close the serial connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # pylint: disable=broad-except
                pass
        self._reader = None
        self._writer = None
        self.status = FlipperStatus.DISCONNECTED
        logger.info("FlipperDevice disconnected")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.disconnect()

    # ------------------------------------------------------------------
    # CLI command execution
    # ------------------------------------------------------------------

    async def run_command(self, command: str) -> str:
        """
        Send a CLI command and return the response string.

        In simulated mode a realistic stub response is returned so that
        higher-level code can be tested without hardware.
        """
        if self._simulated:
            return self._simulate_command(command)

        async with self._lock:
            if self.status != FlipperStatus.CONNECTED:
                raise FlipperConnectionError("Not connected to Flipper Zero")
            self._writer.write((command + "\r\n").encode())
            await self._writer.drain()
            response = await asyncio.wait_for(
                self._read_until_prompt(), timeout=self.timeout
            )
            return response

    async def _read_until_prompt(self) -> str:
        """Read bytes from the serial stream until the CLI prompt appears."""
        buf = b""
        while True:
            chunk = await self._reader.read(256)
            if not chunk:
                break
            buf += chunk
            if b">: " in buf or b">" in buf[-4:]:
                break
        return buf.decode(errors="replace").strip()

    # ------------------------------------------------------------------
    # Simulated responses
    # ------------------------------------------------------------------

    #: Dispatch table mapping CLI command prefixes → stub response strings.
    _SIM_RESPONSES: Dict[str, str] = {
        "info": (
            "Hardware version: 7.x\n"
            "Software version: 0.99.1-sim\n"
            "Build date: 2024-01-01\n"
            "Hardware target: 7\n"
            "Serial number: SIM000001\n"
            ">: "
        ),
        "device_info": (
            "Hardware version: 7.x\n"
            "Software version: 0.99.1-sim\n"
            "Build date: 2024-01-01\n"
            "Hardware target: 7\n"
            "Serial number: SIM000001\n"
            ">: "
        ),
        "subghz rx": (
            "Listening at 433920000 Hz...\n"
            "Received: CAME 0xABC123 (12 bits)\n"
            ">: "
        ),
        "subghz tx": "Transmitting... OK\n>: ",
        "nfc detect": (
            "NFC detected!\n"
            "UID: 04:AB:CD:EF\n"
            "Type: Mifare Classic 1K\n"
            "ATQA: 00 04\n"
            "SAK: 08\n"
            ">: "
        ),
        "nfc emulate": "Emulating... OK\n>: ",
        "ir": "Infrared signal captured/transmitted OK\n>: ",
        "gpio": "GPIO OK\n>: ",
        "bad_usb": "OK\n>: ",
        "help": (
            "Available commands:\n"
            "  info           - Device information\n"
            "  subghz rx      - Receive Sub-GHz signal\n"
            "  subghz tx      - Transmit Sub-GHz signal\n"
            "  nfc detect     - Detect NFC card\n"
            "  ir rx          - Receive IR signal\n"
            "  ir tx          - Transmit IR signal\n"
            "  gpio           - GPIO control\n"
            ">: "
        ),
    }

    def _simulate_command(self, command: str) -> str:
        """Return realistic stub output for a CLI command using a dispatch table."""
        cmd = command.strip().lower()
        for prefix, response in self._SIM_RESPONSES.items():
            if cmd == prefix or cmd.startswith(prefix + " "):
                return response
        return "OK\n>: "

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    async def get_info(self) -> FlipperInfo:
        """Query and return device information."""
        if self._info and self._simulated:
            return self._info
        raw = await self.run_command("device_info")
        info = FlipperInfo()
        for line in raw.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if key == "hardware_version":
                    info.hardware_version = val
                elif key == "software_version":
                    info.software_version = val
                elif key == "build_date":
                    info.build_date = val
                elif key == "serial_number":
                    info.serial_number = val
                else:
                    info.extra[key] = val
        self._info = info
        return info

    async def subghz_receive(
        self,
        frequency_hz: float,
        timeout_s: float = 5.0,
    ) -> Optional[SubGHzSignal]:
        """Listen on a Sub-GHz frequency and return the first captured signal."""
        cmd = f"subghz rx {int(frequency_hz)}"
        raw = await self.run_command(cmd)
        if "Received" in raw or "received" in raw:
            return SubGHzSignal(
                frequency_hz=frequency_hz,
                modulation="RAW",
                raw_lines=[raw],
            )
        return None

    async def subghz_transmit(self, signal: SubGHzSignal) -> bool:
        """Transmit a Sub-GHz signal."""
        key_hex = " ".join(f"{b:02X}" for b in signal.data) if signal.data else "00"
        cmd = (
            f"subghz tx {int(signal.frequency_hz)} "
            f"{signal.modulation} {key_hex}"
        )
        raw = await self.run_command(cmd)
        return "OK" in raw

    async def nfc_detect(self) -> Optional[NFCCard]:
        """Detect and read an NFC card."""
        raw = await self.run_command("nfc detect")
        if "UID" not in raw and "uid" not in raw:
            return None
        card = NFCCard(uid="", technology="Unknown")
        for line in raw.splitlines():
            line_lower = line.lower()
            if "uid:" in line_lower:
                card.uid = line.split(":", 1)[1].strip()
            elif "type:" in line_lower:
                card.technology = line.split(":", 1)[1].strip()
            elif "atqa:" in line_lower:
                card.atqa = line.split(":", 1)[1].strip()
            elif "sak:" in line_lower:
                card.sak = line.split(":", 1)[1].strip()
        return card

    async def ir_transmit(self, protocol: str, address: int, command: int) -> bool:
        """Transmit an IR signal."""
        raw = await self.run_command(
            f"ir tx {protocol} {address:#06x} {command:#06x}"
        )
        return "OK" in raw

    async def gpio_write(self, pin: str, value: int) -> bool:
        """Write a GPIO pin value (0 or 1)."""
        raw = await self.run_command(f"gpio write {pin} {value}")
        return "OK" in raw

    def to_dict(self) -> Dict[str, Any]:
        """Serialise device state for status reporting."""
        return {
            "port": self.port,
            "status": self.status.value,
            "simulated": self._simulated,
            "info": {
                "hardware_version": self._info.hardware_version if self._info else None,
                "software_version": self._info.software_version if self._info else None,
                "serial_number": self._info.serial_number if self._info else None,
            },
        }
