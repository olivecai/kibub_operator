# README for Server and kibub operator

Instructions on **teleop**, **recording**, **training**, **deploying** models using lerobot and Gr00t. 

This repository should be cloned on the **Server** at `/home/user/agent-kibub/kibub_operator` and on the **Client** at `/home/kibub/kibub_operator`.


# Kibub operator 

## SSH into kibub
To access the kibub shell: `ssh kibub@kibub`

## Kibub operator install and setup from scatch

1. Launch a Kibub SSH session: `ssh kibub@kibub`. 
2. Clone **kibub_operator** (https://github.com/olivecai/kibub_operator). If already cloned, cd into repo and `git pull origin main`
3. Run `conda create -n lerobot -y; conda activate lerobot`
4. Run `cd kibub_operator; pip install -r /home/kibub/kibub_operator/client_requirements.txt`
5. Run `pip show lerobot`, you should see 'Editable project location: /home/kibub/lerobot'. If not, something is wrong :-(
6. Log into huggingface: `hf auth login` and set HF_USER in cli. (ie `export HF_USER=oliveoil8888`)

## Kibub operator setup on reboot
Assuming that you have the conda environment and the repositories: run `conda activate lerobot`

# Follower leader dual arm setup with cameras 

Ensure leaders and followers are connected to kibub machine and enumerated as `/dev/leader_right` `/dev/leader_left` `/dev/follower_right` `/dev/follower_left`. If necessary, you may have to calibrate the arms. 

If you already calibrated them before, you can skip this step since the files are saved in the calibration folder and persist after reboot.

```
lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/leader_left --teleop.id=leader_left
lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/leader_right --teleop.id=leader_right
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/follower_left --robot.id=follower_left
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/follower_right --robot.id=follower_right
```

## Dual arm teleoperation (no cameras needed for teleop)

*Teleoperate follower arms using leader arms*

kibub shell: 
```
conda activate lerobot
cd /home/kibub/kibub_operator/so101_dual_arms/

python teleop_dual.py --mode dual
```

## Record a dataset with cameras 

*Pushes dataset to huggingface*

Modify the variables REPO, TASK, EPISODE_TIME_S, RESET_TIME_S, EPISODES, and CAMERAS. Ensure your storage space is sufficient lest your recording fail midway (check /home/kibub/.cache/huggingface/lerobot/)

For CAMERAS, pass a string with the name of each camera you want to include. All available camera names are listed as keys in the dictionary CAMERA_CONFIGS in the file kibub_operator/DEVICES.py.

kibub shell:
```

hf auth login
HF_USER=oliveoil8888
conda activate lerobot
cd /home/kibub/kibub_operator/so101_dual_arms/
REPO="pick-up-cup"
TASK="Pick up the cup by the handle"
EPISODE_TIME_S=20
RESET_TIME_S=5
EPISODES=30
HF_USER=oliveoil8888 
CAMERAS="top_realsense_color overhead_realsense wrist_right wrist_left" 

python3 record_dual_with_cameras.py --repo-id ${HF_USER}/${REPO} --task "${TASK}" --episode-time-s ${EPISODE_TIME_S} --reset-time-s ${RESET_TIME_S} --episodes ${EPISODES} --camera ${CAMERAS} --push
```

The script outputs a link to your online dataset upon completion. you can also visit your Huggingface account page and navigate to 'Datasets'.

#### Dataset tools: modifying, deleting, adding, removing, etc:

*Edits huggingface dataset*

Check out this link for the huggingface documentation: https://huggingface.co/docs/lerobot/en/using_dataset_tools 

Quick commands for convenience:

Delete certain episodes and save new dataset at indices:

kibub shell:
```
lerobot-edit-dataset \
    --repo_id oliveoil8888/pick-up-cup-left-3 \
    --new_repo_id oliveoil8888/pick-up-cup-left-4 \
    --operation.type delete_episodes \
    --operation.episode_indices "[10, 11]"
```

After editing your dataset, you can push it to huggingface via the python script below (simply type `python` or `python3` in your terminal and paste the code below within the python interpreter). Modify the LOCAL and REPO paths:

kibub shell in a Python interpreter:
```
from huggingface_hub import HfApi

api = HfApi()

LOCAL = "/home/kibub/.cache/huggingface/lerobot/oliveoil8888/pick-place-cube-cup-1" # locally stored path
REPO  = "oliveoil8888/pick-place-cube-cup-1" # repo-id to push to the hub

api.create_repo(
    repo_id=REPO,
    repo_type="dataset",
    exist_ok=True,
)


for folder in ["data", "meta", "videos"]:
    print(f"Uploading {folder}...")
    api.upload_folder(
        repo_id=REPO,
        repo_type="dataset",
        folder_path=f"{LOCAL}/{folder}",
        path_in_repo=folder,
    )
    print(f"Done: {folder}")

api.create_tag(REPO, tag="v3.0", repo_type="dataset")

print("All done.")
```

## Train a model and save checkpoints locally:

*Download the dataset from huggingface, then trains and saves checkpoints of the model locally*

For instructions on training on the cluster, read agent-kibub/cluster/README.md at https://github.com/olivecai/agent-kibub/blob/main/cluster/README.md.

For advice on training and parameters, read agent-kibub/

Below is the bash terminal code to train on your local CUDA device:

server shell:
```
SERVER_USER=$(whoami)
conda activate lerobot
REPO=pick-up-cup-left-overhead-4-2-merge
TASK="Pick up the cup by the cup handle"
POLICY="groot"
HF_USER=oliveoil8888
STEPS=50000
BATCH_SIZE=4

cd;

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True #this is to avoid the cuda out of memory error

#download the dataset from huggingface
hf download ${HF_USER}/${REPO}   --repo-type dataset   --local-dir /home/${SERVER_USER}/.cache/huggingface/lerobot/${HF_USER}/${REPO}

#train the model
lerobot-train --dataset.repo_id=${HF_USER}/${REPO} --policy.type=${POLICY} --policy.base_model_path=nvidia/GR00T-N1.5-3B --policy.push_to_hub=false --output_dir=agent-kibub-outputs/train/${POLICY}-${REPO} --job_name=job-${REPO} --policy.device=cuda --wandb.enable=true --steps=${STEPS} --batch_size=${BATCH_SIZE} --save_checkpoint=true
```

## Finetune your pretrained model:

*Download the dataset from huggingface, then trains and saves checkpoints of the model locally, finetuning a pretrained policy*

same command as training, but add `--policy.pretrained_path=<whatever the path to your pretrained_model is>`

Server shell:

```
conda activate lerobot
REPO="repo_name_finetuned"
TASK="Task description"
POLICY="groot"
HF_USER=oliveoil8888
STEPS=10000 # usually will be much fewer steps
BATCH_SIZE=4

cd;

lerobot-train \
  --dataset.repo_id=${HF_USER}/${REPO} \
  --dataset.root=/home/${USER}/.cache/huggingface/lerobot/${HF_USER}/${REPO} \
  --policy.type=${POLICY} \
  --policy.base_model_path=nvidia/GR00T-N1.5-3B \
  --policy.pretrained_path=oliveoil8888/groot-pick-up-cup-left-arm-recoveries \
  --policy.push_to_hub=false \
  --output_dir=agent-kibub-outputs/train/${POLICY}-${REPO} \
  --job_name=job-${REPO} \
  --policy.device=cuda \
  --wandb.enable=true \
  --steps=50000 \
  --batch_size=4 \
  --save_checkpoint=true
```

## Push your trained model to huggingface:

*Pushes last saved checkpoint onto huggingface*

Server shell
```
conda activate lerobot

cd;

REPO="short_and_sweet_repo_name"
TASK="Something describing a simple task"
POLICY="groot"
HF_USER=oliveoil8888

hf upload   ${HF_USER}/${POLICY}-${REPO} agent-kibub-outputs/train/${POLICY}-${REPO}/checkpoints/last/pretrained_model   .   --repo-type model

# should see 'Start hashing 7 files' ...
```

## Inference

*Server GPU for policy inference, kibub streams data*
Server shell:

```
conda activate lerobot
python -m lerobot.async_inference.policy_server   --host=0.0.0.0   --port=8080   --fps=30
```

kibub shell: 
```
REPO=pick-up-cup-right-model
TASK="Pick up the cup"

POLICY=groot
HF_USER=oliveoil8888
conda activate lerobot

## use the top realsense color
python -m lerobot.async_inference.robot_client     --robot.type=bi_so_follower      --robot.left_arm_config.port=/dev/follower_left      --robot.right_arm_config.port=/dev/follower_right      --task="${TASK}"      --server_address=10.145.8.86:8080      --policy_type=${POLICY}       --pretrained_name_or_path=${HF_USER}/${REPO}  --policy_device=cuda       --actions_per_chunk=16     --debug_visualize_queue_size=true     --robot.id=follower     --robot.top_cameras="{ top_realsense_color: {type: opencv, index_or_path: /dev/top_realsense_color, width: 640, height: 480, fps: 30} }"      --robot.right_arm_config.cameras="{ wrist: {type: opencv, index_or_path: /dev/wrist_right, width: 640, height: 480, fps: 30}}"     --robot.left_arm_config.cameras="{ wrist:  {type: opencv, index_or_path: /dev/wrist_left,  width: 640, height: 480, fps: 30}}"

## use the top realsense color and the overhead realsense color
python -m lerobot.async_inference.robot_client     --robot.type=bi_so_follower      --robot.left_arm_config.port=/dev/follower_left      --robot.right_arm_config.port=/dev/follower_right      --task="${TASK}"      --server_address=10.145.8.86:8080      --policy_type=${POLICY}       --pretrained_name_or_path=${HF_USER}/${POLICY}-${REPO}  --policy_device=cuda       --actions_per_chunk=16     --debug_visualize_queue_size=true     --robot.id=follower     --robot.top_cameras="{ top_realsense_color: {type: opencv, index_or_path: /dev/top_realsense_color, width: 640, height: 480, fps: 30}, overhead_realsense: {type: opencv, index_or_path: /dev/overhead_realsense, width: 640, height: 480, fps: 30}}"      --robot.right_arm_config.cameras="{ wrist: {type: opencv, index_or_path: /dev/wrist_right, width: 640, height: 480, fps: 30}}"     --robot.left_arm_config.cameras="{ wrist:  {type: opencv, index_or_path: /dev/wrist_left,  width: 640, height: 480, fps: 30}}"
```


## Modifying the lerobot code

Since the lerobot fork is installed as editable on both kibub and Server, you can simply branch from main in /lerobot on either machine, make your changes, and push to your branch.
Then, on kibub or Server, you can just pull and the changes will be reflected.

Troubleshooting: run `pip show lerobot` to ensure your lerobot fork repo is editable.

## Clearing up space on kibub

Delete the datasets under 'oliveoil8888' (or replace 'oliveoil8888' with your Hugginface usertag): `rm -rf /home/kibub/.cache/huggingface/lerobot/oliveoil8888/*`