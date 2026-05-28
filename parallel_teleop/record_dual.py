#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Dataset Recorder
====================================
Records BOTH arms into a single LeRobot-compatible dataset with:
  observation.state  shape [12]  — [right_arm × 6, left_arm × 6]
  action             shape [12]  — same layout
Uploads to HuggingFace on completion.

Usage
-----
python record_dual.py \
  --repo-id your-username/dual-arm-dataset \
  --task "pick up the block" \
  --episodes 50
"""

import argparse
import time
import signal
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
from lerobot.common.robot_devices.robots.factory import make_robot
from lerobot.common.robot_devices.utils import RobotDeviceAlreadyConnectedError
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

# ── Arm configuration ────────────────────────────────────────────────────────

RIGHT_ARM_CONFIG = {
    "type": "so101_follower",
    "port": "/dev/follower_right",
    "id": "test_follower_right",
}

LEFT_ARM_CONFIG = {
    "type": "so101_follower",
    "port": "/dev/follower_left",
    "id": "test_follower_left",
}

RIGHT_LEADER_CONFIG = {
    "type": "so101_leader",
    "port": "/dev/leader_right",
    "id": "test_leader_right",
}

LEFT_LEADER_CONFIG = {
    "type": "so101_leader",
    "port": "/dev/leader_left",
    "id": "test_leader_left",
}

JOINT_NAMES_SINGLE = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]

# Dual-arm feature names: right first, then left
JOINT_NAMES_DUAL = (
    [f"right_{j}" for j in JOINT_NAMES_SINGLE]
    + [f"left_{j}"  for j in JOINT_NAMES_SINGLE]
)


def make_dual_arm_dataset(repo_id: str, task: str, fps: int) -> LeRobotDataset:
    """Creates a LeRobotDataset with 12-DOF state/action features."""
    features = {
        "observation.state": {
            "dtype": "float32",
            "shape": (12,),
            "names": JOINT_NAMES_DUAL,
        },
        "action": {
            "dtype": "float32",
            "shape": (12,),
            "names": JOINT_NAMES_DUAL,
        },
    }
    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        features=features,
        robot_type="so101_dual_follower",
    )
    return dataset


def read_arm(arm_robot):
    """Returns (obs_state: np.ndarray[6], action: np.ndarray[6])."""
    obs = arm_robot.capture_observation()
    state  = obs["observation.state"].numpy()   # shape [6]
    action = arm_robot.get_action().numpy()     # shape [6]  (leader command)
    return state, action


def record(args):
    print(f"\nConnecting to arms...")

    # Instantiate both follower robots
    right_robot = make_robot(RIGHT_ARM_CONFIG)
    left_robot  = make_robot(LEFT_ARM_CONFIG)
    right_robot.connect()
    left_robot.connect()

    # Instantiate both leader robots (so we can read their commanded positions)
    right_leader = make_robot(RIGHT_LEADER_CONFIG)
    left_leader  = make_robot(LEFT_LEADER_CONFIG)
    right_leader.connect()
    left_leader.connect()

    print("Arms connected.\n")

    dataset = make_dual_arm_dataset(args.repo_id, args.task, args.fps)
    episode_idx = 0
    frame_dt = 1.0 / args.fps

    print(f"Recording {args.episodes} episodes")
    print(f"Controls: [Enter] = save & next episode | [d] + [Enter] = discard | [Ctrl-C] = stop & upload\n")

    def save_and_upload(sig=None, frame=None):
        print("\nFinalising dataset...")
        dataset.consolidate(run_compute_stats=True)
        if args.push:
            print(f"Uploading to {args.repo_id} ...")
            dataset.push_to_hub(tags=["LeRobot", "so101", "dual-arm"])
            print("Upload complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, save_and_upload)
    signal.signal(signal.SIGTERM, save_and_upload)

    while episode_idx < args.episodes:
        print(f"─── Episode {episode_idx + 1}/{args.episodes} ───")
        print("Move the arms. Press [Enter] to save, type 'd' then [Enter] to discard.")

        frames = []
        recording = True

        # Start recording frames in a tight loop
        # We collect until user presses Enter
        import threading
        user_input = {"value": None}

        def wait_for_input():
            user_input["value"] = input()

        input_thread = threading.Thread(target=wait_for_input, daemon=True)
        input_thread.start()

        episode_start = time.time()
        while input_thread.is_alive():
            t0 = time.perf_counter()

            # Read both arms simultaneously
            right_state,  right_action  = read_arm(right_robot)
            left_state,   left_action   = read_arm(left_robot)

            # Concatenate: right first, then left → shape [12]
            state  = np.concatenate([right_state,  left_state],  axis=0).astype(np.float32)
            action = np.concatenate([right_action, left_action], axis=0).astype(np.float32)

            frames.append({"observation.state": state, "action": action})

            # Maintain target FPS
            elapsed = time.perf_counter() - t0
            sleep_time = frame_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        discard = user_input["value"].strip().lower() == "d"

        if discard or len(frames) == 0:
            print(f"Episode {episode_idx + 1} discarded.\n")
            continue

        # Write frames into dataset
        for frame in frames:
            import torch
            dataset.add_frame({
                "observation.state": torch.from_numpy(frame["observation.state"]),
                "action":            torch.from_numpy(frame["action"]),
            })

        dataset.save_episode(task=args.task)
        print(f"Saved episode {episode_idx + 1} ({len(frames)} frames @ {args.fps} fps)\n")
        episode_idx += 1

    save_and_upload()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id",  required=True, help="e.g. your-username/dual-arm-dataset")
    parser.add_argument("--task",     required=True, help="Natural language task description")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--fps",      type=int, default=30)
    parser.add_argument("--push",     action="store_true", default=True,
                        help="Push to HuggingFace on completion")
    args = parser.parse_args()
    record(args)


if __name__ == "__main__":
    main()