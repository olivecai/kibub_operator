#!/usr/bin/env python3
"""
XLeRobot Dual-Arm Teleoperation + Data Collection
===================================================
Modes
-----
dual         — standard dual-arm teleop
single_right — right leader controls both followers  
single_left  — left leader controls both followers
record       — dual-arm teleop with LeRobot dataset recording

Usage
-----
python teleop_dual.py --mode dual
python teleop_dual.py --mode record --repo-id your-hf-username/my-dataset --task "pick up the block" --episodes 50
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
    leader   = ARMS[leader_key]
    follower = ARMS[follower_key]
    return [
        "lerobot-teleoperate",
        "--robot.type=so101_follower",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        "--teleop.type=so101_leader",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
    ]


def build_record_command(
    leader_key: str,
    follower_key: str,
    repo_id: str,
    task: str,
    num_episodes: int,
    fps: int,
    cameras: list[str],
) -> list[str]:
    """
    Uses lerobot-record which handles episode segmentation, camera capture,
    and HuggingFace upload automatically.
    """
    leader   = ARMS[leader_key]
    follower = ARMS[follower_key]

    cmd = [
        "lerobot-record",
        "--robot.type=so101_follower",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        "--teleop.type=so101_leader",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
        f"--dataset.repo_id={repo_id}",
        f"--dataset.num_episodes={num_episodes}",
        f"--dataset.single_task={task}",
        f"--dataset.fps={fps}",
        "--dataset.reset_time_s=5",
        "--dataset.episode_time_s=15",

        "--dataset.push_to_hub=true",
        "--display_data=false"
    ]

    # Attach any camera indices (OpenCV device IDs)
    for i, cam in enumerate(cameras):
        cmd += [
            f"--robot.cameras.cam{i}.type=opencv",
            f"--robot.cameras.cam{i}.index_or_path={cam}",
            f"--robot.cameras.cam{i}.width=640",
            f"--robot.cameras.cam{i}.height=480",
            f"--robot.cameras.cam{i}.fps={fps}",
        ]

    return cmd


def run_teleop(mode: str):
    pairs = MODES[mode]
    processes = []

    print(f"\nStarting teleoperation — mode: {mode}")
    for leader_key, follower_key in pairs:
        cmd = build_teleop_command(leader_key, follower_key)
        print(f"  {leader_key} → {follower_key}")
        print(f"  $ {' '.join(cmd)}\n")
        proc = subprocess.Popen(cmd)
        processes.append(proc)
        time.sleep(0.5)

    return processes


def run_record(repo_id: str, task: str, num_episodes: int, fps: int, cameras: list[str]):
    """
    Records both arms simultaneously. Each lerobot-record process handles
    one follower arm and its assigned cameras. Episodes are synced by wall
    clock — both processes listen for the same keyboard signals (space to
    end episode, escape to stop early).

    NOTE: If lerobot-record doesn't natively support multi-robot in one
    process on your version, run two processes with split camera lists.
    """
    pairs = MODES["dual"]
    processes = []

    # Split cameras evenly between the two arms (or assign all to one if preferred)
    mid = len(cameras) // 2
    camera_splits = [cameras[:mid] if mid > 0 else cameras, cameras[mid:]]

    print(f"\nStarting data collection")
    print(f"  Repo  : {repo_id}")
    print(f"  Task  : {task}")
    print(f"  FPS   : {fps}")
    print(f"  Episodes: {num_episodes}")
    print(f"  Cameras : {cameras or 'none'}\n")
    print("Controls: [Space] = save episode | [Esc] = discard | [Ctrl-C] = stop & upload\n")

    for i, (leader_key, follower_key) in enumerate(pairs):
        arm_cameras = camera_splits[i] if i < len(camera_splits) else []
        cmd = build_record_command(
            leader_key, follower_key, repo_id, task, num_episodes, fps, arm_cameras
        )
        print(f"  {leader_key} → {follower_key}  (cameras: {arm_cameras or 'none'})")
        print(f"  $ {' '.join(cmd)}\n")
        proc = subprocess.Popen(cmd)
        processes.append(proc)
        time.sleep(0.5)

    return processes


def wait_with_shutdown(processes: list):
    print("Press Ctrl-C to stop.\n")

    def shutdown(sig, frame):
        print("\nStopping all processes...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        for proc in processes:
            if proc.poll() is not None:
                print(f"A process exited (code {proc.returncode}). Stopping all.")
                shutdown(None, None)
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="XLeRobot dual-arm teleop + data collection")
    parser.add_argument(
        "--mode",
        choices=[*MODES.keys(), "record"],
        default="dual",
    )
    # Record-mode arguments
    parser.add_argument("--repo-id",     default="your-hf-username/xlerobot-dataset",
                        help="HuggingFace repo ID, e.g. alice/pick-block")
    parser.add_argument("--task",        default="Perform the task",
                        help="Natural language task description stored in the dataset")
    parser.add_argument("--episodes",    type=int, default=50,
                        help="Number of episodes to record")
    parser.add_argument("--fps",         type=int, default=30)
    parser.add_argument("--cameras",     nargs="*", default=[],
                        help="OpenCV camera indices, e.g. --cameras 0 2 4 6")
    args = parser.parse_args()

    if args.mode == "record":
        processes = run_record(
            repo_id=args.repo_id,
            task=args.task,
            num_episodes=args.episodes,
            fps=args.fps,
            cameras=args.cameras,
        )
    else:
        processes = run_teleop(args.mode)

    wait_with_shutdown(processes)


if __name__ == "__main__":
    main()