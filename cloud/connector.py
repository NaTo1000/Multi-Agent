"""
Cloud connector -- pluggable backends for telemetry upload and heavy compute offload.

Supported connectors:
  - http    : generic HTTP POST (default) -- uses async httpx
  - aws     : AWS IoT Core via MQTT / HTTPS -- uses asyncio.to_thread for boto3
  - gcp     : GCP Pub/Sub -- uses asyncio.to_thread
  - azure   : Azure IoT Hub -- uses asyncio.to_thread
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class CloudConnector(ABC):
    """Abstract base class for cloud connectors."""

    def __init__(self, endpoint: str, config: Dict[str, Any]):
        self.endpoint = endpoint
        self.config = config

    @abstractmethod
    async def push(self, payload: Dict[str, Any]) -> bool:
        """Push a telemetry payload to the cloud backend."""

    @abstractmethod
    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Pull a message / command from the cloud backend."""

    @classmethod
    def create(
        cls,
        connector_type: str,
        endpoint: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> CloudConnector:
        """Factory method."""
        config = config or {}
        connectors = {
            "http": HTTPConnector,
            "aws": AWSConnector,
            "gcp": GCPConnector,
            "azure": AzureConnector,
        }
        klass = connectors.get(connector_type.lower())
        if klass is None:
            raise ValueError(
                f"Unknown connector type: {connector_type}. "
                f"Choose from {list(connectors)}"
            )
        return klass(endpoint, config)


class HTTPConnector(CloudConnector):
    """Generic HTTP POST connector using async httpx."""

    async def push(self, payload: Dict[str, Any]) -> bool:
        if not self.endpoint:
            logger.debug("HTTP connector: no endpoint configured, skipping push")
            return True
        api_key = self.config.get("api_key") or os.environ.get("CLOUD_API_KEY", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                return 200 <= resp.status_code < 300
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP push failed: %d %s", exc.response.status_code, exc.response.text)
            return False
        except Exception as exc:
            logger.error("HTTP push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.endpoint:
            return None
        try:
            url = f"{self.endpoint}/messages"
            if topic:
                url += f"?topic={topic}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("HTTP pull error: %s", exc)
            return None


class AWSConnector(CloudConnector):
    """
    AWS IoT Core connector.
    Uses boto3 (synchronous) wrapped in asyncio.to_thread for non-blocking execution.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            import boto3  # type: ignore

            def _sync_push() -> bool:
                client = boto3.client(
                    "iot-data",
                    endpoint_url=self.endpoint,
                    region_name=self.config.get("aws_region", "us-east-1"),
                )
                topic = self.config.get("aws_topic", "esp32/telemetry")
                client.publish(topic=topic, qos=1, payload=json.dumps(payload))
                return True

            return await asyncio.to_thread(_sync_push)
        except ImportError:
            logger.warning("boto3 not installed -- AWS push unavailable")
            return False
        except Exception as exc:
            logger.error("AWS push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None  # AWS IoT uses subscriptions; polling not supported here


class GCPConnector(CloudConnector):
    """
    GCP Pub/Sub connector.
    Uses google-cloud-pubsub (synchronous) wrapped in asyncio.to_thread.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            from google.cloud import pubsub_v1  # type: ignore

            def _sync_push() -> bool:
                publisher = pubsub_v1.PublisherClient()
                data = json.dumps(payload).encode()
                future = publisher.publish(self.endpoint, data)
                future.result(timeout=10)
                return True

            return await asyncio.to_thread(_sync_push)
        except ImportError:
            logger.warning("google-cloud-pubsub not installed -- GCP push unavailable")
            return False
        except Exception as exc:
            logger.error("GCP push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None


class AzureConnector(CloudConnector):
    """
    Azure IoT Hub connector.
    Uses azure-iot-device (synchronous) wrapped in asyncio.to_thread.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            from azure.iot.device import IoTHubDeviceClient, Message  # type: ignore

            conn_str = self.config.get("azure_connection_string", "")
            if not conn_str:
                logger.warning("azure_connection_string not configured")
                return False

            def _sync_push() -> bool:
                client = IoTHubDeviceClient.create_from_connection_string(conn_str)
                msg = Message(json.dumps(payload))
                client.send_message(msg)
                client.shutdown()
                return True

            return await asyncio.to_thread(_sync_push)
        except ImportError:
            logger.warning("azure-iot-device not installed -- Azure push unavailable")
            return False
        except Exception as exc:
            logger.error("Azure push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None
