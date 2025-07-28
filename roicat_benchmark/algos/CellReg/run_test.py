import os
import sys
import subprocess

current_dir = "/n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark"

params = {}
params["data_path"] = "/n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/datasets/CellReg_default"
params["output_dir"] = "/n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/demo_output"

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
