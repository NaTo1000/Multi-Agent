"""
Firmware Agent -- on-the-fly firmware generation, compilation,
and OTA deployment for ESP32 modules.

Delegates build logic to firmware.builder.FirmwareBuilder (DRY).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from firmware.builder import FirmwareBuilder
from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)


class FirmwareAgent(AgentBase):
    """
    Agent that handles on-the-fly firmware creation and OTA deployment.

    Workflow:
    1. ``build``  -- generate C++ source from template + params, invoke compiler
    2. ``flash``  -- push compiled binary to one or more devices via OTA
    3. ``rollback`` -- revert device to previous firmware version
    4. ``firmware_status`` -- query current firmware state on device
    5. ``list_builds`` -- list all cached builds
    """

    TASKS = {"build", "flash", "build_and_flash", "rollback", "firmware_status", "list_builds"}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("firmware_agent", config)
        self._builder = FirmwareBuilder(
            build_dir=config.get("build_dir") if config else None,
        )

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
            return self._builder.list_builds()
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _build(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a firmware image from a named template plus runtime params.

        Delegates entirely to FirmwareBuilder.
        """
        template_name = params.get("template", "base")
        features: List[str] = params.get("features", ["wifi"])
        version = params.get(
            "version",
            datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%S"),
        )
        extra: Dict[str, Any] = params.get("extra", {})

        result = await self._builder.build(
            template=template_name,
            features=features,
            version=version,
            defines=extra,
        )
        # Add success flag expected by build_and_flash
        result["success"] = True
        return result

    async def _flash(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Flash a build to one device via OTA."""
        if not device:
            return {"ok": False, "reason": "no_device"}

        build_id = params.get("build_id")
        firmware_url = params.get("firmware_url")

        if build_id:
            meta = self._builder.get_build(build_id)
            if not meta:
                return {"ok": False, "reason": f"build {build_id} not found"}
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
        except Exception:
            return {"device_id": device.device_id, "version": device.firmware_version}
