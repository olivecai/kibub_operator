# README for cow and kibub operator

Instructions on teleop, recording, training, deploying on the cow and kibub machines, using lerobot and Gr00t. 
This repository should be cloned on kibub, and does not need to be cloned on cow, though it has the cow requiremnts.txt just for safe keeping.
Both cow and kibub need the forked lerobot repo.

As of june 4 2026, the openclaw agent should not need to access this repo (it should be totally robot agnostic); check out the openclaw-embodied repo at https://github.com/olivecai/openclaw-embodied 

# Cow operator

## Cow operator install and setup from scatch
1. Create a virtual environment following steps 1 and 2 in the lerobot installation instructions here: https://huggingface.co/docs/lerobot/installation. 
3. In step 3 of the lerobot installation instructions, run `git clone https://github.com/olivecai/lerobot.git` **instead** of `git clone https://github.com/huggingface/lerobot.git` into /home/${COW_USER}/.
4. Follow the rest of the lerobot installation instructions, working inside of your virtual env. Importantly, run `pip install -e` in the /lerobot directory. When you run `pip show lerobot`, you should see 'Editable project location: /home/${COW_USER}/lerobot'
5. Run `pip install -r /home/${COW_USER}/kibub_operator/cow/lerobot_requirements.txt` to install the rest of the needed packages (set COW_USER accordingly; COW_USER=ocai, for example)
6. Log into huggingface: `hf auth login` and set HF_USER in cli. (ie HF_USER=oliveoil8888)

# Kibub operator 

## SSH into kibub
To access the kibub shell: `ssh kibub@kibub`

## Kibub operator install and setup from scatch
1. On the kibub machine in /home/kibub/, clone this repository: https://github.com/olivecai/kibub_operator.
2. Create a virtual environment following steps 1 and 2 in the lerobot installation instructions here: https://huggingface.co/docs/lerobot/installation. 
3. In step 3 of the lerobot installation instructions, run git clone `https://github.com/olivecai/lerobot.git` **instead** of `git clone https://github.com/huggingface/lerobot.git` into /home/kibub/.
4. Follow the rest of the lerobot installation instructions, working inside of your virtual env. Importantly, run `pip install -e` in the /lerobot directory. When you run `pip show lerobot`, you should see 'Editable project location: /home/kibub/lerobot'
5. Run `pip install -r /home/kibub/kibub_operator/kibub/requirements.txt` to install the rest of the needed packages.
6. Log into huggingface: `hf auth login` and set HF_USER in cli. (ie HF_USER=oliveoil8888)

## Kibub operator setup on reboot
Assuming that you have the conda environment and the repositories: run `conda activate lerobot`

# Follower leader dual arm setup with cameras 
*not wireless. both followers and leaders are connected to kibub machine*

Ensure leaders and followers are connected to kibub machine and enumerated as /dev/leader_right /dev/leader_left /dev/follower_right /dev/follower_left. If necessary, you may have to calibrate the arms. 

If you already calibrated them before, you can skip this step since the files are saved in the calibration folder and don't go away after reboot.

```
lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/leader_left --teleop.id=leader_left
lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/leader_right --teleop.id=leader_right
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/follower_left --robot.id=follower_left
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/follower_right --robot.id=follower_right
```

## Dual arm teleoperation (no cameras)
kibub shell: 
```
conda activate lerobot
cd /home/kibub/so101_dual_arms/

python teleop_dual.py --mode dual
```

## Record a dataset with cameras 
*Pushes dataset to huggingface*
kibub shell:
```
conda activate lerobot
cd /home/kibub/so101_dual_arms/
REPO="short_and_sweet_repo_name"
TASK="Something describing a simple task"
EPISODE_TIME_S=10
RESET_TIME_S=4
EPISODES=50
HF_USER=oliveoil8888 
CAMERAS="top_realsense_color top_realsense_depth wrist_right wrist_left top_webcam" 
#total five cameras that you can include/exclude

python3 record_dual_with_cameras.py --repo-id ${HF_USER}/${REPO} --task “${TASK}” --episode-time-s ${EPISODE_TIME_S} --reset-time-s ${RESET_TIME_S} --episodes ${EPISODES} --camera ${CAMERAS} --push
```

## Train a model and save checkpoints locally:
*Retrieves the dataset from huggingface, saves model locally*
cow shell:
```
conda activate lerobot
cd /home/${COW_USER}$/lerobot
REPO="short_and_sweet_repo_name"
TASK="Something describing a simple task"
POLICY="groot"
HF_USER=oliveoil8888
STEPS=5000
BATCH_SIZE=5

lerobot-train --dataset.repo_id=${HF_USER}/${REPO} --policy.type=${POLICY} --policy.base_model_path=nvidia/GR00T-N1.5-3B --policy.push_to_hub=false --output_dir=outputs/train/${POLICY}-${REPO} --job_name=job-${REPO} --policy.device=cuda --wandb.enable=false --steps=${STEPS} --batch_size=${BATCH_SIZE} --save_checkpoint=true
```

## Push your trained model to huggingface:
*Pushes last saved checkpoint onto huggingface*
cow shell
```
conda activate lerobot
cd /home/${COW_USER}$/lerobot
REPO="short_and_sweet_repo_name"
TASK="Something describing a simple task"
POLICY="groot"
HF_USER=oliveoil8888

hf upload   ${HF_USER}/${POLICY}-${REPO} outputs/train/${POLICY}-${REPO}/checkpoints/last/pretrained_model   .   --repo-type model
```

## Inference
*Cow GPU for policy inference, kibub streams data*
cow shell:

```
conda activate lerobot
python -m lerobot.async_inference.policy_server   --host=0.0.0.0   --port=8080   --fps=30
```

kibub shell: 
TODO: add the wristr cameras and make sure the inference works with both wrist cameras!!!!
```
conda activate lerobot
python -m lerobot.async_inference.robot_client   --robot.type=bi_so_follower  --robot.left_arm_config.port=/dev/follower_left    --robot.right_arm_config.port=/dev/follower_right    --robot.top_cameras="{ top_color: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}, top_depth: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}}"   --task=${TASK}   --server_address=10.145.8.86:8080   --policy_type=${POLICY}   --pretrained_name_or_path=${HF_USER}/${POLICY}-${REPO}   --policy_device=cuda   --actions_per_chunk=16 --debug_visualize_queue_size=true --robot.id=follower
```

## Modifying the lerobot code

Since the lerobot fork is installed as editable on both kibub and cow, you can simply branch from main in /lerobot on either machine, make your changes, and push to your branch.
Then, on kibub or cow, you can just pull and the changes will be reflected.

Troubleshooting: run `pip show lerobot` to ensure your lerobot fork repo is editable.