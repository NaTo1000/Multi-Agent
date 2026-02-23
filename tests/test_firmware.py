"""
Tests for firmware builder, GPS parser, and AI frequency lock controller.
"""

import asyncio
import pytest
from pathlib import Path

from firmware.builder import FirmwareBuilder
from comms.gps import GPSManager
from ai.frequency_lock import FrequencyLockController, PIDController


# ------------------------------------------------------------------
# FirmwareBuilder
# ------------------------------------------------------------------

def test_builder_assemble_base():
    builder = FirmwareBuilder()
    source = builder.assemble(template="base", features=[], version="1.0.0")
    assert "1.0.0" in source


def test_builder_assemble_with_features():
    builder = FirmwareBuilder()
    source = builder.assemble(template="base", features=["wifi", "ble"], version="2.0")
    assert "wifi" in source.lower() or "WiFi" in source or "Auto-generated" in source


def test_builder_assemble_with_defines():
    builder = FirmwareBuilder()
    source = builder.assemble(
        template="base",
        features=[],
        version="1.0.0",
        defines={"MY_CUSTOM_DEFINE": "42"},
    )
    assert "#define MY_CUSTOM_DEFINE 42" in source


@pytest.mark.asyncio
async def test_builder_build_creates_file():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    builder = FirmwareBuilder(build_dir=tmp)
    result = await builder.build(
        template="base", features=["wifi"], version="pytest-1.0"
    )
    assert result["build_id"]
    assert result["version"] == "pytest-1.0"
    assert Path(result["binary_path"]).exists()


@pytest.mark.asyncio
async def test_builder_build_idempotent():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    builder = FirmwareBuilder(build_dir=tmp)
    kwargs = {"template": "base", "features": ["wifi"], "version": "idem-1.0"}
    r1 = await builder.build(**kwargs)
    r2 = await builder.build(**kwargs)
    assert r1["build_id"] == r2["build_id"]


# ------------------------------------------------------------------
# GPS parser
# ------------------------------------------------------------------

def test_gps_parse_valid_gga():
    gps = GPSManager()
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    fix = gps.parse_nmea(sentence)
    assert fix is not None
    assert abs(fix.latitude - 48.117) < 0.01
    assert abs(fix.longitude - 11.517) < 0.01
    assert fix.satellites == 8
    assert fix.altitude_m == pytest.approx(545.4)


def test_gps_parse_no_fix():
    gps = GPSManager()
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,0,00,,,M,,M,,*70"
    fix = gps.parse_nmea(sentence)
    assert fix is None  # fix quality = 0


def test_gps_parse_invalid():
    gps = GPSManager()
    assert gps.parse_nmea("not a sentence") is None
    assert gps.parse_nmea("") is None


def test_gps_inject_nmea():
    gps = GPSManager()
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    fix = gps.inject_nmea(sentence)
    assert fix is not None
    assert gps.get_fix() is fix


def test_gps_no_fix_initially():
    gps = GPSManager()
    assert gps.get_fix() is None


# ------------------------------------------------------------------
# PIDController
# ------------------------------------------------------------------

def test_pid_zero_error():
    pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
    output = pid.update(0.0)
    assert output == pytest.approx(0.0)


def test_pid_proportional():
    pid = PIDController(kp=2.0, ki=0.0, kd=0.0)
    output = pid.update(5.0)
    assert output == pytest.approx(10.0, abs=1.0)


def test_pid_reset():
    pid = PIDController(kp=1.0, ki=1.0, kd=0.0)
    pid.update(10.0)
    pid.reset()
    assert pid._integral == 0.0
    assert pid._prev_error == 0.0


# ------------------------------------------------------------------
# FrequencyLockController
# ------------------------------------------------------------------

def test_freq_lock_compute_correction_above_target():
    ctrl = FrequencyLockController(target_rssi=-50.0, kp=5000.0, ki=0.0, kd=0.0)
    # current RSSI is above target → error is negative → correction is negative
    correction = ctrl.compute_correction(-40.0)
    assert correction < 0


def test_freq_lock_compute_correction_below_target():
    ctrl = FrequencyLockController(target_rssi=-50.0, kp=5000.0, ki=0.0, kd=0.0)
    # current RSSI is below target → error is positive → correction is positive
    correction = ctrl.compute_correction(-70.0)
    assert correction > 0


def test_freq_lock_clamped():
    ctrl = FrequencyLockController(
        target_rssi=-50.0, kp=5000.0, ki=0.0, kd=0.0, max_correction_hz=1e6
    )
    correction = ctrl.compute_correction(-10.0)
    assert abs(correction) <= 1e6
