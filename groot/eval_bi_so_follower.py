#!/usr/bin/env python
"""
GR00T policy evaluation client for the BiSOFollower (dual-arm SO-101) robot.

Adapted from Isaac-GR00T's examples/SO-100/eval_lerobot.py, generalized for:
  - 4 state/action modality groups: right_arm, right_gripper, left_arm, left_gripper
    (instead of the SO-100 single-arm client's single_arm/gripper pair)
  - 5 cameras: wrist_right, wrist_left, top_realsense_color, top_realsense_depth, top_webcam
    (instead of a single front+wrist pair)

Run this on the machine connected to the robot hardware (kibub).
The GR00T policy server (scripts/inference_service.py --server) should
already be running on the GPU machine (ocai), bound to 0.0.0.0:5555.

Example:
    python eval_bi_so_follower.py \
        --robot.left_arm_config.port=/dev/ttyACM0 \
        --robot.right_arm_config.port=/dev/ttyACM1 \
        --robot.id=kibub_bi_arm \
        --policy_host=<OCAI_LAN_IP> \
        --policy_port=5555 \
        --lang_instruction="Pick up the screw and place it in the bin."

NOTE: --robot.* camera args (per-arm wrist cams + top_cameras) should be
filled in to match your actual calibration / camera config file, the same
way you'd configure them for `lerobot record` with this robot. If you
already have a saved RobotConfig (e.g. used during data collection), reuse
it here instead of re-specifying cameras on the command line.
"""

import logging
import sys
import time
from dataclasses import asdict, dataclass
from pprint import pformat

import draccus
import numpy as np

from lerobot.robots import (  # noqa: F401
    RobotConfig,
    make_robot_from_config,
)
from lerobot.robots.bi_so_follower import BiSOFollowerConfig  # noqa: F401
from lerobot.utils.utils import init_logging, log_say

# Adjust this path if gr00t/eval/service.py lives elsewhere relative to this script.
sys.path.append("/home/ocai/Isaac-GR00T/gr00t/eval")  # noqa: E402 - adjust path for your machine
from service import ExternalRobotInferenceClient  # noqa: E402

#################################################################################

# Canonical per-arm joint order, taken directly from SOFollower's motor bus definition.
# This MUST match the order your training dataset used when building the
# right_arm / left_arm 5-vectors in metadata.json.
ARM_JOINT_ORDER = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
GRIPPER_JOINT = "gripper"

# Camera key mapping: BiSOFollower.get_observation() keys -> GR00T video.* keys
# Left/right wrist cams come back suffixed _right / _left from BiSOFollower;
# top cameras come back unprefixed, using whatever names are in top_cameras config.
CAMERA_KEY_MAP = {
    "wrist_right": "wrist_right",
    "wrist_left": "wrist_left",
    "top_realsense_color": "top_realsense_color",
    "top_realsense_depth": "top_realsense_depth",
    "top_webcam": "top_webcam",
}


class Gr00tBiArmInferenceClient:
    """
    GR00T policy client for the BiSOFollower dual-arm robot.

    Builds the 4-group state representation (right_arm, right_gripper,
    left_arm, left_gripper) expected by the so101_dual data config from
    BiSOFollower's per-motor observation dict, and converts the policy's
    per-group action chunks back into BiSOFollower's per-motor action dict.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5555,
        camera_keys: list[str] | None = None,
        show_images: bool = False,
    ):
        self.policy = ExternalRobotInferenceClient(host=host, port=port)
        self.camera_keys = camera_keys or list(CAMERA_KEY_MAP.keys())
        self.show_images = show_images
        self.modality_keys = ["right_arm", "right_gripper", "left_arm", "left_gripper"]

    def _build_obs_dict(self, observation_dict: dict, lang: str) -> dict:
        obs_dict = {}

        # --- Video keys ---
        for raw_key, video_key in CAMERA_KEY_MAP.items():
            if raw_key in observation_dict:
                obs_dict[f"video.{video_key}"] = observation_dict[raw_key]

        # --- State keys ---
        # BiSOFollower prefixes motor keys with right_ / left_, e.g. "right_shoulder_pan.pos"
        right_arm_vals = [observation_dict[f"right_{j}.pos"] for j in ARM_JOINT_ORDER]
        right_gripper_val = [observation_dict[f"right_{GRIPPER_JOINT}.pos"]]
        left_arm_vals = [observation_dict[f"left_{j}.pos"] for j in ARM_JOINT_ORDER]
        left_gripper_val = [observation_dict[f"left_{GRIPPER_JOINT}.pos"]]

        obs_dict["state.right_arm"] = np.array(right_arm_vals, dtype=np.float64)
        obs_dict["state.right_gripper"] = np.array(right_gripper_val, dtype=np.float64)
        obs_dict["state.left_arm"] = np.array(left_arm_vals, dtype=np.float64)
        obs_dict["state.left_gripper"] = np.array(left_gripper_val, dtype=np.float64)

        obs_dict["annotation.human.task_description"] = lang

        # Add leading "history=1" dimension, matching eval_lerobot.py's convention
        for k in obs_dict:
            if isinstance(obs_dict[k], np.ndarray):
                obs_dict[k] = obs_dict[k][np.newaxis, ...]
            else:
                obs_dict[k] = [obs_dict[k]]

        return obs_dict

    def get_action(self, observation_dict: dict, lang: str) -> list[dict]:
        obs_dict = self._build_obs_dict(observation_dict, lang)

        # Query the policy server
        action_chunk = self.policy.get_action(obs_dict)

        # action_chunk is a dict like:
        #   action.right_arm:    (horizon, 5)
        #   action.right_gripper:(horizon, 1)
        #   action.left_arm:     (horizon, 5)
        #   action.left_gripper: (horizon, 1)
        action_horizon = action_chunk["action.right_arm"].shape[0]

        actions = []
        for i in range(action_horizon):
            action_dict = self._convert_to_robot_action(action_chunk, i)
            actions.append(action_dict)
        return actions

    def _convert_to_robot_action(self, action_chunk: dict, idx: int) -> dict:
        """Convert one timestep of the action chunk into BiSOFollower's
        send_action() format: {"right_shoulder_pan.pos": ..., "left_gripper.pos": ..., ...}
        """
        action_dict = {}

        right_arm = np.atleast_1d(action_chunk["action.right_arm"][idx])
        for j, joint in enumerate(ARM_JOINT_ORDER):
            action_dict[f"right_{joint}.pos"] = float(right_arm[j])

        right_gripper = np.atleast_1d(action_chunk["action.right_gripper"][idx])
        action_dict[f"right_{GRIPPER_JOINT}.pos"] = float(right_gripper[0])

        left_arm = np.atleast_1d(action_chunk["action.left_arm"][idx])
        for j, joint in enumerate(ARM_JOINT_ORDER):
            action_dict[f"left_{joint}.pos"] = float(left_arm[j])

        left_gripper = np.atleast_1d(action_chunk["action.left_gripper"][idx])
        action_dict[f"left_{GRIPPER_JOINT}.pos"] = float(left_gripper[0])

        return action_dict


#################################################################################


def print_yellow(text):
    print("\033[93m {}\033[00m".format(text))


@dataclass
class EvalConfig:
    robot: RobotConfig  # BiSOFollowerConfig, with left_arm_config / right_arm_config / top_cameras
    policy_host: str = "localhost"  # host of the gr00t inference_service.py server
    policy_port: int = 5555
    action_horizon: int = 8  # number of actions to execute from each predicted chunk
    lang_instruction: str = "Pick up the screw and place it in the bin."
    play_sounds: bool = False
    timeout: int = 60  # seconds
    show_images: bool = False


@draccus.wrap()
def eval(cfg: EvalConfig):
    init_logging()
    logging.info(pformat(asdict(cfg)))

    # Step 1: Initialize and connect the bimanual robot
    robot = make_robot_from_config(cfg.robot)
    robot.connect()

    # Step 2: Initialize the GR00T policy client
    policy_client = Gr00tBiArmInferenceClient(
        host=cfg.policy_host,
        port=cfg.policy_port,
        show_images=cfg.show_images,
    )

    log_say(f"Starting eval with instruction: {cfg.lang_instruction}", cfg.play_sounds)

    start_time = time.perf_counter()
    try:
        while time.perf_counter() - start_time < cfg.timeout:
            observation_dict = robot.get_observation()
            action_chunk = policy_client.get_action(observation_dict, cfg.lang_instruction)

            for i in range(min(cfg.action_horizon, len(action_chunk))):
                t0 = time.perf_counter()
                robot.send_action(action_chunk[i])
                # Basic loop-rate pacing; adjust to match your control frequency (e.g. 30Hz -> ~0.033s)
                elapsed = time.perf_counter() - t0
                sleep_time = max(0.0, (1.0 / 30.0) - elapsed)
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print_yellow("Interrupted by user, stopping...")
    finally:
        robot.disconnect()


if __name__ == "__main__":
    eval()
