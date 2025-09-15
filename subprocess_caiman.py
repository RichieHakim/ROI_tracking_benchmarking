import subprocess
import threading
import time

import os
import sys
import argparse
from pathlib import Path
from scipy.io import savemat as scipy_savemat
import richfile as rf

from roicat_benchmark.algos.CaImAn.caiman_runner import benchmark_caiman
from roicat_benchmark.utils.sample_param_maker import cellreg_param_maker
from roicat_benchmark.utils.utils import process_monitor, popen_reader, output_maker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--param-path", dest="param_path", type=str, required=True, default=None)
    args = parser.parse_args()

    current_dir = Path(__file__).parent

    params = rf.demo.RichFile_data(check=False,path=args.param_path).load()

    start_time = time.time()
    raw_caiman_temp_name = benchmark_caiman(params)
    end_time = time.time()
    print(f"CaImAn run took {end_time - start_time:.2f} seconds", flush=True)

    ## Submit output generator job, if running on non-interactive SLURM job
    output_maker(
        current_dir=current_dir,
        algo="CaImAn",
        result_file=raw_caiman_temp_name,
    )
    return 0
    
if __name__ == "__main__":
    main()