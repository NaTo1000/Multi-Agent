"""
Firmware Builder -- standalone build engine for ESP32 firmware images.
Can be used independently of the orchestrator for CLI-driven builds,
or delegated to by the FirmwareAgent.
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
DEFAULT_BUILD_DIR = Path(tempfile.gettempdir()) / "esp32_builds"


class FirmwareBuilder:
    """
    Builds ESP32 firmware images from templates.

    Maintains an in-memory build cache keyed by content hash.
    """

    def __init__(self, build_dir: Optional[str | Path] = None):
        self.build_dir = Path(build_dir) if build_dir else DEFAULT_BUILD_DIR
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self._build_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Source assembly
    # ------------------------------------------------------------------

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

        lines: List[str] = [f"// Auto-generated firmware v{version}", ""]
        for k, v in defines.items():
            lines.append(f"#define {k.upper()} {v}")
        lines.append("")

        base = TEMPLATE_DIR / f"{template}.cpp"
        lines.append(
            base.read_text(encoding="utf-8")
            if base.exists()
            else self._default_source(version)
        )

        for feat in features:
            fp = TEMPLATE_DIR / f"{feat}.cpp"
            if fp.exists():
                lines += [f"// --- {feat} ---", fp.read_text(encoding="utf-8")]

        return "\n".join(lines)

    @staticmethod
    def _default_source(version: str) -> str:
        return (
            '#include <Arduino.h>\n'
            f'#define FIRMWARE_VERSION "{version}"\n'
            '\n'
            'void setup() {\n'
            '    Serial.begin(115200);\n'
            '    Serial.println("ESP32 Multi-Agent v" FIRMWARE_VERSION);\n'
            '}\n'
            '\n'
            'void loop() {\n'
            '    delay(1000);\n'
            '}\n'
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

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

        # Cache hit -- return existing metadata
        if build_id in self._build_cache:
            logger.info("Firmware %s already built (cache hit)", build_id)
            return self._build_cache[build_id]

        out_dir = self.build_dir / build_id
        out_dir.mkdir(exist_ok=True)
        (out_dir / "main.cpp").write_text(source, encoding="utf-8")

        binary = out_dir / "firmware.bin"
        compiled = False

        if shutil.which("arduino-cli"):
            compiled = await self._run_arduino_cli(out_dir, out_dir / "main.cpp", binary)
        else:
            binary.write_bytes(b"\x00" * 64)
            logger.warning(
                "arduino-cli not found -- placeholder binary written for %s", build_id
            )

        metadata: Dict[str, Any] = {
            "build_id": build_id,
            "version": version,
            "template": template,
            "features": features,
            "binary_path": str(binary),
            "compiled": compiled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._build_cache[build_id] = metadata
        logger.info("Firmware build %s complete (compiled=%s)", build_id, compiled)
        return metadata

    # ------------------------------------------------------------------
    # Cache accessors
    # ------------------------------------------------------------------

    def get_build(self, build_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a cached build, or None."""
        return self._build_cache.get(build_id)

    def list_builds(self) -> Dict[str, Any]:
        """Return all cached build metadata."""
        return {"builds": list(self._build_cache.values())}

    # ------------------------------------------------------------------
    # arduino-cli helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_arduino_cli(
        build_dir: Path, source_file: Path, output: Path
    ) -> bool:
        """Invoke arduino-cli to compile source for esp32 (non-blocking)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "arduino-cli", "compile",
                "--fqbn", "esp32:esp32:esp32",
                "--output-dir", str(build_dir),
                str(source_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode == 0:
                bins = list(build_dir.glob("*.bin"))
                if bins:
                    shutil.copy(bins[0], output)
                return True
            logger.error("arduino-cli error: %s", stderr.decode())
            return False
        except Exception as exc:
            logger.error("arduino-cli invocation failed: %s", exc)
            return False
