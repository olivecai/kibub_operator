"""
Calibration
===========
Wraps lerobot's calibration workflow for the XLeRobot SO-101 arms.

Run via:
    python teleop.py --mode calibrate
or directly:
    python -m core.calibration
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Arms to calibrate (in order)
_ARM_ROLES = [
    ("leader_right",   "/dev/ttyACM3", "leader"),
    ("leader_left",    None,           "leader"),   # port from config / skipped if None
    ("follower_right", "/dev/ttyACM1", "follower"),
    ("follower_left",  "/dev/ttyACM0", "follower"),
]

_CALIB_DIR = Path("configs/calibration")


def _try_import_lerobot():
    try:
        from lerobot.common.robot_devices.motors.dynamixel import DynamixelMotorsBus
        from lerobot.common.robot_devices.robots.utils import get_arm_id
        return True
    except ImportError:
        return False


def run_calibration(cfg: dict):
    """
    Interactive calibration wizard.
    Iterates through each arm, runs lerobot's built-in calibration,
    and saves the result to configs/calibration/<arm_name>.json.
    """
    _CALIB_DIR.mkdir(parents=True, exist_ok=True)

    if not _try_import_lerobot():
        log.error(
            "lerobot is not installed. "
            "Install it with:  pip install lerobot\n"
            "Then re-run calibration."
        )
        sys.exit(1)

    # Pull overridden ports from config
    devices_cfg = cfg.get("devices", {})
    arm_list = [
        (name, devices_cfg.get(name, default_port), role)
        for name, default_port, role in _ARM_ROLES
    ]

    print("\n" + "=" * 60)
    print("  XLeRobot SO-101 Calibration Wizard")
    print("=" * 60)
    print("You will be guided through calibrating each arm.")
    print("Follow the prompts to move joints to their limits.\n")

    for arm_name, port, role in arm_list:
        if port is None:
            ans = input(f"\nSkip {arm_name} (no port configured)? [Y/n] ").strip().lower()
            if ans != "n":
                print(f"  → Skipping {arm_name}")
                continue
            port = input(f"  Enter serial port for {arm_name}: ").strip()

        calib_path = _CALIB_DIR / f"{arm_name}.json"

        print(f"\n{'─'*50}")
        print(f"  Calibrating: {arm_name}  ({role})  @  {port}")
        print(f"  Output:      {calib_path}")
        print(f"{'─'*50}")

        _calibrate_arm(arm_name=arm_name, port=port, role=role, output=calib_path)

    print("\n✓ Calibration complete.")
    print(f"  Results saved to: {_CALIB_DIR.resolve()}\n")


def _calibrate_arm(arm_name: str, port: str, role: str, output: Path):
    """
    Run lerobot's calibration for a single arm.
    This mimics what lerobot's `record` script does internally.
    """
    try:
        from lerobot.common.robot_devices.motors.dynamixel import DynamixelMotorsBus
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
        from lerobot.common.robot_devices.robots.utils import get_arm_id
    except ImportError as e:
        log.error(f"lerobot import failed: {e}")
        return

    from core.device_manager import SO101_MOTORS

    bus = DynamixelMotorsBus(port=port, motors=SO101_MOTORS)

    try:
        bus.connect()
        log.info(f"Connected to {arm_name} for calibration.")

        # lerobot exposes run_arm_calibration for manual homing
        try:
            from lerobot.common.robot_devices.robots.manipulator import (
                run_arm_calibration,
            )
            calibration = run_arm_calibration(bus, robot_type="so101", arm_name=arm_name, arm_type=role)
        except ImportError:
            # Older lerobot API — fall back to built-in calibration
            log.warning("run_arm_calibration not found; using bus.run_full_calibration()")
            calibration = bus.run_full_calibration()

        # Persist calibration
        import json
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(calibration, f, indent=2)
        log.info(f"Calibration saved → {output}")

    finally:
        bus.disconnect()
