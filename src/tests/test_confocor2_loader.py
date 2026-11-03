"""Parity tests for the optimized ConfoCor2 RAW loader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from fretGUI.misc.fcsfiles import ConfoCor2Raw

HEADER = b'ConfoCor 2 - Raw data file 1.0'
# Header is validated with startswith on the first 30 bytes read from the file.
HEADER_PADDED = HEADER + b'\x00' * (30 - len(HEADER))

SAMPLE_DIR = (
    Path(__file__).resolve().parents[2] / 'samle_files' / 'lsm510'
)


def _reference_asarray(data: np.ndarray):
    """Original expand-and-mask ConfoCor2 decode (pre-optimization)."""
    if data.size == 0:
        empty = np.empty(0, dtype='u8')
        return empty, empty
    times = np.empty((len(data) // 2, 4), dtype='u8')
    times[:, 0] = data[::2]
    times[:, 1:] = 1
    times = times.flatten()
    np.cumsum(times, out=times)
    flags = np.repeat(data[1::2], 8).reshape(-1, 8)
    flags &= np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype='u1')
    ch0 = np.take(times, np.where(flags[:, 0::2].flatten() != 0)[0])
    ch1 = np.take(times, np.where(flags[:, 1::2].flatten() != 0)[0])
    return ch0, ch1


def _reference_merge(times_donor, times_acceptor):
    """Original hstack/vstack merge used by LSM510Node.load."""
    df = np.hstack([
        np.vstack([times_donor, np.zeros(times_donor.size)]),
        np.vstack([times_acceptor, np.ones(times_acceptor.size)]),
    ]).T
    df_sorted = df[np.argsort(df[:, 0])].T
    timestamps = df_sorted[0].astype('int64')
    detectors = df_sorted[1].astype('bool')
    return timestamps, detectors


def _fast_merge(times_donor, times_acceptor):
    merged = np.concatenate((times_donor, times_acceptor))
    order = np.argsort(merged.astype(np.float64, copy=False))
    timestamps = merged[order].astype(np.int64, copy=False)
    detectors = order >= times_donor.size
    return timestamps, detectors


def _write_raw(path: Path, words: bytes):
    path.write_bytes(HEADER_PADDED + words)


class ConfoCor2LoaderTests(unittest.TestCase):
    def test_synthetic_channels_match_reference(self):
        # Word layout: (delta, flags). Flags bit0/2/4/6 = ch0 slots 0..3,
        # bit1/3/5/7 = ch1 slots 0..3.
        words = bytes([
            5, 0b00000001,  # ch0 @ slot0 -> time 5
            0, 0b00000010,  # ch1 @ slot0 -> time 5+3+0 = 8
            2, 0b00001100,  # ch0 @ slot1, ch1 @ slot1 after +2
            1, 0b11000000,  # ch0 @ slot3, ch1 @ slot3
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.001'
            _write_raw(path, words)
            with ConfoCor2Raw(str(path)) as fcs:
                ch0, ch1 = fcs.asarray()
                self.assertEqual(fcs.frequency, 20_000_000)

        raw = np.frombuffer(words, dtype='u1')
        ref0, ref1 = _reference_asarray(raw)
        np.testing.assert_array_equal(ch0, ref0)
        np.testing.assert_array_equal(ch1, ref1)

    def test_synthetic_merge_matches_reference(self):
        words = bytes([
            5, 0b00000001,
            0, 0b00000010,
            2, 0b00001100,
            1, 0b11000000,
        ])
        raw = np.frombuffer(words, dtype='u1')
        ch0, ch1 = _reference_asarray(raw)
        # Default LSM510 mapping: donor=ch1, acceptor=ch0
        ref_ts, ref_det = _reference_merge(ch1, ch0)
        fast_ts, fast_det = _fast_merge(ch1, ch0)
        np.testing.assert_array_equal(fast_ts, ref_ts)
        np.testing.assert_array_equal(fast_det, ref_det)

    def test_empty_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'empty.001'
            _write_raw(path, b'')
            with ConfoCor2Raw(str(path)) as fcs:
                ch0, ch1 = fcs.asarray()
        self.assertEqual(ch0.size, 0)
        self.assertEqual(ch1.size, 0)
        self.assertEqual(ch0.dtype, np.dtype('u8'))
        self.assertEqual(ch1.dtype, np.dtype('u8'))

    @unittest.skipUnless(SAMPLE_DIR.is_dir(), 'samle_files/lsm510 not present')
    def test_sample_files_match_reference(self):
        samples = sorted(
            p for p in SAMPLE_DIR.iterdir()
            if p.is_file() and not p.name.startswith('.')
        )
        self.assertTrue(samples, 'expected ConfoCor2 sample files')
        for path in samples:
            with self.subTest(file=path.name):
                with open(path, 'rb') as fh:
                    header = fh.read(30)
                    self.assertTrue(
                        header.startswith(HEADER),
                        f'{path.name} is not a ConfoCor2 RAW file',
                    )
                    raw = np.fromfile(fh, dtype='u1')

                ref0, ref1 = _reference_asarray(raw)
                with ConfoCor2Raw(str(path)) as fcs:
                    ch0, ch1 = fcs.asarray()
                    self.assertEqual(fcs.frequency, 20_000_000)
                    self.assertEqual(1.0 / fcs.frequency, 5e-8)

                np.testing.assert_array_equal(ch0, ref0)
                np.testing.assert_array_equal(ch1, ref1)

                # Default channel map: donor=1, acceptor=0
                ref_ts, ref_det = _reference_merge(ch1, ch0)
                fast_ts, fast_det = _fast_merge(ch1, ch0)
                np.testing.assert_array_equal(fast_ts, ref_ts)
                np.testing.assert_array_equal(fast_det, ref_det)


if __name__ == '__main__':
    unittest.main()
