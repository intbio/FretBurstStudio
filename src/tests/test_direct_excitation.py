import unittest

import numpy as np
from fretbursts.burstlib import Data
from fretbursts.fretmath import correct_E_gamma_leak_dir

from fretGUI.burst_corrections import (
    DIRECT_EXCITATION_TOOLTIP,
    install_proportional_direct_excitation,
)


install_proportional_direct_excitation()


class _Bursts:
    def __init__(self, count):
        self.num_bursts = count


def _counts(donor, acceptor):
    return np.array(donor, dtype=float), np.array(acceptor, dtype=float)


def _measurement(
    donor,
    acceptor,
    *,
    gamma=1.0,
    leakage=0.0,
    dir_ex=0.0,
    alternated=False,
    alex=False,
    naa=None,
):
    donor, acceptor = _counts(donor, acceptor)
    data = Data()
    fields = dict(
        nch=1,
        alternated=alternated,
        ALEX=alex,
        meas_type="smFRET-usALEX" if alternated else "smFRET",
        mburst=[_Bursts(donor.size)],
        nd=[donor],
        na=[acceptor],
        nt=[donor + acceptor],
        _gamma=float(gamma),
        _leakage=float(leakage),
        _dir_ex=float(dir_ex),
        bg_corrected=True,
        leakage_corrected=False,
        dir_ex_corrected=False,
        dithering=False,
        pax=False,
    )
    if naa is not None:
        fields["naa"] = [np.array(naa, dtype=float)]
    data.add(**fields)
    return data


class DirectExcitationTests(unittest.TestCase):
    def test_tooltip_states_both_coefficients(self):
        self.assertIn("dir_ex_t", DIRECT_EXCITATION_TOOLTIP)
        self.assertIn("correct_E_gamma_leak_dir", DIRECT_EXCITATION_TOOLTIP)
        self.assertIn("dir_ex * naa", DIRECT_EXCITATION_TOOLTIP)
        self.assertIn("this same number is not dir_ex_t", DIRECT_EXCITATION_TOOLTIP)

    def test_non_alex_efficiency_matches_fretmath(self):
        donor = [80.0, 40.0]
        acceptor = [20.0, 60.0]
        gamma = 0.8
        leakage = 0.05
        direct = 0.1
        raw_donor, raw_acceptor = _counts(donor, acceptor)
        proximity = raw_acceptor / (raw_acceptor + raw_donor)
        data = _measurement(
            donor,
            acceptor,
            gamma=gamma,
            leakage=leakage,
            dir_ex=direct,
        )

        data.leakage_correction(mute=True)
        data.direct_excitation_correction(mute=True)
        data._calculate_fret_eff()

        expected = correct_E_gamma_leak_dir(
            proximity, gamma, leakage, direct
        )
        np.testing.assert_allclose(data.E[0], expected)

    def test_corrections_apply_direct_excitation_without_alex(self):
        data = _measurement([100.0, 50.0], [25.0, 40.0], gamma=0.7, dir_ex=0.2)
        data.add(leakage_corrected=True)
        before = data.na[0].copy()

        data.corrections(mute=True)

        self.assertTrue(data.dir_ex_corrected)
        self.assertFalse(np.allclose(data.na[0], before))
        expected = (before - 0.2 * 0.7 * data.nd[0]) / 1.2
        np.testing.assert_allclose(data.na[0], expected)

    def test_alex_still_subtracts_acceptor_excitation_counts(self):
        donor = [100.0]
        acceptor = [40.0]
        acceptor_excitation = [50.0]
        direct = 0.2
        gamma = 0.7
        data = _measurement(
            donor,
            acceptor,
            gamma=gamma,
            dir_ex=direct,
            alternated=True,
            alex=True,
            naa=acceptor_excitation,
        )
        data.add(leakage_corrected=True)
        before = data.na[0].copy()

        data.corrections(mute=True)

        np.testing.assert_allclose(data.na[0], before - direct * data.naa[0])
        proportional = (before - direct * gamma * data.nd[0]) / (1.0 + direct)
        self.assertFalse(np.allclose(data.na[0], proportional))

    def test_gamma_change_reapplies_non_alex_proportion(self):
        donor = [80.0, 40.0]
        acceptor = [20.0, 60.0]
        leakage = 0.05
        direct = 0.1
        data = _measurement(
            donor,
            acceptor,
            gamma=0.8,
            leakage=leakage,
            dir_ex=direct,
        )
        data.leakage_correction(mute=True)
        data.direct_excitation_correction(mute=True)
        raw_donor, raw_acceptor = _counts(donor, acceptor)

        def restore_raw_counts(alex_all=False, pure_python=False):
            data.nd[0] = raw_donor.copy()
            data.na[0] = raw_acceptor.copy()
            data.nt[0] = raw_donor + raw_acceptor
            data.add(
                bg_corrected=False,
                leakage_corrected=False,
                dir_ex_corrected=False,
                dithering=False,
            )

        data.calc_ph_num = restore_raw_counts
        data.add(bg_corrected=False)
        data.gamma = 1.4

        proximity = raw_acceptor / (raw_acceptor + raw_donor)
        expected = correct_E_gamma_leak_dir(proximity, 1.4, leakage, direct)
        np.testing.assert_allclose(data.E[0], expected)


if __name__ == "__main__":
    unittest.main()
