import argparse
from pathlib import Path
import os
import h5py
import numpy as np
import subprocess
import scipy.sparse as sparse
from scipy.io import loadmat as loadmat_scipy

import richfile as rf
import natsort

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", type=str, required=True, choices=["CellReg", "CaImAn"])
    parser.add_argument("--job-id", dest="job_id", type=str, required=False, default=None)
    parser.add_argument("--result-dir", dest="result_dir", type=str, required=False, default=None)
    parser.add_argument("--result-file", dest="result_file", type=str, required=False, default=None)
    args = parser.parse_args()

    print(f"Formatting output for {args.algo}", flush=True)
    if (args.result_dir is None) and (args.result_file is None):
        raise ValueError("Either --result-dir or --result-file must be provided")

    ## Create output preset
    output_preset = {
        "algo": args.algo,
        "job_id": args.job_id,
        "ucids_bySession": None,
        "warped_footprints": None,
        "warp_field": None,
        "resources": None,
    }

    ## Algo-specific loading
    if args.algo == "CellReg":
        if args.result_file is None:
            algo_output = list(Path(args.result_dir).glob("cellRegistered*.mat"))
            if len(algo_output) == 0:
                raise ValueError(f"No cellRegistered*.mat file found in {args.result_dir}")
            elif len(algo_output) > 1:
                raise ValueError(f"Multiple cellRegistered*.mat files found in {args.result_dir}. Specify with --result-file")
            else:
                algo_output = algo_output[0]
        else:
            algo_output = Path(args.result_file)

        ## Load the output
        with h5py.File(algo_output, "r") as handle:
            ## cell_to_index_map shape: (n_clusters, n_sessions)
            cell_to_index_map = handle['cell_registered_struct']['cell_to_index_map'][:].T
            default_ucids_bySession = []
            for session_ref in handle['cell_registered_struct']['centroid_locations_corrected'][0]:
                ## Generate default ucids: ROI-length array of -1
                default_ucids_bySession.append(np.full(handle['cell_registered_struct'][session_ref][:].shape[1], -1))
            disp_xs, disp_ys = handle['cell_registered_struct']['displacement_fields'][:]
            cellreg_warp_field = [np.stack([disp_xs[...,sess_idx], disp_ys[...,sess_idx]], axis=-1) for sess_idx in range(disp_xs.shape[-1])]
            output_preset["warp_field"] = cellreg_warp_field

        ## Load corrected footprints to sparse csc matrix
        corrected_footprints = []
        corrected_footprints_path = natsort.natsorted(list(algo_output.parent.glob("spatial_footprints_corrected_*.mat")))
        for corrected_footprint_path in corrected_footprints_path:
            ## Match CaImAn's format; (flattened_pixels, # of components)
            print(f"Loading corrected footprints from {corrected_footprint_path}", flush=True)
            corrected_footprint = loadmat_scipy(corrected_footprint_path)['footprint']
            n_components = corrected_footprint.shape[1]
            H, W = corrected_footprint[0,0].shape
            each_component = [corrected_footprint[0,ii].reshape(H*W, 1) for ii in range(n_components)]
            reshaped_footprint = sparse.csc_matrix(sparse.hstack(each_component))
            corrected_footprints.append(reshaped_footprint)
        corrected_footprints_path_str = [str(corrected_footprint_path) for corrected_footprint_path in corrected_footprints_path]
        output_preset["warped_footprints"] = corrected_footprints
        output_preset["corrected_footprints_path"] = corrected_footprints_path_str

        ## Assign cluster ids to each rois
        ucids_bySession = generate_ucids_bySession(cell_to_index_map, default_ucids_bySession)
        output_preset["ucids_bySession"] = ucids_bySession
    
    elif args.algo == "CaImAn":
        if args.result_file is None:
            algo_output = list(Path(args.result_dir).glob("caiman_results.richfile"))
            if len(algo_output) == 0:
                raise ValueError(f"No caiman_results.richfile file found in {args.result_dir}")
            else:
                algo_output = algo_output[0]
        else:
            algo_output = Path(args.result_file)

        print(f"Loading output from {algo_output}", flush=True)

        ## Load the output
        caiman_output = rf.demo.RichFile_data(check=False,path=algo_output)
        assignments = np.nan_to_num(caiman_output["assignments"].load(), nan=-1) + 1

        ## Create ucids_bySession
        default_ucids_bySession = []
        for s_idx in range(assignments.shape[1]):
            default_ucids_bySession.append(np.full(len(caiman_output["matchings"][s_idx].load()), -1))

        ucids_bySession = generate_ucids_bySession(assignments, default_ucids_bySession)
        output_preset["ucids_bySession"] = ucids_bySession
        
        output_preset["warped_footprints"] = []
        output_preset["warp_field"] = caiman_output["warp_maps"].load()

    ## Common loading

    ## Get performance metrics
    resources_path = algo_output.parent / "tracked_resources.richfile"
    print(f"Loading resources from {resources_path}", flush=True)
    tracked_resources = rf.demo.RichFile_data(check=False,path=str(resources_path)).load()

    ## Preset of sacct metrics
    tracked_resources["sacct_maxrss"] = 0
    tracked_resources["sacct_cpu_time"] = 0
    tracked_resources["raw_sacct_output"] = None

    ## Check MaxRSS and computation performance metrics
    if args.job_id is not None:
        job_id = args.job_id
        try:
            maxrss_output = subprocess.check_output(
                ['sacct', '-j', job_id, '--format=MaxRSS%30', '-n', '--noconvert']
            ).decode().strip()
            print(f"sacct_output: {maxrss_output}", flush=True)
            tracked_resources["raw_sacct_output"] = maxrss_output
            MaxRSS = int(maxrss_output.split()[0])
            tracked_resources["sacct_maxrss"] = MaxRSS
            print(f"Sacct MaxRSS: {MaxRSS / (1024**2)} MB, {MaxRSS / (1024**3)} GB", flush=True)

            ## Get job-related CPU time
            cpu_usage = subprocess.check_output(
                ['sacct', '-j', job_id, '--format=UserCPU%30', '-n', '--noconvert']
            ).decode().strip()
            print(f"CPUTime sacct_output: {cpu_usage}", flush=True)
            CPUUsage = cpu_usage.split()[0]
            days = 0
            if '-' in CPUUsage:
                days, CPUUsage = CPUUsage.split('-')
            parts = CPUUsage.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
            elif len(parts) == 2:
                hours = 0
                minutes = int(parts[0])
                seconds = float(parts[1])
            else:   
                raise ValueError(f"Invalid CPUUsage format: {CPUUsage}")
            total_seconds = int(days) * 24 * 3600 + hours * 3600 + minutes * 60 + seconds
            print(f"Sacct CPU Time: {total_seconds} seconds", flush=True)
            tracked_resources["sacct_cpu_time"] = total_seconds
        except Exception as e:
            print(f"Formatting issues for MaxRSS: {e}", flush=True)
            sacct_output = subprocess.check_output(
                ['sacct', '-j', job_id, '--format=MaxRSS%30', '-n', '--noconvert']
            ).decode().strip()
            print(f"sacct_output: {sacct_output}", flush=True)
            tracked_resources["raw_sacct_output"] = sacct_output
    else:
        job_id = 0
        tracked_resources["raw_sacct_output"] = ""
        tracked_resources["sacct_maxrss"] = 0
        tracked_resources["sacct_cpu_time"] = 0
    output_preset["resources"] = tracked_resources

    ## Save output
    rf_save_path = algo_output.parent / f"{args.algo}_output_{job_id}.richfile"
    print(f"Saving output to {rf_save_path}", flush=True)
    rf.demo.RichFile_data(path=str(rf_save_path)).save(output_preset, overwrite=True)

def generate_ucids_bySession(assignments, ucids_bySession):
    """
    assignments: (n_clusters, n_sessions)
    ucids_bySession: n_sessions length list. Each element is a ROI-length numpy array of -1.
    Shamefully, assignments are assumed to follow 1-indexing with 0 as non-assigned roi values.
    """
    ## Sanity check
    assert assignments.shape[1] == len(ucids_bySession), "Number of sessions do not match"
    assert len(np.unique(assignments)) - 1 == max(len(session_rois) for session_rois in ucids_bySession), f"Max number of rois per session do not match: {len(np.unique(assignments))} != {max(len(session_rois) for session_rois in ucids_bySession)}"

    ## Assign cluster ids to each rois
    cluster_counter = 0
    for cluster_num, cluster in enumerate(assignments):
        if np.count_nonzero(cluster) > 1:
            for s_idx, n_idx in enumerate(cluster):
                if n_idx:
                    ucids_bySession[s_idx][int(n_idx-1)] = cluster_counter
            cluster_counter += 1

    return ucids_bySession

if __name__ == "__main__":
    main()