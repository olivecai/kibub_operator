#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Teleoperation
================================
Wraps lerobot-teleoperate in subprocesses — one per arm pair.
Relies entirely on lerobot's proven teleoperation code.

Modes
-----
dual         — leader_right → follower_right  AND  leader_left → follower_left
single_right — leader_right → follower_right  AND  leader_right → follower_left
single_left  — leader_left  → follower_right  AND  leader_left  → follower_left

Usage
-----
python teleop_dual.py --mode dual
python teleop_dual.py --mode single_right
python teleop_dual.py --mode single_left
"""

import argparse
import subprocess
import signal
import sys
import time

# ── Arm configuration ─────────────────────────────────────────────────────────

ARMS = {
    "leader_right":   {"port": "/dev/leader_right",   "id": "test_leader_right"},
    "leader_left":    {"port": "/dev/leader_left",    "id": "test_leader_left"},
    "follower_right": {"port": "/dev/follower_right", "id": "test_follower_right"},
    "follower_left":  {"port": "/dev/follower_left",  "id": "test_follower_left"},
}

# ── Mode definitions: list of (leader_key, follower_key) pairs ────────────────

MODES = {
    "dual": [
        ("leader_right", "follower_right"),
        ("leader_left",  "follower_left"),
    ],
    "single_right": [
        ("leader_right", "follower_right"),
        ("leader_right", "follower_left"),
    ],
    "single_left": [
        ("leader_left", "follower_right"),
        ("leader_left", "follower_left"),
    ],
}


def build_command(leader_key: str, follower_key: str) -> list[str]:
    leader   = ARMS[leader_key]
    follower = ARMS[follower_key]
    return [
        "lerobot-teleoperate",
        f"--robot.type=so101_follower",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        f"--teleop.type=so101_leader",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
    ]


def main():
    parser = argparse.ArgumentParser(description="XLeRobot dual-arm teleoperation")
    parser.add_argument(
        "--mode",
        choices=list(MODES.keys()),
        default="dual",
        help="Teleoperation mode (default: dual)",
    )
    args = parser.parse_args()

    pairs = MODES[args.mode]
    processes = []

    print(f"\nStarting teleoperation — mode: {args.mode}")
    for leader_key, follower_key in pairs:
        cmd = build_command(leader_key, follower_key)
        print(f"  {leader_key} → {follower_key}")
        print(f"  $ {' '.join(cmd)}\n")
        proc = subprocess.Popen(cmd)
        processes.append(proc)
        time.sleep(0.5)  # slight stagger to avoid serial bus collisions at startup

    print("Press Ctrl-C to stop all arms.\n")

    def shutdown(sig, frame):
        print("\nStopping all teleop processes...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for any process to exit unexpectedly
    while True:
        for proc in processes:
            if proc.poll() is not None:
                print(f"A teleop process exited unexpectedly (code {proc.returncode}). Stopping all.")
                shutdown(None, None)
        time.sleep(1)


if __name__ == "__main__":
    main()