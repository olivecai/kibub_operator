#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Teleoperation + Data Collection
===================================================
Wraps lerobot-teleoperate (or lerobot-record) in subprocesses — one per arm pair.

Modes
-----
dual         — leader_right → follower_right  AND  leader_left → follower_left
single_right — leader_right → follower_right  AND  leader_right → follower_left
single_left  — leader_left  → follower_right  AND  leader_left  → follower_left

Usage
-----
# Pure teleoperation (no recording)
python teleop_dual.py --mode dual

# Record a dataset (saves locally, then push to HF)
python teleop_dual.py --mode dual --record \
    --repo-id your-hf-username/my-task \
    --task "Pick up the red block" \
    --num-episodes 50 \
    --cameras camera_right:0 camera_left:1

# Push an already-recorded local dataset to HuggingFace
python teleop_dual.py --push-only --repo-id your-hf-username/my-task
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

# ── Mode definitions: list of (leader_key, follower_key) pairs ───────────────

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


def build_teleop_command(leader_key: str, follower_key: str) -> list[str]:
    """Pure teleoperation — no data saved."""
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


def build_record_command(
    leader_key: str,
    follower_key: str,
    repo_id: str,
    task: str,
    num_episodes: int,
    cameras: dict[str, int],   # {name: cv2_index}
    fps: int,
    episode_time_s: int,
    reset_time_s: int,
    local_dir: str,
) -> list[str]:
    """
    Record episodes using lerobot-record.

    lerobot-record saves every episode as a Parquet + video file under
    ~/.cache/huggingface/lerobot/<repo_id>/ by default (override with
    --dataset.root). When finished it can auto-push to HuggingFace Hub.
    """
    leader   = ARMS[leader_key]
    follower = ARMS[follower_key]

    cmd = [
        "lerobot-record",
        # ── Robot ──────────────────────────────────────────────────────
        f"--robot.type=so101_follower",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        # ── Teleop ─────────────────────────────────────────────────────
        f"--teleop.type=so101_leader",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
        # ── Dataset ────────────────────────────────────────────────────
        f"--dataset.repo_id={repo_id}",
        f"--dataset.single_task={task}",
        f"--dataset.num_episodes={num_episodes}",
        f"--dataset.fps={fps}",
        f"--dataset.root={local_dir}",
        # ── Episode timing ─────────────────────────────────────────────
        f"--dataset.episode_time_s={episode_time_s}",
        f"--dataset.reset_time_s={reset_time_s}",
        # ── Push to Hub after recording ────────────────────────────────
        "--dataset.push_to_hub=true",
        "--dataset.video=true",
    ]

    # Attach cameras: --robot.cameras.[name].type=opencv
    #                 --robot.cameras.[name].index=N
    for cam_name, cam_index in cameras.items():
        cmd += [
            f"--robot.cameras.{cam_name}.type=opencv",
            f"--robot.cameras.{cam_name}.index={cam_index}",
            f"--robot.cameras.{cam_name}.fps={fps}",
            f"--robot.cameras.{cam_name}.width=640",
            f"--robot.cameras.{cam_name}.height