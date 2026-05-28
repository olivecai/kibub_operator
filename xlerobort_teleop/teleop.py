#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Teleoperation
================================
Supports multiple teleoperation modes for two SO-101 follower arms
controlled by SO-101 leader arm(s).

Usage:
    python teleop.py --mode dual          # Two leaders → two followers (default)
    python teleop.py --mode single_right  # Right leader → both followers mirrored
    python teleop.py --mode single_left   # Left leader → both followers mirrored
    python teleop.py --mode mirror        # Right leader → both followers (same pose)
    python teleop.py --mode calibrate     # Run lerobot calibration wizard
    python teleop.py --config my_config.yaml  # Load custom config
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from core.device_manager import DeviceManager
from core.teleop_modes import (
    DualLeaderMode,
    SingleLeaderBothMode,
    MirrorMode,
)
from core.calibration import run_calibration

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "teleop.log"),
    ],
)
log = logging.getLogger("teleop")

# ── Graceful shutdown ─────────────────────────────────────────────────────────

_shutdown = False

def _handle_signal(sig, frame):
    global _shutdown
    log.info("Shutdown signal received — stopping teleoperation loop…")
    _shutdown = True

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="XLeRobot Dual-Arm Teleoperation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["dual", "single_right", "single_left", "mirror", "calibrate"],
        default="dual",
        help="Teleoperation mode (default: dual)",
    )
    parser.add_argument(
        "--config",
        default="configs/default.yaml",
        help="Path to YAML config file (default: configs/default.yaml)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override control loop frequency in Hz",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without opening serial ports",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args()


def load_config(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        log.warning(f"Config not found at {cfg_path} — using built-in defaults.")
        return {}
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
    log.info(f"Loaded config from {cfg_path}")
    return cfg


def run(args, cfg: dict):
    devices_cfg = cfg.get("devices", {})

    ports = {
        "leader_right":   devices_cfg.get("test_leader_right",   "/dev/leader_right"),
        "leader_left":    devices_cfg.get("test_leader_left",    "/dev/leader_left"),          # optional
        "follower_right": devices_cfg.get("test_follower_right", "/dev/follower_right"),
        "follower_left":  devices_cfg.get("test_follower_left",  "/dev/follower_left"),
    }

    control_cfg = cfg.get("control", {})
    fps      = args.fps or control_cfg.get("fps", 50)
    baudrate = control_cfg.get("baudrate", 1000000)
    dt       = 1.0 / fps

    log.info(f"Mode: {args.mode}  |  FPS: {fps}  |  Baud: {baudrate}")
    log.info(f"Ports → {ports}")

    if args.dry_run:
        log.info("[DRY RUN] Would open devices and start loop — exiting.")
        return

    dm = DeviceManager(ports=ports, baudrate=baudrate)

    mode_map = {
        "dual":         DualLeaderMode,
        "single_right": lambda dm, cfg: SingleLeaderBothMode(dm, cfg, leader_side="right"),
        "single_left":  lambda dm, cfg: SingleLeaderBothMode(dm, cfg, leader_side="left"),
        "mirror":       MirrorMode,
    }

    mode_cls = mode_map[args.mode]
    mode = mode_cls(dm, cfg)

    log.info(f"Starting teleoperation — press Ctrl-C to stop.")
    mode.on_start()

    try:
        while not _shutdown:
            t0 = time.perf_counter()
            mode.step()
            elapsed = time.perf_counter() - t0
            sleep_for = dt - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            elif elapsed > dt * 1.5:
                log.debug(f"Loop overrun: {elapsed*1000:.1f} ms (target {dt*1000:.1f} ms)")
    finally:
        log.info("Shutting down devices…")
        mode.on_stop()
        dm.close()
        log.info("Done.")


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = load_config(args.config)

    if args.mode == "calibrate":
        run_calibration(cfg)
        return

    run(args, cfg)


if __name__ == "__main__":
    main()
