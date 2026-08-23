"""
Cloud integration package — pluggable webhook + compute backends.

Pick where telemetry webhooks go (http/vps/local, AWS, GCP, Azure) via
``CloudConnector`` and where heavy compute runs (local VPS, AWS Lambda,
GCP Cloud Functions) via ``ComputeBackend``.
"""

from .connector import CloudConnector, HTTPConnector, AWSConnector, GCPConnector, AzureConnector
from .compute import (
    ComputeBackend,
    LocalComputeBackend,
    AWSComputeBackend,
    GCPComputeBackend,
    compute_config_from_dict,
)

__all__ = [
    "CloudConnector",
    "HTTPConnector",
    "AWSConnector",
    "GCPConnector",
    "AzureConnector",
    "ComputeBackend",
    "LocalComputeBackend",
    "AWSComputeBackend",
    "GCPComputeBackend",
    "compute_config_from_dict",
]
