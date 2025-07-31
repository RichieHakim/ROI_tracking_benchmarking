from setuptools import setup, find_packages

setup(
    name='roicat_benchmark',
    version='0.1',
    packages=find_packages(),
    description='Run CaImAn and CellReg on the RoiCat benchmark',
    install_requires=[
        'natsort',
        'richfile==0.5.3',
    ],
)