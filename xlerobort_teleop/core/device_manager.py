"""
DeviceManager
=============
Wraps lerobot's FeetechMotorsBus for each SO-101 arm.
Falls back to a minimal stub if lerobot is not importable.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

# ── lerobot import with graceful fallback ─────────────────────────────────────

try:
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus
    _LEROBOT_AVAILABLE = True
except ImportError:
    _LEROBOT_AVAILABLE = False
    log.warning(
        "lerobot not found — running in STUB mode. "
        "Arm reads will return zeros; writes are no-ops."
    )


# ── Motor definitions for SO-101 (Feetech STS3215) ───────────────────────────

def _make_so101_motors(norm_mode=None):
    if not _LEROBOT_AVAILABLE:
        return {m: i+1 for i, m in enumerate([
            "shoulder_pan", "shoulder_lift", "elbow_flex",
            "wrist_flex", "wrist_roll", "gripper",
        ])}
    body_mode = norm_mode or MotorNormMode.RANGE_M100_100
    return {
        "shoulder_pan":  Motor(1, "sts3215", body_mode),
        "shoulder_lift": Motor(2, "sts3215", body_mode),
        "elbow_flex":    Motor(3, "sts3215", body_mode),
        "wrist_flex":    Motor(4, "sts3215", body_mode),
        "wrist_roll":    Motor(5, "sts3215", body_mode),
        "gripper":       Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
    }


MOTOR_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
]


# ── Stub bus ──────────────────────────────────────────────────────────────────

class _StubBus:
    def __init__(self, port: str):
        self.port = port

    def connect(self):
        log.info(f"[STUB] connect → {self.port}")

    def disconnect(self, disable_torque=True):
        log.info(f"[STUB] disconnect → {self.port}")

    def sync_read(self, data_name: str) -> dict:
        return {m: 0.0 for m in MOTOR_NAMES}

    def sync_write(self, data_name: str, values: dict):
        log.debug(f"[STUB] sync_write {data_name} = {values} → {self.port}")

    def disable_torque(self):
        pass

    def enable_torque(self, motor=None):
        pass


def _make_bus(port: Optional[str], calibration=None):
    if port is None:
        return None
    if _LEROBOT_AVAILABLE:
        return FeetechMotorsBus(
            port=port,
            motors=_make_so101_motors(),
            calibration=calibration,
        )
    return _StubBus(port=port)


# ── DeviceManager ─────────────────────────────────────────────────────────────

class DeviceManager:
    """
    Manages up to four SO-101 arms over Feetech serial buses.
    leader_left is optional (None = not connected).
    """

    def __init__(self, ports: Dict[str, Optional[str]], baudrate: int = 1_000_000):
        self.ports = ports

        self._buses: Dict[str, Optional[object]] = {
            "leader_right":   _make_bus(ports.get("leader_right")),
            "leader_left":    _make_bus(ports.get("leader_left")),
            "follower_right": _make_bus(ports.get("follower_right")),
            "follower_left":  _make_bus(ports.get("follower_left")),
        }

        for name, bus in self._buses.items():
            if bus is not None:
                try:
                    bus.connect()
                    log.info(f"Connected: {name} @ {ports.get(name)}")
                except Exception as e:
                    log.error(f"Failed to connect {name}: {e}")
                    raise

    def read_positions(self, arm: str) -> Dict[str, float]:
        bus = self._get_bus(arm)
        return bus.sync_read("Present_Position")

    def write_positions(self, arm: str, positions: Dict[str, float]):
        bus = self._get_bus(arm)
        bus.sync_write("Goal_Position", positions)

    def write_torque(self, arm: str, enable: bool):
        bus = self._buses.get(arm)
        if bus is None:
            return
        if enable:
            bus.enable_torque()
        else:
            bus.disable_torque()

    def close(self):
        for name, bus in self._buses.items():
            if bus is not None:
                try:
                    bus.disconnect()
                    log.info(f"Disconnected: {name}")
                except Exception as e:
                    log.warning(f"Error disconnecting {name}: {e}")

    def _get_bus(self, arm: str):
        bus = self._buses.get(arm)
        if bus is None:
            raise RuntimeError(f"Arm '{arm}' is not configured.")
        return bus

    @property
    def has_left_leader(self) -> bool:
        return self._buses.get("leader_left") is not None
