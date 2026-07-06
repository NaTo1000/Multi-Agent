"""
AI Agent — intelligent automation layer.

Provides:
- Autonomous frequency optimisation using gradient-ascent RSSI feedback
- Predictive interference detection using rolling statistics
- Adaptive modulation selection
- Anomaly detection on telemetry streams
- Natural-language research + recommendation generation
"""

import logging
import math
import statistics
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device
from ai.chaimera3sp import CHAiMERA3sp
from ai.hiai import HiAiModule

logger = logging.getLogger(__name__)

WINDOW_SIZE = 50  # samples for rolling statistics


class AIAgent(AgentBase):
    """
    AI/ML automation agent.

    Uses lightweight on-device algorithms (no heavy ML framework required)
    plus optional cloud offload for heavier inference tasks.
    """

    TASKS = {
        "auto_optimise",
        "detect_interference",
        "predict_congestion",
        "anomaly_detect",
        "recommend_config",
        "research",
        "auto_tune_fleet",
        "full_series",
        "pipeline_sim",
        "hiai_profile",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ai_agent", config)
        # Per-device rolling RSSI window
        self._rssi_windows: Dict[str, Deque[float]] = {}
        # Per-device recommendation cache
        self._recommendations: Dict[str, Dict[str, Any]] = {}
        # CHAiMERA3sp multi-provider AI router
        self._chaimera = CHAiMERA3sp(self.config.get("chaimera3sp"))
        # HiAi personalisation module (instantiated when config["hiai"] is set)
        self._hiai: Optional[HiAiModule] = (
            HiAiModule(chaimera=self._chaimera) if self.config.get("hiai") else None
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
        if task == "auto_optimise":
            return await self._auto_optimise(params, device)
        if task == "detect_interference":
            return await self._detect_interference(params, device)
        if task == "predict_congestion":
            return await self._predict_congestion(params, device)
        if task == "anomaly_detect":
            return self._anomaly_detect(params, device)
        if task == "recommend_config":
            return await self._recommend_config(params, device)
        if task == "research":
            return await self._research(params)
        if task == "auto_tune_fleet":
            return await self._auto_tune_fleet(params)
        if task == "full_series":
            return await self._full_series(params, device)
        if task == "pipeline_sim":
            return await self._pipeline_sim(params, device)
        if task == "hiai_profile":
            return self._hiai_profile(params)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _auto_optimise(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Continuously optimise a device's frequency and modulation by
        iterating toward higher RSSI using coordinate ascent.
        """
        if not device or not self.orchestrator:
            return {"optimised": False, "reason": "no_device_or_orchestrator"}

        freq_agents = self.orchestrator.get_agents_by_type("frequency_agent")
        mod_agents = self.orchestrator.get_agents_by_type("modulation_agent")

        results = []

        # Step 1: fine-tune frequency
        if freq_agents:
            task_id = await self.orchestrator.dispatch_task(
                freq_agents[0].agent_id,
                "fine_tune",
                {"step_hz": 500_000, "iterations": 5},
                device.device_id,
            )
            results.append({"step": "frequency_fine_tune", "task_id": task_id})

        # Step 2: adaptive modulation
        if mod_agents:
            rssi = await device.get_rssi() or -80
            task_id = await self.orchestrator.dispatch_task(
                mod_agents[0].agent_id,
                "adaptive_select",
                {"snr_db": rssi + 100},
                device.device_id,
            )
            results.append({"step": "adaptive_modulation", "task_id": task_id})

        return {"optimised": True, "device_id": device.device_id, "steps": results}

    async def _detect_interference(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Detect RF interference by analysing RSSI variance over a rolling window.
        High variance → likely interference / congested channel.
        """
        if not device:
            return {"interference": False, "reason": "no_device"}

        window = self._rssi_windows.setdefault(
            device.device_id, deque(maxlen=WINDOW_SIZE)
        )
        rssi = await device.get_rssi()
        if rssi is not None:
            window.append(rssi)

        if len(window) < 5:
            return {"interference": False, "reason": "insufficient_data", "samples": len(window)}

        variance = statistics.variance(window)
        mean = statistics.mean(window)
        threshold = params.get("variance_threshold", 25.0)
        interference_detected = variance > threshold

        if interference_detected:
            logger.warning("Interference detected on device %s (variance=%.1f)",
                           device.device_id, variance)

        return {
            "device_id": device.device_id,
            "interference": interference_detected,
            "rssi_mean": round(mean, 2),
            "rssi_variance": round(variance, 2),
            "threshold": threshold,
            "samples": len(window),
        }

    async def _predict_congestion(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Predict future channel congestion using linear extrapolation of RSSI trend.
        Falling RSSI trend → increasing congestion.
        """
        if not device:
            return {"congestion_risk": "unknown"}

        window = self._rssi_windows.get(device.device_id, deque())
        if len(window) < 10:
            return {"congestion_risk": "insufficient_data"}

        samples = list(window)
        n = len(samples)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(samples)
        slope = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(samples)) / \
                sum((i - x_mean) ** 2 for i in range(n))

        horizon = params.get("horizon_steps", 10)
        predicted = samples[-1] + slope * horizon

        risk_level = "low"
        if slope < -0.5:
            risk_level = "medium"
        if slope < -1.0:
            risk_level = "high"

        return {
            "device_id": device.device_id,
            "current_rssi": samples[-1],
            "rssi_slope_per_step": round(slope, 3),
            "predicted_rssi_in_%d_steps" % horizon: round(predicted, 1),
            "congestion_risk": risk_level,
        }

    def _anomaly_detect(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Flag anomalies in device telemetry using z-score method.
        """
        if not device:
            return {"anomalies": []}

        telemetry = device.telemetry
        window = self._rssi_windows.get(device.device_id, deque())
        anomalies = []

        if len(window) >= 10:
            mean = statistics.mean(window)
            stdev = statistics.stdev(window) or 1
            current = telemetry.get("rssi")
            if current is not None:
                z = abs((current - mean) / stdev)
                if z > params.get("z_threshold", 3.0):
                    anomalies.append({
                        "field": "rssi",
                        "value": current,
                        "z_score": round(z, 2),
                    })

        return {
            "device_id": device.device_id if device else None,
            "anomalies": anomalies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _recommend_config(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Generate a configuration recommendation based on current device state.
        """
        if not device:
            return {"recommendations": []}

        recs = []
        rssi = await device.get_rssi() or -100

        if rssi < -80:
            recs.append({
                "priority": "high",
                "action": "switch_modulation",
                "params": {"scheme": "LoRa"},
                "reason": "Low RSSI detected — LoRa offers better sensitivity",
            })
        elif rssi > -50:
            recs.append({
                "priority": "low",
                "action": "switch_modulation",
                "params": {"scheme": "QAM16"},
                "reason": "Strong signal — higher throughput modulation available",
            })

        window = self._rssi_windows.get(device.device_id, deque())
        if len(window) >= 10:
            variance = statistics.variance(window)
            if variance > 25:
                recs.append({
                    "priority": "medium",
                    "action": "hop_channel",
                    "params": {},
                    "reason": "High RSSI variance suggests interference — channel hop recommended",
                })

        self._recommendations[device.device_id] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": recs,
        }
        return self._recommendations[device.device_id]

    async def _research(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query a configured AI provider (via CHAiMERA3sp) or a legacy cloud AI
        endpoint for research-grade recommendations on frequency, modulation, or
        firmware strategy.  Falls back to built-in heuristics when neither is set.

        When ``params`` contains ``user_id``, the query is personalised via
        HiAi (if enabled) by injecting it into the provider context so that
        CHAiMERA3sp can pre-process the prompt through the HiAi pipeline.
        """
        query = params.get("query", "")
        context = dict(params.get("context", {}))
        # Forward user_id and history for HiAi personalisation
        if params.get("user_id"):
            context.setdefault("user_id", params["user_id"])
        if params.get("conversation_history"):
            context.setdefault("conversation_history", params["conversation_history"])

        # Try CHAiMERA3sp providers first
        if self._chaimera.configured_providers:
            try:
                provider = params.get("provider")  # optional explicit provider override
                result = await self._chaimera.query(
                    query, context=context, provider=provider
                )
                result.setdefault("query", query)
                result.setdefault("source", "chaimera3sp")
                return result
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("CHAiMERA3sp research failed: %s — trying fallback", exc)

        # Legacy single-endpoint fallback
        endpoint = self.config.get("ai_research_endpoint")
        if endpoint:
            try:
                import json
                import urllib.request

                body = json.dumps({"query": query, "context": context}).encode()
                req = urllib.request.Request(
                    endpoint, data=body, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("AI research endpoint failed: %s — using heuristics", exc)

        # Built-in heuristic response
        return {
            "query": query,
            "source": "builtin_heuristics",
            "response": (
                "For ESP32 frequency optimisation: prefer 5 GHz WiFi for throughput, "
                "915 MHz LoRa for long-range low-power, and BLE 5 for short-range "
                "high-speed. Enable GPS for location-aware adaptive power control."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _auto_tune_fleet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run auto-optimise across all online devices simultaneously.
        """
        if not self.orchestrator:
            return {"tuned": 0}
        devices = self.orchestrator.get_online_devices()
        import asyncio
        results = await asyncio.gather(
            *[self._auto_optimise(params, d) for d in devices],
            return_exceptions=True,
        )
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("optimised"))
        return {
            "tuned": successes,
            "total": len(devices),
            "results": [r if isinstance(r, dict) else str(r) for r in results],
        }

    def _hiai_profile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return the current :class:`~ai.user_profile.UserProfile` for a given
        user, or an error dict when HiAi is not enabled.

        Params:
            user_id: The stable identifier for the target user.

        Returns a serialisable profile dict, or ``{"error": ...}`` when the
        module is not configured or the user has no recorded interactions.
        """
        if self._hiai is None:
            return {
                "error": "HiAi module is not enabled (set config['hiai'] to enable).",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        user_id = params.get("user_id", "")
        if not user_id:
            return {
                "error": "user_id param is required for hiai_profile.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        store = self._hiai.get_profile_store()
        profile = store.get_profile(user_id)
        if profile is None:
            return {
                "user_id": user_id,
                "exists": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "user_id": user_id,
            "exists": True,
            "profile": profile.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _full_series(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Run the full AI analysis series in one pass (or multiple passes).

        Executes interference detection, anomaly detection, configuration
        recommendations, and auto-optimisation in sequence.  When CHAiMERA3sp
        providers are configured, each pass is bookended by a research query
        that summarises the round for context.

        The ``passes`` parameter controls how many times the series is
        repeated (1 = single, 2 = double, 3 = triple).
        """
        passes = int(params.get("passes", 1))
        all_rounds: List[Dict[str, Any]] = []

        for round_idx in range(passes):
            round_result: Dict[str, Any] = {"round": round_idx + 1}

            round_result["interference"] = await self._detect_interference(params, device)
            round_result["anomaly"] = self._anomaly_detect(params, device)
            round_result["recommendations"] = await self._recommend_config(params, device)

            if device and self.orchestrator:
                round_result["optimise"] = await self._auto_optimise(params, device)

            if self._chaimera.configured_providers:
                try:
                    summary_prompt = (
                        f"Full AI series round {round_idx + 1}/{passes}. "
                        "Summarise the RF health status and suggest next steps based on: "
                        f"interference={round_result['interference'].get('interference', 'unknown')}, "
                        f"anomalies={len(round_result['anomaly'].get('anomalies', []))}, "
                        f"recommendations={len(round_result['recommendations'].get('recommendations', []))}."
                    )
                    chaimera_result = await self._chaimera.query(summary_prompt, context=params)
                    round_result["chaimera_summary"] = chaimera_result.get("response", "")
                    round_result["chaimera_provider"] = chaimera_result.get("provider", "")
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("CHAiMERA3sp full_series summary failed (round %d): %s",
                                   round_idx + 1, exc)

            all_rounds.append(round_result)

        return {
            "task": "full_series",
            "passes": passes,
            "rounds": all_rounds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _pipeline_sim(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Series → Parallel → Series pipeline simulation.

        The pipeline runs in three distinct phases:

        **Phase 1 — Series entry (triple command simulation)**
          Three commands execute sequentially; each receives the output of the
          previous as additional context so the pipeline carries accumulated
          state forward:
            1. Interference detection
            2. Anomaly detection
            3. Congestion prediction

        **Phase 2 — Parallel heavy compute**
          All workloads that can run independently are launched concurrently
          with ``asyncio.gather``:
            - Configuration recommendation
            - Auto-optimisation (when a device is present)
            - CHAiMERA3sp research queries — one per configured provider
              (broadcast strategy) so every provider is utilised in parallel
            - A local heavy-compute simulation (statistical summary over the
              RSSI window) that runs as a separate coroutine alongside the
              remote AI calls

        **Phase 3 — Series termination (data transmission)**
          Results from the parallel phase are collected and processed
          sequentially to form the outbound transmission payload:
            1. Aggregate parallel outputs into a single result dict
            2. Build a structured transmission record (serialisable snapshot)
            3. Return the final payload, ready for cloud push or logging

        The overall shape of the returned dict::

            {
              "task":      "pipeline_sim",
              "phase1":    { "interference": ..., "anomaly": ..., "congestion": ... },
              "phase2":    { "recommendations": ..., "optimise": ...,
                             "chaimera": [...], "local_compute": ... },
              "phase3":    { "payload_size_bytes": int, "record_count": int,
                             "transmission": {...} },
              "timestamp": "<ISO-8601>",
            }
        """
        import asyncio
        import json

        timestamp = datetime.now(timezone.utc).isoformat()

        # ------------------------------------------------------------------ #
        # Phase 1 — Series: triple command simulation                         #
        # ------------------------------------------------------------------ #
        phase1: Dict[str, Any] = {}

        # Command 1: interference scan
        interference = await self._detect_interference(params, device)
        phase1["interference"] = interference

        # Command 2: anomaly detection (context enriched with phase1 output)
        anomaly_params = {**params, "prior_interference": interference.get("interference", False)}
        anomaly = self._anomaly_detect(anomaly_params, device)
        phase1["anomaly"] = anomaly

        # Command 3: congestion prediction (context enriched with commands 1+2)
        congestion_params = {
            **params,
            "prior_interference": interference.get("interference", False),
            "prior_anomaly_count": len(anomaly.get("anomalies", [])),
        }
        congestion = await self._predict_congestion(congestion_params, device)
        phase1["congestion"] = congestion

        logger.debug("pipeline_sim phase1 complete: interference=%s anomalies=%d",
                     interference.get("interference"), len(anomaly.get("anomalies", [])))

        # ------------------------------------------------------------------ #
        # Phase 2 — Parallel: heavy compute                                   #
        # ------------------------------------------------------------------ #

        phase1_summary = {
            "interference": interference.get("interference", False),
            "anomaly_count": len(anomaly.get("anomalies", [])),
            "congestion_risk": congestion.get("congestion_risk", "unknown"),
        }

        async def _heavy_recommend() -> Dict[str, Any]:
            return await self._recommend_config(params, device)

        async def _heavy_optimise() -> Dict[str, Any]:
            if device and self.orchestrator:
                return await self._auto_optimise(params, device)
            return {"optimised": False, "reason": "no_device_or_orchestrator"}

        async def _heavy_chaimera(provider_name: Optional[str] = None) -> Dict[str, Any]:
            """Query a single CHAiMERA3sp provider (or use first-available)."""
            if not self._chaimera.configured_providers:
                return {"provider": "none", "response": "", "error": "no providers configured"}
            prompt = (
                "Heavy compute analysis — pipeline phase 2. "
                f"Phase-1 summary: {phase1_summary}. "
                "Provide RF optimisation recommendations for an ESP32 fleet."
            )
            try:
                return await self._chaimera.query(prompt, context=params,
                                                  provider=provider_name)
            except Exception as exc:  # pylint: disable=broad-except
                return {"provider": provider_name or "chaimera", "response": "",
                        "error": str(exc)}

        async def _heavy_local_compute() -> Dict[str, Any]:
            """
            CPU-bound statistical summary of all known RSSI windows.
            Simulates a heavy local compute workload running in parallel with
            the remote AI calls.
            """
            summaries = []
            for dev_id, window in self._rssi_windows.items():
                if len(window) < 2:
                    continue
                mean = sum(window) / len(window)
                variance = sum((x - mean) ** 2 for x in window) / len(window)
                summaries.append({
                    "device_id": dev_id,
                    "samples": len(window),
                    "mean_rssi": round(mean, 2),
                    "variance": round(variance, 2),
                })
            return {"device_summaries": summaries, "devices_analysed": len(summaries)}

        # Build the parallel coroutine list — always include recommend,
        # optimise, and local compute; add one CHAiMERA3sp coroutine per
        # configured provider (broadcast pattern).
        parallel_coros = [
            _heavy_recommend(),
            _heavy_optimise(),
            _heavy_local_compute(),
        ]
        chaimera_providers = self._chaimera.configured_providers
        for pname in chaimera_providers:
            parallel_coros.append(_heavy_chaimera(pname))
        # Always include at least one CHAiMERA3sp call even when unconfigured
        # (it returns a graceful no-provider response)
        if not chaimera_providers:
            parallel_coros.append(_heavy_chaimera(None))

        parallel_results = await asyncio.gather(*parallel_coros, return_exceptions=True)

        recommendations_result = (
            parallel_results[0] if isinstance(parallel_results[0], dict)
            else {"error": str(parallel_results[0])}
        )
        optimise_result = (
            parallel_results[1] if isinstance(parallel_results[1], dict)
            else {"error": str(parallel_results[1])}
        )
        local_compute_result = (
            parallel_results[2] if isinstance(parallel_results[2], dict)
            else {"error": str(parallel_results[2])}
        )
        chaimera_results = [
            r if isinstance(r, dict) else {"error": str(r)}
            for r in parallel_results[3:]
        ]

        phase2: Dict[str, Any] = {
            "recommendations": recommendations_result,
            "optimise": optimise_result,
            "local_compute": local_compute_result,
            "chaimera": chaimera_results,
        }

        logger.debug("pipeline_sim phase2 complete: %d parallel tasks finished",
                     len(parallel_results))

        # ------------------------------------------------------------------ #
        # Phase 3 — Series: data transmission termination                     #
        # ------------------------------------------------------------------ #

        # Step 1: aggregate all results into a single flat record
        transmission_record: Dict[str, Any] = {
            "pipeline_version": "1.0",
            "timestamp": timestamp,
            "phase1_interference": phase1["interference"].get("interference", False),
            "phase1_anomaly_count": len(phase1["anomaly"].get("anomalies", [])),
            "phase1_congestion_risk": phase1["congestion"].get("congestion_risk", "unknown"),
            "phase2_recommendations": phase2["recommendations"].get("recommendations", []),
            "phase2_optimised": phase2["optimise"].get("optimised", False),
            "phase2_devices_analysed": phase2["local_compute"].get("devices_analysed", 0),
            "phase2_chaimera_responses": [
                {"provider": r.get("provider", ""), "response": r.get("response", "")}
                for r in phase2["chaimera"]
            ],
        }

        # Step 2: serialise to measure payload size
        serialised = json.dumps(transmission_record, default=str)
        payload_bytes = len(serialised.encode())

        # Step 3: build the final outbound transmission payload
        transmission: Dict[str, Any] = {
            "record": transmission_record,
            "format": "json",
            "encoding": "utf-8",
        }

        phase3: Dict[str, Any] = {
            "payload_size_bytes": payload_bytes,
            "record_count": 1,
            "transmission": transmission,
        }

        logger.debug("pipeline_sim phase3 complete: payload=%d bytes", payload_bytes)

        return {
            "task": "pipeline_sim",
            "phase1": phase1,
            "phase2": phase2,
            "phase3": phase3,
            "timestamp": timestamp,
        }
