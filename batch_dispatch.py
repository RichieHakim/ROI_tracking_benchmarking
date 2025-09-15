import argparse
from pathlib import Path
import roicat_benchmark
import sys
from roicat_benchmark.utils.utils import split_common_different_paths
import subprocess

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", type=str, required=True, choices=["CellReg", "CaImAn"])
    parser.add_argument("--data-dir", dest="data_dir", type=str, required=False, default=None)
    parser.add_argument("--output-dir", dest="output_dir", type=str, required=False, default=None)
    parser.add_argument("--pattern-to-search", dest="pattern_to_search", action="append", required=False, default=None)
    parser.add_argument("--num-array", dest="num_array", type=int, required=False, default=1)
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
        args.pattern_to_search = ["data_roicat", "data_roicat_prealigned"]

    ## List target data
    ## For the sake of consistency, we assume *.mat file lives in the same directory as the *.richfile file
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

        algo_outputs = list(this_output_dir.rglob(f"{args.algo}_output"))
        if len(algo_outputs) != 0:
            check_output = []
            for algo_output in algo_outputs:
                check_output.extend(list(algo_output.rglob(output_name)))
            if len(check_output) > 0:
                print(f"We have output file {check_output[0]}.", flush=True)
                if not args.overwrite:
                    print(f"Skip this job...", flush=True)
                    print(f"If you want to overwrite, use --overwrite", flush=True)
                    continue
                else:
                    print(f"Overwriting {check_output[0]}", flush=True)

        ## Get the pattern to search
        if args.algo == "CaImAn":
            this_pattern_to_search = sweep_data_path.name
        elif args.algo == "CellReg":
            this_stem = sweep_data_path.stem
            this_pattern_to_search = this_stem + "_[0-9]*.mat"
        ## Prepare job command
        this_job_command = [
            "sbatch",
            "--array",
            f"1-{args.num_array}",
            "--output",
            f"{str(this_output_dir)}/runner_%A_%a.out",
            "--error",
            f"{str(this_output_dir)}/runner_%A_%a.err",
            # "bash",
            str(algo_shell_script),
            # "--data-dir",
            str(sweep_data_path.parent),
            # "--output-dir",
            str(this_output_dir),
            # "--pattern-to-search",
            str(this_pattern_to_search),
        ]
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