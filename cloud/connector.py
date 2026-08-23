"""
Cloud connector — pluggable webhook backends for telemetry upload.

Supported connectors (the user picks where the webhook points):
  - http    : generic HTTP POST webhook (default)
  - vps     : alias for "http" — point it at your own VPS
  - local   : alias for "http" — a webhook listener on your local network
  - aws     : AWS IoT Core via MQTT / HTTPS
  - gcp     : GCP Pub/Sub
  - azure   : Azure IoT Hub

Config keys honoured by the generic HTTP/VPS connector:
  - api_key      : sent as ``Authorization: ******
  - path_prefix  : appended to the endpoint (e.g. "/telemetry")
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
        """
        Factory method.

        ``connector_type`` accepts ``http``, ``vps`` / ``local`` (self-hosted
        webhook on your own VPS or local server), ``aws``, ``gcp``, or ``azure``.

        When ``connector_type`` is unknown but a nested ``config["backend"]``
        key is present, that value is used instead — this supports config
        files written as::

            cloud_connector:
              backend: aws
              endpoint: "https://..."

        When ``endpoint`` is empty, ``config["endpoint"]`` is used as a
        fallback for the same nested style.
        """
        config = config or {}
        connectors = {
            "http": HTTPConnector,
            "vps": HTTPConnector,
            "local": HTTPConnector,
            "aws": AWSConnector,
            "gcp": GCPConnector,
            "azure": AzureConnector,
        }
        klass = connectors.get(connector_type.lower())
        if klass is None:
            nested = config.get("backend")
            if isinstance(nested, str):
                klass = connectors.get(nested.lower())
        if klass is None:
            raise ValueError(f"Unknown connector type: {connector_type}. "
                             f"Choose from {sorted(connectors)}")
        if not endpoint and isinstance(config.get("endpoint"), str):
            endpoint = config["endpoint"]
        return klass(endpoint, config)


class HTTPConnector(CloudConnector):
    """
    Generic HTTP POST webhook connector.

    Also serves the ``vps`` and ``local`` connector types — point the
    endpoint at your own VPS or local server to keep the whole backend
    self-hosted.
    """

    def _url(self, path: str = "") -> str:
        prefix = str(self.config.get("path_prefix", "")).strip("/")
        url = self.endpoint.rstrip("/")
        if prefix:
            url = f"{url}/{prefix}"
        if path:
            url = f"{url}/{path.lstrip('/')}"
        return url

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self.config.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"******"
        return headers

    async def push(self, payload: Dict[str, Any]) -> bool:
        if not self.endpoint:
            logger.debug("HTTP connector: no endpoint configured, skipping push")
            return True  # Treat as success in development
        try:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(self._url(), data=body, headers=self._headers())
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
            url = self._url("messages")
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
                endpoint_url=self.endpoint or None,
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
