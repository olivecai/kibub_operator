#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Dataset Recorder  (with cameras)
====================================================
Records BOTH arms + N cameras into a single LeRobotDataset v3.

State/action shape: [12]  (right arm first, then left arm)
Camera keys:  "observation.images.top"
              "observation.images.wrist_right"
              "observation.images.wrist_left"
              (add/remove cameras in CAMERA_CONFIGS below)

Usage
-----
python record_dual_cameras.py \
  --repo-id your-username/dual-arm-dataset \
  --task "pick up the block" \
  --episodes 50
"""

import argparse
import time
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

# ── CAMERA: Custom camera API ────────────────────────────────────────────────────
from camera_api import Camera, CameraConfig

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

# ── CAMERA: define your cameras here ─────────────────────────────────────────
#
# key        → dataset key, becomes "observation.images.<key>"
# id      → OS camera id (ls /dev/video* to find yours)
# width/height/fps should match your camera's supported modes
#
# Remove entries you don't have; add more the same way.
#
CAMERA_CONFIGS = {
    "top_realsense_color": CameraConfig(
        index_or_path='/dev/video4',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG",  # Realsense RGB stream is usually YUYV by default, which is slow to capture with OpenCV. MJPG is much faster.
    ),
    "top_realsense_depth": CameraConfig(
        index_or_path='/dev/video2',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "top_webcam": CameraConfig(
        index_or_path='/dev/video6',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "wrist_right": CameraConfig(
        index_or_path='/dev/wrist_right',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "wrist_left": CameraConfig(
        index_or_path='/dev/wrist_left',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
}
# ── CAMERA end ────────────────────────────────────────────────────────────────


def make_robots(args):
    right_follower_cfg = SO101FollowerConfig(
        port="/dev/follower_right",
        id="follower_right",
    )
    left_follower_cfg = SO101FollowerConfig(
        port="/dev/follower_left",
        id="follower_left",
    )
    right_leader_cfg = SO101LeaderConfig(
        port="/dev/leader_right",
        id="leader_right",
    )
    left_leader_cfg = SO101LeaderConfig(
        port="/dev/leader_left",
        id="leader_left",
    )

    right_robot  = SO101Follower(right_follower_cfg)
    left_robot   = SO101Follower(left_follower_cfg)
    right_leader = SO101Leader(right_leader_cfg)
    left_leader  = SO101Leader(left_leader_cfg)

    return right_robot, left_robot, right_leader, left_leader


# ── CAMERA: instantiate and connect all cameras ───────────────────────────────
def make_cameras(selected_names=None) -> dict:
    """
    Instantiate and connect cameras. If `selected_names` is provided (list of
    keys), only those cameras from `CAMERA_CONFIGS` will be used.
    """
    cameras = {}
    for name, cfg in CAMERA_CONFIGS.items():
        if selected_names is not None and name not in selected_names:
            continue
        print(f"Attempting to connect to camera {name} with cfg {cfg}")
        cam = Camera(cfg)
        cam.connect()
        print(f"  Camera '{name}' connected  (index_or_path={cfg.index_or_path}, {cfg.width}x{cfg.height}@{cfg.fps}fps)")
        cameras[name] = cam
    return cameras
# ── CAMERA end ────────────────────────────────────────────────────────────────


def make_dataset(repo_id: str, fps: int, selected_names=None) -> LeRobotDataset:
    """
    Build dataset features for dual-arm state/action [12] + camera images.
    """
    features = {
        # ── proprioception / control ──────────────────────────────────────────
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

    # ── CAMERA: add one image feature per camera ──────────────────────────────
    #
    # LeRobot v3 stores images as uint8 tensors with shape (H, W, 3) in the
    # frame buffer; the video encoder handles compression at save_episode time.
    # The "video" dtype tells the dataset to write .mp4 files instead of .png.
    #
    for cam_name, cfg in CAMERA_CONFIGS.items():
        if selected_names is not None and cam_name not in selected_names:
            continue
        features[f"observation.images.{cam_name}"] = {
            "dtype": "video",                       # → encoded to .mp4 per episode
            "shape": (cfg.height, cfg.width, 3),    # (H, W, C)  uint8 RGB
            "names": ["height", "width", "channel"],
        }
    # ── CAMERA end ────────────────────────────────────────────────────────────

    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        features=features,
        robot_type="so101_dual_follower",
        use_videos=True,                # ← must be True when any feature is "video"
        image_writer_threads=4,         # one thread per camera is a good starting point
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

    # ── CAMERA: connect cameras ───────────────────────────────────────────────
    print("Connecting to cameras...")
    # Validate and connect only requested cameras (if any)
    cameras = make_cameras(selected_names=args.cameras)
    print("Warming up cameras...")
    time.sleep(0.5)  # Let background threads capture initial frames
    print()
    # ── CAMERA end ────────────────────────────────────────────────────────────

    dataset = make_dataset(args.repo_id, args.fps, selected_names=args.cameras)
    frame_dt = 1.0 / args.fps

    _, events = init_keyboard_listener()

    def cleanup_and_upload(sig=None, frame=None):
        print("\nFinalising and uploading dataset...")
        right_robot.disconnect()
        left_robot.disconnect()
        right_leader.disconnect()
        left_leader.disconnect()
        # ── CAMERA: disconnect cameras ────────────────────────────────────────
        for cam in cameras.values():
            cam.disconnect()
        # ── CAMERA end ────────────────────────────────────────────────────────
        dataset.push_to_hub(tags=["LeRobot", "so101", "dual-arm"], display_data=False)
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  cleanup_and_upload)
    signal.signal(signal.SIGTERM, cleanup_and_upload)

    print(f"Recording {args.episodes} episodes @ {args.fps} fps")
    print("Controls: [→] save & next  |  [←] discard & redo  |  [Esc] stop & upload\n")

    episode_idx = 0
    while episode_idx < args.episodes and not events["stop_recording"]:
        print(f"Recording episode {episode_idx + 1} of {args.episodes}")
        log_say(f"Recording episode {episode_idx + 1} of {args.episodes}")
        events["exit_early"]       = False
        events["rerecord_episode"] = False

        episode_start = time.perf_counter()

        countdown_timer = None
        while not events["exit_early"] and not events["stop_recording"]:
            t0 = time.perf_counter()

            # last 5 seconds give a countdown:
            elapsed = t0 - episode_start
            if elapsed > args.episode_time_s - 5:
                seconds_left = int(args.episode_time_s - elapsed)
                if seconds_left != countdown_timer:
                    print(f"Recording will end in {seconds_left} seconds")
                    countdown_timer = seconds_left

            # ── Read both arms ────────────────────────────────────────────────
            right_obs    = right_robot.get_observation()
            left_obs     = left_robot.get_observation()
            right_action = right_leader.get_action()
            left_action  = left_leader.get_action()

            # Flatten to numpy vectors
            right_state_vec  = np.array(list(right_obs.values()),    dtype=np.float32)
            left_state_vec   = np.array(list(left_obs.values()),     dtype=np.float32)
            right_action_vec = np.array(list(right_action.values()), dtype=np.float32)
            left_action_vec  = np.array(list(left_action.values()),  dtype=np.float32)

            # Concatenate → shape [12]: right first, then left
            state_12  = np.concatenate([right_state_vec,  left_state_vec],  axis=0)
            action_12 = np.concatenate([right_action_vec, left_action_vec], axis=0)

            # Send commands to followers
            right_robot.send_action(right_action)
            left_robot.send_action(left_action)

            # ── CAMERA: capture one frame per camera ──────────────────────────
            #
            # Camera.async_read() is non-blocking and returns the latest
            # frame already captured by the camera's background thread.
            # Use .read() instead if you want a blocking synchronous grab.
            # (custom camera_api implementation)
            #
            camera_frames = {}
            for cam_name, cam in cameras.items():
                frame = cam.async_read(timeout_ms=3000)   # np.ndarray uint8 (H,W,3) BGR
                if frame is None:
                    print(f"  WARNING: Camera '{cam_name}' failed to capture frame (timeout)")
                    
                    continue
                # LeRobot expects RGB, so convert
                frame_rgb = frame[..., ::-1].copy()      # BGR → RGB
                camera_frames[cam_name] = torch.from_numpy(frame_rgb)
            # ── CAMERA end ────────────────────────────────────────────────────

            # ── Write frame into dataset ──────────────────────────────────────
            frame_data = {
                "observation.state": torch.from_numpy(state_12),
                "action":            torch.from_numpy(action_12),
                "task":       args.task,
            }
            # ── CAMERA: merge camera frames into frame_data ───────────────────
            for cam_name, tensor in camera_frames.items():
                frame_data[f"observation.images.{cam_name}"] = tensor

            # ── CAMERA end ────────────────────────────────────────────────────
            # print("DEBUGGING: frame_data keys:", list(frame_data.keys()))
            dataset.add_frame(frame_data)

            # ── Timing ───────────────────────────────────────────────────────
            if time.perf_counter() - episode_start >= args.episode_time_s:
                break
            elapsed    = time.perf_counter() - t0
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

        if args.reset_time_s > 0 and episode_idx < args.episodes:
            log_say("Reset the environment")
            print(f"Resetting... (you have {args.reset_time_s} seconds)")
            reset_start = time.perf_counter()
            while time.perf_counter() - reset_start < args.reset_time_s:
                if events["exit_early"] or events["stop_recording"]:
                    break
                # Keep followers tracking leaders during reset
                right_robot.send_action(right_leader.get_action())
                left_robot.send_action(left_leader.get_action())
                time.sleep(frame_dt)
            events["exit_early"] = False

    log_say("Recording complete — uploading to HuggingFace")
    right_robot.disconnect()
    left_robot.disconnect()
    right_leader.disconnect()
    left_leader.disconnect()

    # ── CAMERA: disconnect all cameras before upload ──────────────────────────
    for cam in cameras.values():
        cam.disconnect()
    # ── CAMERA end ────────────────────────────────────────────────────────────

    print("Finalizing dataset...")
    dataset.finalize()
    if args.push:
        dataset.push_to_hub(
            tags=["LeRobot", "so101", "dual-arm"],
            display_data=False,
        )
        print(f"Dataset pushed to: https://huggingface.co/datasets/{args.repo_id}")


def main():
    parser = argparse.ArgumentParser(description="XLeRobot dual-arm data collection with cameras")
    parser.add_argument("--repo-id",        required=True)
    parser.add_argument("--task",           required=True)
    parser.add_argument("--episodes",       type=int,   default=50)
    parser.add_argument("--fps",            type=int,   default=30)
    parser.add_argument("--cameras",        nargs="+", default=None,
                        help="List of camera keys to include (from CAMERA_CONFIGS).")
    parser.add_argument("--episode-time-s", type=float, default=60.0,
                        help="Seconds per episode (default 60)")
    parser.add_argument("--reset-time-s",   type=float, default=10.0,
                        help="Reset pause between episodes (default 10)")
    parser.add_argument("--push",           action="store_true", default=True)
    args = parser.parse_args()
    # Validate camera names if provided
    if args.cameras is not None:
        available = set(CAMERA_CONFIGS.keys())
        requested = set(args.cameras)
        unknown = requested - available
        if unknown:
            parser.error(f"Unknown camera(s): {', '.join(sorted(unknown))}. Available: {', '.join(sorted(available))}")
    record(args)


if __name__ == "__main__":
    main()