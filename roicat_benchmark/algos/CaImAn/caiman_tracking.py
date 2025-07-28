## CaImAn code adapted from version 1.12.2, on 2025-07-24
## https://github.com/flatironinstitute/CaImAn, main branch
## Modifications made for benchmark purposes

import cv2
import logging
import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment
import time
from typing import Optional

from caiman.base.rois import com
from caiman.motion_correction import tile_and_correct, get_patch_centers, interpolate_shifts

def register_ROIs(A1,
                  A2,
                  dims,
                  template1=None,
                  template2=None,
                  align_flag=True,
                  D=None,
                  max_thr=0,
                  use_opt_flow=True,
                  thresh_cost=.7,
                  max_dist=10,
                  enclosed_thr=None,
                  print_assignment=False,
                  plot_results=False,
                  Cn=None,
                  cmap='viridis',
                  align_options: Optional[dict] = None):
    """
    Register ROIs across different sessions using an intersection over union 
    metric and the Hungarian algorithm for optimal matching

    Args:
        A1: ndarray or csc_matrix  # pixels x # of components
            ROIs from session 1

        A2: ndarray or csc_matrix  # pixels x # of components
            ROIs from session 2

        dims: list or tuple
            dimensionality of the FOV

        template1: ndarray dims
            template from session 1

        template2: ndarray dims
            template from session 2

        align_flag: bool
            align the templates before matching

        D: ndarray
            matrix of distances in the event they are pre-computed

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

        print_assignment: bool
            print pairs of matched ROIs

        plot_results: bool
            create a plot of matches and mismatches

        Cn: ndarray
            background image for plotting purposes

        cmap: string
            colormap for background image
        
        align_options: Optional[dict]
            mcorr options to override defaults when align_flag is True and use_opt_flow is False

    Returns:
        matched_ROIs1: list
            indices of matched ROIs from session 1

        matched_ROIs2: list
            indices of matched ROIs from session 2

        non_matched1: list
            indices of non-matched ROIs from session 1

        non_matched2: list
            indices of non-matched ROIs from session 2

        performance:  list
            (precision, recall, accuracy, f_1 score) with A1 taken as ground truth

        A2: csc_matrix  # pixels x # of components
            ROIs from session 2 aligned to session 1

    """
    logger = logging.getLogger("caiman")

    if 'ndarray' not in str(type(A1)):
        A1 = A1.toarray()
    if 'ndarray' not in str(type(A2)):
        A2 = A2.toarray()

    if template1 is None or template2 is None:
        align_flag = False

    x_grid, y_grid = np.meshgrid(np.arange(0., dims[1]).astype(np.float32), np.arange(0., dims[0]).astype(np.float32))

    if align_flag:     # first align ROIs from session 2 to the template from session 1
        template1 -= template1.min()
        template1 /= template1.max()
        template2 -= template2.min()
        template2 /= template2.max()

        if use_opt_flow:
            template1_norm = np.uint8(template1 * (template1 > 0) * 255)
            template2_norm = np.uint8(template2 * (template2 > 0) * 255)
            flow = cv2.calcOpticalFlowFarneback(template1_norm, template2_norm, None,
                                                0.5, 3, 128, 3, 7, 1.5, 0)
            x_remap = (flow[:, :, 0] + x_grid).astype(np.float32)
            y_remap = (flow[:, :, 1] + y_grid).astype(np.float32)

        else:
            align_defaults = {
                "strides": (int(dims[0] / 4), int(dims[1] / 4)),
                "overlaps": (16, 16),
                "max_shifts": (10, 10),
                "shifts_opencv": True,
                "upsample_factor_grid": 4,
                "shifts_interpolate": True,
                "max_deviation_rigid": 2
                # any other argument to tile_and_correct can also be used in align_options
            }

            if align_options:
                # override defaults with input options
                align_defaults.update(align_options)
            align_options = align_defaults

            template2, shifts, _, _ = tile_and_correct(template2, template1 - template1.min(),
                                                       add_to_movie=template2.min(), **align_options)

            if align_options["max_deviation_rigid"] == 0:
                # repeat rigid shifts to size of the image
                shifts_x_full = np.full(dims, -shifts[1])
                shifts_y_full = np.full(dims, -shifts[0])
            else:
                # piecewise - interpolate from patches to get shifts per pixel
                patch_centers = get_patch_centers(dims, overlaps=align_options["overlaps"], strides=align_options["strides"],
                                                  shifts_opencv=align_options["shifts_opencv"],
                                                  upsample_factor_grid=align_options["upsample_factor_grid"])
                patch_grid = tuple(len(centers) for centers in patch_centers)
                _sh_ = np.stack(shifts, axis=0)
                shifts_x = np.reshape(_sh_[:, 1], patch_grid, order='C').astype(np.float32)
                shifts_y = np.reshape(_sh_[:, 0], patch_grid, order='C').astype(np.float32)

                shifts_x_full = interpolate_shifts(-shifts_x, patch_centers, tuple(range(d) for d in dims))
                shifts_y_full = interpolate_shifts(-shifts_y, patch_centers, tuple(range(d) for d in dims))

            x_remap = (shifts_x_full + x_grid).astype(np.float32)
            y_remap = (shifts_y_full + y_grid).astype(np.float32)

        A_2t = np.reshape(A2, dims + (-1,), order='F').transpose(2, 0, 1)
        A2 = np.stack([cv2.remap(img.astype(np.float32), x_remap, y_remap, cv2.INTER_NEAREST) for img in A_2t], axis=0)
        A2 = np.reshape(A2.transpose(1, 2, 0), (A1.shape[0], A_2t.shape[0]), order='F')

    A1 = np.stack([a * (a > max_thr * a.max()) for a in A1.T]).T
    A2 = np.stack([a * (a > max_thr * a.max()) for a in A2.T]).T

    if D is None:
        if 'csc_matrix' not in str(type(A1)):
            A1 = scipy.sparse.csc_matrix(A1)
        if 'csc_matrix' not in str(type(A2)):
            A2 = scipy.sparse.csc_matrix(A2)

        cm_1 = com(A1, *dims)
        cm_2 = com(A2, *dims)
        A1_tr = (A1 > 0).astype(float)
        A2_tr = (A2 > 0).astype(float)
        D = distance_masks([A1_tr, A2_tr], [cm_1, cm_2], max_dist, enclosed_thr=enclosed_thr)

    matches, costs = find_matches(D, print_assignment=print_assignment)
    matches = matches[0]
    costs = costs[0]

    # store indices

    idx_tp = np.where(np.array(costs) < thresh_cost)[0]
    if len(idx_tp) > 0:
        matched_ROIs1 = matches[0][idx_tp]     # ground truth
        matched_ROIs2 = matches[1][idx_tp]     # algorithm - comp
        non_matched1 = np.setdiff1d(list(range(D[0].shape[0])), matches[0][idx_tp])
        non_matched2 = np.setdiff1d(list(range(D[0].shape[1])), matches[1][idx_tp])
        TP = np.sum(np.array(costs) < thresh_cost) * 1.
    else:
        TP = 0.
        plot_results = False
        matched_ROIs1 = []
        matched_ROIs2 = []
        non_matched1 = list(range(D[0].shape[0]))
        non_matched2 = list(range(D[0].shape[1]))

    # compute precision and recall

    FN = D[0].shape[0] - TP
    FP = D[0].shape[1] - TP
    TN = 0

    performance = dict()
    performance['recall'] = TP / (TP + FN)
    performance['precision'] = TP / (TP + FP)
    performance['accuracy'] = (TP + TN) / (TP + FP + FN + TN)
    performance['f1_score'] = 2 * TP / (2 * TP + FP + FN)
    logger.info(performance)

    return matched_ROIs1, matched_ROIs2, non_matched1, non_matched2, performance, A2

def find_matches(D_s, print_assignment: bool = False) -> tuple[list, list]:
    # todo todocument
    logger = logging.getLogger("caiman")

    matches = []
    costs = []
    t_start = time.time()
    for ii, D in enumerate(D_s):
        # we make a copy not to set changes in the original
        DD = D.copy()
        if np.sum(np.where(np.isnan(DD))) > 0:
            logger.error('Exception: Distance Matrix contains invalid value NaN')
            raise Exception('Distance Matrix contains invalid value NaN')

        # we do the hungarian
        indexes = linear_sum_assignment(DD)
        indexes2 = [(ind1, ind2) for ind1, ind2 in zip(indexes[0], indexes[1])]
        matches.append(indexes)
        DD = D.copy()
        total = []
        # we want to extract those information from the hungarian algo
        for row, column in indexes2:
            value = DD[row, column]
            if print_assignment:
                logger.debug(f'({row}, {column}) -> {value}')
            total.append(value)
        logger.debug(f'FOV: {ii}, shape: {DD.shape[0]},{DD.shape[1]} total cost: {np.sum(total)}')
        logger.debug(time.time() - t_start)
        costs.append(total)
        # send back the results in the format we want
    return matches, costs


def distance_masks(M_s:list, cm_s: list[list], max_dist: float, enclosed_thr: Optional[float] = None) -> list:
    """
    Compute distance matrix based on an intersection over union metric. Matrix are compared in order,
    with matrix i compared with matrix i+1

    Args:
        M_s: tuples of 1-D arrays
            The thresholded A matrices (masks) to compare, output of threshold_components

        cm_s: list of list of 2-ples
            the centroids of the components in each M_s

        max_dist: float
            maximum distance among centroids allowed between components. This corresponds to a distance
            at which two components are surely disjoined

        enclosed_thr: float
            if not None set distance to at most the specified value when ground truth is a subset of inferred

    Returns:
        D_s: list of matrix distances

    Raises:
        Exception: 'Nan value produced. Error in inputs'

    """
    D_s = []

    for gt_comp, test_comp, cmgt_comp, cmtest_comp in zip(M_s[:-1], M_s[1:], cm_s[:-1], cm_s[1:]):

        # todo : better with a function that calls itself
        # not to interfere with M_s
        gt_comp = gt_comp.copy()[:, :]
        test_comp = test_comp.copy()[:, :]

        # the number of components for each
        nb_gt   = gt_comp.shape[-1]
        nb_test = test_comp.shape[-1]
        D = np.ones((nb_gt, nb_test))

        cmgt_comp = np.array(cmgt_comp)
        cmtest_comp = np.array(cmtest_comp)
        if enclosed_thr is not None:
            gt_val = gt_comp.T.dot(gt_comp).diagonal()
        for i in range(nb_gt):
            # for each components of gt
            k = gt_comp[:, np.repeat(i, nb_test)] + test_comp
            # k is correlation matrix of this neuron to every other of the test
            for j in range(nb_test):   # for each components on the tests
                dist = np.linalg.norm(cmgt_comp[i] - cmtest_comp[j])
                                       # we compute the distance of this one to the other ones
                if dist < max_dist:
                                       # union matrix of the i-th neuron to the jth one
                    union = k[:, j].sum()
                                       # we could have used OR for union and AND for intersection while converting
                                       # the matrice into real boolean before

                    # product of the two elements' matrices
                    # we multiply the boolean values from the jth omponent to the ith
                    intersection = np.array(gt_comp[:, i].T.dot(test_comp[:, j]).todense()).squeeze()

                    # if we don't have even a union this is pointless
                    if union > 0:

                        # intersection is removed from union since union contains twice the overlapping area
                        # having the values in this format 0-1 is helpful for the hungarian algorithm that follows
                        D[i, j] = 1 - 1. * intersection / \
                            (union - intersection)
                        if enclosed_thr is not None:
                            if intersection == gt_val[j] or intersection == gt_val[i]:
                                D[i, j] = min(D[i, j], 0.5)
                    else:
                        D[i, j] = 1.

                    if np.isnan(D[i, j]):
                        raise Exception('Nan value produced. Error in inputs')
                else:
                    D[i, j] = 1

        D_s.append(D)
    return D_s