# ROI_tracking_benchmarking
Benchmarking for different ROI tracking algorithms for calcium imaging data

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

For some reason, the CaImAn environment has version issues. If you run into any tensorflow issues, try downgrading both python and tensorflow:
```
conda install python=3.10
pip install -U tensorflow==2.14
```

## Usage
CaImAn for running the benchmark.
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 run_benchmark.py --data-path /n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/ROI_tracking_benchmarking/datasets/CaImAn_default/alignment.pickle --output-dir /n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/ROI_tracking_benchmarking/demo_output --algo CaImAn
```

CellReg for running the benchmark.
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 run_benchmark.py --data-path /n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/ROI_tracking_benchmarking/datasets/CellReg_default/ --output-dir /n/data1/hms/neurobio/sabatini/gyu/roicat_benchmark/ROI_tracking_benchmarking/demo_output --algo CellReg
```