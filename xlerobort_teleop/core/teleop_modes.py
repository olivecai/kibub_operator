"""
Teleoperation Modes
===================

All modes inherit from BaseTeleopMode and implement three hooks:
  on_start()  — called once before the loop begins
  step()      — called every control tick
  on_stop()   — called on shutdown / exception

Available modes
---------------
DualLeaderMode
    Two leaders, each controlling its own follower.
    leader_right → follower_right
    leader_left  → follower_left

SingleLeaderBothMode(leader_side="right"|"left")
    One leader arm sends the same pose to BOTH followers.
    Useful when one arm is being repaired / not attached yet.

MirrorMode
    Right leader drives right follower normally.
    Left follower receives a mirrored (laterally flipped) copy
    of the right leader's pose — shoulder_pan negated.

    This produces symmetric bimanual motion from a single leader,
    like opening a box symmetrically.

Adding a new mode
-----------------
1.  Subclass BaseTeleopMode.
2.  Override on_start / step / on_stop as needed.
3.  Register it in teleop.py's mode_map dict.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict

from .device_manager import DeviceManager, MOTOR_NAMES

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

# Motors whose values are negated when mirroring left↔right
_MIRROR_NEGATE = {"shoulder_pan", "wrist_roll"}
# Encoder range for XL330 at default resolution
_ENCODER_CENTER = 2048


def mirror_positions(positions: Dict[str, int]) -> Dict[str, int]:
    """
    Produce a laterally mirrored pose.
    For each motor in _MIRROR_NEGATE the offset from centre is flipped.
    """
    out = {}
    for motor, val in positions.items():
        if motor in _MIRROR_NEGATE:
            out[motor] = 2 * _ENCODER_CENTER - val
        else:
            out[motor] = val
    return out


# ── Base class ────────────────────────────────────────────────────────────────

class BaseTeleopMode(ABC):
    """Abstract base for all teleoperation modes."""

    def __init__(self, dm: DeviceManager, cfg: dict):
        self.dm = dm
        self.cfg = cfg
        self._step_count = 0

    def on_start(self):
        """Enable torque on all connected followers."""
        for follower in ("test_follower_right", "test_follower_left"):
            try:
                self.dm.write_torque(follower, True)
            except RuntimeError:
                pass
        log.info(f"{self.__class__.__name__} started.")

    def on_stop(self):
        """Disable torque on all connected followers."""
        for follower in ("test_follower_right", "test_follower_left"):
            try:
                self.dm.write_torque(follower, False)
            except RuntimeError:
                pass
        log.info(f"{self.__class__.__name__} stopped after {self._step_count} steps.")

    @abstractmethod
    def step(self):
        """Execute one control tick."""

    def _safe_read(self, arm: str) -> Dict[str, int]:
        try:
            return self.dm.read_positions(arm)
        except Exception as e:
            log.warning(f"Read error on {arm}: {e}")
            return {m: _ENCODER_CENTER for m in MOTOR_NAMES}

    def _safe_write(self, arm: str, positions: Dict[str, int]):
        try:
            self.dm.write_positions(arm, positions)
        except Exception as e:
            log.warning(f"Write error on {arm}: {e}")


# ── Mode: Dual Leader ─────────────────────────────────────────────────────────

class DualLeaderMode(BaseTeleopMode):
    """
    Standard 1:1 bilateral teleoperation.

        leader_right → follower_right
        leader_left  → follower_left

    Requires both leader ports to be configured.
    """

    def on_start(self):
        if not self.dm.has_left_leader:
            raise RuntimeError(
                "DualLeaderMode requires 'leader_left' port to be set in config."
            )
        super().on_start()

    def step(self):
        pos_r = self._safe_read("test_leader_right")
        pos_l = self._safe_read("test_leader_left")

        self._safe_write("test_follower_right", pos_r)
        self._safe_write("test_follower_left",  pos_l)

        self._step_count += 1
        if self._step_count % 500 == 0:
            log.debug(f"[dual] step {self._step_count} | R gripper={pos_r.get('gripper')} L gripper={pos_l.get('gripper')}")


# ── Mode: Single Leader → Both ────────────────────────────────────────────────

class SingleLeaderBothMode(BaseTeleopMode):
    """
    One leader arm drives BOTH follower arms with the same joint angles.
    Handy for synchronised parallel manipulation (e.g. lifting a tray).

    Args:
        leader_side: "right" (default) or "left"
    """

    def __init__(self, dm: DeviceManager, cfg: dict, leader_side: str = "right"):
        super().__init__(dm, cfg)
        if leader_side not in ("right", "left"):
            raise ValueError(f"leader_side must be 'right' or 'left', got '{leader_side}'")
        self.leader_arm = f"leader_{leader_side}"
        self.leader_side = leader_side

    def on_start(self):
        if self.leader_side == "left" and not self.dm.has_left_leader:
            raise RuntimeError(
                "SingleLeaderBothMode(leader_side='left') requires 'leader_left' port."
            )
        super().on_start()
        log.info(f"Single-leader mode: {self.leader_arm} → follower_right + follower_left")

    def step(self):
        pos = self._safe_read(self.leader_arm)

        self._safe_write("test_follower_right", pos)
        self._safe_write("test_follower_left",  pos)

        self._step_count += 1


# ── Mode: Mirror ──────────────────────────────────────────────────────────────

class MirrorMode(BaseTeleopMode):
    """
    Right leader drives right follower normally.
    Left follower receives a laterally mirrored version of the same pose —
    shoulder_pan and wrist_roll are reflected about the encoder midpoint.

    This creates symmetric bimanual motion from a single leader arm,
    for example opening a container symmetrically, or placing objects
    in parallel on either side of the workspace.

    No left leader arm required.
    """

    def on_start(self):
        super().on_start()
        log.info("Mirror mode: leader_right → follower_right AND mirrored → follower_left")

    def step(self):
        pos_r  = self._safe_read("leader_right")
        pos_l  = mirror_positions(pos_r)

        self._safe_write("test_follower_right", pos_r)
        self._safe_write("test_follower_left",  pos_l)

        self._step_count += 1
        if self._step_count % 500 == 0:
            log.debug(
                f"[mirror] step {self._step_count} "
                f"| pan_R={pos_r.get('shoulder_pan')} pan_L={pos_l.get('shoulder_pan')}"
            )
