# ROI_tracking_benchmarking
Benchmarking for different ROI tracking algorithms for calcium imaging data

CaImAn code paraphrased from version 1.12.2, on 2025-07-24
https://github.com/flatironinstitute/CaImAn, main branch

CellReg code paraphrased on 2025-07-24 with matlab/2023b
https://github.com/zivlab/CellReg, master branch

## Installation
Start with cloning the repo.
```
git clone {this repo}
```
CellReg is MatLab code, so no need to install.
CaImAn requires installation:
```
mamba create -n caiman caiman ## build a caiman environment
conda activate caiman ## head into the env
```

Then, install benchmark dependencies.
```
cd ROI_tracking_benchmarking
pip install -e .
```

Sometimes, the CaImAn environment has version issues. If you run into any tensorflow issues, try downgrading both python and tensorflow:
```
conda install python=3.10
pip install -U tensorflow==2.14
pip install -e .
```

## Data structure
RichFile expected. Expected to contain at least two keys: 'spatialFootprints' and 'FOV_images'.

- 'spatialFootprints' is a list of csc matrices of (# of components, pixels).
- 'FOV_images' is a list of 2D numpy arrays.

## Usage for test data
Untar the data_roicat_test data in test/test_dataset.

## Prepare matlab files for CellReg
Use roicat_benchmark/utils/sample_matfile_maker.py to convert richfile to matfile.
The function takes four arguments:
- '--data-dir': the directory containing richfiles.
- '--output-dir': the directory to save converted matfiles. If not provided, it will be the same as --data-dir.
- '--pattern-to-search': the pattern to search for the richfile. Default is ["data_roicat.richfile", "data_roicat_prealigned.richfile"].
- '--verbose': print verbose output. Default is False.

CellReg expects matfiles to be in the same directory of the original richfile.

Example:
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 roicat_benchmark/utils/sample_matfile_maker.py --data-dir test/test_dataset --pattern-to-search data_roicat_test.richfile --verbose
```

CaImAn can take richfile as input.

## Submit benchmark jobs
Use batch_dispatch to submit benchmark / hyperparameter sweep jobs.
The function takes the following arguments:
- '--algo': the algorithm to run. Choices are "CellReg" and "CaImAn".
- '--data-dir': data directory. Prefers absolute path.
- '--output-dir': the directory to save the output. Prefers absolute path.
- '--pattern-to-search': the pattern to search for the richfile. Default is ["data_roicat", "data_roicat_prealigned", "data_roicat_partial"].
- '--params-path': the path to the hyperparameter file. Prefers absolute path. check out bin/sweep_params.json for more details.
- '--plot-results': plot the results. Default is False.
- '--partition': Slurm-related command. Partition to run the job. Default is None.
- '--memory': Slurm-related command. Total asked memory to run the job. Default is None.
- '--overwrite': overwrite the existing output. Default is False.

Slurm-related commands are only relevant if you're running on a cluster. Default values are defined in the shell scripts.
Checkout bin/slurm_CaImAn.sh and bin/slurm_CellReg.sh for more details.

We disabled plotting options for CaImAn. CaImAn plotting function incurs unaffordable memory usage and significantly distorts benchmark results.

Minimal submission example for CaImAn:
```
python3 batch_dispatch.py --algo CaImAn --data-dir {your_data_dir} --output-dir {your_output_dir} --params-path {your_params_path}
```

Minimal submission example for CellReg:
```
python3 batch_dispatch.py --algo CellReg --data-dir {your_data_dir} --output-dir {your_output_dir} --params-path {your_params_path}
```

## Hyperparameters
For CaImAn, the hyperparameters are:
- max_thr: Threshold for spatial footprint binarization. Any value below this threshold will be set to 0. Any value above this threshold will be set to 1. Default is 0.0.
- thresh_cost: Threshold for ROI matching based on linear sum assignment problem. Costs are normalized to [0.0, 1.0] by distance_masks function. Lower values mean more strict matching. Default is 0.7. Values in [0.0, 1.0].
- max_dist: Any footprint-to-footprint distance above this value will be considered as disjoint. Unit in pixel space, by com function. Default is 10.

For CellReg, the hyperparameters are:
- microns_per_pixel: Unit of length in the image.
- maximum_distance: Maximum distance between two ROIs to be considered the same. Default is 12.
- transformation_smoothness: imregdemons parameter "AccumulatedFieldSmoothing". Default is 2.0. Values recommended in [0.5, 3.0].
- p_same_threshold: How similar two ROIs need to be to be considered the same. Default is 0.5. Values in [0.0, 1.0].
- registration_approach: ["Simple threshold", "Probabilistic"]
- model_type: ["Spatial correlation", "Centroid distance", "best"]

CellReg hyperparameters are chosen based on the GUI settings.
To maximize performance, nonrigid registration is chosen to be the default.
CellReg only uses centroid distance models for 2-photon data (check CellReg's User Manual for more details).

Each hyperparameter set admits "grid_condition", which is a list of conditions to be evaluated.
For example,
'''
"grid_condition": [
    "registration_approach == 'Probabilistic' or p_same_threshold == 0.5"
]
'''
This means that the hyperparameter sweep grid will only contain parameter sets where the registration approach is either "Probabilistic" or the p_same_threshold is 0.5.
If no grid condition is provided, the full grid will be used.

## Output format
