#!/bin/bash --login
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=30G
#SBATCH --job-name=CURL
#SBATCH --time=15:00:00
#SBATCH --partition=gpu_cuda
#SBATCH --gres=gpu:nvidia_a100_80gb_pcie_1g.10gb
#SBATCH --account=a_lead
#SBATCH -o curlt3.out
#SBATCH -e curlt3.error

module load miniconda3
source $EBROOTMINICONDA3/etc/profile.d/conda.sh
conda activate rl
cd /home/s4642506/RL-Visual-Continuous-Control

srun python ./src/train.py --domain_name cartpole --task_name swingup --tag track3
