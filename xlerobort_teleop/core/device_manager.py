"""
DeviceManager
=============
Wraps lerobot's Motor Bus objects for each SO-101 arm.
Falls back to a minimal stub if lerobot is not importable,
so the rest of the code can be unit-tested without hardware.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

# ── lerobot import with graceful fallback ─────────────────────────────────────

try:
    from lerobot.motors.dynamixel import DynamixelMotorsBus    
    _LEROBOT_AVAILABLE = True
except ImportError:
    _LEROBOT_AVAILABLE = False
    log.warning(
        "lerobot not found — running in STUB mode. "
        "Arm reads will return zeros; writes are no-ops."
    )


# ── Motor definitions for SO-101 ─────────────────────────────────────────────

SO101_MOTORS = {
    "shoulder_pan":   (1, "xl330-m077"),
    "shoulder_lift":  (2, "xl330-m077"),
    "elbow_flex":     (3, "xl330-m077"),
    "wrist_flex":     (4, "xl330-m077"),
    "wrist_roll":     (5, "xl330-m077"),
    "gripper":        (6, "xl330-m077"),
}


# ── Stub bus used when lerobot is unavailable ─────────────────────────────────

class _StubBus:
    """No-hardware stub — logs instead of writing to serial."""

    def __init__(self, port: str, motors: dict):
        self.port = port
        self.motors = motors
        self._connected = False

    def connect(self):
        log.info(f"[STUB] connect → {self.port}")
        self._connected = True

    def disconnect(self):
        log.info(f"[STUB] disconnect → {self.port}")
        self._connected = False

    def read(self, data_name: str, motor_names: list) -> list:
        return [0] * len(motor_names)

    def write(self, data_name: str, values, motor_names: list):
        log.debug(f"[STUB] write {data_name} = {values} → {self.port}")

    def set_calibration(self, calibration: dict):
        pass


def _make_bus(port: Optional[str], motors: dict):
    """Factory: real DynamixelMotorsBus when lerobot is available, else stub."""
    if port is None:
        return None
    if _LEROBOT_AVAILABLE:
        return DynamixelMotorsBus(port=port, motors=motors)
    return _StubBus(port=port, motors=motors)


# ── DeviceManager ─────────────────────────────────────────────────────────────

MOTOR_NAMES = list(SO101_MOTORS.keys())


class DeviceManager:
    """
    Manages four SO-101 arms (two leaders, two followers).
    leader_left is optional for single-leader modes.
    """

    def __init__(self, ports: Dict[str, Optional[str]], baudrate: int = 1_000_000):
        self.ports = ports
        self.baudrate = baudrate

        self._buses: Dict[str, Optional[object]] = {
            "leader_right":   _make_bus(ports.get("leader_right"),   SO101_MOTORS),
            "leader_left":    _make_bus(ports.get("leader_left"),    SO101_MOTORS),
            "follower_right": _make_bus(ports.get("follower_right"), SO101_MOTORS),
            "follower_left":  _make_bus(ports.get("follower_left"),  SO101_MOTORS),
        }

        for name, bus in self._buses.items():
            if bus is not None:
                try:
                    bus.connect()
                    log.info(f"Connected: {name} @ {ports.get(name)}")
                except Exception as e:
                    log.error(f"Failed to connect {name}: {e}")
                    raise

    # ── Read helpers ──────────────────────────────────────────────────────────

    def read_positions(self, arm: str) -> Dict[str, int]:
        """Return {motor_name: position_value} for the given arm."""
        bus = self._buses.get(arm)
        if bus is None:
            raise RuntimeError(f"Arm '{arm}' is not configured.")
        raw = bus.read("Present_Position", MOTOR_NAMES)
        return dict(zip(MOTOR_NAMES, raw))

    # ── Write helpers ─────────────────────────────────────────────────────────

    def write_positions(self, arm: str, positions: Dict[str, int]):
        """Write position dict to the given arm."""
        bus = self._buses.get(arm)
        if bus is None:
            raise RuntimeError(f"Arm '{arm}' is not configured.")
        values = [positions[m] for m in MOTOR_NAMES]
        bus.write("Goal_Position", values, MOTOR_NAMES)

    def write_torque(self, arm: str, enable: bool):
        bus = self._buses.get(arm)
        if bus is None:
            return
        val = [1 if enable else 0] * len(MOTOR_NAMES)
        bus.write("Torque_Enable", val, MOTOR_NAMES)
        log.debug(f"Torque {'ON' if enable else 'OFF'} → {arm}")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self):
        for name, bus in self._buses.items():
            if bus is not None:
                try:
                    bus.disconnect()
                    log.info(f"Disconnected: {name}")
                except Exception as e:
                    log.warning(f"Error disconnecting {name}: {e}")

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def has_left_leader(self) -> bool:
        return self._buses.get("leader_left") is not None
