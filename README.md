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

## Abstract SLURM workflow

The full pipeline on SLURM can be summarized as:

```text
batch_dispatch.py
    └── slurm_{algo}.sh  (SLURM array job)
          └── run_benchmark.py
                └── slurm_format_output.sh
                      └── format_output.py
collect_output.py  (manual)
batch_dispatch.py  (optional rerun of failed jobs)
```

## Data structure
RichFile expected. Expected to contain at least two keys: 'spatialFootprints' and 'FOV_images'.

- 'spatialFootprints' is a list of csc matrices of (# of components, pixels).
- 'FOV_images' is a list of 2D numpy arrays.

## Input directory structure

We support batch data submission as long as data are structured as follows:

```text
arbitrary/
└── stem/
    └── mother_dir/
        ├── child_1/
        │   └── child_1_data.richfile
        └── child_2/
            └── child_2_data.richfile
```
Simple test data is provided in test/test_dataset. Untar the data_roicat_test.tar to play around with the code.

## Prepare matlab files for CellReg
CellReg needs per-session matfiles. Use roicat_benchmark/utils/sample_matfile_maker.py to convert richfile to per-session matfiles.
The function takes four arguments:
- '--data-dir': the directory containing richfiles.
- '--output-dir': the directory to save converted matfiles. If not provided, it will be the same as --data-dir.
- '--pattern-to-search': the pattern to search for the richfile. Default is ["data_roicat.richfile", "data_roicat_prealigned.richfile"].
- '--verbose': print verbose output. Default is False.

Example:
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 roicat_benchmark/utils/sample_matfile_maker.py --data-dir test/test_dataset --pattern-to-search data_roicat_test.richfile --verbose
```

CellReg expects matfiles to be in the same directory of the original richfile. The converted matfiles will be structured as follows:

```text
arbitrary/
└── stem/
    └── mother_dir/
        ├── child_1/
        │   └── child_1_data.richfile
        │   └── child_1_data_0001.mat
        │   └── child_1_data_0002.mat
        │   └── ...
        └── child_2/
            └── child_2_data.richfile
            └── child_2_data_0001.mat
            └── child_2_data_0002.mat
            └── ...
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

## Output directory structure
Output structure mirrors the input tree. If submitted --data-dir is `arbitrary/stem/mother_dir`, structure will be as follows:
```text
output_dir/
├── child_1/
    ├── sweep_params.json          # copied from the dispatch step; 
    └── {algo}_output/
        ├── {algo}_sweep_log.json  # one line per hyperparameter set / job
        ├── collection_bin/        # finalized richfile outputs only
        ├── JobId_%A_%a/           # raw outputs for each SLURM array job
        └── slurm_bin/             # stdout / stderr logs
└── child_2/
    ├── sweep_params.json          # Same as child_1/...
    └── {algo}_output/
        ├──...
```

On the other hand, if --data-dir is `arbitrary/stem/mother_dir/child_1`, structure will be as follows:
```text
output_dir/
├── sweep_params.json          # copied from the dispatch step; 
└── {algo}_output/
    ├── {algo}_sweep_log.json  # one line per hyperparameter set / job
    ├── collection_bin/        # finalized richfile outputs only
    ├── JobId_%A_%a/           # raw outputs for each SLURM array job
    └── slurm_bin/             # stdout / stderr logs
```

## A little bit more detailed workflow
0. **Prepare shell files and json files**
    - We recommend to adjust shell file parameters to your cluster's environment and your data size.
    - hyperparameter json files (e.g. `sweep_params.json`) should be provided.

1. **Dispatch & setup — `batch_dispatch.py`**
    - Scans the input tree under submitted `--data-dir`.
    - Creates the mirrored `output_dir/mirrored/stem/{algo}_output/` directory structure.
    - Copies `sweep_params.json` (global sweep configuration).
    - Creates `{algo}_sweep_log.json` in each child directory (one line per one hyperparameter set).
    - Submits a non-interactive SLURM array job via `bin/slurm_{algo}.sh`.

2. **SLURM entrypoint — `slurm_{algo}.sh` -> `run_benchmark.py`**
    - Reads the hyperparameter set corresponding to array index `%a` from `{algo}_sweep_log.json`
    - Calls each algorithm, `slurm_{algo}.sh`, as a python subprocess.
    - Writes **raw outputs** into the appropriate `JobId_%A_%a/` directory.

3. **Output formatting — `slurm_format_output.sh` -> `format_output.py`**
    - When the benchmark subprocess is done, `run_benchmark.py` submits a second non-interactive SLURM job using `slurm_format_output.sh`.
    - `slurm_format_output.sh` runs `format_output.py`, which:
        - Reads raw data from `JobId_%A_%a/`.
        - Produces finalized, cleaned `*.richfile` outputs.
        - Copies them into the corresponding `collection_bin/` directory.

4. **Result collection — `collect_output.py`**
    - Manually run `collect_output.py` to summarize a sweep:
        - Aggregates results and metrics across all children (not implemented yet).
        - Appends indices of failed or missing jobs to the **last line** of each
        `{algo}_sweep_log.json`.

6. **Rerun failed jobs — `batch_dispatch.py` (optional)**
    - On rerun, `batch_dispatch.py`:
        - Reads the last line of `{algo}_sweep_log.json`.
        - Submits SLURM jobs **only** for jobs marked as not done.
    - This avoids re-running successful jobs and supports incremental recovery.
    - Due to this feature, we do not recommend obliterating or overwriting `{algo}_sweep_log.json` file.

