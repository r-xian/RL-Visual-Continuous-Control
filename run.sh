#!/bin/bash --login
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=30G
#SBATCH --job-name=CURL
#SBATCH --time=24:00:00
#SBATCH --partition=gpu_cuda
#SBATCH --gres=gpu:a100:1
#SBATCH --account=a_lead
#SBATCH -o curl.out
#SBATCH -e curl.error

module load miniconda3
source $EBROOTMINICONDA3/etc/profile.d/conda.sh
conda activate rl
cd /home/s4642506/RL-Visual-Continuous-Control

srun python ./src/train.py --agent curl
# srun python ./src/test.py --agent sacae
