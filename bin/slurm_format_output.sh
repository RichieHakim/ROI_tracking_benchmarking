#!/bin/bash
#SBATCH -c 1
#SBATCH -t 0-01:00
#SBATCH --mem=32G
#SBATCH -p short
#SBATCH --job-name=FormatOutput
set -e

# Load modules
module load gcc/14.2.0
module load python/3.13.1
module load conda/miniforge3/24.11.3-0

conda activate caiman

## Get repo directory
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

## Get arguments
ALGO=$1
PARENT_JOBID=$2
RESULT_FILE=$3

## Make sure parent job is terminated; for 5 mins.
for i in {1..5}; do
    JOB_STATE=$(sacct -j $PARENT_JOBID --format=State --noheader | head -n1 | xargs)
    if [[ "$JOB_STATE" == "COMPLETED" || "$JOB_STATE" == "FAILED" || "$JOB_STATE" == "CANCELLED" || "$JOB_STATE" == "TIMEOUT" ]]; then
        echo "Parent job $PARENT_JOBID is terminated (state: $JOB_STATE)."
        break
    else
        echo "Parent job $PARENT_JOBID is not terminated (state: $JOB_STATE). Sleeping 1 min..."
        sleep 60
    fi
done

## Run format output
args=(
    python3 roicat_benchmark/format_output.py
    --algo "$ALGO"
    --job-id "$PARENT_JOBID"
    --result-file "$RESULT_FILE"
)

echo "Running: ${args[@]}"

"${args[@]}"

echo "Format output done at $(date '+%Y-%m-%d %H:%M:%S')"
