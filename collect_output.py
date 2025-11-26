import argparse
from pathlib import Path
from roicat_benchmark.utils.utils import write_failed_indices, last_line_load_params
import json
import richfile as rf

def main():
    ## Real data collection
    ## TODO: Test for multiple subcollections
    ## TODO: Collection bin has multiple same array indices (stupid case with overwrite). Reject them or take the latest one
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-dir", dest="collection_dir", type=str, required=False, default=None)
    args = parser.parse_args()

    current_dir = Path(__file__).parent
    if args.collection_dir is None:
        args.collection_dir = Path.cwd()
    else:
        args.collection_dir = Path(args.collection_dir)

    ## Allow to check for subcollections
    pattern_to_search = "*_sweep_log.json"
    list_subcollections = list(args.collection_dir.parent.rglob(pattern_to_search))
    print(f"Found {len(list_subcollections)} subcollections", flush=True)
    for subcollection in list_subcollections:
        merge_sweep(subcollection)        

def merge_sweep(log_path):
    ## TODO Gather data into big richfile. What's needed?
    ## TODO Any canonical process can be appended here (e.g. performance scoring...)
    output_string = f"{log_path.parent.stem}_*.richfile"
    collection_bin_path = log_path.parent / "collection_bin"
    list_result_files = list(collection_bin_path.rglob(output_string))
    print(f"Searching for {output_string} in {collection_bin_path}", flush=True)
    print(f"Found {len(list_result_files)} result files", flush=True)

    ## Get json information
    last_line, line_count = last_line_load_params(log_path, return_length=True, verbose=True)
    # last_line, line_count = last_line_load_params(log_path, return_length=True)
    print(f"Last JSON line: {last_line}", flush=True)
    print(f"Line count: {line_count}", flush=True)
    if "failed_id" in last_line:
        line_count -= 1

    ## TODO ...then, check for the failed job indices
    jobs_done = [result.stem.split("_")[-1] for result in list_result_files]
    successful_jobs = set(jobs_done)
    failed_jobs = [str(ii) for ii in range(line_count) if str(ii) not in successful_jobs]

    array_command = ",".join(failed_jobs)
    print(f"Failed jobs index: {array_command}", flush=True)
    write_failed_indices(log_path, array_command, last_line=last_line)


if __name__ == "__main__":
    main()