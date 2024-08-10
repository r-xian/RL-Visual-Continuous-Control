#!/bin/bash --login
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=30G
#SBATCH --job-name=CURL_cheetah
#SBATCH --gres=gpu:nvidia_a100_80gb_pcie_1g.10gb
#SBATCH --time=72:00:00
#SBATCH --partition=gpu_cuda
#SBATCH --account=a_lead
#SBATCH -o cheetah_curl.out
#SBATCH -e cheetah_curl.error

module load miniconda3
source $EBROOTMINICONDA3/etc/profile.d/conda.sh
conda activate rl
cd /home/s4642506/RL-Visual-Continuous-Control

srun python ./src/train.py --agent curl --domain_name cheetah --task_name run

# --domain_name finger --task_name spin
# --domain_name reacher --task_name easy
# --domain_name cartpole --task_name swingup
# --domain_name cheetah --task_name run
# --domain_name walker --task_name walk
# --domain_name ball_in_cup --task_name catch


#Finger Spin, Cartpole Swingup, Reacher Easy, Cheetah Run, Walker Walk, and Ball in Cup Catch
