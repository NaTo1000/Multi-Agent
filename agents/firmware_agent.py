"""
Firmware Agent — on-the-fly firmware generation, compilation,
and OTA deployment for ESP32 modules.
"""

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

FIRMWARE_TEMPLATE_DIR = Path(__file__).parent.parent / "firmware" / "templates"
FIRMWARE_BUILD_DIR = Path(tempfile.gettempdir()) / "esp32_firmware_builds"


class FirmwareAgent(AgentBase):
    """
    Agent that handles on-the-fly firmware creation and OTA deployment.

    Workflow:
    1. `build`  — generate C++ source from template + params, invoke esp-idf/arduino-cli
    2. `flash`  — push compiled binary to one or more devices via OTA
    3. `rollback` — revert device to previous firmware version
    4. `status` — query current firmware state on device
    """

    TASKS = {"build", "flash", "build_and_flash", "rollback", "firmware_status", "list_builds"}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("firmware_agent", config)
        self._build_cache: Dict[str, Dict[str, Any]] = {}  # build_id → metadata
        FIRMWARE_BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "build":
            return await self._build(params)
        if task == "flash":
            return await self._flash(params, device)
        if task == "build_and_flash":
            build_result = await self._build(params)
            if not build_result.get("success"):
                return build_result
            return await self._flash(
                {"build_id": build_result["build_id"]}, device
            )
        if task == "rollback":
            return await self._rollback(params, device)
        if task == "firmware_status":
            return await self._firmware_status(device)
        if task == "list_builds":
            return self._list_builds()
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _build(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a firmware image from a named template plus runtime params.

        Parameters:
          - template: name of template in firmware/templates/ (default: "base")
          - features: list of feature flags to enable (e.g. ["wifi", "ble", "gps"])
          - version:  semantic version string (default: auto-generated)
          - extra:    arbitrary key-value pairs injected as #defines
        """
        template_name = params.get("template", "base")
        features: List[str] = params.get("features", ["wifi"])
        version = params.get("version", datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%S"))
        extra: Dict[str, Any] = params.get("extra", {})

        # Load and merge template sources
        sources = self._assemble_sources(template_name, features, version, extra)
        build_id = hashlib.sha256(sources.encode()).hexdigest()[:12]

        build_dir = FIRMWARE_BUILD_DIR / build_id
        if build_dir.exists():
            logger.info("Firmware %s already built (cache hit)", build_id)
            if build_id in self._build_cache:
                return self._build_cache[build_id]
            # Rebuild metadata from stored binary (cross-process cache miss)
            binary_path = build_dir / "firmware.bin"
            cached_meta: Dict[str, Any] = {
                "success": True,
                "build_id": build_id,
                "version": version,
                "template": template_name,
                "features": features,
                "binary_path": str(binary_path),
                "compiled": binary_path.stat().st_size > 64 if binary_path.exists() else False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._build_cache[build_id] = cached_meta
            return cached_meta

        build_dir.mkdir(parents=True)
        source_file = build_dir / "main.cpp"
        source_file.write_text(sources, encoding="utf-8")

        # Attempt real compilation if arduino-cli is available
        binary_path = build_dir / "firmware.bin"
        compiled = False
        if shutil.which("arduino-cli"):
            compiled = await self._run_arduino_cli(build_dir, source_file, binary_path)
        else:
            # Write a placeholder binary for environments without the toolchain
            binary_path.write_bytes(b"\x00" * 64)
            logger.warning(
                "arduino-cli not found — placeholder binary written for build %s", build_id
            )

        metadata: Dict[str, Any] = {
            "success": True,
            "build_id": build_id,
            "version": version,
            "template": template_name,
            "features": features,
            "binary_path": str(binary_path),
            "compiled": compiled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._build_cache[build_id] = metadata
        logger.info("Firmware build %s complete (compiled=%s)", build_id, compiled)
        return metadata

    async def _flash(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Flash a build to one device via OTA."""
        if not device:
            return {"ok": False, "reason": "no_device"}
        build_id = params.get("build_id")
        firmware_url = params.get("firmware_url")

        if build_id:
            meta = self._build_cache.get(build_id)
            if not meta:
                return {"ok": False, "reason": f"build {build_id} not found"}
            # In production this URL would point to a hosted artifact
            firmware_url = firmware_url or f"/builds/{build_id}/firmware.bin"

        if not firmware_url:
            return {"ok": False, "reason": "no firmware_url or build_id supplied"}

        ok = await device.flash_firmware(firmware_url)
        return {"ok": ok, "device_id": device.device_id, "firmware_url": firmware_url}

    async def _rollback(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"ok": False, "reason": "no_device"}
        resp = await device.send_command("ota_rollback")
        ok = resp.get("status") == "ok"
        return {"ok": ok, "device_id": device.device_id}

    async def _firmware_status(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"version": None}
        try:
            resp = await device.send_command("get_firmware_info")
            return {
                "device_id": device.device_id,
                "version": resp.get("version", device.firmware_version),
                "build_date": resp.get("build_date"),
                "features": resp.get("features", []),
            }
        except Exception:  # pylint: disable=broad-except
            return {"device_id": device.device_id, "version": device.firmware_version}

    def _list_builds(self) -> Dict[str, Any]:
        return {"builds": list(self._build_cache.values())}

    # ------------------------------------------------------------------
    # Source assembly
    # ------------------------------------------------------------------

    def _assemble_sources(
        self,
        template: str,
        features: List[str],
        version: str,
        extra: Dict[str, Any],
    ) -> str:
        """Concatenate the base template with feature modules."""
        lines = [f'// Auto-generated firmware v{version}', ""]
        for key, val in extra.items():
            lines.append(f"#define {key.upper()} {val}")
        lines.append("")

        base_path = FIRMWARE_TEMPLATE_DIR / f"{template}.cpp"
        if base_path.exists():
            lines.append(base_path.read_text(encoding="utf-8"))
        else:
            lines.append(self._default_base_source(version))

        for feature in features:
            feat_path = FIRMWARE_TEMPLATE_DIR / f"{feature}.cpp"
            if feat_path.exists():
                lines.append(f"// --- Feature: {feature} ---")
                lines.append(feat_path.read_text(encoding="utf-8"))

        return "\n".join(lines)

    @staticmethod
    def _default_base_source(version: str) -> str:
        return f"""
#include <Arduino.h>

#define FIRMWARE_VERSION "{version}"

void setup() {{
    Serial.begin(115200);
    Serial.println("ESP32 Multi-Agent v" FIRMWARE_VERSION);
}}

void loop() {{
    delay(1000);
}}
"""

    # ------------------------------------------------------------------
    # arduino-cli helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_arduino_cli(
        build_dir: Path, source_file: Path, output: Path
    ) -> bool:
        """Invoke arduino-cli to compile source for esp32."""
        try:
            cmd = [
                "arduino-cli", "compile",
                "--fqbn", "esp32:esp32:esp32",
                "--output-dir", str(build_dir),
                str(source_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                # arduino-cli places the .bin in the build dir
                bins = list(build_dir.glob("*.bin"))
                if bins:
                    shutil.copy(bins[0], output)
                return True
            logger.error("arduino-cli error: %s", result.stderr)
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("arduino-cli invocation failed: %s", exc)
            return False
