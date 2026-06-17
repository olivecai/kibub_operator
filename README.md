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
6. For good measure, since these things don't quite like to work very well: `cd /home/${USER}/lerobot/ ; pip install lerobot[groot]`
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
cd /home/kibub/kibub_operator/so101_dual_arms/

python teleop_dual.py --mode dual
```

## Record a dataset with cameras 
*Pushes dataset to huggingface*
kibub shell:
```
hf auth login
HF_USER=oliveoil8888
conda activate lerobot
cd /home/kibub/kibub_operator/so101_dual_arms/
REPO="pick-cup-left-recoveries"
TASK="Pick up the cup by the cup handle using the left arm"
EPISODE_TIME_S=15
RESET_TIME_S=5
EPISODES=30
HF_USER=oliveoil8888 
CAMERAS="top_realsense_color top_realsense_depth wrist_right wrist_left top_webcam" 
#total five cameras that you can include/exclude

python3 record_dual_with_cameras.py --repo-id ${HF_USER}/${REPO} --task "${TASK}" --episode-time-s ${EPISODE_TIME_S} --reset-time-s ${RESET_TIME_S} --episodes ${EPISODES} --camera ${CAMERAS} --push

##############################

hf auth login
HF_USER=oliveoil8888
conda activate lerobot
cd /home/kibub/kibub_operator/so101_dual_arms/
REPO="stack-cup"
TASK="Place the cup onto the stack of cups"
EPISODE_TIME_S=30
RESET_TIME_S=8
EPISODES=30
HF_USER=oliveoil8888 
CAMERAS="top_realsense_color top_realsense_depth wrist_right wrist_left top_webcam" 
#total five cameras that you can include/exclude

python3 record_dual_with_cameras.py --repo-id ${HF_USER}/${REPO} --task "${TASK}" --episode-time-s ${EPISODE_TIME_S} --reset-time-s ${RESET_TIME_S} --episodes ${EPISODES} --camera ${CAMERAS} --push


################################


hf auth login
HF_USER=oliveoil8888
conda activate lerobot
cd /home/kibub/kibub_operator/so101_dual_arms/
REPO="put-screw-into-box-1"
TASK="Holding the box steady, pick up the screw and place it into the box"
EPISODE_TIME_S=20
RESET_TIME_S=2
EPISODES=50
HF_USER=oliveoil8888 
CAMERAS="top_realsense_color top_realsense_depth wrist_right wrist_left top_webcam" 
#total five cameras that you can include/exclude

python3 record_dual_with_cameras.py --repo-id ${HF_USER}/${REPO} --task "${TASK}" --episode-time-s ${EPISODE_TIME_S} --reset-time-s ${RESET_TIME_S} --episodes ${EPISODES} --camera ${CAMERAS} --push

```

#### Dataset tools: modifying, deleting, adding, removing, etc:

Check out this link for the huggingface documentation: https://huggingface.co/docs/lerobot/en/using_dataset_tools 

Quick commands for convenience:

Delete certain episodes and save new dataset at indices:
```
lerobot-edit-dataset \
    --repo_id oliveoil8888/put-screw-into-box-1 \
    --new_repo_id oliveoil8888/put-screw-into-box-2 \
    --operation.type delete_episodes \
    --operation.episode_indices "[29,30,33, 45]"

    lerobot-edit-dataset \
    --repo_id oliveoil8888/pick-cup-left-recoveries \
    --new_repo_id oliveoil8888/pick-up-cup-left-recoveries \
    --operation.type delete_episodes \
    --operation.episode_indices "[17]"

lerobot-edit-dataset \
    --repo_id lerobot/${REPO} \
    --new_repo_id lerobot/${REPO}_doctored \
    --operation.type delete_episodes \
    --operation.episode_indices "[0, 2, 5]"
```

After editing your dataset, you can push it to huggingface in a python interpreter with:
```
from huggingface_hub import HfApi

api = HfApi()

LOCAL = "/home/kibub/.cache/huggingface/lerobot/oliveoil8888/put-screw-into-box-2" # locally stored path
REPO  = "oliveoil8888/pick-and-place-screw" # repo-id to push to the hub

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
*Download the dataset from huggingface, then trains and saves model locally*
cow shell:
```
COW_USER=$(whoami)
conda activate lerobot
cd /home/${COW_USER}/lerobot
REPO="pick-and-place-screw"
TASK="Put the screw into the box"
POLICY="groot"
HF_USER=oliveoil8888
STEPS=10000
BATCH_SIZE=4

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True #this is to avoid the cuda out of memory error

#download the dataset from huggingface
hf download ${HF_USER}/${REPO}   --repo-type dataset   --local-dir /home/${COW_USER}/.cache/huggingface/lerobot/${HF_USER}/${REPO}

#train the model
lerobot-train --dataset.repo_id=${HF_USER}/${REPO} --policy.type=${POLICY} --policy.base_model_path=nvidia/GR00T-N1.5-3B --policy.push_to_hub=false --output_dir=outputs/train/${POLICY}-${REPO} --job_name=job-${REPO} --policy.device=cuda --wandb.enable=false --steps=${STEPS} --batch_size=${BATCH_SIZE} --save_checkpoint=true
```

## Finetune your pretrained model:

same command as training, but add --pretrained_path=pretrained_model

cow shell:

```
conda activate lerobot
cd /home/${COW_USER}$/lerobot
REPO="repo_name_finetuned"
TASK="Task description"
POLICY="groot"
HF_USER=oliveoil8888
STEPS=10000 # usually will be much fewer steps
BATCH_SIZE=4

lerobot-train \
  --dataset.repo_id=${HF_USER}/${REPO} \
  --dataset.root=/home/${USER}/.cache/huggingface/lerobot/${HF_USER}/${REPO} \
  --policy.type=${POLICY} \
  --policy.base_model_path=nvidia/GR00T-N1.5-3B \
  --policy.pretrained_path=oliveoil8888/groot-pick-up-cup-left-arm-recoveries \
  --policy.push_to_hub=false \
  --output_dir=outputs/train/${POLICY}-${REPO} \
  --job_name=job-${REPO} \
  --policy.device=cuda \
  --wandb.enable=true \
  --steps=50000 \
  --batch_size=4 \
  --save_checkpoint=true
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

# should see 'Start hashing 7 files' ...
```

## Inference
*Cow GPU for policy inference, kibub streams data*
cow shell:

```
conda activate lerobot
python -m lerobot.async_inference.policy_server   --host=0.0.0.0   --port=8080   --fps=30
```

kibub shell: 
```
REPO=pick-and-place-screw
TASK="Holding the box steady, pick up the screw from the table and place it into the box"

POLICY=groot
HF_USER=oliveoil8888
conda activate lerobot

python -m lerobot.async_inference.robot_client     --robot.type=bi_so_follower      --robot.left_arm_config.port=/dev/follower_left      --robot.right_arm_config.port=/dev/follower_right      --task="${TASK}"      --server_address=10.145.8.86:8080      --policy_type=${POLICY}       --pretrained_name_or_path=${HF_USER}/${POLICY}-${REPO}  --policy_device=cuda       --actions_per_chunk=16     --debug_visualize_queue_size=true     --robot.id=follower     --robot.top_cameras="{ top_realsense_color: {type: opencv, index_or_path: /dev/top_realsense_color, width: 640, height: 480, fps: 30}, top_realsense_depth: {type: opencv, index_or_path: /dev/top_realsense_depth, width: 640, height: 480, fps: 30}, top_webcam: {type: opencv, index_or_path: /dev/top_webcam, width: 640, height: 480, fps: 30}}"      --robot.right_arm_config.cameras="{ wrist: {type: opencv, index_or_path: /dev/wrist_right, width: 640, height: 480, fps: 30}}"     --robot.left_arm_config.cameras="{ wrist:  {type: opencv, index_or_path: /dev/wrist_left,  width: 640, height: 480, fps: 30}}"


```


## Modifying the lerobot code

Since the lerobot fork is installed as editable on both kibub and cow, you can simply branch from main in /lerobot on either machine, make your changes, and push to your branch.
Then, on kibub or cow, you can just pull and the changes will be reflected.

Troubleshooting: run `pip show lerobot` to ensure your lerobot fork repo is editable.