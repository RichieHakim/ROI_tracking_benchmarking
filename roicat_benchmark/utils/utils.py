import os
import sys
from pathlib import Path
import json
import itertools
import subprocess
import threading
import multiprocessing
import resource
import psutil
import time

##### Subprocess runner utils #####

def run_subprocess(
    script_path,
    param_path,
    child_name,
    monitor_result,
    stdout_queue=None,
    stderr_queue=None,
):
    try:
        sub_start_time = time.time()
        alive_process = subprocess.Popen(
            ["bash", str(script_path), str(param_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        ## Threads for readout
        stdout_thread, stderr_thread = popen_reader(
            process=alive_process, stdout_queue=stdout_queue, stderr_queue=stderr_queue
        )

        stdout_thread.start()
        stderr_thread.start()

        ## Wait for process to start
        time.sleep(10)

        # ## Start monitoring the process
        # process_monitor(
        #     process_to_monitor=alive_process,
        #     interval=600,
        #     child_name=child_name,
        #     stop_event=None,
        # )

        ## Wait for the process to finish
        return_code = alive_process.wait()
        sub_end_time = time.time()
        print(
            f"Subprocess took {sub_end_time - sub_start_time:.2f} seconds", flush=True
        )
        print(f"Process terminated with return code {return_code}", flush=True)

        stdout_thread.join()
        stderr_thread.join()

        ## MaxRSS check
        rusage = resource.getrusage(resource.RUSAGE_CHILDREN)
        maxrss = rusage.ru_maxrss
        print(
            f"MaxRSS: {maxrss / 1024 / 1024:.2f} MB ({maxrss / 1024 / 1024 / 1024:.2f} GB)",
            flush=True,
        )
        cpu_time = rusage.ru_utime + rusage.ru_stime
        print(f"CPU time: {cpu_time:.2f} seconds", flush=True)
        cpu_usage = cpu_time / (sub_end_time - sub_start_time)
        print(f"CPU usage: {cpu_usage:.2f}%", flush=True)

        ## Log
        monitor_result["maxrss"] = maxrss
        monitor_result["cpu_time"] = cpu_time
        monitor_result["cpu_usage"] = cpu_usage
        monitor_result["start_time"] = sub_start_time
        monitor_result["end_time"] = sub_end_time
        monitor_result["success"] = True
        monitor_result["error"] = None
    except Exception as e:
        monitor_result["error"] = str(e)


def popen_reader(process: subprocess.Popen, stdout_queue: multiprocessing.Queue, stderr_queue: multiprocessing.Queue):
    """
    Read the output of the process.
    """

    def _popen_readout(pipe, queue, prefix):
        for line in iter(pipe.readline, ""):
            output_line = line.strip()
            queue.put((prefix, output_line))
            print(f"{prefix}: {output_line}", flush=True)
        pipe.close()

    stdout_thread = threading.Thread(
        target=_popen_readout,
        args=(process.stdout, stdout_queue, "stdout"),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_popen_readout,
        args=(process.stderr, stderr_queue, "stderr"),
        daemon=True,
    )
    return stdout_thread, stderr_thread


def process_monitor(
    process_to_monitor: subprocess.Popen | None = None,
    interval: int = 600,
    child_name: str | None = None,
    stop_event: threading.Event | None = None,
):
    """
    Monitor the process and its children.
    If the process is a shell subprocess, monitor the shell subprocess.
    If the process is a child subprocess, monitor the child subprocess. Failure falls back to the shell subprocess.
    If the process is main process, monitor the main process.

    Args:
        process_to_monitor: subprocess.Popen, the process to monitor. If None, monitor the main process.
        interval: int, the interval to check the process.
        child_name: str, the name of the child process to monitor. If None, monitor the main process.
        stop_event: threading.Event, the event to stop the monitoring.
    """

    ## Initialize the process overseer
    if process_to_monitor is None:
        if stop_event is None:
            raise ValueError("stop_event is required for main process monitoring")
        process_overseer = psutil.Process(os.getpid())
        print(f"Monitor main process", flush=True)
        main_monitor(process_overseer, stop_event, interval)
    else:
        try:
            process_overseer = psutil.Process(process_to_monitor.pid)
            print(f"Monitor process {process_to_monitor.pid}", flush=True)
            child_monitor(process_to_monitor, process_overseer, child_name, interval)
        except psutil.NoSuchProcess:
            print(f"Process {process_to_monitor.pid} not found", flush=True)
            return


def child_monitor(
    process_to_monitor: subprocess.Popen,
    process_overseer: psutil.Process,
    child_name: str | None = None,
    interval: int = 600,
):
    """
    Monitor the child process.
    """
    ## Gracefully wait a bit for the process to start
    time.sleep(10)

    ## If child_name is provided, monitor the child process
    if child_name is not None:
        process_children = process_overseer.children(recursive=True)
        child_alive = next(
            (child for child in process_children if child_name in child.name().lower()),
            None,
        )

        ## If child is alive, monitor it
        if child_alive:
            print(
                f"Child {child_name} found alive with PID {child_alive.pid}", flush=True
            )
            while process_to_monitor.poll() is None:
                if not miniscreen(child_alive):
                    print(f"Child {child_name} terminated", flush=True)
                    break
                ## Check for every interval
                time.sleep(interval)
        ## If child is not alive, fall back to the shell subprocess
        else:
            print(
                f"Child {child_name} not found alive, rather track the shell subprocess",
                flush=True,
            )
            while process_to_monitor.poll() is None:
                if not miniscreen(process_overseer):
                    print(f"Shell subprocess terminated", flush=True)
                    break
                ## Check for every interval
                time.sleep(interval)
    ## If child name is not provided, again fall back to the shell subprocess
    else:
        print(f"No child name provided, rather track the shell subprocess", flush=True)
        while process_to_monitor.poll() is None:
            if not miniscreen(process_overseer):
                print(f"Shell subprocess terminated", flush=True)
                break
            ## Check for every interval
            time.sleep(interval)


def main_monitor(
    process_overseer: psutil.Process,
    stop_event: threading.Event = None,
    interval: int = 600,
):
    """
    Monitor the main process.
    """
    while not stop_event.is_set():
        if not miniscreen(process_overseer):
            print(f"Process of interest {process_overseer.pid} terminated", flush=True)
            break
        ## Check for every interval
        time.sleep(interval)


def miniscreen(process: psutil.Process):
    """
    Simple memory and cpu usage monitor.
    """
    try:
        mem_usage = process.memory_info().rss / 1024 / 1024
        cpu_usage = process.cpu_percent(interval=1.0)
        print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(
            f"Current memory usage: {mem_usage:.2f} MB ({mem_usage/1024:.2f} GB)",
            flush=True,
        )
        print(f"CPU usage: {cpu_usage:.2f}%", flush=True)
        return True
    except psutil.NoSuchProcess:
        print(f"Process {process.pid} not found", flush=True)
        return False

##### SLURM utils #####
def get_slurm_jobid(placeholder: str = "-1"):
    """
    Get the SLURM job ID and array ID.
    If not on SLURM, return the placeholder for job ID and array ID.
    """
    if "SLURM_JOB_ID" in os.environ:
        job_id = os.getenv("SLURM_ARRAY_JOB_ID", os.getenv("SLURM_JOB_ID"))
        array_id = os.getenv("SLURM_ARRAY_TASK_ID", placeholder)
    else:
        job_id = placeholder
        array_id = placeholder
    return job_id, array_id

##### Benchmark Output utils #####
def output_maker(
    current_dir: str,
    algo: str,
    result_file: str,
):
    """
    Submit sbatch job to format the output, or run the format output script locally.
    """
    job_id, array_id = get_slurm_jobid()

    
    if job_id != "-1":
        full_id = f"{job_id}_{array_id}"
        print(f"Submitting output generator job for {full_id}", flush=True)

        output_dir = Path(result_file).parent

        stdout_path = output_dir / f"format_output_{full_id}.out"
        stderr_path = output_dir / f"format_output_{full_id}.err"

        ## Create command to submit
        cmd_submit = [
            "sbatch",
            "--output",
            str(stdout_path),
            "--error",
            str(stderr_path),
            f"{current_dir}/bin/slurm_format_output.sh",
            # "--algo",
            algo,
            # "--job-id",
            full_id,
            # "--result-file",
            str(result_file),
        ]
        print(f"Command to submit: {cmd_submit}", flush=True)

        ## Submit output generator job
        try:
            output_generator_job = subprocess.run(cmd_submit)
        except Exception as e:
            print(f"Error submitting output generator job: {e}", flush=True)
            sys.exit(1)

        print(f"Terminate current job", flush=True)
        sys.exit(0)
    else:
        print("Not on SLURM. Please run format_output.py locally", flush=True)



##### Path and Dispatch utils #####
def split_common_different_paths(path_list: list[Path]):
    ## Just sanity check; paths should be absolute
    paths = [p.resolve() if not p.is_absolute() else p for p in path_list]
    
    ## Get a string copy for os.path.commonpath
    string_paths = [str(p) for p in paths]
    common_path = Path(os.path.commonpath(string_paths))

    ## Don't use isfile, as RichFile classifies as a directory
    if "." in str(common_path):
        common_path = common_path.parent
    
    ## Now construct the different parts of the paths
    each_paths = [p.relative_to(common_path) for p in paths]
    part_dirs = [ep.parent for ep in each_paths]
    
    return common_path, part_dirs, each_paths

def create_sweep_grid(params_path: Path, algo: str):
    """
    Split the params file into a list of params.
    Assume single depth per algo. Susceptible to nested param sets.
    We strictly constrain overwriting the sweep log file.
    """
    with open(str(params_path), "r") as param_handle:
        sweep_params = json.load(param_handle)
    
    if algo not in sweep_params:
        raise ValueError(f"Parameter set for {algo} not found in params file {params_path}")
    
    algo_sweep_params = sweep_params[algo]
    condition_set = algo_sweep_params.pop("grid_condition")
    keys = [key for key in algo_sweep_params.keys() if key != "grid_condition"] ## just being careful
    values = [algo_sweep_params[key] for key in keys]
    raw_grid = list(dict(zip(keys, sets)) for sets in itertools.product(*values))

    ## Filter the grid based on the "grid_condition"
    if len(condition_set) > 0:
        print(f"Filtering grid based on the following conditions: {condition_set}", flush=True)
        sweep_grid = [param_set for param_set in raw_grid if filter_condition(param_set, condition_set)]
    else:
        print(f"No grid conditions provided, using full grid with {len(raw_grid)} parameter sets", flush=True)
        sweep_grid = raw_grid
    print(f"Final grid with {len(sweep_grid)} parameter sets", flush=True)
    return sweep_grid

def filter_condition(param_set, condition_set):
    """
    Based on "grid_condition" in param_set, filter the param_set.
    """
    local_eval_env = dict(param_set)
    global_eval_env = {"__builtins__": None}

    try:
        for cond in condition_set:
            if not bool(eval(cond, global_eval_env, local_eval_env)):
                return False
        return True
    except Exception as e:
        raise ValueError(f"Error evaluating condition {cond}: {e}")

def create_sweep_log(sweep_grid, log_path):
    if log_path.exists():
        print(f"""Sweep log already exists at {log_path}.
        Overwriting this file is strictly prohibited. Check collection.py file for more details.
        We assume this is a re-run of the same sweep, to complete failed jobs.""", flush=True)
        sweep_ids_to_run = read_failed_indices(log_path)
    else:
        with open(str(log_path), "w") as log_handle:
            for ii, param_set in enumerate(sweep_grid):
                this_line = {
                    "sweep_id": ii,
                    **param_set,
                }
                log_handle.write(json.dumps(this_line) + "\n")
        print(f"Sweep log created at {log_path}", flush=True)
        sweep_ids_to_run = f"0-{len(sweep_grid)-1}"
    return sweep_ids_to_run

##### JSON utils #####
def read_failed_indices(log_path):
    """
    Check the last line of the sweep log to find out the failed job indices.
    """
    last_line = last_line_load_params(log_path)
    if "failed_id" in last_line:
        return last_line["failed_id"]
    else:
        last_id = last_line["sweep_id"]
        return f"0-{last_id}"

def write_failed_indices(log_path, failed_indices:str, last_line: None):
    """
    Write the failed job indices to the last line of the sweep log.
    """
    if last_line is None:
        last_line = last_line_load_params(log_path)
    if "failed_id" in last_line:
        last_line["failed_id"] = failed_indices
    else:
        with open(str(log_path), "a") as log_handle:
            log_handle.write(json.dumps({"failed_id": failed_indices}) + "\n")

def line_load_params(log_path: Path, line_id: int):
    """
    We use index -1 to indicate no array job. For no array job, just use the first parameter set.
    """
    if line_id < 0:
        line_id = 0

    with open(str(log_path), "r") as log_handle:
        for ii, line in enumerate(log_handle):
            if ii == line_id:
                return json.loads(line)

def last_line_load_params(log_path: Path, return_length: bool = False, verbose: bool = False):
    """
    Load the last line of the sweep log.
    """
    line_count = 0
    last_line = None
    with open(str(log_path), "r") as log_handle:
        for line in log_handle:
            line = line.strip()
            if not line:
                continue
            last_line = line
            line_count += 1
            if verbose:
                print(f"Line {line_count}: {line}")
    
    if last_line is None:
        raise ValueError(f"No parameter set found in {log_path}")
    
    try:
        if return_length:
            return json.loads(last_line), line_count
        else:
            return json.loads(last_line)
    except Exception as e:
        raise ValueError(f"Error loading last line of {log_path}: {e}")
