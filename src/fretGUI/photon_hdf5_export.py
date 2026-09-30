"""Build Photon-HDF5 dictionaries from fretbursts Data objects."""

import copy
import os

import numpy as np


_DATA_EXTENSIONS = (
    '.h5', '.hdf5', '.hdf', '.raw', '.sm', '.spc', '.ptu', '.ht3', '.pt3', '.t3r',
)
_INVALID_FILENAME_CHARS = '<>:"/\\|?*'


class PhotonHdf5ExportError(ValueError):
    """The measurement cannot be written as Photon-HDF5."""


def export_file_name(fbsdata):
    """File name for one measurement, using its plot label when set."""
    label = (getattr(fbsdata, 'display_name', '') or '').strip()
    if not label:
        path = getattr(fbsdata, 'path', '') or ''
        label = os.path.basename(path) or 'measurement'
    stem = _stem_name(label)
    return _clean_filename(stem) + '.hdf5'


def destination_paths(datasets, folder):
    """Paths for a batch, with a numeric suffix when labels collide."""
    used = set()
    paths = []
    for item in datasets:
        filename = export_file_name(item)
        stem, ext = os.path.splitext(filename)
        candidate = filename
        number = 2
        while candidate.lower() in used:
            candidate = f'{stem}_{number}{ext}'
            number += 1
        used.add(candidate.lower())
        paths.append(os.path.join(folder, candidate))
    return paths


def data_dict_from_fretbursts(data):
    """Photon-HDF5 mapping for the measurement this Data object actually is."""
    channels = _channels(data)
    if not channels:
        raise PhotonHdf5ExportError(
            'This measurement has no photon timestamps to export. '
            'Joined burst data cannot be written as Photon-HDF5.'
        )

    clk_p = _clock_period(data)
    base, polarized = _classify(data)
    n_spots = max(int(_field(data, 'nch') or 0), max(index for index, _arrays in channels) + 1)
    kind = _kind_setup(base, polarized, n_spots, clk_p)
    multi = len(channels) > 1 or channels[0][0] != 0

    payload = {
        'description': _description(data, base),
        'acquisition_duration': _duration(data, channels, clk_p),
    }
    setup = _setup_group(data, kind)
    payload['setup'] = setup
    sample = _copy_mapping(_field(data, 'sample'))
    if sample is not None:
        payload['sample'] = sample
    for name in ('identity', 'provenance'):
        group = _copy_mapping(_field(data, name))
        if group:
            payload[name] = group

    fname = _field(data, 'fname')
    if isinstance(fname, str) and os.path.isfile(fname):
        payload['_filename'] = fname

    for index, arrays in channels:
        timestamps, detectors, nanotimes, particles = arrays
        group_name = 'photon_data' if not multi and index == 0 else f'photon_data{index}'
        group = {
            'timestamps': np.asarray(timestamps, dtype='int64').ravel(),
            'timestamps_specs': {'timestamps_unit': float(clk_p)},
            'detectors': detectors,
            'measurement_specs': _measurement_specs(
                data, kind, detectors.dtype, index
            ),
        }
        if nanotimes is not None:
            group['nanotimes'] = np.asarray(nanotimes).ravel()
            group['nanotimes_specs'] = _nanotimes_specs(data, index, group['nanotimes'])
        if particles is not None:
            group['particles'] = np.asarray(particles).ravel()
        payload[group_name] = group
    return payload


def _channels(data):
    count = 0
    for name in ('ph_times_m', 'ph_times_t'):
        series = _field(data, name)
        if isinstance(series, (list, tuple)):
            count = max(count, len(series))
    declared = _field(data, 'nch')
    if declared:
        count = max(count, int(declared))

    channels = []
    for index in range(count):
        arrays = _channel_arrays(data, index)
        if arrays is None:
            continue
        channels.append((index, arrays))
    return channels


def _channel_arrays(data, index):
    full = _series(data, 'ph_times_t', index)
    if full is not None and np.asarray(full).size:
        timestamps = np.asarray(full, dtype='int64').ravel()
        detectors = _aligned_detectors(data, 'det_t', index, timestamps)
        nanotimes = _aligned(data, 'nanotimes_t', index, timestamps.size)
        particles = _aligned(data, 'particles_t', index, timestamps.size)
        return timestamps, detectors, nanotimes, particles

    selected = _series(data, 'ph_times_m', index)
    if selected is None or not np.asarray(selected).size:
        return None
    timestamps = np.asarray(selected, dtype='int64').ravel()
    detectors = _aligned_detectors(data, 'detectors', index, timestamps)
    nanotimes = _aligned(data, 'nanotimes', index, timestamps.size)
    particles = _aligned(data, 'particles', index, timestamps.size)
    return timestamps, detectors, nanotimes, particles


def _aligned_detectors(data, name, index, timestamps):
    detectors = _aligned(data, name, index, timestamps.size)
    if detectors is not None:
        return _as_detectors(detectors)
    return _detectors_from_mask(data, index, timestamps)


def _detectors_from_mask(data, index, timestamps):
    donor, acceptor = _spectral_ids(data, index, 2)[:2]
    mask = _series(data, 'A_em', index)
    if mask is not None and np.asarray(mask).ravel().size == timestamps.size:
        acceptor_mask = np.asarray(mask).ravel().astype(bool)
        values = np.where(acceptor_mask, acceptor, donor)
        return values.astype(np.uint8, copy=False)
    return np.zeros(timestamps.size, dtype=np.uint8)


def _as_detectors(array):
    values = np.asarray(array).ravel()
    if values.dtype == bool:
        return values.astype(np.uint8)
    if not np.issubdtype(values.dtype, np.integer):
        return values.astype(np.int64)
    return values


def _aligned(data, name, index, size):
    series = _series(data, name, index)
    if series is None:
        return None
    values = np.asarray(series).ravel()
    if values.size != size:
        return None
    return values


def _series(data, name, index):
    value = _field(data, name)
    if not isinstance(value, (list, tuple)) or index >= len(value):
        return None
    return value[index]


def _classify(data):
    meas_type = str(_field(data, 'meas_type') or '')
    lifetime = bool(_field(data, 'lifetime')) or _has_series(data, 'nanotimes') or _has_series(data, 'nanotimes_t')
    alex = bool(_field(data, 'ALEX')) or 'ALEX' in meas_type
    polarized = bool(_field(data, 'polarization')) or '2pol' in meas_type
    if '1color' in meas_type and not alex and 'PAX' not in meas_type:
        base = 'one-color'
    elif 'PAX' in meas_type:
        base = 'pax'
    elif '3c' in meas_type:
        base = 'usalex-3c'
    elif lifetime and (alex or 'nsALEX' in meas_type or 'PIE' in meas_type):
        base = 'nsalex'
    elif alex or 'usALEX' in meas_type:
        base = 'usalex'
    elif lifetime:
        base = 'smfret-lifetime'
    else:
        base = 'smfret'
    return base, polarized


def _has_series(data, name):
    value = _field(data, name)
    return isinstance(value, (list, tuple)) and any(
        item is not None and np.asarray(item).size for item in value
    )


def _kind_setup(base, polarized, n_spots, clk_p):
    spectral = {'one-color': 1, 'usalex-3c': 3}.get(base, 2)
    polarization = 2 if polarized else 1
    split = 1
    if base == 'nsalex':
        cw = [False, False]
        alternated = [True, True] if polarized else [False, False]
        modulated = True
        lifetime = True
        measurement_type = 'generic' if polarized else 'smFRET-nsALEX'
    elif base == 'usalex':
        cw = [True, True]
        alternated = [True, True]
        modulated = True
        lifetime = False
        measurement_type = 'generic' if polarized else 'smFRET-usALEX'
    elif base == 'usalex-3c':
        cw = [True, True, True]
        alternated = [True, True, True]
        modulated = True
        lifetime = False
        measurement_type = 'generic' if polarized else 'smFRET-usALEX-3c'
    elif base == 'pax':
        cw = [True, True]
        alternated = [False, True]
        modulated = True
        lifetime = False
        measurement_type = 'generic'
    elif base == 'smfret-lifetime':
        cw = [False]
        alternated = [False]
        modulated = True
        lifetime = True
        measurement_type = 'generic' if polarized else 'smFRET'
    elif base == 'one-color':
        cw = [True]
        alternated = [False]
        modulated = False
        lifetime = False
        measurement_type = 'generic'
        spectral = 1
    else:
        cw = [True]
        alternated = [False]
        modulated = False
        lifetime = False
        measurement_type = 'generic' if polarized else 'smFRET'
    return {
        'base': base,
        'clk_p': clk_p,
        'measurement_type': measurement_type,
        'num_pixels': int(spectral * polarization * split * n_spots),
        'num_spots': int(n_spots),
        'num_spectral_ch': int(spectral),
        'num_polarization_ch': int(polarization),
        'num_split_ch': int(split),
        'modulated_excitation': bool(modulated),
        'lifetime': bool(lifetime),
        'excitation_cw': np.array(cw, dtype=bool),
        'excitation_alternated': np.array(alternated, dtype=bool),
    }


def _setup_group(data, kind):
    setup = _copy_mapping(_field(data, 'setup')) or {}
    for name in (
        'num_pixels',
        'num_spots',
        'num_spectral_ch',
        'num_polarization_ch',
        'num_split_ch',
        'modulated_excitation',
        'lifetime',
        'excitation_cw',
        'excitation_alternated',
    ):
        setup[name] = kind[name]
    if kind['lifetime'] and not bool(np.all(kind['excitation_cw'])):
        rate = _laser_rate(data, kind['clk_p'])
        setup.setdefault(
            'laser_repetition_rates',
            np.full(len(kind['excitation_cw']), rate, dtype=float),
        )
    return setup


def _measurement_specs(data, kind, detectors_dtype, index):
    specs = {'measurement_type': kind['measurement_type']}
    detectors_specs = {}
    if kind['num_spectral_ch'] > 1:
        for channel, detector_id in enumerate(_spectral_ids(data, index, kind['num_spectral_ch'])):
            detectors_specs[f'spectral_ch{channel + 1}'] = np.array(
                [detector_id], dtype=detectors_dtype
            )
    if kind['num_polarization_ch'] > 1:
        parallel, perpendicular = _polarization_ids(data, index)
        detectors_specs['polarization_ch1'] = np.array([parallel], dtype=detectors_dtype)
        detectors_specs['polarization_ch2'] = np.array([perpendicular], dtype=detectors_dtype)
    if detectors_specs:
        specs['detectors_specs'] = detectors_specs
    if kind['base'] in ('usalex', 'usalex-3c', 'pax', 'nsalex'):
        _add_alex_fields(specs, data, required=kind['base'] != 'nsalex')
    if kind['lifetime'] and not bool(np.all(kind['excitation_cw'])):
        specs['laser_repetition_rate'] = float(_laser_rate(data, kind['clk_p']))
    return specs


def _add_alex_fields(specs, data, required):
    period = _field(data, 'alex_period')
    if period is None and required:
        raise PhotonHdf5ExportError(
            'This alternated measurement has no alex_period to export.'
        )
    if period is not None:
        specs['alex_period'] = int(np.atleast_1d(period).ravel()[0])
        offset = _field(data, 'offset', _field(data, 'alex_offset', 0))
        specs['alex_offset'] = int(np.atleast_1d(offset).ravel()[0])
    for field_name, attribute in (
        ('alex_excitation_period1', 'D_ON'),
        ('alex_excitation_period2', 'A_ON'),
    ):
        value = _field(data, attribute)
        if value is not None:
            specs[field_name] = np.atleast_1d(np.asarray(value)).astype('int64').ravel()


def _spectral_ids(data, index, count):
    donor, acceptor = 0, 1
    spec = _field(data, 'det_donor_accept')
    if isinstance(spec, (list, tuple)) and index < len(spec):
        pair = spec[index]
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            donor = int(np.atleast_1d(pair[0]).ravel()[0])
            acceptor = int(np.atleast_1d(pair[1]).ravel()[0])
    ids = [donor, acceptor]
    next_id = max(ids) + 1
    while len(ids) < count:
        ids.append(next_id)
        next_id += 1
    return ids[:count]


def _polarization_ids(data, index):
    spec = _field(data, 'det_p_s_pol')
    if isinstance(spec, (list, tuple)) and index < len(spec):
        pair = spec[index]
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return (
                int(np.atleast_1d(pair[0]).ravel()[0]),
                int(np.atleast_1d(pair[1]).ravel()[0]),
            )
    return 0, 1


def _nanotimes_specs(data, index, nanotimes):
    info = {}
    params = _field(data, 'nanotimes_params')
    if isinstance(params, (list, tuple)) and index < len(params) and isinstance(params[index], dict):
        info = params[index]
    unit = info.get('tcspc_unit', _field(data, 'tcspc_unit', 1e-12))
    bins = info.get('tcspc_num_bins')
    if bins is None:
        bins = int(np.max(nanotimes)) + 1 if nanotimes.size else 1
    specs = {
        'tcspc_unit': float(unit),
        'tcspc_num_bins': int(bins),
    }
    if info.get('tcspc_range') is not None:
        specs['tcspc_range'] = float(info['tcspc_range'])
    return specs


def _laser_rate(data, clk_p):
    value = _field(data, 'laser_repetition_rate')
    if value is not None:
        return float(np.atleast_1d(value).ravel()[0])
    setup = _field(data, 'setup')
    if isinstance(setup, dict) and setup.get('laser_repetition_rates') is not None:
        return float(np.atleast_1d(setup['laser_repetition_rates']).ravel()[0])
    if clk_p:
        return float(1.0 / clk_p)
    return 8e7


def _clock_period(data):
    clk_p = _field(data, 'clk_p')
    if clk_p is None:
        return 12.5e-9
    return float(clk_p)


def _duration(data, channels, clk_p):
    stored = _field(data, 'acquisition_duration')
    if stored is not None:
        return float(np.atleast_1d(stored).ravel()[0])
    span = 0.0
    for _index, arrays in channels:
        timestamps = arrays[0]
        if timestamps.size:
            span = max(span, float(timestamps[-1] - timestamps[0]) * clk_p)
    return span


def _description(data, base):
    text = _text(_field(data, 'description'))
    if text:
        return text
    meas_type = _text(_field(data, 'meas_type')) or base
    return f'FRETBurstStudio export ({meas_type})'


def _copy_mapping(value):
    if not isinstance(value, dict):
        return None
    try:
        return copy.deepcopy(value)
    except Exception:
        return None


def _text(value):
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace').strip()
    return str(value).strip()


def _field(data, name, default=None):
    if isinstance(data, dict):
        return data.get(name, default)
    return getattr(data, name, default)


def _stem_name(name):
    root, ext = os.path.splitext(name)
    if ext.lower() in _DATA_EXTENSIONS:
        return root
    return name


def _clean_filename(name):
    cleaned = ''.join(
        '_' if char in _INVALID_FILENAME_CHARS else char
        for char in name
    ).strip().rstrip('.')
    return cleaned or 'measurement'
