"""
Firmware Builder — standalone wrapper around the FirmwareAgent build logic.
Can be used independently of the orchestrator for CLI-driven builds.
"""

import asyncio
import hashlib
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
BUILD_DIR = Path(tempfile.gettempdir()) / "esp32_builds"


class FirmwareBuilder:
    """
    Builds ESP32 firmware images from templates.

    Can be used directly or via the FirmwareAgent.
    """

    def __init__(self, build_dir: Optional[Path] = None):
        self.build_dir = build_dir or BUILD_DIR
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def assemble(
        self,
        template: str = "base",
        features: Optional[List[str]] = None,
        version: Optional[str] = None,
        defines: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Assemble C++ source from templates and return as a string.
        """
        features = features or ["wifi"]
        version = version or datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%S")
        defines = defines or {}

        lines = [f"// Auto-generated firmware v{version}", ""]
        for k, v in defines.items():
            lines.append(f"#define {k.upper()} {v}")
        lines.append("")

        base = TEMPLATE_DIR / f"{template}.cpp"
        lines.append(base.read_text(encoding="utf-8") if base.exists() else
                     self._default_source(version))

        for feat in features:
            fp = TEMPLATE_DIR / f"{feat}.cpp"
            if fp.exists():
                lines += [f"// --- {feat} ---", fp.read_text(encoding="utf-8")]

        return "\n".join(lines)

    @staticmethod
    def _default_source(version: str) -> str:
        return f"""
#include <Arduino.h>
void setup() {{ Serial.begin(115200); Serial.println("v{version}"); }}
void loop() {{ delay(1000); }}
"""

    async def build(
        self,
        template: str = "base",
        features: Optional[List[str]] = None,
        version: Optional[str] = None,
        defines: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble source and compile with arduino-cli (if available)."""
        features = features or ["wifi"]
        version = version or datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%S")

        source = self.assemble(template, features, version, defines)
        build_id = hashlib.sha256(source.encode()).hexdigest()[:12]
        out_dir = self.build_dir / build_id
        out_dir.mkdir(exist_ok=True)
        (out_dir / "main.cpp").write_text(source, encoding="utf-8")

        binary = out_dir / "firmware.bin"
        compiled = False

        if shutil.which("arduino-cli"):
            try:
                result = subprocess.run(
                    [
                        "arduino-cli", "compile",
                        "--fqbn", "esp32:esp32:esp32",
                        "--output-dir", str(out_dir),
                        str(out_dir / "main.cpp"),
                    ],
                    capture_output=True, text=True, timeout=180,
                )
                compiled = result.returncode == 0
                if not compiled:
                    logger.error("arduino-cli stderr: %s", result.stderr)
                bins = list(out_dir.glob("*.bin"))
                if bins:
                    shutil.copy(bins[0], binary)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Build error: %s", exc)
        else:
            binary.write_bytes(b"\x00" * 64)
            logger.warning("arduino-cli not found — placeholder binary written")

        return {
            "build_id": build_id,
            "version": version,
            "template": template,
            "features": features,
            "binary_path": str(binary),
            "compiled": compiled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
