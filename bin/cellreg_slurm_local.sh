#!/bin/bash

module load matlab/2023b
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
CELLREG_DIR="$SCRIPT_DIR/roicat_benchmark/algos/CellReg"
matlab -nodesktop -batch "addpath(genpath('$CELLREG_DIR')); cellreg_cmd('$1','$2', $3, $4, $5, $6, $7, $8, '$9')"
