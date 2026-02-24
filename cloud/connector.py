"""
Cloud connector — pluggable backends for telemetry upload and heavy compute offload.

Supported connectors:
  - http    : generic HTTP POST (default)
  - aws     : AWS IoT Core via MQTT / HTTPS
  - gcp     : GCP Pub/Sub
  - azure   : Azure IoT Hub
"""

import json
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

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
    ) -> "CloudConnector":
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
            raise ValueError(f"Unknown connector type: {connector_type}. "
                             f"Choose from {list(connectors)}")
        return klass(endpoint, config)


class HTTPConnector(CloudConnector):
    """Generic HTTP POST connector."""

    async def push(self, payload: Dict[str, Any]) -> bool:
        if not self.endpoint:
            logger.debug("HTTP connector: no endpoint configured, skipping push")
            return True  # Treat as success in development
        try:
            body = json.dumps(payload).encode()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.get('api_key', '')}",
            }
            req = urllib.request.Request(self.endpoint, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            logger.error("HTTP push failed: %s %s", exc.code, exc.reason)
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("HTTP push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.endpoint:
            return None
        try:
            url = f"{self.endpoint}/messages"
            if topic:
                url += f"?topic={topic}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("HTTP pull error: %s", exc)
            return None


class AWSConnector(CloudConnector):
    """
    AWS IoT Core connector.
    Uses boto3 (if installed) for MQTT-over-WebSocket or HTTPS Data API.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            import boto3  # type: ignore
            client = boto3.client(
                "iot-data",
                endpoint_url=self.endpoint,
                region_name=self.config.get("aws_region", "us-east-1"),
            )
            topic = self.config.get("aws_topic", "esp32/telemetry")
            client.publish(topic=topic, qos=1, payload=json.dumps(payload))
            return True
        except ImportError:
            logger.warning("boto3 not installed — AWS push unavailable")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("AWS push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None  # AWS IoT uses subscriptions; polling not supported here


class GCPConnector(CloudConnector):
    """
    GCP Pub/Sub connector.
    Requires google-cloud-pubsub to be installed.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            from google.cloud import pubsub_v1  # type: ignore
            publisher = pubsub_v1.PublisherClient()
            topic_path = self.endpoint  # should be "projects/{p}/topics/{t}"
            data = json.dumps(payload).encode()
            future = publisher.publish(topic_path, data)
            future.result(timeout=10)
            return True
        except ImportError:
            logger.warning("google-cloud-pubsub not installed — GCP push unavailable")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("GCP push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None


class AzureConnector(CloudConnector):
    """
    Azure IoT Hub connector.
    Requires azure-iot-device to be installed.
    """

    async def push(self, payload: Dict[str, Any]) -> bool:
        try:
            from azure.iot.device import IoTHubDeviceClient, Message  # type: ignore
            conn_str = self.config.get("azure_connection_string", "")
            if not conn_str:
                logger.warning("azure_connection_string not configured")
                return False
            client = IoTHubDeviceClient.create_from_connection_string(conn_str)
            msg = Message(json.dumps(payload))
            client.send_message(msg)
            client.shutdown()
            return True
        except ImportError:
            logger.warning("azure-iot-device not installed — Azure push unavailable")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Azure push error: %s", exc)
            return False

    async def pull(self, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None
