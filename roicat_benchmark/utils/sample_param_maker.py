from scipy.io import savemat
from pathlib import Path
import natsort

def cellreg_param_maker(data_dir, output_dir=None, pattern_to_search=None):
    data_dir = Path(data_dir)
    if output_dir is None:
        output_dir = Path(data_dir) / "temp_output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    if pattern_to_search is None:
        pattern_to_search = ["*.mat"]
    else:
        pattern_to_search = pattern_to_search

    ## Iterate over data_path
    print(f"Search mat files in {data_dir} for {pattern_to_search}", flush=True)
    matfiles_to_search = []
    for pattern in pattern_to_search:
        matfiles_to_search.extend(list(map(str, data_dir.rglob(pattern))))
    matfiles_to_search = natsort.natsorted(matfiles_to_search)

    print(f"Found {len(matfiles_to_search)} matfiles for CellReg", flush=True)
    print(f"Matfiles for CellReg: {matfiles_to_search}", flush=True)

    ## Add default param set
    params={}
    params["data_dir"] = str(data_dir)
    params["data_path"] = matfiles_to_search
    params["output_dir"] = str(output_dir)
    params["plot_results"] = True

    params["microns_per_pixel"] = 1.2
    params["maximal_distance"] = 12
    params["transformation_smoothness"] = 2.0
    params["p_same_threshold"] = 0.5
    params["registration_approach"] = "Simple threshold" # "Probabilistic" or "Simple threshold"
    params["model_type"] = "best" # "Spatial correlation", "Centroid distance", or "best"

    return params