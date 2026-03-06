"""
Deployment-ready installation package for the Multi-Agent ESP32 Orchestration System.

Usage:
    pip install .                  # Standard install
    pip install -e .               # Editable / development install
    pip install .[full]            # Include all optional cloud backends
    python setup.py --version      # Print package version
"""

from setuptools import setup, find_packages
from pathlib import Path

HERE = Path(__file__).parent
LONG_DESCRIPTION = (HERE / "README.md").read_text(encoding="utf-8") if (HERE / "README.md").exists() else ""

setup(
    name="multi-agent-esp32",
    version="2.0.0",
    description="Multi-Agent ESP32 Orchestration System with Flipper Zero support and fault-tolerant sequencing",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="NaTo1000",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*", "*.tests", "*.tests.*"]),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.0.0",
        "PyYAML>=6.0",
        "pyserial>=3.5",
        "pyserial-asyncio>=0.6",
    ],
    extras_require={
        "ble": ["bleak>=0.21.0"],
        "aws": ["boto3>=1.34.0"],
        "gcp": ["google-cloud-pubsub>=2.18.0"],
        "azure": ["azure-iot-device>=2.12.0"],
        "full": [
            "bleak>=0.21.0",
            "boto3>=1.34.0",
            "google-cloud-pubsub>=2.18.0",
            "azure-iot-device>=2.12.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "multi-agent=main:main",
            "flipper-agent=flipper.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Hardware",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
)
