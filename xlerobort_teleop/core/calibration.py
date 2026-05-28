"""
Calibration
===========
Uses lerobot's SOLeader / SOFollower classes directly,
which handle the full interactive calibration flow for SO-101 Feetech arms.

Run via:
    python teleop.py --mode calibrate
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

# Arm definitions: (config_id, port, role)
# role is "leader" or "follower"
_ARMS = [
    ("test_leader_right",   "/dev/leader_right",   "leader"),
    ("test_leader_left",    "/dev/leader_left",    "leader"),
    ("test_follower_right", "/dev/follower_right", "follower"),
    ("test_follower_left",  "/dev/follower_left",  "follower"),
]


def run_calibration(cfg: dict):
    """
    Interactive calibration for all four SO-101 arms using lerobot's
    built-in SOLeader / SOFollower calibration flow.
    """
    try:
        from lerobot.motors import MotorNormMode
        from lerobot.motors.feetech import FeetechMotorsBus
        from lerobot.robots.so_follower.so_follower import SOFollower
        from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
        from lerobot.teleoperators.so_leader.so_leader import SOLeader
        from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig
    except ImportError as e:
        log.error(f"lerobot import failed: {e}\nInstall with: pip install lerobot")
        sys.exit(1)

    # Allow config overrides
    devices_cfg = cfg.get("devices", {})
    arms = [
        (
            devices_cfg.get(f"id_{role}_{side}", arm_id),
            devices_cfg.get(f"{role}_{side}", port),
            role,
        )
        for arm_id, port, role in _ARMS
        for side in []  # unpacked below
    ]
    # Rebuild cleanly with config overrides
    arms = []
    for arm_id, port, role in _ARMS:
        key = arm_id.replace("test_", "")          # e.g. "leader_right"
        arms.append((
            cfg.get("calibration_ids", {}).get(key, arm_id),
            devices_cfg.get(key, port),
            role,
        ))

    print("\n" + "=" * 60)
    print("  XLeRobot SO-101 Calibration Wizard (Feetech STS3215)")
    print("=" * 60)
    print("Each arm will be calibrated in sequence.")
    print("Follow the on-screen prompts to move each joint.\n")

    for arm_id, port, role in arms:
        ans = input(f"\nCalibrate '{arm_id}' ({role}) @ {port}? [Y/n] ").strip().lower()
        if ans == "n":
            print(f"  → Skipping {arm_id}")
            continue

        print(f"\n{'─'*50}")
        print(f"  {arm_id}  ({role})  →  {port}")
        print(f"{'─'*50}")

        try:
            if role == "leader":
                config = SOLeaderTeleopConfig(port=port, id=arm_id)
                arm = SOLeader(config)
            else:
                config = SOFollowerRobotConfig(port=port, id=arm_id)
                arm = SOFollower(config)

            # connect(calibrate=True) triggers the interactive calibration flow
            # if no calibration file exists, or lets you re-run it
            arm.connect(calibrate=True)
            arm.disconnect()
            print(f"  ✓ {arm_id} calibrated.")

        except Exception as e:
            log.error(f"Calibration failed for {arm_id}: {e}")
            print(f"  ✗ {arm_id} failed — check connection and try again.")

    print("\n✓ Calibration session complete.\n")
