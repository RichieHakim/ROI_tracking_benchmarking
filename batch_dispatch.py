import argparse
from pathlib import Path
import roicat_benchmark
import sys
from roicat_benchmark.utils.utils import split_common_different_paths, create_sweep_grid, create_sweep_log
import subprocess
import shutil

def main():
    ## TODO: Maybe handle relevant paths...currently, all absolute paths assumed...
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", type=str, required=True, choices=["CellReg", "CaImAn"])
    parser.add_argument("--data-dir", dest="data_dir", type=str, required=False, default=None)
    parser.add_argument("--output-dir", dest="output_dir", type=str, required=False, default=None)
    parser.add_argument("--pattern-to-search", dest="pattern_to_search", action="append", required=False, default=None)
    parser.add_argument("--params-path", dest="params_path", type=str, required=False, default=None)
    parser.add_argument("--plot-results", dest="plot_results", action="store_true", default=False)
    parser.add_argument("--partition", type=str, required=False, default=None)
    parser.add_argument("--memory", type=str, required=False, default=None)
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", default=False)
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

    if args.pattern_to_search is None:
        args.pattern_to_search = ["data_roicat", "data_roicat_prealigned", "data_roicat_partial", "data_roicat_test"]

    if args.params_path is None:
        args.params_path = current_dir / "bin" / "default_params.json"
    else:
        args.params_path = Path(args.params_path)

    ## List target data
    ## NOTE For the sake of consistency, we assume *.mat file lives in the same directory as the *.richfile file
    algo_data_suffix = ".richfile"
    patterns_to_search = list(map(lambda x: x.split(".")[0] + algo_data_suffix, args.pattern_to_search))
    print(f"Searching for {patterns_to_search}", flush=True)
    sweep_data = []
    if args.data_dir.suffix == algo_data_suffix:
        ## Input args.data_dir is already a single file
        sweep_data.append(args.data_dir)
    else:
        ## Input args.data_dir is a directory.
        ## Search for each patterns
        for pattern in patterns_to_search:
            sweep_data.extend(list(args.data_dir.rglob(pattern)))
        if len(sweep_data) == 0:
            raise ValueError(f"No {algo_data_suffix} files found in {args.data_dir}")
        else:
            print(f"Found {sweep_data}", flush=True)

    ## How many sweeps are there?
    ## It is a preset of the hyperparameter grid, will be applied to each dataset.
    sweep_grid = create_sweep_grid(args.params_path, args.algo)
    num_sweeps = len(sweep_grid)
    print(f"Number of Hyperparameter sweeps: {num_sweeps}", flush=True)

    ## Now submit jobs
    algo_shell_script = current_dir / "bin" / f"slurm_{args.algo}.sh"
    # algo_shell_script = "/n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/output_test.sh"
    output_name = f"{args.algo}_output*.richfile"

    ## shared_path + part_files = original sweep_data path
    ## part_dirs = part_files.parent
    shared_path, part_dirs, part_files = split_common_different_paths(sweep_data)
    for sweep_data_path, part_dir, part_file in zip(sweep_data, part_dirs, part_files):
        ## Make the output directory
        this_output_dir = args.output_dir / part_dir
        this_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {this_output_dir}", flush=True)

        ## Per each dataset, copy the master hyperparameter file
        sweep_params_path = this_output_dir / args.params_path.name
        if not sweep_params_path.exists():
            print(f"Copying params file to {sweep_params_path}", flush=True)
            shutil.copy(args.params_path, sweep_params_path)
        else:
            print(f"Overwriting params file at {sweep_params_path}", flush=True)
            shutil.copy(args.params_path, sweep_params_path)

        ## Flag for overwriting previous runs
        algo_output_dir = this_output_dir / f"{args.algo}_output"
        algo_output_dir.mkdir(parents=True, exist_ok=True)

        ## NOTE Legacy: single job overwrite.
        # expected_output_name = f"{args.algo}_output_*.richfile"
        # algo_outputs = list(algo_output_dir.rglob(expected_output_name))
        # print(f"Searching for expected output files: {expected_output_name} in {algo_output_dir}", flush=True)
        # print(f"Checking if output files exist: {algo_outputs}", flush=True)
        # if len(algo_outputs) != 0:
        #     if not args.overwrite:
        #         print(f"Skip this job...", flush=True)
        #         print(f"If you want to overwrite, use --overwrite", flush=True)
        #         continue
        #     else:
        #         print(f"Rerunning or overwriting {algo_outputs}", flush=True)

        ## Create sweep log
        ## This is to assign hyperparameter grid to each dataset.
        sweep_log_path = algo_output_dir / f"{args.algo}_sweep_log.json"
        sweep_ids_to_run = create_sweep_log(sweep_grid, sweep_log_path)

        ## Maybe just disable overwrite flag...? Any reason to keep it?
        if args.overwrite:
            sweep_ids_to_run = f"{0-{num_sweeps-1}}"

        ## Get the pattern to search
        if args.algo == "CaImAn":
            this_pattern_to_search = sweep_data_path.name
        elif args.algo == "CellReg":
            this_stem = sweep_data_path.stem
            this_pattern_to_search = this_stem + "_[0-9]*.mat"

        ## Gather slurm output
        slurm_output_dir = algo_output_dir / "slurm_bin"
        ## Prepare job command
        submit_command = [
            "sbatch",
            "--array",
            # f"0-{num_sweeps-1}",
            sweep_ids_to_run,
            "--output",
            f"{str(slurm_output_dir)}/runner_%A_%a.out",
            "--error",
            f"{str(slurm_output_dir)}/runner_%A_%a.err",            
        ]
        if args.partition is not None:
            submit_command.extend(["-p", args.partition])
        if args.memory is not None:
            submit_command.extend([f"--mem={args.memory}"])

        param_command = [
            # "bash",
            str(algo_shell_script),
            # "--data-dir",
            str(sweep_data_path.parent),
            # "--output-dir",
            str(algo_output_dir),
            # "--plot-results",
            str(args.plot_results),
            # "--pattern-to-search",
            str(this_pattern_to_search),
        ]

        this_job_command = submit_command + param_command
        print(f"Job submission command: {this_job_command}", flush=True)

        # test_job = subprocess.Popen(this_job_command)
        # test_job.wait()

        ## Submit output generator job
        try:
            output_generator_job = subprocess.run(this_job_command)
        except Exception as e:
            print(f"Error submitting output generator job: {e}", flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()