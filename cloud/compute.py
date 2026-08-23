"""
Compute backend — pluggable heavy-compute offload targets.

Where telemetry *goes* is configured via :mod:`cloud.connector` (webhook);
where heavy jobs (firmware builds, AI batch work, OTA image signing, ...)
*run* is configured here.

Supported backends:
  - local   : run the job on this host / your own VPS (default — no cloud needed)
  - aws     : invoke an AWS Lambda function via boto3
  - gcp     : POST to a Google Cloud Function / Cloud Run HTTPS endpoint
              (falls back to a plain HTTP POST — any reachable endpoint works)

Configuration example (config/default.yaml):

    compute:
      backend: local          # local | aws | gcp
      endpoint: ""            # gcp function URL, or your own VPS job endpoint
      function: ""            # aws lambda function name
      aws_region: "us-east-1"

Per-request overrides are supported by passing ``backend`` / ``endpoint`` /
``function`` in the task params.
"""

import asyncio
import json
import logging
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComputeBackend(ABC):
    """Abstract base class for compute offload backends."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def run(self, job: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a compute job.

        :param job: job name (e.g. "firmware_build", "ai_batch")
        :param payload: JSON-serialisable job parameters
        :returns: dict with at least ``ok`` and ``backend`` keys
        """

    @classmethod
    def create(
        cls,
        backend_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> "ComputeBackend":
        """Factory method. ``backend_type`` is ``local`` | ``vps`` | ``aws`` | ``gcp``."""
        config = config or {}
        backends = {
            "local": LocalComputeBackend,
            "vps": LocalComputeBackend,
            "aws": AWSComputeBackend,
            "gcp": GCPComputeBackend,
        }
        klass = backends.get(backend_type.lower())
        if klass is None:
            raise ValueError(f"Unknown compute backend: {backend_type}. "
                             f"Choose from {sorted(backends)}")
        return klass(config)


def compute_config_from_dict(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalise a ``compute`` config section that may be written either flat::

        compute_backend: aws
        compute_function: my-lambda

    or nested::

        compute:
          backend: aws
          function: my-lambda

    Returns the flat dict consumed by :meth:`ComputeBackend.create`.
    """
    cfg = cfg or {}
    if isinstance(cfg.get("compute"), dict):
        return cfg["compute"]
    if isinstance(cfg.get("backend"), str):
        return cfg
    prefix = "compute_"
    flat = {k[len(prefix):]: v for k, v in cfg.items() if k.startswith(prefix)}
    return flat or {}


class LocalComputeBackend(ComputeBackend):
    """
    Runs jobs on the local host or your own VPS — the zero-cloud option.

    If ``config["endpoint"]`` is set, jobs are POSTed to that HTTP endpoint
    (a worker you run yourself); otherwise the job is acknowledged and
    executed in-process by the caller (useful for development).
    """

    async def run(self, job: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self.config.get("endpoint", "")
        if not endpoint:
            logger.info("Local compute: no remote endpoint, job '%s' handled in-process", job)
            return {"ok": True, "backend": "local", "job": job, "mode": "in-process"}

        body = json.dumps({"job": job, "payload": payload}).encode()
        headers = {"Content-Type": "application/json"}
        api_key = self.config.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"******"

        def _post() -> Dict[str, Any]:
            req = urllib.request.Request(endpoint.rstrip("/"), data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw}
                return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": data}

        try:
            result = await asyncio.to_thread(_post)
            result["backend"] = "local"
            result["job"] = job
            result["mode"] = "http"
            return result
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Local compute endpoint error: %s", exc)
            return {"ok": False, "backend": "local", "job": job, "error": str(exc)}


class AWSComputeBackend(ComputeBackend):
    """
    Offloads jobs to AWS Lambda via boto3.
    Requires ``boto3`` and credentials configured in the environment.
    """

    async def run(self, job: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        function = self.config.get("function") or self.config.get("aws_lambda_function")
        if not function:
            logger.warning("AWS compute backend: no lambda function configured")
            return {"ok": False, "backend": "aws", "job": job, "error": "function_required"}
        try:
            import boto3  # type: ignore
        except ImportError:
            logger.warning("boto3 not installed — AWS compute unavailable")
            return {"ok": False, "backend": "aws", "job": job, "error": "boto3_not_installed"}

        def _invoke() -> Dict[str, Any]:
            client = boto3.client(
                "lambda",
                region_name=self.config.get("aws_region", "us-east-1"),
            )
            resp = client.invoke(
                FunctionName=function,
                InvocationType="RequestResponse",
                Payload=json.dumps({"job": job, "payload": payload}),
            )
            raw = resp["Payload"].read().decode() or "{}"
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"raw": raw}
            return {
                "ok": 200 <= resp.get("StatusCode", 500) < 300 and "FunctionError" not in resp,
                "status": resp.get("StatusCode"),
                "response": data,
            }

        try:
            result = await asyncio.to_thread(_invoke)
            result["backend"] = "aws"
            result["job"] = job
            result["function"] = function
            return result
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("AWS Lambda invoke error: %s", exc)
            return {"ok": False, "backend": "aws", "job": job, "error": str(exc)}


class GCPComputeBackend(ComputeBackend):
    """
    Offloads jobs to a Google Cloud Function / Cloud Run HTTPS endpoint.
    Uses a plain HTTP POST, so any reachable HTTPS endpoint works; set
    ``config["api_key"]`` or handle auth at the function URL layer.
    """

    async def run(self, job: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self.config.get("endpoint") or self.config.get("gcp_function_url", "")
        if not endpoint:
            logger.warning("GCP compute backend: no function endpoint configured")
            return {"ok": False, "backend": "gcp", "job": job, "error": "endpoint_required"}

        body = json.dumps({"job": job, "payload": payload}).encode()
        headers = {"Content-Type": "application/json"}
        api_key = self.config.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"******"

        def _post() -> Dict[str, Any]:
            req = urllib.request.Request(endpoint, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw}
                return {"ok": 200 <= resp.status < 300, "status": resp.status, "response": data}

        try:
            result = await asyncio.to_thread(_post)
            result["backend"] = "gcp"
            result["job"] = job
            return result
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("GCP compute endpoint error: %s", exc)
            return {"ok": False, "backend": "gcp", "job": job, "error": str(exc)}
