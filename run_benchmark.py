import subprocess
import threading
import multiprocessing
import time

import os
import sys
import argparse

from pathlib import Path
from scipy.io import savemat as scipy_savemat

import json
import richfile as rf

from roicat_benchmark.algos.CaImAn.caiman_runner import benchmark_caiman
from roicat_benchmark.utils.sample_param_maker import cellreg_param_maker
from roicat_benchmark.utils.utils import run_subprocess, process_monitor, popen_reader, output_maker, line_load_params

def main():
    ## TODO: This would be where we let hyperparameter optimizers to choose the best parameters
    ## For now, we just load the default parameters

    ## TODO: For memory and cpu usage...should we just submit additional jobs? Maybe that'd be the best way to go,...
    ## TODO: ...with output handling.

    ## TODO: Add jobid to the output
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", type=str, required=True, choices=["CellReg", "CaImAn"])
    parser.add_argument("--data-dir", dest="data_dir", type=str, required=False, default=None)
    parser.add_argument("--output-dir", dest="output_dir", type=str, required=False, default=None)
    parser.add_argument("--pattern-to-search", dest="pattern_to_search", action="append", required=False, default=None)
    parser.add_argument("--plot-results", dest="plot_results", action="store_true", default=False)
    args = parser.parse_args()

    current_dir = Path(__file__).parent
    if args.data_dir is None:
        args.data_dir = current_dir / "datasets"
    else:
        args.data_dir = Path(args.data_dir)
    if args.output_dir is None:
        args.output_dir = current_dir / "demo_output" / f"{args.algo}_output"
    else:
        args.output_dir = Path(args.output_dir)

    sweep_param_path = args.output_dir / f"{args.algo}_sweep_log.json"

    print(f"Running {args.algo}", flush=True)
    print(f"Data directory: {args.data_dir}", flush=True)
    print(f"Plot results: {args.plot_results}", flush=True)

    if args.pattern_to_search is None:
        args.pattern_to_search = ["*"]
    
    if args.algo == "CellReg":
        ## Default output directory
        ## Check for array job
        if "SLURM_JOB_ID" in os.environ:
            job_id = os.environ["SLURM_JOB_ID"]
            if "SLURM_ARRAY_TASK_ID" in os.environ:
                array_id = os.environ["SLURM_ARRAY_TASK_ID"]
            else:
                array_id = "-1"
        else:
            job_id = "-1"
            array_id = "-1"
        cellreg_output_dir = args.output_dir / f"JobId_{job_id}_{array_id}"
        cellreg_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {cellreg_output_dir}", flush=True)

        ## Search for spatial footprints
        cellreg_patterns = list(map(lambda x: x.split(".")[0] + ".mat", args.pattern_to_search))
        print(f"For CellReg, searching for {cellreg_patterns}", flush=True)

        params = cellreg_param_maker(
            data_dir=args.data_dir,
            output_dir=cellreg_output_dir,
            pattern_to_search=cellreg_patterns)

        ## TODO: Seems like CellReg only uses centroid models for 2p data. Check this in GUI.
        ## Take hyperparameters
        sweep_param_set = line_load_params(sweep_param_path, array_id)
        for key, value in sweep_param_set.items():
            params[key] = value
        params["plot_results"] = args.plot_results

        print(params, flush=True)

        param_path = cellreg_output_dir / "cellreg_params.mat"
        scipy_savemat(param_path, params)
        print(f"Saved {param_path}", flush=True)

        print("Start Manager and subprocess...", flush=True)
        benchmark_manager = multiprocessing.Manager()
        stdout_queue = multiprocessing.Queue()
        stderr_queue = multiprocessing.Queue()
        monitor_result = benchmark_manager.dict({
            "return_code": None,
            "maxrss": None,
            "cpu_time": None,
            "cpu_usage": None,
            "start_time": None,
            "end_time": None,
            "success": False,
            "error": None,
        })

        ## Initialize the subprocess for CellReg
        print("Initialize subprocess...", flush=True)
        script_path = f"{current_dir}/bin/cellreg_slurm_local.sh"
        benchmark_proc = multiprocessing.Process(
            target=run_subprocess,
            args=(script_path, param_path, "matlab", monitor_result, stdout_queue, stderr_queue),
            daemon=True,
        )
        benchmark_proc.start()

        ## Print queues
        while benchmark_proc.is_alive():
            ## Get stdout
            try:
                _, stdout_line = stdout_queue.get(timeout=1)
                print(f"stdout: {stdout_line}", flush=True)
            except multiprocessing.queues.Empty:
                pass
            except Exception as e:
                print(f"Error: {e}", flush=True)
                break
            ## Get stderr
            try:
                _, stderr_line = stderr_queue.get(timeout=1)
                print(f"stderr: {stderr_line}", flush=True)
            except multiprocessing.queues.Empty:
                pass
            except Exception as e:
                print(f"Error: {e}", flush=True)
                break
        else:
            ## Done!
            ## Let's clear queue first
            print("Clearing queues...", flush=True)
            while not stdout_queue.empty():
                _, stdout_line = stdout_queue.get()
                print(f"stdout: {stdout_line}", flush=True)
            while not stderr_queue.empty():
                _, stderr_line = stderr_queue.get()
                print(f"stderr: {stderr_line}", flush=True)

        benchmark_proc.join()
        num_cpus = os.cpu_count()
        monitor_result["num_cpus"] = num_cpus
        monitor_path = cellreg_output_dir / "tracked_resources.richfile"
        rf.demo.RichFile_data(path=str(monitor_path)).save(obj=dict(monitor_result), overwrite=True)
        print(f"Saved {monitor_path}", flush=True)

        ## Submit output generator job, if running on non-interactive SLURM job
        cellreg_output_file = cellreg_output_dir / "cellRegistered.mat"
        output_maker(
            current_dir=current_dir,
            algo="CellReg",
            result_file=str(cellreg_output_file),
        )

        ## output_maker should terminate the job anyway...
        sys.exit(0)
        
    elif args.algo == "CaImAn":
        if "SLURM_JOB_ID" in os.environ:
            job_id = os.environ["SLURM_JOB_ID"]
            if "SLURM_ARRAY_TASK_ID" in os.environ:
                array_id = os.environ["SLURM_ARRAY_TASK_ID"]
            else:
                array_id = "-1"
        else:
            job_id = "-1"
            array_id = "-1"
        caiman_output_dir = args.output_dir / f"JobId_{job_id}_{array_id}"
        caiman_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {caiman_output_dir}", flush=True)

        ## Search for single data file
        ## If args.data_dir is already a file, then just use it
        ## Otherwise, search for the pattern
        caiman_patterns = list(map(lambda x: x.split(".")[0] + ".richfile", args.pattern_to_search))
        print(f"For CaImAn, searching for {caiman_patterns}", flush=True)
        params = {}
        params["data_dir"] = str(args.data_dir)
        if args.data_dir.suffix == ".richfile":
            ## Input args.data_dir is a richfile
            params["data_path"] = str(args.data_dir)
        else:
            ## Input args.data_dir is a directory.
            ## Search for a single richfile.
            richfiles = []
            for pattern in caiman_patterns:
                richfiles.extend(list(args.data_dir.rglob(pattern)))
            if len(richfiles) == 0:
                raise ValueError(f"No richfiles found in {args.data_dir}")
            elif len(richfiles) > 1:
                raise ValueError(f"Multiple richfiles found in {args.data_dir}. Please specify with --pattern-to-search")
            else:
                print(f"Found {richfiles[0]}", flush=True)
                params["data_path"] = str(richfiles[0])
        print(f"Use data path: {params['data_path']}", flush=True)

        params["output_dir"] = str(caiman_output_dir)
        params["plot_results"] = args.plot_results
        ## These tends to be the default values for CaImAn.
        params["max_thr"] = 0
        params["thresh_cost"] = 0.7
        params["max_dist"] = 10

        ## Take hyperparameters
        sweep_param_set = line_load_params(sweep_param_path, array_id)
        for key, value in sweep_param_set.items():
            params[key] = value

        param_path = caiman_output_dir / "caiman_params.richfile"
        print(f"Saved {param_path}", flush=True)
        rf.demo.RichFile_data(path=str(param_path)).save(obj=params, overwrite=True)


        print("Start Manager and subprocess...", flush=True)
        benchmark_manager = multiprocessing.Manager()
        stdout_queue = multiprocessing.Queue()
        stderr_queue = multiprocessing.Queue()
        monitor_result = benchmark_manager.dict({
            "return_code": None,
            "maxrss": None,
            "cpu_time": None,
            "cpu_usage": None,
            "start_time": None,
            "end_time": None,
            "success": False,
            "error": None,
        })

        ## Prepare args
        script_path = f"{current_dir}/bin/caiman_slurm_local.sh"
        benchmark_proc = multiprocessing.Process(
            target=run_subprocess,
            args=(script_path, param_path, "python", monitor_result, stdout_queue, stderr_queue),
            daemon=True,
        )
        benchmark_proc.start()

        ## Print queues
        while benchmark_proc.is_alive():
            ## Get stdout
            try:
                _, stdout_line = stdout_queue.get(timeout=1)
                print(f"stdout: {stdout_line}", flush=True)
            except multiprocessing.queues.Empty:
                pass
            except Exception as e:
                print(f"Error: {e}", flush=True)
                break
            ## Get stderr
            try:
                _, stderr_line = stderr_queue.get(timeout=1)
                print(f"stderr: {stderr_line}", flush=True)
            except multiprocessing.queues.Empty:
                pass
            except Exception as e:
                print(f"Error: {e}", flush=True)
                break
        else:
            ## Done!
            ## Let's clear queue first
            print("Clearing queues...", flush=True)
            while not stdout_queue.empty():
                _, stdout_line = stdout_queue.get()
                print(f"stdout: {stdout_line}", flush=True)
            while not stderr_queue.empty():
                _, stderr_line = stderr_queue.get()
                print(f"stderr: {stderr_line}", flush=True)

        benchmark_proc.join()
        num_cpus = os.cpu_count()
        monitor_result["num_cpus"] = num_cpus
        monitor_path = caiman_output_dir / "tracked_resources.richfile"
        rf.demo.RichFile_data(path=str(monitor_path)).save(obj=dict(monitor_result), overwrite=True)
        print(f"Saved {monitor_path}", flush=True)

        sys.exit(0)

    else:
        raise ValueError(f"Algorithm {args.algo} not supported")

if __name__ == "__main__":
    main()