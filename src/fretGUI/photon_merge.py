"""Concatenate single-spot smFRET photon streams into one measurement."""

import numpy as np
import fretbursts


class PhotonMergeError(ValueError):
    """The measurements cannot be concatenated as one smFRET stream."""


def merge_smfret_streams(data_list, gap=0.0):
    """Return one single-spot smFRET Data object with timestamps intact.

    Later files start one clock tick, plus ``gap`` seconds, after the
    previous file's last photon.
    """
    if not data_list:
        raise PhotonMergeError('Check at least one measurement.')

    clocks = [_clock(data) for data in data_list]
    if any(not np.isclose(clock, clocks[0], rtol=1e-6, atol=0.0) for clock in clocks[1:]):
        raise PhotonMergeError('These measurements use different clock periods.')

    nanotime_streams = [_nanotimes(data) for data in data_list]
    present = [stream is not None for stream in nanotime_streams]
    if any(present) and not all(present):
        raise PhotonMergeError(
            'Nanotimes must be present on every measurement or on none.'
        )

    times = []
    masks = []
    nanos = []
    cursor = None
    clk = clocks[0]
    gap_clk = int(round(float(gap) / clk)) if clk else 0
    gap_clk = max(gap_clk, 0)
    for data, nano in zip(data_list, nanotime_streams):
        _require_single_spot_smfret(data)
        timestamps, acceptor = _photons(data)
        if nano is not None and nano.size != timestamps.size:
            raise PhotonMergeError('Nanotimes length does not match timestamps.')
        if cursor is None:
            shift = 0
        else:
            shift = cursor + 1 + gap_clk - int(timestamps[0])
        shifted = timestamps.astype('int64') + np.int64(shift)
        times.append(shifted)
        masks.append(acceptor)
        if nano is not None:
            nanos.append(nano)
        cursor = int(shifted[-1])

    merged = fretbursts.Data(
        ph_times_m=[np.concatenate(times)],
        A_em=[np.concatenate(masks)],
        clk_p=float(clk),
        nch=1,
        alternated=False,
        meas_type='smFRET',
    )
    if nanos:
        merged.add(nanotimes=[np.concatenate(nanos)], lifetime=True)
    return merged


def _require_single_spot_smfret(data):
    nch = _field(data, 'nch', 1)
    if int(nch or 1) != 1:
        raise PhotonMergeError(
            'Join Measurements is for continuous single-spot smFRET.'
        )
    meas_type = str(_field(data, 'meas_type') or '')
    alternated = bool(_field(data, 'ALEX')) or bool(_field(data, 'alternated'))
    if alternated or any(token in meas_type for token in ('ALEX', 'PAX', 'PIE')):
        raise PhotonMergeError(
            'Join Measurements is for continuous single-spot smFRET.'
        )


def _photons(data):
    timestamps = _channel_array(data, 'ph_times_m', 'photon timestamps')
    acceptor = _channel_array(data, 'A_em', 'acceptor mask').astype(bool)
    if acceptor.size != timestamps.size:
        raise PhotonMergeError('Acceptor mask length does not match timestamps.')
    return timestamps.astype('int64'), acceptor


def _nanotimes(data):
    value = _field(data, 'nanotimes')
    if not isinstance(value, (list, tuple)) or not value or value[0] is None:
        return None
    array = np.asarray(value[0]).ravel()
    if array.size == 0:
        return None
    return array


def _channel_array(data, name, label):
    value = _field(data, name)
    if not isinstance(value, (list, tuple)) or not value or value[0] is None:
        raise PhotonMergeError(f'A measurement has no {label}.')
    array = np.asarray(value[0]).ravel()
    if array.size == 0:
        raise PhotonMergeError(f'A measurement has no {label}.')
    return array


def _clock(data):
    clk = _field(data, 'clk_p')
    if clk is None:
        raise PhotonMergeError('A measurement has no clock period.')
    return float(clk)


def _field(data, name, default=None):
    if isinstance(data, dict):
        return data.get(name, default)
    return getattr(data, name, default)
