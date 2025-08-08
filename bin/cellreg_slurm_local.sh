#!/bin/bash

module load matlab/2023b
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
CELLREG_DIR="$REPO_DIR/roicat_benchmark/algos/CellReg"
matlab -nodesktop -batch "addpath(genpath('$CELLREG_DIR')); cellreg_cmd('$1')"
