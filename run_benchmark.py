import subprocess
import threading
import psutil
import time

import os
import argparse
from pathlib import Path
from scipy.io import savemat
import natsort

from roicat_benchmark.algos.CaImAn.caiman_runner import benchmark_caiman
from roicat_benchmark.utils.sample_param_maker import cellreg_param_maker

## TODO: Better IO path handling
## TODO: Especially for CellReg, think about how to pass pattern_to_search
def main():
    ## TODO: This would be where we let hyperparameter optimizers to choose the best parameters
    ## For now, we just load the default parameters
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
        args.output_dir = current_dir / "demo_output"
    else:
        args.output_dir = Path(args.output_dir)

    print(f"Running {args.algo}", flush=True)
    print(f"Data directory: {args.data_dir}", flush=True)
    print(f"Output directory: {args.output_dir}", flush=True)
    print(f"Plot results: {args.plot_results}", flush=True)

    if args.pattern_to_search is None:
        args.pattern_to_search = ["*"]
    
    if args.algo == "CellReg":
        cellreg_output_dir = args.output_dir / "CellReg_output"
        cellreg_output_dir.mkdir(parents=True, exist_ok=True)
        cellreg_patterns = list(map(lambda x: x + ".mat", args.pattern_to_search))
        print(f"For CellReg, searching for {cellreg_patterns}", flush=True)

        args.output_dir.mkdir(parents=True, exist_ok=True)
        params = cellreg_param_maker(
            data_dir=args.data_dir,
            output_dir=cellreg_output_dir,
            pattern_to_search=cellreg_patterns)

        ## TODO: Seems like CellReg only uses centroid models for 2p data. Check this in GUI.
        params["plot_results"] = args.plot_results
        params["microns_per_pixel"] = 1.2
        params["transformation_smoothness"] = 2.0
        params["p_same_certainty_threshold"] = 0.95
        params["p_same_threshold"] = 0.5
        params["sufficient_correlation_centroids"] = 0.2
        params["sufficient_correlation_footprints"] = 0.3
        params["registration_approach"] = "Simple threshold"

        print(params, flush=True)

        param_path = args.output_dir / "cellreg_params.mat"
        savemat(param_path, params)
        print(f"Saved {param_path}", flush=True)

        # result = subprocess.run(["bash", f"{current_dir}/bin/cellreg_slurm_local.sh", str(param_path)],
        #                         capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)

        ## To check whether the script is alive or not, online.
        print("Initialize subprocess...", flush=True)
        script_path = f"{current_dir}/bin/cellreg_slurm_local.sh"
        alive_process = subprocess.Popen(
            ["bash", script_path, str(param_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        def process_readout(pipe, prefix):
            for line in iter(pipe.readline, ""):
                print(f"{prefix}: {line.strip()}", flush=True)
            pipe.close()

        ## Threads for readout
        stdout_thread = threading.Thread(
            target=process_readout,
            args=(alive_process.stdout, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=process_readout,
            args=(alive_process.stderr, "stderr"),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        ## Wait for process to start
        time.sleep(10)

        try:
            bash_alive = psutil.Process(alive_process.pid)
            process_children = bash_alive.children(recursive=True)
            matlab_alive = next((child for child in process_children if 'matlab' in child.name().lower()), None)

            if matlab_alive:
                print(f"Matlab process found with PID {matlab_alive.pid}", flush=True)
                while alive_process.poll() is None:
                    try:
                        mem_usage = matlab_alive.memory_info().rss / 1024 / 1024
                        cpu_usage = matlab_alive.cpu_percent(interval=1.0)
                        print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                        print(f"Current memory usage: {mem_usage:.2f} MB ({mem_usage/1024:.2f} GB)", flush=True)
                        print(f"CPU usage: {cpu_usage:.2f}%", flush=True)
                    except psutil.NoSuchProcess:
                        print("Matlab process terminated", flush=True)
                        break
                    time.sleep(600) ## Check every 10 mins
            else:
                print("Matlab process not found. Try shell process...", flush=True)
                while alive_process.poll() is None:
                    try:
                        mem_usage = bash_alive.memory_info().rss / 1024 / 1024
                        cpu_usage = bash_alive.cpu_percent(interval=1.0)
                        print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                        print(f"Current memory usage: {mem_usage:.2f} MB ({mem_usage/1024:.2f} GB)", flush=True)
                        print(f"CPU usage: {cpu_usage:.2f}%", flush=True)
                    except psutil.NoSuchProcess:
                        print("Shell process terminated", flush=True)
                        break
                    time.sleep(600) ## Check every 10 mins
        except psutil.NoSuchProcess:
            print("Process terminated", flush=True)

        ## Wait for the process to finish
        return_code = alive_process.wait()
        print(f"Process terminated with return code {return_code}", flush=True)

        stdout_thread.join()
        stderr_thread.join()

        print("Monitoring terminated", flush=True)
        
    elif args.algo == "CaImAn":
        caiman_output_dir = args.output_dir / "CaImAn_output"
        caiman_output_dir.mkdir(parents=True, exist_ok=True)

        caiman_patterns = list(map(lambda x: x + ".richfile", args.pattern_to_search))
        print(f"For CaImAn, searching for {caiman_patterns}", flush=True)
        params = {}
        params["data_dir"] = str(args.data_dir)
        if args.data_dir.suffix == ".richfile":
            ## Input args.data_dir is a richfile
            params["data_path"] = args.data_dir
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
                params["data_path"] = richfiles[0]

        params["output_dir"] = str(caiman_output_dir)
        params["plot_results"] = args.plot_results
        params["max_thr"] = 0
        params["thresh_cost"] = 0.7
        params["max_dist"] = 10

        def background_monitoring(interval=600, stop_event=None):
            alive_python = psutil.Process(os.getpid())
            while not stop_event.is_set():
                try:
                    mem_usage = alive_python.memory_info().rss / 1024 / 1024
                    cpu_usage = alive_python.cpu_percent(interval=1.0)
                    print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                    print(f"Current memory usage: {mem_usage:.2f} MB ({mem_usage/1024:.2f} GB)", flush=True)
                    print(f"CPU usage: {cpu_usage:.2f}%", flush=True)
                except psutil.NoSuchProcess:
                    print("Python process terminated", flush=True)
                    break
                time.sleep(interval)

        print("Start monitoring...", flush=True)
        stop_event = threading.Event()
        monitor_thread = threading.Thread(
            target=background_monitoring,
            args=(600, stop_event),
            daemon=True,
        )
        monitor_thread.start()

        print(f"CaImAn started at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        try:
            benchmark_caiman(params)
        except Exception as e:
            print(f"CaImAn failed: {e}", flush=True)
        finally:
            stop_event.set()
            monitor_thread.join()
            print("Monitoring terminated", flush=True)

        print(f"CaImAn done at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    else:
        raise ValueError(f"Algorithm {args.algo} not supported")

if __name__ == "__main__":
    main()