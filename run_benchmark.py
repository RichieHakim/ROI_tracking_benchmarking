import os
import sys
import subprocess
import argparse

from roicat_benchmark.algos.CaImAn.caiman_runner import benchmark_caiman

def main():
    ## TODO: This would be where we let hyperparameter optimizers to choose the best parameters
    ## For now, we just load the default parameters
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", dest="data_path", type=str, required=True)
    parser.add_argument("--output-dir", dest="output_dir", type=str, required=True)
    parser.add_argument("--algo", type=str, required=True, choices=["CellReg", "CaImAn"])
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))

    params = {}
    params["data_path"] = args.data_path
    params["output_dir"] = args.output_dir
    
    if args.algo == "CellReg":
        params["microns_per_pixel"] = 1.2
        params["transformation_smoothness"] = 2.0
        params["p_same_certainty_threshold"] = 0.95
        params["p_same_threshold"] = 0.5
        params["sufficient_correlation_centroids"] = 0.2
        params["sufficient_correlation_footprints"] = 0.3
        params["registration_approach"] = "Simple threshold"

        ordered_inputs = [
            params["data_path"],
            params["output_dir"],
            str(params["microns_per_pixel"]),
            str(params["transformation_smoothness"]),
            str(params["p_same_certainty_threshold"]),
            str(params["p_same_threshold"]),
            str(params["sufficient_correlation_centroids"]),
            str(params["sufficient_correlation_footprints"]),
            params["registration_approach"]
        ]

        result = subprocess.run(["bash", f"{current_dir}/bin/cellreg_slurm_local.sh"] + ordered_inputs,
                                capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)
    elif args.algo == "CaImAn":
        params["max_thr"] = 0
        params["thresh_cost"] = 0.7
        params["max_dist"] = 10
        benchmark_caiman(params)
    else:
        raise ValueError(f"Algorithm {args.algo} not supported")

if __name__ == "__main__":
    main()