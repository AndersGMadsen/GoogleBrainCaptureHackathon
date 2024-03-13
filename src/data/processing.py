import os
import mne
import numpy as np
from tqdm import tqdm

from src.data.utils.eeg import get_raw

import torch


def normalize_and_add_scaling_channel(x: torch.Tensor, low=-1, high=1, data_min = -0.001, data_max = 0.001, scale_idx = -1):

    if len(x.shape) == 2:
        xmin = x.min()
        xmax = x.max()

    elif len(x.shape) == 3:
        xmin = torch.min(torch.min(x, keepdim=True, dim=1)[0], keepdim=True, dim=-1)[0]
        xmax = torch.max(torch.max(x, keepdim=True, dim=1)[0], keepdim=True, dim=-1)[0]

    x = (x - xmin) / (xmax - xmin)

    # Now all scaled 0 -> 1, remove 0.5 bias
    x -= 0.5
    # Adjust for low/high bias and scale up
    x += (high + low) / 2
    x = (high - low) * x
    
    X = torch.zeros((x.shape[0], x.shape[1] + 1, x.shape[2]))
    X[:, :-1] = x

    max_scale = data_max - data_min

    scale = 2 * (torch.clamp_max((x.max() - x.min()) / max_scale, 1.0) - 0.5)
    X[:, scale_idx] = scale

    return X



def load_data_dict(data_folder_path: str, annotation_dict: dict, tmin: float = -0.5, tlen: float = 6, labels: bool = False):
    """Loads the data from the data folder.
    Parameters
    ----------
    data_folder_path : str
        The path to the data folder.
    channel_config : list
        The configuration of the channels.
    tmin : float
        The start time.
    tlen : float
        The duration of an epoch.
    labels : bool
        Whether to include labels.
    Returns
    -------
    data_dict : dict
        The data dictionary.
    """
    data_dict = {}

    for subject in tqdm(os.listdir(data_folder_path)):
        data_dict[subject] = {}

        for session in os.listdir(data_folder_path + subject):
            session_name = session.split('.')[0]
            data_dict[subject][session_name] = {}
            
            edf_file_path = data_folder_path + subject + '/' + session
            raw = get_raw(edf_file_path, filter=True)

            if labels:
                # TODO: remove try-except, was added to handle TUAR data
                try:
                    events = mne.events_from_annotations(raw, event_id=annotation_dict, verbose='error')
                except:
                    print(f'No annotations in {subject} {session_name}')
                    data_dict[subject].pop(session_name)
                    continue

                tmax = tmin + tlen
                epochs = mne.Epochs(raw, events=events[0], tmin=tmin, tmax=tmax, event_repeated='merge', verbose='error')

                y = epochs.events[:, 2]

                data_dict[subject][session_name]['y'] = epochs.events[:, 2]
            else:
                epochs = mne.make_fixed_length_epochs(raw, duration=tlen, preload=True, verbose='error')

            data_dict[subject][session_name]['X'] = epochs.get_data()

    return data_dict


import torch

def get_data(data_dict, subject_list=None):
    """Returns the data and labels.
    Parameters
    ----------
    data_dict : dict
        The data dictionary.
    subject_list : list
        The list of subjects.
    Returns
    -------
    X : torch.Tensor
        The data.
    y : torch.Tensor
        The labels.
    """
    if subject_list is None:
        subject_list = list(data_dict.keys())

    X = [torch.tensor(data_dict[subject][session]['X']) for subject in subject_list for session in data_dict[subject].keys()]
    X = torch.cat(X)

    X = normalize_and_add_scaling_channel(X)

    if 'y' in data_dict[subject_list[0]][list(data_dict[subject_list[0]].keys())[0]]:
        y = [torch.tensor(data_dict[subject][session]['y']) for subject in subject_list for session in data_dict[subject].keys()]
        y = torch.cat(y)
        return X, y

    return X
