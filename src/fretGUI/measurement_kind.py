"""Short labels for the excitation scheme of a loaded measurement."""

import numpy as np


_CHIPS = {
    'CW': 'Continuous-wave, donor-only excitation (smFRET).',
    'ALEX': (
        'Alternating laser excitation: both lasers are continuous-wave '
        'and switched on a microsecond period (smFRET-usALEX).'
    ),
    'PIE': (
        'Pulse-interleaved excitation: both lasers are pulsed and '
        'interleaved (Photon-HDF5 smFRET-nsALEX).'
    ),
    'PAX': 'Pulsed acceptor excitation (PAX).',
    'Pulsed': 'Donor-only pulsed excitation with TCSPC microtimes (smFRET).',
    '1C': 'One detection color (smFRET-1color).',
    'µt': 'Microtimes (TCSPC nanotimes) are present.',
    '2pol': 'Two polarization channels.',
}

# PIE and Pulsed already mean the file has TCSPC microtimes.
_MICROTIME_IMPLIED = frozenset(('PIE', 'Pulsed'))


def method_chips(data):
    """Excitation chip, then µt and 2pol when those facts are separate."""
    if data is None:
        return []
    meas_type = _meas_type(data)
    code = _excitation_code(data, meas_type)
    chips = []
    if code:
        chips.append(_chip(code))
    if _has_microtimes(data) and code not in _MICROTIME_IMPLIED:
        chips.append(_chip('µt'))
    if _two_polarizations(data, meas_type):
        chips.append(_chip('2pol'))
    return chips


def method_type_line(data):
    """Plain-language type sentence, or the raw meas_type when unrecognized."""
    chips = method_chips(data)
    if chips:
        return ' '.join(chip['tooltip'] for chip in chips)
    return _meas_type(data)


def _chip(code):
    return {'code': code, 'tooltip': _CHIPS[code]}


def _excitation_code(data, meas_type):
    if '1color' in meas_type:
        return '1C'
    if 'PAX' in meas_type:
        return 'PAX'
    if 'nsALEX' in meas_type or 'PIE' in meas_type:
        return 'PIE'
    alex = _as_bool(_field(data, 'ALEX', False)) or 'ALEX' in meas_type
    if 'usALEX' in meas_type or alex:
        return 'ALEX'
    if not _donor_only(meas_type):
        return ''
    if _as_bool(_field(data, 'lifetime', False)):
        return 'Pulsed'
    return 'CW'


def _donor_only(meas_type):
    if any(token in meas_type for token in ('1color', 'PAX', 'ALEX', 'PIE')):
        return False
    return 'smFRET' in meas_type


def _two_polarizations(data, meas_type):
    if '2pol' in meas_type or _as_bool(_field(data, 'polarization', False)):
        return True
    setup = _field(data, 'setup')
    if not isinstance(setup, dict):
        return False
    count = setup.get('num_polarization_ch')
    if count is None:
        return False
    try:
        return int(np.atleast_1d(count).ravel()[0]) > 1
    except (TypeError, ValueError):
        return False


def _has_microtimes(data):
    return _series_present(data, 'nanotimes') or _series_present(data, 'nanotimes_t')


def _series_present(data, name):
    value = _field(data, name)
    if isinstance(value, (list, tuple)):
        return any(_nonempty(item) for item in value)
    return _nonempty(value)


def _nonempty(value):
    if value is None:
        return False
    try:
        return np.asarray(value).size > 0
    except (TypeError, ValueError):
        return False


def _meas_type(data):
    value = _field(data, 'meas_type', '')
    if isinstance(value, bytes):
        value = value.decode('utf-8', 'replace')
    return str(value or '')


def _as_bool(value):
    if isinstance(value, (list, tuple, np.ndarray)):
        array = np.atleast_1d(value).ravel()
        return bool(array.size and array[0])
    return bool(value)


def _field(data, name, default=None):
    if isinstance(data, dict):
        return data.get(name, default)
    return getattr(data, name, default)
