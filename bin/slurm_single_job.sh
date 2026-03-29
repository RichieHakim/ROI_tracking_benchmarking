#!/bin/bash

set -e

if [ -n "$SLURM_JOB_ID" ]; then
    echo "Running on SLURM"
    SCRIPT_PATH=$(scontrol show job "$SLURM_JOB_ID" | awk -F= '/Command=/{print $2}' | head -n1)
    if [[ "$SCRIPT_PATH" == "/bin/bash" ]]; then
        echo "Interactive SLURM session"
        SCRIPT_PATH=${BASH_SOURCE[0]}
    elif [[ "$SCRIPT_PATH" != /* ]]; then
        SCRIPT_PATH="$SLURM_SUBMIT_DIR/$SCRIPT_PATH"
    fi
    echo "Script path: $SCRIPT_PATH"
    REPO_DIR=$( cd "$( dirname "$SCRIPT_PATH" )" && cd .. && pwd )
    echo "Repo directory: $REPO_DIR"
else
    echo "Running locally"
    REPO_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )
    echo "Repo directory: $REPO_DIR"
fi

ALGO=$1
ARRAY_NUM=$2
shift 2

TIMENOW=$(date +%Y%m%d_%H%M%S)

if [ "$ALGO" == "CellReg" ]; then
    echo "Running CellReg"
    STDOUT_PATH="$REPO_DIR/bin/slurm_output/${ALGO}_%A_%a_${TIMENOW}.out"
    STDERR_PATH="$REPO_DIR/bin/slurm_output/${ALGO}_%A_%a_${TIMENOW}.err"

    sbatch --array 1-"$ARRAY_NUM" --output "$STDOUT_PATH" --error "$STDERR_PATH" $REPO_DIR/bin/slurm_CellReg.sh "$@"
elif [ "$ALGO" == "CaImAn" ]; then
    echo "Running CaImAn"
    STDOUT_PATH="$REPO_DIR/bin/slurm_output/${ALGO}_%A_%a_${TIMENOW}.out"
    STDERR_PATH="$REPO_DIR/bin/slurm_output/${ALGO}_%A_%a_${TIMENOW}.err"
    sbatch --array 1-"$ARRAY_NUM" --output "$STDOUT_PATH" --error "$STDERR_PATH" $REPO_DIR/bin/slurm_CaImAn.sh "$@"
else
    echo "Algorithm $ALGO not supported"
    exit 1
fi