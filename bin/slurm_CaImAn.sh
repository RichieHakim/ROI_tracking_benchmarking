#!/bin/bash
#SBATCH -c 4
#SBATCH -t 0-08:00
#SBATCH --mem=240G
#SBATCH -p short
#SBATCH --job-name=CaImAn

set -e

# Load modules
module load gcc/14.2.0
module load python/3.13.1
module load conda/miniforge3/24.11.3-0

conda activate caiman

if [ -n "$SLURM_JOB_ID" ]; then
    echo "Running on SLURM"
    SCRIPT_PATH=$(scontrol show job "$SLURM_JOB_ID" | awk -F= '/Command=/{print $2}' | head -n1)
    if [[ "$SCRIPT_PATH" != /* ]]; then
        SCRIPT_PATH="$SLURM_SUBMIT_DIR/$SCRIPT_PATH"
    fi
    echo "Script path: $SCRIPT_PATH"
    REPO_DIR=$( cd "$( dirname "$SCRIPT_PATH" )" && cd .. && pwd )
else
    echo "Running locally"
    REPO_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )
fi

echo "Repo directory: $REPO_DIR"
cd $REPO_DIR

DATA_DIR=$1
OUTPUT_DIR=$2

shift 2
PATTERNS=("$@")

echo "Job started at $(date '+%Y-%m-%d %H:%M:%S')"

args=(
    python3 run_benchmark.py
    --algo CaImAn
    --data-dir "$DATA_DIR"
    --output-dir "$OUTPUT_DIR"
)

for pattern in "${PATTERNS[@]}"; do
    args+=(--pattern-to-search "$pattern")
done

args+=(--plot-results)

echo "Running: ${args[@]}"

"${args[@]}"

echo "Job done at $(date '+%Y-%m-%d %H:%M:%S')"

echo "Check for MaxRSS"

sstat -j $SLURM_JOB_ID --format=MaxRSS%30 -n --noconvert