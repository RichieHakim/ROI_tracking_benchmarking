import argparse
from pathlib import Path
import numpy as np
import h5py
import hdf5storage
import richfile as rf
import os
import natsort

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", dest="data_dir", type=str, required=True)
    parser.add_argument("--output-dir", dest="output_dir", type=str, required=False, default=None)
    parser.add_argument("--pattern-to-search", dest="pattern_to_search", action="append", required=False, default=None)
    parser.add_argument("--verbose", dest="verbose", action="store_true", default=False)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if args.output_dir is None:
        output_dir = data_dir
    else:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.pattern_to_search is None:
        args.pattern_to_search = ["data_roicat.richfile", "data_roicat_prealigned.richfile", "data_roicat_partial.richfile", "data_roicat_test.richfile"]
    else:
        pattern_to_search = args.pattern_to_search
    print(f"Pattern to search: {pattern_to_search}", flush=True)

    ## Iterate over data_dir
    sub_richfiles = []
    for pattern in pattern_to_search:
        sub_richfiles.extend(list(data_dir.rglob(pattern)))
    sub_richfiles = natsort.natsorted(sub_richfiles)
    
    if args.verbose:
        print(f"Found {len(sub_richfiles)} sub-richfiles", flush=True)
        verbose_richfiles = [str(richfile.relative_to(data_dir)) for richfile in sub_richfiles]
        print(f"Sub-richfiles: {verbose_richfiles}", flush=True)

    for sub_richfile in sub_richfiles:
        path_suffix = sub_richfile.parent.relative_to(data_dir)
        filename = sub_richfile.stem
        single_output_dir = output_dir / path_suffix
        single_output_dir.mkdir(parents=True, exist_ok=True)
        save_matfile(sub_richfile, single_output_dir, filename)


def save_matfile(single_data_path, single_output_dir, filename):
    data = rf.demo.RichFile_data(check=False,path=single_data_path).load()

    # footprints = data["dataset"]["spatial_footprints"]
    # FOV_hw = data["simulation"]["FOV_hw"]

    footprints = data['spatialFootprints']
    FOV_hw = data['FOV_images'][0].shape

    for ii, session in enumerate(footprints):
        print(f"Processing session {ii+1} of {len(footprints)}", flush=True)
        n_neurons = session.shape[0]
        footprints_shape = session.toarray().reshape(n_neurons, FOV_hw[0], FOV_hw[1]).shape
        
        mat_file_name = single_output_dir / f"{filename}_{ii+1:04d}.mat"
        
        ## Save dummy file for MatLab header
        hdf5storage.savemat(str(mat_file_name), {})

        ## Save actual data
        ## Weird shape order is to match python-MATLAB reading order
        with h5py.File(mat_file_name, "a") as handle:
            to_matlab = handle.create_dataset(
                "allFiltersMat",
                shape=(FOV_hw[1], FOV_hw[0], n_neurons),
                dtype="float64",
                chunks=(FOV_hw[1], FOV_hw[0], 1),
                fillvalue=0.0,
            )
            to_matlab.attrs["MATLAB_class"] = np.bytes_("double")

            for neuron_idx, neuron in enumerate(session):
                neuron_to_write = neuron.toarray().reshape(FOV_hw[0], FOV_hw[1]).T.astype("float64")
                to_matlab[:, :, neuron_idx] = neuron_to_write

        print(f"Saved {mat_file_name}", flush=True)

if __name__ == "__main__":
    main()