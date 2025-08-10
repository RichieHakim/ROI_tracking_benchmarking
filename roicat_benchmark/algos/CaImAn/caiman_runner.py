import numpy as np
import scipy.sparse
import scipy.io
import natsort
import pickle
import logging
import richfile as rf
from pathlib import Path
from roicat_benchmark.algos.CaImAn.caiman_tracking import register_ROIs


def benchmark_caiman(params):
    data = rf.demo.RichFile_data(check=False,path=params["data_path"]).load()

    # ## CaImAn asks csc matrices of (pixels, # of components)
    # spatial_footprints = [reshaped_data.T for reshaped_data in data['dataset']['spatial_footprints']]
    # template_images = data['dataset']['FOV_images']
    # dims = template_images[0].shape

    ## RealData richfile format
    ## CaImAn asks csc matrices of (pixels, # of components)
    spatial_footprints = [
        reshaped_data.T for reshaped_data in data['spatialFootprints']
    ]
    template_images = data['FOV_images']
    dims = template_images[0].shape

    spatial_union, assignments, matchings, warp_maps = register_multisession(
        spatial_footprints,
        dims,
        template_images,
        max_thr=params["max_thr"],
        thresh_cost=params["thresh_cost"],
        max_dist=params["max_dist"],
        plot_results=params["plot_results"],
        plot_save_dir=params["output_dir"]
    )

    caiman_results = {
        "spatial_union": spatial_union,
        "assignments": assignments,
        "matchings": matchings,
        "warp_maps": warp_maps,
    }

    rf.demo.RichFile_data(Path(params["output_dir"]) / "caiman_results.richfile").save(obj=caiman_results, overwrite=True)
    print(f"Saved {Path(params['output_dir']) / 'caiman_results.richfile'}", flush=True)
    print(f"CaImAn run done", flush=True)
    return caiman_results


def register_multisession(A,
                          dims,
                          templates=[None],
                          align_flag=True,
                          max_thr=0,
                          use_opt_flow=True,
                          thresh_cost=.7,
                          max_dist=10,
                          enclosed_thr=None,
                          plot_results=False,
                          plot_save_dir=None):
    """
    Register ROIs across multiple sessions using an intersection over union metric
    and the Hungarian algorithm for optimal matching. Registration occurs by 
    aligning session 1 to session 2, keeping the union of the matched and 
    non-matched components to register with session 3 and so on.

    Args:
        A: list of ndarray or csc_matrix matrices # pixels x # of components
           ROIs from each session

        dims: list or tuple
            dimensionality of the FOV

        template: list of ndarray matrices of size dims
            templates from each session

        align_flag: bool
            align the templates before matching

        max_thr: scalar
            max threshold parameter before binarization    

        use_opt_flow: bool
            use dense optical flow to align templates

        thresh_cost: scalar
            maximum distance considered

        max_dist: scalar
            max distance between centroids

        enclosed_thr: float
            if not None set distance to at most the specified value when ground 
            truth is a subset of inferred

    Returns:
        A_union: csc_matrix # pixels x # of total distinct components
            union of all kept ROIs 

        assignments: ndarray int of size # of total distinct components x # sessions
            element [i,j] = k if component k from session j is mapped to component
            i in the A_union matrix. If there is no much the value is NaN

        matchings: list of lists
            matchings[i][j] = k means that component j from session i is represented
            by component k in A_union

    """
    logger = logging.getLogger("caiman")

    n_sessions = len(A)
    templates = list(templates)
    if len(templates) == 1:
        templates = n_sessions * templates

    if n_sessions <= 1:
        raise Exception('number of sessions must be greater than 1')

    A = [a.toarray() if 'ndarray' not in str(type(a)) else a for a in A]

    A_union = A[0].copy()
    matchings, warp_maps = [], []
    matchings.append(list(range(A_union.shape[-1])))

    for sess in range(1, n_sessions):
        reg_results = register_ROIs(A[sess],
                                    A_union,
                                    dims,
                                    template1=templates[sess],
                                    template2=templates[sess - 1],
                                    align_flag=align_flag,
                                    max_thr=max_thr,
                                    use_opt_flow=use_opt_flow,
                                    thresh_cost=thresh_cost,
                                    max_dist=max_dist,
                                    enclosed_thr=enclosed_thr,
                                    plot_results=plot_results)

        mat_sess, mat_un, nm_sess, nm_un, _, A2, warp_map, fig = reg_results
        logger.info(len(mat_sess))
        A_union = A2.copy()
        A_union[:, mat_un] = A[sess][:, mat_sess]
        A_union = np.concatenate((A_union.toarray(), A[sess][:, nm_sess]), axis=1)
        new_match = np.zeros(A[sess].shape[-1], dtype=int)
        new_match[mat_sess] = mat_un
        new_match[nm_sess] = range(A2.shape[-1], A_union.shape[-1])
        matchings.append(new_match.tolist())
        warp_maps.append(warp_map)
        if plot_results:
            fig.suptitle(f"Session {sess}", fontsize=24, fontweight="bold")
            fig.tight_layout()
            fig_title = Path(plot_save_dir) / f"caiman_registration_results_session_{sess}.png"
            fig.savefig(fig_title)
            print(f"Saved {fig_title}", flush=True)

    assignments = np.empty((A_union.shape[-1], n_sessions)) * np.nan
    for sess in range(n_sessions):
        assignments[matchings[sess], sess] = range(len(matchings[sess]))

    return A_union, assignments, matchings, warp_maps