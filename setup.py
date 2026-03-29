from setuptools import setup, find_packages

setup(
    name='roicat_benchmark',
    version='0.1',
    packages=find_packages(),
    description='Run CaImAn and CellReg on the RoiCat benchmark',
    install_requires=[
        'numpy==1.26.4',
        'natsort==8.4.0',
        'richfile==0.5.3',
        'hdf5storage==0.2.0',
        'psutil==7.0.0'
    ],
)