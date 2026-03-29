#!/bin/bash

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
    if [[ "$SCRIPT_PATH" == "/bin/bash" ]]; then
        SCRIPT_PATH="${BASH_SOURCE[0]}"
    fi
    echo "Script path: $SCRIPT_PATH"
    REPO_DIR=$( cd "$( dirname "$SCRIPT_PATH" )" && cd .. && pwd )
else
    echo "Running locally"
    REPO_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )
fi

echo "Repo directory: $REPO_DIR"
cd $REPO_DIR

PARAM_PATH=$1

echo "Job started at $(date '+%Y-%m-%d %H:%M:%S')"

args=(
    python3 subprocess_caiman.py
    --param-path "$PARAM_PATH"
)

echo "Running: ${args[@]}"

"${args[@]}"