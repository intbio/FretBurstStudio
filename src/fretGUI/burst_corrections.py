"""Apply the proportional direct-excitation correction to non-ALEX data.

``fretmath.correct_E_gamma_leak_dir`` defines corrected efficiency from the
background-only proximity ratio. FRETBursts removes leakage from acceptor
counts before computing ``E = na / (gamma*nd + na)`` and, for alternated
data only, subtracts ``dir_ex * naa``. That ``naa`` coefficient is not
``dir_ex_t``. Alternated measurements keep that path. Every other
measurement changes ``na`` so the existing efficiency formula matches
``correct_E_gamma_leak_dir``.
"""

import numpy as np
from fretbursts.burstlib import Data

DIRECT_EXCITATION_TOOLTIP = (
    "Non-ALEX: dir_ex_t from the FRET correction formulas. "
    "Direct excitation is n_dir = dir_ex_t * (na + gamma*nd), "
    "the acceptor/donor absorption ratio at the donor-excitation wavelength. "
    "Corrected E matches correct_E_gamma_leak_dir.\n\n"
    "ALEX and PAX: this same number is not dir_ex_t. "
    "It subtracts dir_ex * naa from acceptor counts, "
    "where naa is acceptor emission during acceptor excitation."
)

_installed = False
_original_direct_excitation_correction = Data.direct_excitation_correction
_original_corrections = Data.corrections
_original_update_gamma = Data._update_gamma


def install_proportional_direct_excitation():
    """Install the non-ALEX direct-excitation path on ``Data``."""
    global _installed
    if _installed:
        return
    Data.direct_excitation_correction = _direct_excitation_correction
    Data.corrections = _corrections
    Data._update_gamma = _update_gamma
    _installed = True


def _direct_excitation_correction(self, mute=False):
    if self.alternated:
        return _original_direct_excitation_correction(self, mute=mute)
    if self.dir_ex_corrected:
        return -1
    if self.dir_ex != 0:
        direct = float(self.dir_ex)
        gamma = self.get_gamma_array()
        for channel, n_bursts in enumerate(self.num_bursts):
            if n_bursts == 0:
                continue
            acceptor = self.na[channel]
            donor = self.nd[channel]
            acceptor[:] = (
                acceptor - direct * gamma[channel] * donor
            ) / (1.0 + direct)
            self.nt[channel] = donor + acceptor
    self.add(dir_ex_corrected=True)


def _corrections(self, mute=False):
    _original_corrections(self, mute=mute)
    if not self.alternated:
        self.direct_excitation_correction(mute=mute)


def _update_gamma(self, gamma):
    """Rebuild non-ALEX counts when direct excitation depends on gamma."""
    if not _proportional_direct_excitation_is_applied(self):
        _original_update_gamma(self, gamma)
        return
    assert (np.size(gamma) == 1) or (np.size(gamma) == self.nch)
    self.add(_gamma=np.asfarray(gamma))
    self._update_corrections()


def _proportional_direct_excitation_is_applied(self):
    return (
        not self.alternated
        and self.dir_ex != 0
        and getattr(self, "dir_ex_corrected", False)
        and "mburst" in self
    )
