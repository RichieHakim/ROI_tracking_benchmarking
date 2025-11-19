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
Untar the test data in test/test_dataset.

## Prepare matlab files for CellReg
Use roicat_benchmark/utils/sample_matfile_maker.py to convert richfile to matfile.
The function takes four arguments:
- '--data-dir': the directory containing richfiles.
- '--output-dir': the directory to save converted matfiles. If not provided, it will be the same as --data-dir.
- '--pattern-to-search': the pattern to search for the richfile. Default is ["data_roicat.richfile", "data_roicat_prealigned.richfile"].
- '--verbose': print verbose output. Default is False.

Example:
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 roicat_benchmark/utils/sample_matfile_maker.py --data-dir test/test_dataset --output-dir test/test_dataset/matfile_output --pattern-to-search testdata.richfile --verbose
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

Minimal submission example for CaImAn:
```
python3 batch_dispatch.py --algo CaImAn --data-dir {your_data_dir} --output-dir {your_output_dir} --params-path {your_params_path}
```

Minimal submission example for CellReg:
```
python3 batch_dispatch.py --algo CellReg --data-dir {your_data_dir} --output-dir {your_output_dir} --params-path {your_params_path}
```