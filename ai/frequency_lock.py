"""
Frequency Lock Controller — closed-loop PID controller for precise
frequency locking and fine-tuning of ESP32 radio modules.

The controller minimises the error between target and measured frequency
(or maximises RSSI as a proxy for correct tuning).
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PIDController:
    """
    Simple PID controller.

    Used to compute a correction delta for frequency tuning based on the
    difference between target and measured signal quality.
    """

    def __init__(self, kp: float = 1.0, ki: float = 0.01, kd: float = 0.1):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_time: float = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = time.monotonic()

    def update(self, error: float) -> float:
        """
        Feed an error value and return the controller output.

        error  — (target_metric - actual_metric)
        output — correction to apply (e.g. frequency delta in Hz)
        """
        now = time.monotonic()
        dt = max(now - self._prev_time, 1e-6)

        proportional = self.kp * error
        self._integral += error * dt
        integral = self.ki * self._integral
        derivative = self.kd * (error - self._prev_error) / dt

        self._prev_error = error
        self._prev_time = now
        return proportional + integral + derivative


class FrequencyLockController:
    """
    Closed-loop frequency lock controller for an ESP32 device.

    Uses a PID controller driven by RSSI feedback to iteratively
    correct the operating frequency toward the optimal point.
    """

    def __init__(
        self,
        target_rssi: float = -50.0,
        kp: float = 5000.0,   # maps RSSI error (dB) → Hz correction
        ki: float = 100.0,
        kd: float = 500.0,
        max_correction_hz: float = 1e6,
    ):
        self.target_rssi = target_rssi
        self.max_correction_hz = max_correction_hz
        self._pid = PIDController(kp, ki, kd)

    def reset(self) -> None:
        self._pid.reset()

    def compute_correction(self, current_rssi: float) -> float:
        """
        Compute the frequency correction (Hz) based on current RSSI.

        Positive output → increase frequency
        Negative output → decrease frequency
        """
        error = self.target_rssi - current_rssi  # positive when we need better signal
        correction = self._pid.update(error)
        # Clamp to maximum safe correction
        return max(-self.max_correction_hz, min(self.max_correction_hz, correction))

    async def run_lock_cycle(
        self, device: Any, iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Run multiple PID correction cycles on a device.

        Returns a summary of the locking process.
        """
        self.reset()
        history = []

        for i in range(iterations):
            rssi = await device.get_rssi()
            if rssi is None:
                logger.warning("Could not read RSSI from %s on iteration %d",
                               device.device_id, i)
                continue

            correction = self.compute_correction(rssi)
            new_freq = device.current_frequency + correction
            await device.set_frequency(new_freq)

            history.append({
                "iteration": i,
                "rssi": rssi,
                "correction_hz": round(correction, 1),
                "new_frequency_hz": new_freq,
            })

            logger.debug(
                "FrequencyLock [%s] iter=%d rssi=%.1f corr=%.0f Hz → %.3f MHz",
                device.device_id, i, rssi, correction, new_freq / 1e6,
            )

            if abs(rssi - self.target_rssi) < 2.0:
                logger.info(
                    "FrequencyLock converged on %s after %d iterations", device.device_id, i + 1
                )
                break

        final_rssi = await device.get_rssi()
        return {
            "device_id": device.device_id,
            "final_frequency_hz": device.current_frequency,
            "final_rssi": final_rssi,
            "target_rssi": self.target_rssi,
            "iterations": len(history),
            "converged": abs((final_rssi or -100) - self.target_rssi) < 2.0,
            "history": history,
        }
