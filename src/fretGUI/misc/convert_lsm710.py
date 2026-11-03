"""Group Zeiss ConfoCor3 (LSM 710) raw channel files and merge one pair.

Each channel of a measurement is stored in its own raw file. Files that share
a measurement id, repetition, position, and kinetic index belong to one
experiment. Channel 1 (header channel 0) is the acceptor and channel 2
(header channel 1) is the donor, matching the original ``convert2h5`` script.
"""

import os
import re

import numpy as np

from fretGUI.misc.fcsfiles import ConfoCor3Raw


_CHANNEL_SUFFIX = re.compile(r'_Ch\d+$', re.IGNORECASE)


def read_channel_info(path):
    """Return header fields for one ConfoCor3 raw file, or None.

    The file is closed before this returns. A file whose header is not
    ConfoCor3 raw data returns None instead of raising.
    """
    raw = None
    try:
        raw = ConfoCor3Raw(path)
        return {
            'path': os.path.abspath(path),
            'channel': int(raw.channel),
            'measurement_identifier': raw.measurement_identifier,
            'repetition_number': int(raw.repetition_number),
            'measurement_position': int(raw.measurement_position),
            'kinetic_index': int(raw.kinetic_index),
            'frequency': int(raw.frequency),
        }
    except ValueError:
        return None
    finally:
        if raw is not None:
            raw.close()


def experiment_label(path):
    """Filename stem with the ``_ChN`` suffix removed."""
    stem = os.path.splitext(os.path.basename(path))[0]
    return _CHANNEL_SUFFIX.sub('', stem) or stem


def channel_name(channel):
    """File-header name. Header channel 0 is Ch1, channel 1 is Ch2."""
    return f'Ch{int(channel) + 1}'


def channel_tooltip(channels):
    """One line per channel file, named the way the raw files are named."""
    return '\n'.join(
        f'{channel_name(channel)}: {path}'
        for channel, path in sorted(channels.items())
    )


def _group_key(info):
    return (
        info['measurement_identifier'],
        info['repetition_number'],
        info['measurement_position'],
        info['kinetic_index'],
    )


def _report(messages, text):
    messages.append(text)


def group_channel_files(paths, pending=None):
    """Group raw paths into experiments that have both channel 0 and 1.

    Parameters
    ----------
    paths : sequence of str
        Files selected by the user, in any order.
    pending : dict, optional
        Incomplete groups from an earlier call, keyed by
        ``(measurement_identifier, repetition, position, kinetic)`` and
        valued by ``{channel: absolute path}``.

    Returns
    -------
    experiments : list of dict
        Complete groups sorted by header key. Each dict has ``key``,
        ``channels``, ``row_path`` (the channel 0 file), and ``label``.
    pending : dict
        Groups that still lack channel 0 or channel 1.
        messages : list of str
        Files that were skipped, including non-ConfoCor3 files and
        duplicate channels. The loader prints these.
    """
    buckets = {
        key: dict(channels)
        for key, channels in (pending or {}).items()
    }
    messages = []

    for path in paths:
        if not path:
            continue
        try:
            info = read_channel_info(path)
        except Exception as error:
            _report(messages, f'Could not read {path}: {error}')
            continue
        if info is None:
            _report(messages, f'Not a ConfoCor3 raw file: {path}')
            continue

        channels = buckets.setdefault(_group_key(info), {})
        channel = info['channel']
        kept = channels.get(channel)
        if kept is not None:
            if kept == info['path']:
                _report(messages, f'Duplicate file ignored: {info["path"]}')
            else:
                _report(
                    messages,
                    f'Duplicate {channel_name(channel)} ignored: {info["path"]} '
                    f'(keeping {kept})',
                )
            continue
        channels[channel] = info['path']

    experiments = []
    still_pending = {}
    for key in sorted(buckets):
        channels = buckets[key]
        if 0 in channels and 1 in channels:
            row_path = channels[0]
            experiments.append({
                'key': key,
                'channels': dict(channels),
                'row_path': row_path,
                'label': experiment_label(row_path),
            })
        else:
            still_pending[key] = dict(channels)
    return experiments, still_pending, messages


def merge_donor_acceptor(times_donor, times_acceptor):
    """Merge two arrival-time streams. Acceptor photons are True in the mask.

    Simultaneous photons keep the same order as the original
    ``hstack`` / ``argsort`` conversion.
    """
    times_donor = np.asarray(times_donor)
    times_acceptor = np.asarray(times_acceptor)
    merged = np.concatenate((times_donor, times_acceptor))
    order = np.argsort(merged.astype(np.float64, copy=False))
    timestamps = merged[order].astype(np.int64, copy=False)
    detectors = order >= times_donor.size
    return timestamps, detectors


def merge_channel_files(donor_path, acceptor_path):
    """Read two ConfoCor3 raw files and return timestamps, mask, and clock.

    ``donor_path`` and ``acceptor_path`` are closed before this returns.
    Both files must use the same sampling frequency.
    """
    with ConfoCor3Raw(donor_path) as donor:
        times_donor = donor.asarray()
        donor_frequency = int(donor.frequency)
    with ConfoCor3Raw(acceptor_path) as acceptor:
        times_acceptor = acceptor.asarray()
        acceptor_frequency = int(acceptor.frequency)
    if donor_frequency != acceptor_frequency:
        raise ValueError(
            f'Sampling frequency mismatch: {donor_path} is '
            f'{donor_frequency} Hz and {acceptor_path} is '
            f'{acceptor_frequency} Hz'
        )
    if donor_frequency <= 0:
        raise ValueError(f'Invalid sampling frequency in {donor_path}')
    timestamps, detectors = merge_donor_acceptor(times_donor, times_acceptor)
    return timestamps, detectors, 1.0 / donor_frequency


def convert2h5(ch1_fname, ch2_fname, h5_fname,
               description='Super description',
               author='best author',
               author_affiliation='Moscow State Uni',
               sample_name='super sample',
               buffer_name='super buffer',
               dye_names='Cy3, Cy5'):
    """Write one Photon-HDF5 file from a Channel 1 / Channel 2 raw pair.

    Channel 1 is the acceptor and channel 2 is the donor. ``sample_name``,
    ``buffer_name``, and ``dye_names`` are accepted so existing callers keep
    working; they are not written into the file.
    """
    del sample_name, buffer_name, dye_names
    import phconvert.hdf5 as photon_hdf5

    # ch1_fname is the acceptor file, ch2_fname is the donor file.
    timestamps, detectors, timestamps_unit = merge_channel_files(
        ch2_fname,
        ch1_fname,
    )

    photon_data = dict(
        timestamps=timestamps,
        detectors=np.asarray(detectors).astype('uint8'),
        timestamps_specs={'timestamps_unit': timestamps_unit},
    )

    setup = dict(
        num_pixels=2,
        num_spots=1,
        num_spectral_ch=2,
        num_polarization_ch=1,
        num_split_ch=1,
        modulated_excitation=False,
        excitation_alternated=[False],
        lifetime=False,
        excitation_wavelengths=[532e-9],
        excitation_cw=[True],
        detection_wavelengths=[580e-9, 640e-9],
    )

    identity = dict(
        author=author,
        author_affiliation=author_affiliation,
    )

    measurement_specs = dict(
        measurement_type='smFRET',
        detectors_specs={
            'spectral_ch1': [0],
            'spectral_ch2': [1],
        },
    )
    photon_data['measurement_specs'] = measurement_specs

    data = dict(
        description=description,
        photon_data=photon_data,
        setup=setup,
        identity=identity,
    )
    photon_hdf5.save_photon_hdf5(data, h5_fname=h5_fname, overwrite=True)
