import argparse
from pathlib import Path
from roicat_benchmark.utils.utils import write_failed_indices, last_line_load_params, nested_glob
import json
import richfile as rf

def main():
    ## Real data collection
    ## TODO: Test for multiple subcollections
    ## TODO: Collection bin has multiple same array indices (stupid case with overwrite). Reject them or take the latest one
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-dir", dest="collection_dir", type=str, required=False, default=None)
    parser.add_argument("--max-depth", dest="max_depth", type=int, required=False, default=-1)
    parser.add_argument("--verbose", dest="verbose", action="store_true", required=False, default=False)
    args = parser.parse_args()

    current_dir = Path(__file__).parent
    if args.collection_dir is None:
        args.collection_dir = Path.cwd()
    else:
        args.collection_dir = Path(args.collection_dir)

    ## Allow to check for subcollections
    pattern_to_search = "*_sweep_log.json"
    list_subcollections = nested_glob(path=args.collection_dir, pattern=pattern_to_search, max_depth=args.max_depth)
    if len(list_subcollections) == 0:
        print(f"No subcollections found in {args.collection_dir}, searching in parent directory", flush=True)
        list_subcollections = nested_glob(path=args.collection_dir.parent, pattern=pattern_to_search, max_depth=args.max_depth)
    print(f"Found {len(list_subcollections)} subcollections", flush=True)
    for subcollection in list_subcollections:
        merge_sweep(subcollection, verbose=args.verbose)        

def merge_sweep(log_path, verbose=False):
    ## TODO Gather data into big richfile. What's needed?
    ## TODO Any canonical process can be appended here (e.g. performance scoring...)
    output_string = f"{log_path.parent.stem}_*.richfile"
    collection_bin_path = log_path.parent / "collection_bin"
    list_result_files = list(collection_bin_path.rglob(output_string))
    print(f"Searching for {output_string} in {collection_bin_path}", flush=True)
    if verbose:
        print(f"Found {len(list_result_files)} result files", flush=True)

    ## Get json information
    last_line, line_count = last_line_load_params(log_path, return_length=True, verbose=verbose)
    # last_line, line_count = last_line_load_params(log_path, return_length=True)
    if verbose:
        print(f"Last JSON line: {last_line}", flush=True)
        print(f"Line count: {line_count}", flush=True)
    if "failed_id" in last_line:
        line_count -= 1

    ## TODO ...then, check for the failed job indices
    jobs_done = [result.stem.split("_")[-1] for result in list_result_files]
    successful_jobs = set(jobs_done)
    new_failed_jobs = [str(ii) for ii in range(line_count) if str(ii) not in successful_jobs]
    array_command = ",".join(new_failed_jobs)

    old_failed_jobs = last_line.get("failed_id", None)
    if (old_failed_jobs is None) or (old_failed_jobs != array_command):
        print(f"Old failed jobs: {old_failed_jobs}", flush=True)
        print(f"Updated failed jobs index: {array_command}", flush=True)
        write_failed_indices(log_path, array_command, last_line=last_line)
    else:
        print(f"No new failed jobs found, failed jobs index: {array_command}", flush=True)

def collect_data(list_subcollections):
    pass


if __name__ == "__main__":
    main()