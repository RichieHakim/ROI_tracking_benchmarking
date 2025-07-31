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

For some reason, the CaImAn environment has version issues. If you run into any tensorflow issues, try downgrading both python and tensorflow:
```
conda install python=3.10
pip install -U tensorflow==2.14
```

## Usage for test data
First, untar the test data in datasets/test_pass. Then, run the following commands to run the benchmark.

CaImAn for running the benchmark.
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 run_benchmark.py --data-path datasets/test_pass/Adesnik_Ian_sigma_translation_0.50_repeat0/Adesnik_Ian_sigma_translation_0.50_repeat0/generated_dataset.richfile --output-dir demo_output --algo CaImAn
```

CellReg for running the benchmark.
```
cd ROI_tracking_benchmarking ## Skip if you're already in the directory
python3 run_benchmark.py --data-path datasets/test_pass/Adesnik_Ian_sigma_translation_0.50_repeat0/Adesnik_Ian_sigma_translation_0.50_repeat0/generated_dataset.richfile --output-dir demo_output --algo CellReg
```