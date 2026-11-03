"""Grouping and merge tests for the ConfoCor3 / LSM710 loader."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path

import NodeGraphQt
import numpy as np
from Qt import QtWidgets

import fretGUI.custom_nodes.custom_nodes as custom_nodes
from fretGUI.misc.convert_lsm710 import (
    experiment_label,
    group_channel_files,
    merge_channel_files,
)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

SAMPLE_DIR = Path(__file__).resolve().parents[2] / 'samle_files' / 'lsm710'

_PREFIX = b'Carl Zeiss ConfoCor3 - raw data file - version 3.000 - Channel'
_IDENTIFIER = struct.pack('<IIII', 1, 2, 3, 4)


def write_raw(
    path,
    channel,
    delays,
    repetition=0,
    position=0,
    kinetic=0,
    frequency=20_000_000,
    identifier=_IDENTIFIER,
):
    """Write a minimal ConfoCor3 raw file. ``channel`` is zero-based."""
    header = _PREFIX + b' ' + str(channel + 1).encode('ascii')
    if len(header) != 64:
        raise AssertionError(f'header for channel {channel} is {len(header)} bytes')
    payload = struct.pack(
        '<16sIIII32s',
        identifier,
        int(position),
        int(kinetic),
        int(repetition),
        int(frequency),
        b'\x00' * 32,
    )
    data = np.asarray(list(delays), dtype='<u4').tobytes()
    Path(path).write_bytes(header + payload + data)


def _arrivals(delays):
    return np.cumsum(np.asarray(list(delays), dtype='<u4').astype('u8'))


def _reference_merge(times_donor, times_acceptor):
    """Original convert2h5 hstack/argsort merge. Acceptor mask is 1."""
    df = np.hstack([
        np.vstack([times_donor, np.zeros(times_donor.size)]),
        np.vstack([times_acceptor, np.ones(times_acceptor.size)]),
    ]).T
    df_sorted = df[np.argsort(df[:, 0])].T
    timestamps = df_sorted[0].astype('int64')
    detectors = df_sorted[1].astype(bool)
    return timestamps, detectors


class ConfoCor3GroupingTests(unittest.TestCase):
    @unittest.skipUnless(SAMPLE_DIR.is_dir(), 'samle_files/lsm710 not present')
    def test_sample_files_group_into_four_pairs(self):
        paths = [
            path for path in SAMPLE_DIR.iterdir()
            if path.is_file() and not path.name.startswith('.')
        ]
        self.assertGreaterEqual(len(paths), 2)
        paths.sort(key=lambda path: path.name, reverse=True)

        experiments, pending, messages = group_channel_files(
            [str(path) for path in paths]
        )

        self.assertEqual(messages, [])
        self.assertEqual(pending, {})
        self.assertEqual(
            [item['key'] for item in experiments],
            sorted(item['key'] for item in experiments),
        )
        used = []
        for item in experiments:
            self.assertEqual(item['row_path'], item['channels'][0])
            self.assertTrue(item['channels'][0].endswith('_Ch1.raw'))
            self.assertTrue(item['channels'][1].endswith('_Ch2.raw'))
            self.assertEqual(experiment_label(item['channels'][1]), item['label'])
            self.assertNotRegex(item['label'], r'_Ch\d+$')
            used.extend(item['channels'].values())
        self.assertEqual(
            sorted(used),
            sorted(str(path.resolve()) for path in paths),
        )
        paired = [
            item for item in experiments
            if item['label'].endswith(
                '9b882010464bf98b12673a972682a13e_R1_P1_K1'
            )
        ]
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0]['key'][1:], (0, 0, 0))

    def test_incomplete_group_stays_pending_until_partner_arrives(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ch1 = folder / 'meas_Ch1.raw'
            ch2 = folder / 'meas_Ch2.raw'
            write_raw(ch1, 0, [4])
            write_raw(ch2, 1, [2])

            experiments, pending, messages = group_channel_files([str(ch1)])
            self.assertEqual(experiments, [])
            self.assertEqual(messages, [])
            self.assertEqual(len(pending), 1)
            only = next(iter(pending.values()))
            self.assertEqual(set(only), {0})

            experiments, pending, messages = group_channel_files(
                [str(ch2)],
                pending,
            )

        self.assertEqual(messages, [])
        self.assertEqual(pending, {})
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0]['label'], 'meas')
        self.assertEqual(experiments[0]['channels'][0], str(ch1.resolve()))
        self.assertEqual(experiments[0]['channels'][1], str(ch2.resolve()))

    def test_invalid_file_does_not_drop_a_valid_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            bad = folder / 'noise.raw'
            bad.write_bytes(b'not a confocor file' + b'\x00' * 128)
            ch1 = folder / 'pair_Ch1.raw'
            ch2 = folder / 'pair_Ch2.raw'
            write_raw(ch1, 0, [5, 1])
            write_raw(ch2, 1, [3])

            experiments, pending, messages = group_channel_files(
                [str(bad), str(ch2), str(ch1)]
            )

        self.assertEqual(pending, {})
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0]['channels'][0], str(ch1.resolve()))
        self.assertEqual(experiments[0]['channels'][1], str(ch2.resolve()))
        self.assertTrue(any(str(bad) in message for message in messages))
        self.assertTrue(
            any(message.startswith('Not a ConfoCor3 raw file:') for message in messages)
        )

    def test_duplicate_channel_keeps_the_first_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = folder / 'first_Ch1.raw'
            second = folder / 'second_Ch1.raw'
            donor = folder / 'first_Ch2.raw'
            write_raw(first, 0, [1])
            write_raw(second, 0, [9])
            write_raw(donor, 1, [2])
            experiments, pending, messages = group_channel_files(
                [str(first), str(second), str(donor)]
            )

        self.assertEqual(pending, {})
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0]['channels'][0], str(first.resolve()))
        self.assertTrue(any('Duplicate Ch1' in message for message in messages))

    def test_synthetic_merge_matches_script(self):
        # Channel 1 (index 0) is the acceptor. Channel 2 (index 1) is the donor.
        # Delays include a shared arrival so tie order is part of the comparison.
        acceptor_delays = [5, 1, 4]
        donor_delays = [5, 5, 2]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ch1 = folder / 'pair_Ch1.raw'
            ch2 = folder / 'pair_Ch2.raw'
            write_raw(ch1, 0, acceptor_delays)
            write_raw(ch2, 1, donor_delays)
            timestamps, detectors, clk_p = merge_channel_files(str(ch2), str(ch1))

        ref_ts, ref_det = _reference_merge(
            _arrivals(donor_delays),
            _arrivals(acceptor_delays),
        )
        np.testing.assert_array_equal(timestamps, ref_ts)
        np.testing.assert_array_equal(detectors, ref_det)
        self.assertEqual(clk_p, 5e-8)
        self.assertEqual(int(timestamps[0]), int(_arrivals(donor_delays)[0]))
        self.assertFalse(bool(detectors[0]))

    def test_frequency_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ch1 = folder / 'pair_Ch1.raw'
            ch2 = folder / 'pair_Ch2.raw'
            write_raw(ch1, 0, [1], frequency=20_000_000)
            write_raw(ch2, 1, [1], frequency=10_000_000)
            with self.assertRaises(ValueError) as caught:
                merge_channel_files(str(ch2), str(ch1))
        self.assertIn('Sampling frequency mismatch', str(caught.exception))


class LSM710NodeTests(unittest.TestCase):
    def setUp(self):
        self.graph = NodeGraphQt.NodeGraph()
        self.graph.register_nodes([custom_nodes.LSM710Node])
        self.node = self.graph.create_node('Loaders.LSM710Node')
        self.widget = self.node.file_widget.path_widget

    def test_accepts_raw_drops_only(self):
        self.assertTrue(self.node.accepts_dropped_files([
            '/tmp/a.raw',
            '/tmp/b.RAW',
        ]))
        self.assertFalse(self.node.accepts_dropped_files([
            '/tmp/a.raw',
            '/tmp/b.h5',
        ]))
        self.assertEqual(
            self.node.view.toolTip(),
            custom_nodes.LSM710Node.DESCRIPTION,
        )
        settings = self.node.advanced_settings.settings_widget
        donor = settings._combos['donor_channel']
        acceptor = settings._combos['acceptor_channel']
        self.assertEqual(
            [donor.itemText(index) for index in range(donor.count())],
            ['Ch1', 'Ch2'],
        )
        self.assertEqual(donor.currentData(), 1)
        self.assertEqual(acceptor.currentText(), 'Ch1')
        self.assertEqual(acceptor.currentData(), 0)

    def test_partner_added_later_creates_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ch1 = folder / 'meas_Ch1.raw'
            ch2 = folder / 'meas_Ch2.raw'
            write_raw(ch1, 0, [4, 1])
            write_raw(ch2, 1, [2, 6])

            self.widget.process_files([str(ch1)])
            self.assertEqual(self.widget.get_paths(), [])
            self.assertEqual(len(self.node._pending), 1)

            self.widget.process_files([str(ch2)])
            entries = self.widget.get_file_entries()
            self.assertEqual(len(entries), 1)
            path_id, row_path, checked, _color, display_name = entries[0]
            self.assertEqual(row_path, str(ch1.resolve()))
            self.assertTrue(checked)
            self.assertEqual(display_name, 'meas')
            self.assertEqual(self.node._pending, {})
            record = self.node._experiments[row_path]
            self.assertEqual(record['channels'][1], str(ch2.resolve()))
            row = self.widget._row_for_path(row_path)
            self.assertIn('Ch1:', row.toolTip())
            self.assertIn(str(ch1.resolve()), row.toolTip())
            self.assertIn('Ch2:', row.toolTip())
            self.assertIn(str(ch2.resolve()), row.toolTip())
            self.assertIsNotNone(path_id)

            loaded = self.node.execute()
            loaded_tip = row.text_field.toolTip()
            self.assertNotIn('Not loaded', loaded_tip)
            self.assertTrue(loaded_tip.startswith('Loaded:'))
            self.assertIn('Ch1:', loaded_tip)
            self.assertIn(str(ch2.resolve()), loaded_tip)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].display_name, 'meas')
        self.assertEqual(loaded[0].data.name, 'meas')
        self.assertEqual(loaded[0].data.clk_p, 5e-8)
        timestamps = np.asarray(loaded[0].data.ph_times_m[0])
        detectors = np.asarray(loaded[0].data.A_em[0])
        ref_ts, ref_det = _reference_merge(_arrivals([2, 6]), _arrivals([4, 1]))
        np.testing.assert_array_equal(timestamps, ref_ts)
        np.testing.assert_array_equal(detectors, ref_det)

    def test_invalid_file_does_not_drop_the_rest_of_the_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            bad = folder / 'noise.raw'
            bad.write_bytes(b'this is not a raw header')
            ch1 = folder / 'pair_Ch1.raw'
            ch2 = folder / 'pair_Ch2.raw'
            write_raw(ch1, 0, [8])
            write_raw(ch2, 1, [3])
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.widget.process_files([str(bad), str(ch1), str(ch2)])
            entries = self.widget.get_file_entries()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], str(ch1.resolve()))
        self.assertEqual(entries[0][4], 'pair')
        printed = stdout.getvalue()
        self.assertIn('Not a ConfoCor3 raw file:', printed)
        self.assertIn(str(bad), printed)

    @unittest.skipUnless(SAMPLE_DIR.is_dir(), 'samle_files/lsm710 not present')
    def test_sample_selection_becomes_four_rows(self):
        paths = [
            path for path in SAMPLE_DIR.iterdir()
            if path.is_file() and not path.name.startswith('.')
        ]
        paths.sort(key=lambda path: path.name, reverse=True)
        experiments, _pending, messages = group_channel_files(
            [str(path) for path in paths]
        )
        self.assertEqual(messages, [])
        self.widget.process_files([str(path) for path in paths])
        labels = [entry[4] for entry in self.widget.get_file_entries()]
        self.assertEqual(labels, [item['label'] for item in experiments])
        self.assertEqual(self.node._pending, {})
        for _path_id, row_path, _checked, _color, label in self.widget.get_file_entries():
            record = self.node._experiments[row_path]
            self.assertEqual(record['label'], label)
            self.assertTrue(record['channels'][0].endswith('_Ch1.raw'))
            self.assertTrue(record['channels'][1].endswith('_Ch2.raw'))


if __name__ == '__main__':
    unittest.main()
