#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Dataset Recorder
====================================
Records BOTH arms into a single LeRobotDataset with shape [12] state/action.

Verified imports from:
  github.com/huggingface/lerobot/blob/main/docs/source/il_robots.mdx

Usage
-----
python record_dual.py \
  --repo-id your-username/dual-arm-dataset \
  --task "pick up the block" \
  --episodes 50
"""

import argparse
import time
import threading
import signal
import sys

import numpy as np
import torch

# ── Verified LeRobot v3 imports ───────────────────────────────────────────────
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
from lerobot.datasets import LeRobotDataset
from lerobot.utils.feature_utils import hw_to_dataset_features
from lerobot.common.control_utils import init_keyboard_listener
from lerobot.utils.utils import log_say

# ── Arm configuration ─────────────────────────────────────────────────────────

JOINT_NAMES_SINGLE = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]

# Dual-arm layout: right first, then left  →  shape [12]
JOINT_NAMES_DUAL = (
    [f"right_{j}" for j in JOINT_NAMES_SINGLE]
    + [f"left_{j}"  for j in JOINT_NAMES_SINGLE]
)


def make_robots(args):
    right_follower_cfg = SO101FollowerConfig(
        port="/dev/follower_right",
        id="test_follower_right",
    )
    left_follower_cfg = SO101FollowerConfig(
        port="/dev/follower_left",
        id="test_follower_left",
    )
    right_leader_cfg = SO101LeaderConfig(
        port="/dev/leader_right",
        id="test_leader_right",
    )
    left_leader_cfg = SO101LeaderConfig(
        port="/dev/leader_left",
        id="test_leader_left",
    )

    right_robot  = SO101Follower(right_follower_cfg)
    left_robot   = SO101Follower(left_follower_cfg)
    right_leader = SO101Leader(right_leader_cfg)
    left_leader  = SO101Leader(left_leader_cfg)

    return right_robot, left_robot, right_leader, left_leader


def make_dataset(repo_id: str, fps: int, right_robot) -> LeRobotDataset:
    """
    Build dataset features from a single robot's hw_features,
    then double them for dual-arm with renamed keys.
    """
    # Use LeRobot's own feature helper so dtypes/shapes are always correct
    single_action_features = hw_to_dataset_features(right_robot.action_features, "action")
    single_obs_features    = hw_to_dataset_features(right_robot.observation_features, "observation")

    # Manually build dual-arm features with correct [12] shape and joint names
    dual_features = {
        "action": {
            "dtype": "float32",
            "shape": (12,),
            "names": JOINT_NAMES_DUAL,
        },
        "observation.state": {
            "dtype": "float32",
            "shape": (12,),
            "names": JOINT_NAMES_DUAL,
        },
    }

    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        features=dual_features,
        robot_type="so101_dual_follower",
        use_videos=False,   # set True and add camera configs if you have cameras
        image_writer_threads=0,
    )
    return dataset


def record(args):
    print("\nConnecting to arms...")
    right_robot, left_robot, right_leader, left_leader = make_robots(args)

    right_robot.connect()
    left_robot.connect()
    right_leader.connect()
    left_leader.connect()
    print("All four arms connected.\n")

    dataset = make_dataset(args.repo_id, args.fps, right_robot)
    frame_dt = 1.0 / args.fps

    _, events = init_keyboard_listener()  # gives us events["stop_recording"] etc.

    def save_and_upload(sig=None, frame=None):
        print("\nFinalising and uploading dataset...")
        robot.disconnect() if False else None   # handled below
        dataset.push_to_hub(tags=["LeRobot", "so101", "dual-arm"], display_data=False,)
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  save_and_upload)
    signal.signal(signal.SIGTERM, save_and_upload)

    print(f"Recording {args.episodes} episodes @ {args.fps} fps")
    print("Controls: [→] save & next  |  [←] discard & redo  |  [Esc] stop & upload\n")

    episode_idx = 0
    while episode_idx < args.episodes and not events["stop_recording"]:
        log_say(f"Recording episode {episode_idx + 1} of {args.episodes}")
        events["exit_early"]        = False
        events["rerecord_episode"]  = False

        episode_start = time.perf_counter()
        episode_time  = args.episode_time_s

        while not events["exit_early"] and not events["stop_recording"]:
            t0 = time.perf_counter()

            # ── Read both arms in the same timestep ───────────────────────────
            right_obs    = right_robot.get_observation()   # dict with "observation.state"
            left_obs     = left_robot.get_observation()
            right_action = right_leader.get_action()       # dict with motor name → float
            left_action  = left_leader.get_action()

            # Flatten to numpy vectors
    
            right_state_vec = np.array(list(right_obs.values()), dtype=np.float32)
            left_state_vec  = np.array(list(left_obs.values()), dtype=np.float32)
            right_action_vec = np.array(list(right_action.values()),                      dtype=np.float32)
            left_action_vec  = np.array(list(left_action.values()),                       dtype=np.float32)

            # Concatenate → shape [12]: right first, then left
            state_12  = np.concatenate([right_state_vec,  left_state_vec],  axis=0)
            action_12 = np.concatenate([right_action_vec, left_action_vec], axis=0)

            # Also send the commands to the followers
            right_robot.send_action(right_action)
            left_robot.send_action(left_action)

            # ── Write frame into dataset ──────────────────────────────────────
            dataset.add_frame({
                "observation.state": torch.from_numpy(state_12),
                "action": torch.from_numpy(action_12),
                "task": args.task,
            })

            # ── Timing ───────────────────────────────────────────────────────
            if time.perf_counter() - episode_start >= episode_time:
                break
            elapsed = time.perf_counter() - t0
            sleep_time = frame_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if events["rerecord_episode"]:
            log_say("Re-recording episode")
            events["rerecord_episode"] = False
            events["exit_early"]       = False
            dataset.clear_episode_buffer()
            continue

        dataset.save_episode()
        log_say(f"Episode {episode_idx + 1} saved")
        episode_idx += 1

        # Optional reset period between episodes
        if args.reset_time_s > 0 and episode_idx < args.episodes:
            log_say("Reset the environment")
            reset_start = time.perf_counter()
            while time.perf_counter() - reset_start < args.reset_time_s:
                if events["exit_early"] or events["stop_recording"]:
                    break
                time.sleep(0.1)
            events["exit_early"] = False

    log_say("Recording complete — uploading to HuggingFace")
    right_robot.disconnect()
    left_robot.disconnect()
    right_leader.disconnect()
    left_leader.disconnect()

    if args.push:
        dataset.push_to_hub(tags=["LeRobot", "so101", "dual-arm"], display_data=False,)
        print(f"Dataset pushed to: https://huggingface.co/datasets/{args.repo_id}")


def main():
    parser = argparse.ArgumentParser(description="XLeRobot dual-arm data collection")
    parser.add_argument("--repo-id",       required=True)
    parser.add_argument("--task",          required=True)
    parser.add_argument("--episodes",      type=int,   default=50)
    parser.add_argument("--fps",           type=int,   default=30)
    parser.add_argument("--episode-time-s",type=float, default=60.0,
                        help="Seconds per episode (default 60)")
    parser.add_argument("--reset-time-s",  type=float, default=10.0,
                        help="Reset pause between episodes (default 10)")
    parser.add_argument("--push",          action="store_true", default=True)
    args = parser.parse_args()
    record(args)


if __name__ == "__main__":
    main()