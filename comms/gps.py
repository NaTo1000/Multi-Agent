"""
GPS / GNSS manager — parses NMEA 0183 sentences from a serial GPS module
attached to the orchestration host (e.g. USB GPS dongle on RPi).

Also provides a simple async polling helper for continuous fix updates.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Minimal NMEA GGA pattern
_GGA_RE = re.compile(
    r"\$(?:GP|GN|GL)GGA,"          # talker + sentence
    r"(?P<time>\d{6}(?:\.\d+)?),"  # hhmmss.ss
    r"(?P<lat>\d{4}\.\d+),"        # ddmm.mmm
    r"(?P<ns>[NS]),"
    r"(?P<lon>\d{5}\.\d+),"        # dddmm.mmm
    r"(?P<ew>[EW]),"
    r"(?P<fix>\d),"                 # fix quality
    r"(?P<sats>\d{2}),"
    r"(?P<hdop>[\d.]+),"
    r"(?P<alt>-?[\d.]+),M,"
)


@dataclass
class GPSFix:
    latitude: float
    longitude: float
    altitude_m: float
    satellites: int
    hdop: float
    timestamp: str
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "satellites": self.satellites,
            "hdop": self.hdop,
            "timestamp": self.timestamp,
        }


class GPSManager:
    """
    Async GPS/GNSS manager.

    Opens a serial port (or accepts pre-parsed NMEA strings for testing)
    and exposes the latest fix via `get_fix()`.
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 9600):
        self.port = port
        self.baud = baud
        self._latest_fix: Optional[GPSFix] = None
        self._running = False

    # ------------------------------------------------------------------
    # NMEA parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_nmea(sentence: str) -> Optional[GPSFix]:
        """Parse a single NMEA GGA sentence and return a GPSFix."""
        m = _GGA_RE.match(sentence.strip())
        if not m:
            return None
        if m.group("fix") == "0":
            return None  # No fix

        lat_raw = float(m.group("lat"))
        lat = int(lat_raw / 100) + (lat_raw % 100) / 60
        if m.group("ns") == "S":
            lat = -lat

        lon_raw = float(m.group("lon"))
        lon = int(lon_raw / 100) + (lon_raw % 100) / 60
        if m.group("ew") == "W":
            lon = -lon

        time_str = m.group("time")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT") + \
             f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}Z"

        return GPSFix(
            latitude=round(lat, 7),
            longitude=round(lon, 7),
            altitude_m=float(m.group("alt")),
            satellites=int(m.group("sats")),
            hdop=float(m.group("hdop")),
            timestamp=ts,
            raw=sentence,
        )

    # ------------------------------------------------------------------
    # Async serial reader
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start reading GPS data from the serial port."""
        self._running = True
        asyncio.ensure_future(self._read_loop())

    async def stop(self) -> None:
        self._running = False

    async def _read_loop(self) -> None:
        """Background loop: read NMEA sentences and update the latest fix."""
        try:
            import serial_asyncio  # type: ignore
            reader, _ = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baud
            )
            while self._running:
                line = (await reader.readline()).decode("ascii", errors="ignore").strip()
                fix = self.parse_nmea(line)
                if fix:
                    self._latest_fix = fix
        except ImportError:
            logger.warning("serial_asyncio not installed — GPS reading disabled. "
                           "Install with: pip install pyserial-asyncio")
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("GPS read loop error: %s", exc)

    def get_fix(self) -> Optional[GPSFix]:
        """Return the most recent GPS fix, or None if unavailable."""
        return self._latest_fix

    def inject_nmea(self, sentence: str) -> Optional[GPSFix]:
        """Manually inject a NMEA sentence (useful for testing)."""
        fix = self.parse_nmea(sentence)
        if fix:
            self._latest_fix = fix
        return fix
