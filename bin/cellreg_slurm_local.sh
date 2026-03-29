#!/bin/bash

set -e

module load matlab/2023b

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
echo "Current directory: $(pwd)"
CELLREG_DIR="$REPO_DIR/roicat_benchmark/algos/CellReg"
echo "CellReg directory: $CELLREG_DIR"
matlab -nodesktop -batch "addpath(genpath('$CELLREG_DIR')); cellreg_cmd('$1')"