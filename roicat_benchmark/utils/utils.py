import os
import subprocess
import threading
import psutil
import time

def popen_reader(process: subprocess.Popen):
    """
    Read the output of the process.
    """
    def _popen_readout(pipe, prefix):
        for line in iter(pipe.readline, ""):
            print(f"{prefix}: {line.strip()}", flush=True)
        pipe.close()
    stdout_thread = threading.Thread(
        target=_popen_readout,
        args=(process.stdout, "stdout"),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_popen_readout,
        args=(process.stderr, "stderr"),
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
            raise ValueError("Stop event is required for main process monitoring")
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
        child_alive = next((child for child in process_children if child_name in child.name().lower()), None)

        ## If child is alive, monitor it
        if child_alive:
            print(f"Child {child_name} found alive with PID {child_alive.pid}", flush=True)
            while process_to_monitor.poll() is None:
                if not miniscreen(child_alive):
                    print(f"Child {child_name} terminated", flush=True)
                    break
                ## Check for every interval
                time.sleep(interval)
        ## If child is not alive, fall back to the shell subprocess
        else:
            print(f"Child {child_name} not found alive, rather track the shell subprocess", flush=True)
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
        print(f"Current memory usage: {mem_usage:.2f} MB ({mem_usage/1024:.2f} GB)", flush=True)
        print(f"CPU usage: {cpu_usage:.2f}%", flush=True)
        return True
    except psutil.NoSuchProcess:
        print(f"Process {process.pid} not found", flush=True)
        return False


def check_MaxRSS():
    """
    Legacy function.
    Ended up not using this function. Just call sstat in the parent shell script.
    """
    if 'SLURM_JOB_ID' in os.environ:
        job_id = os.environ['SLURM_JOB_ID']
        print(f"Check MaxRSS for job {job_id}", flush=True)

        try:
            MaxRSS = int(subprocess.check_output(
                ['sstat', '-j', job_id, '--format=MaxRSS%30', '-n', '--noconvert']
            ).decode().strip())
            
            print(f"MaxRSS: {MaxRSS / (1024**2)} MB, {MaxRSS / (1024**3)} GB", flush=True)
        except subprocess.CalledProcessError as e:
            print(f"Error checking MaxRSS: {e}", flush=True)
        except ValueError as e:
            print(f"Formatting issues expected for MaxRSS", flush=True)
            MaxRSS = subprocess.check_output(
                ['sstat', '-j', job_id, '--format=MaxRSS%30', '-n', '--noconvert']
            ).decode().strip()
            print(f"MaxRSS: {MaxRSS}", flush=True)
    else:
        print("Not on SLURM, skipping MaxRSS check", flush=True)