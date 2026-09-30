"""Descriptive Photon-HDF5 fields filled by the user and remembered locally."""

import json

import numpy as np
from Qt import QtCore


SETTINGS_KEY = 'photonHdf5Metadata'

_WARNED = 'Photon-HDF5 warns if this field is missing.'

METADATA_FIELDS = (
    {
        'key': 'description',
        'label': 'Description',
        'section': 'File',
        'multiline': True,
        'tooltip': 'A comment stored at /description.',
    },
    {
        'key': 'author',
        'label': 'Author',
        'section': 'Identity',
        'tooltip': _WARNED,
    },
    {
        'key': 'author_affiliation',
        'label': 'Author affiliation',
        'section': 'Identity',
        'tooltip': _WARNED,
    },
    {
        'key': 'creator',
        'label': 'Creator',
        'section': 'Identity',
        'tooltip': 'Person or group who created this Photon-HDF5 file.',
    },
    {
        'key': 'creator_affiliation',
        'label': 'Creator affiliation',
        'section': 'Identity',
        'tooltip': 'Company or institution the creator is affiliated with.',
    },
    {
        'key': 'funding',
        'label': 'Funding',
        'section': 'Identity',
        'tooltip': 'Funding sources or grants used to produce the data.',
    },
    {
        'key': 'license',
        'label': 'License',
        'section': 'Identity',
        'tooltip': 'License under which the data is released.',
    },
    {
        'key': 'doi',
        'label': 'DOI',
        'section': 'Identity',
        'tooltip': 'Digital Object Identifier for the Photon-HDF5 file.',
    },
    {
        'key': 'url',
        'label': 'URL',
        'section': 'Identity',
        'tooltip': 'URL where the Photon-HDF5 file can be downloaded.',
    },
    {
        'key': 'sample_name',
        'label': 'Sample name',
        'section': 'Sample',
        'tooltip': 'Descriptive name for the sample.',
    },
    {
        'key': 'sample_name_from_filename',
        'label': 'Use filename',
        'section': 'Sample',
        'checkbox': True,
        'tooltip': 'Use each file name as the sample name.',
    },
    {
        'key': 'buffer_name',
        'label': 'Buffer',
        'section': 'Sample',
        'tooltip': 'Descriptive name for the buffer.',
    },
    {
        'key': 'dye_names',
        'label': 'Dye names',
        'section': 'Sample',
        'placeholder': 'Cy3B, ATTO647N',
        'tooltip': 'Comma-separated fluorophore names.',
    },
    {
        'key': 'num_dyes',
        'label': 'Number of dyes',
        'section': 'Sample',
        'tooltip': 'Leave blank to use the number of dye names.',
    },
    {
        'key': 'excitation_wavelengths_nm',
        'label': 'Excitation wavelengths (nm)',
        'section': 'Setup',
        'placeholder': '532, 640',
        'tooltip': _WARNED + ' One value per excitation source.',
    },
    {
        'key': 'detection_wavelengths_nm',
        'label': 'Detection wavelengths (nm)',
        'section': 'Setup',
        'placeholder': '570, 670',
        'tooltip': _WARNED + ' One value per detection channel.',
    },
    {
        'key': 'excitation_powers_mw',
        'label': 'Excitation powers (mW)',
        'section': 'Setup',
        'placeholder': '100, 80',
        'tooltip': 'Power entering the optical system, one value per excitation source.',
    },
)

_IDENTITY_KEYS = (
    'author',
    'author_affiliation',
    'creator',
    'creator_affiliation',
    'funding',
    'license',
    'doi',
    'url',
)
_SAMPLE_KEYS = ('buffer_name', 'dye_names')


def settings_store():
    """Same organization and application names as the main window."""
    return QtCore.QSettings('FretBurstStudio', 'FretBurstStudio')


def normalize_metadata(fields):
    """Flat form values, with a string for every known field."""
    source = fields or {}
    return {
        spec['key']: str(source.get(spec['key'], '') or '').strip()
        for spec in METADATA_FIELDS
    }


def metadata_is_blank(fields):
    return not any(normalize_metadata(fields).values())


def load_metadata(settings=None):
    settings = settings_store() if settings is None else settings
    raw = settings.value(SETTINGS_KEY, '')
    if raw is None or raw == '':
        return normalize_metadata({})
    if isinstance(raw, dict):
        return normalize_metadata(raw)
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return normalize_metadata({})
    if not isinstance(parsed, dict):
        return normalize_metadata({})
    return normalize_metadata(parsed)


def save_metadata(fields, settings=None):
    settings = settings_store() if settings is None else settings
    normalized = normalize_metadata(fields)
    settings.setValue(
        SETTINGS_KEY,
        json.dumps(normalized, ensure_ascii=False),
    )
    settings.sync()
    return normalized


def apply_export_metadata(payload, fields, filename=''):
    """Overlay filled form values. Blank fields leave the file's own values."""
    if metadata_is_blank(fields):
        return payload
    form = normalize_metadata(fields)
    payload = dict(payload)

    description = form['description']
    if description:
        payload['description'] = description

    _merge_text_group(payload, 'identity', form, _IDENTITY_KEYS)
    _merge_sample(payload, form, filename)
    _merge_setup_arrays(payload, form)
    return payload


def _merge_text_group(payload, group_name, form, keys):
    group = dict(payload.get(group_name) or {})
    wrote = False
    for key in keys:
        text = form[key]
        if text:
            group[key] = text
            wrote = True
    if wrote or group_name in payload:
        if group:
            payload[group_name] = group


def _merge_sample(payload, form, filename=''):
    sample = dict(payload.get('sample') or {})
    wrote = False
    sample_name = _sample_name(form, filename)
    if sample_name:
        sample['sample_name'] = sample_name
        wrote = True
    for key in _SAMPLE_KEYS:
        text = form[key]
        if text:
            sample[key] = text
            wrote = True
    num_dyes = _num_dyes(form)
    if num_dyes is not None:
        sample['num_dyes'] = num_dyes
        wrote = True
    if wrote or 'sample' in payload:
        if sample:
            payload['sample'] = sample


def _sample_name(form, filename):
    if _checked(form.get('sample_name_from_filename')):
        return str(filename or '').strip()
    return form.get('sample_name', '')


def _checked(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes')


def _num_dyes(form):
    text = form['num_dyes']
    if text:
        try:
            return int(text)
        except ValueError:
            print(
                f'Export HDF5: number of dyes {text!r} is not an integer; '
                'left unchanged.'
            )
            return None
    names = [part.strip() for part in form['dye_names'].split(',') if part.strip()]
    if names:
        return len(names)
    return None


def _merge_setup_arrays(payload, form):
    setup = dict(payload.get('setup') or {})
    excitation_count = _excitation_count(setup)
    detection_count = _detection_count(setup)
    _assign_array(
        setup,
        'excitation_wavelengths',
        _scaled_floats(form['excitation_wavelengths_nm'], 1e-9, 'excitation wavelengths'),
        excitation_count,
        'excitation sources',
    )
    _assign_array(
        setup,
        'detection_wavelengths',
        _scaled_floats(form['detection_wavelengths_nm'], 1e-9, 'detection wavelengths'),
        detection_count,
        'detection channels',
    )
    _assign_array(
        setup,
        'excitation_input_powers',
        _scaled_floats(form['excitation_powers_mw'], 1e-3, 'excitation powers'),
        excitation_count,
        'excitation sources',
    )
    if setup:
        payload['setup'] = setup


def _assign_array(setup, key, values, expected, noun):
    if values is None:
        return
    if expected is None or len(values) != expected:
        count = 'an unknown number of' if expected is None else str(expected)
        print(
            f'Export HDF5: {key} has {len(values)} values but this file has '
            f'{count} {noun}; left unchanged.'
        )
        return
    setup[key] = np.asarray(values, dtype=float)


def _scaled_floats(text, scale, label):
    if not text:
        return None
    try:
        values = _parse_floats(text)
    except ValueError:
        print(f'Export HDF5: could not read {label} ({text!r}); left unchanged.')
        return None
    return [value * scale for value in values]


def _parse_floats(text):
    parts = [part.strip() for part in text.replace(';', ',').split(',')]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError(text)
    return [float(part) for part in parts]


def _excitation_count(setup):
    values = setup.get('excitation_cw')
    if values is None:
        return None
    array = np.atleast_1d(values).ravel()
    if array.size == 0:
        return None
    return int(array.size)


def _detection_count(setup):
    value = setup.get('num_spectral_ch')
    if value is None:
        return None
    try:
        return int(np.atleast_1d(value).ravel()[0])
    except (TypeError, ValueError):
        return None
