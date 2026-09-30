"""Static photon-distribution fitting for a FRETBursts / FretBurstStudio group.

WHAT THIS ANALYSIS FITS
=======================
This is an original, parametric, STATIC PDA-style count likelihood, not a
port of PAM or an exact reproduction of Antonik's histogram-library method.
It fits K discrete FRET efficiencies and their mixture fractions. Each state
has zero intrinsic efficiency width; its observed width comes from photon
statistics and background. It does NOT fit distance-distribution widths,
exchange rates, lifetimes, or infer structural identities. Extra fitted states
may mimic continuous heterogeneity or a poor noise/brightness model.

To handle background without rounding corrected counts or estimating a noisy
background fraction per burst, this analysis models both raw detection counts:

    u ~ Gamma(shape=a, rate=a/m)       # common, latent excitation/brightness
    cD(E) = 1 - E
    cA(E) = gamma*(E + direct_ratio) + leakage*(1 - E)
    nD | u,E ~ Poisson(u*cD(E) + bD)
    nA | u,E ~ Poisson(u*cA(E) + bA)

bD and bA are EXPECTED background counts in that fixed observation window.
u is the expected donor-channel signal count if E were zero. Its mean m and
shape a are fitted nuisance parameters, shared by all states. The integrated
signal likelihood is negative multinomial; independent Poisson background
counts are convolved analytically (a numerically truncated sum). This is an
exact likelihood UNDER THIS MODEL, including gamma-dependent brightness.
The Gamma brightness distribution is an extra modeling assumption, not a
universal property of confocal diffusion. Check the total-count prediction!
State-dependent quantum yields or excitation profiles violate this model.

INPUTS AND CONVENTIONS
=====================
* Two-color, continuous-wave, donor-excitation-only photon counting.
  ALEX/PAX data and camera intensities are deliberately rejected/not supported.
* d must retain raw photon timestamps, detector identity and mburst.
  Corrected d.nd/d.na/d.E are NEVER used or modified.
* gamma convention: E = corrected_A / (corrected_A + gamma*corrected_D),
  matching FRETBursts. leakage = donor bleed-through A counts / D counts.
* direct_ratio = acceptor / donor absorption cross-section at the donor laser
  wavelength (one donor and one acceptor). Equivalently, direct-excitation A
  signal / (gamma*u). This is NOT FRETBursts' ALEX d.dir_ex parameter.
  Use zero ONLY when direct acceptor excitation is negligible or absent.
* extract_group gets background rates (counts/s) from
  d.bg[Ph_sel(Dex='Dem'/'Aem')][ich][d.bp[ich]], the documented per-burst
  background-period convention. You can instead supply bg_rates_cps=(D,A):
  two scalars, or two arrays indexed like the ORIGINAL d.mburst[ich].
* One CENTRAL, fixed-duration window per sufficiently long burst is used.
  Half-open interval [start, stop); last edge excluded. Short bursts are
  reported and excluded. One window per burst avoids treating correlated
  subdivisions as independent samples. Bursts that contain a fusion gap
  are skipped: the gap is dark time inside the recorded interval, so the
  central window can fall between two passages. Overlapping bursts fused
  with no gap are kept.
* No additional count, E, or acceptor-only threshold is applied here; even
  zero-count central windows are retained in the count likelihood.

FITTING PROTOCOL
================
1. Calibrate backgrounds, leakage, gamma and direct excitation independently.
   Confirm two-color photon identity and exclude obvious detector artifacts.
2. Start with a burst group selected without a narrow E gate. An E/acceptor
   count gate can truncate a state; this script does NOT normalize for it.
   Prefer color-independent burst search. All upstream selection, including
   duration and burst detection, can bias the reported population fractions.
3. Use one spot/file at a time. Choose a window shorter than expected state
   dwell times but long enough for useful photon counts (e.g. 0.5 ms is only
   a starting point, not a universal setting). Inspect the retained fraction.
4. Fit K=1,2,3 with multiple starts. Compare BIC on the SAME windows, but do
   not interpret the lowest BIC as proof of the true number of conformations.
   Mixture-model boundaries and nearly identical states undermine usual
   asymptotic criteria. Inspect raw-PR AND total-count predictive checks.
5. Check convergence, tiny fractions, merged peaks, and parameter bounds.
   If the total-count distribution is poorly reproduced, revisit the shared
   Gamma brightness model; do not just keep adding FRET states.
6. Bootstrap whole bursts (one row per burst here) for conditional confidence
   intervals. Rerun with plausible calibration factors to assess systematic
   uncertainty; the bootstrap does not include calibration/model uncertainty.
7. Repeat shorter/longer windows using the SAME sufficiently long burst group
   when comparing populations. Changes can indicate exchange, photophysics,
   or selection. Dynamic PDA/BVA would be a separate analysis.
8. Report fractions as fractions of retained burst windows, not automatically
   equilibrium solution populations. Without direct acceptor excitation,
   donor-only/dark acceptor and very-low-FRET states may be indistinguishable.

REFERENCES
==========
Antonik et al. 2006: https://doi.org/10.1021/jp057257%2B
Kalinin et al. 2008: https://doi.org/10.1021/jp711942q
https://fretbursts.readthedocs.io/en/latest/data_class.html
Studio's FBSData.data wraps Data; selector nodes use Data.select_bursts().
"""

from __future__ import annotations

from dataclasses import dataclass, field
import warnings
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln, digamma, i0e, i1e, logsumexp, softmax
from scipy.stats import poisson


@dataclass(frozen=True)
class FitStart:
    """Starting values and bounds for the efficiencies and the exchange rate.

    ``efficiencies`` holds up to three ``(guess, low, high)`` triples.
    One state uses the first, two states and the dynamic model use the
    first two, and three states uses all three. Exchange bounds are in
    exchanges per window.
    """
    efficiencies: tuple = (
        (0.2, 0.01, 0.99),
        (0.5, 0.01, 0.99),
        (0.8, 0.01, 0.99),
    )
    equilibrium: float = 0.5
    exchanges_per_window: float = 1.0
    exchange_low: float = 1e-3
    exchange_high: float = 1e3


def _efficiency_box(guess, low, high):
    """Return a feasible (guess, low, high) inside (0, 1)."""
    lo = float(min(low, high))
    hi = float(max(low, high))
    lo = float(np.clip(lo, 1e-4, 1.0 - 1e-4))
    hi = float(np.clip(hi, 1e-4, 1.0 - 1e-4))
    if hi - lo < 1e-4:
        hi = min(1.0 - 1e-4, lo + 1e-4)
    value = float(np.clip(guess, lo, hi))
    return value, lo, hi


def _finite_difference(high, low, delta):
    """Difference of log-weights, treating missing nodes as very unlikely."""
    high = np.where(np.isfinite(high), high, -1e3)
    low = np.where(np.isfinite(low), low, -1e3)
    return (high - low) / delta


def _state_boxes(start, n_states, initial_E):
    """(guess, low, high) for each state, clipped into (0, 1)."""
    if start is None:
        if initial_E is None:
            guesses = (
                np.linspace(0.15, 0.85, n_states)
                if n_states > 1 else np.array([0.5])
            )
        else:
            guesses = np.asarray(initial_E, dtype=float)
        return [_efficiency_box(float(guess), 0.01, 0.99) for guess in guesses]
    specs = list(start.efficiencies)
    if len(specs) < n_states:
        raise ValueError(f"Need guesses for {n_states} states.")
    return [_efficiency_box(*specs[index]) for index in range(n_states)]


@dataclass(frozen=True)
class Calibration:
    """Fixed, independently calibrated factors; see module docstring."""
    gamma: float
    leakage: float
    direct_ratio: float

    def __post_init__(self):
        values = np.array([self.gamma, self.leakage, self.direct_ratio])
        if not np.isfinite(values).all() or self.gamma <= 0 or (values[1:] < 0).any():
            raise ValueError("gamma must be >0; leakage/direct_ratio must be >=0.")


@dataclass
class Counts:
    """One row per independent burst window; bD/bA are expected counts.

    For externally prepared raw counts, construct this directly. Values must
    be integer observations, NOT background-subtracted or gamma-corrected.
    All rows must have the same window duration and calibration.
    """
    nD: np.ndarray
    nA: np.ndarray
    bD: np.ndarray
    bA: np.ndarray
    burst_id: np.ndarray
    window_s: float
    info: dict = field(default_factory=dict)

    def __post_init__(self):
        self.nD = self._integer_counts(self.nD)
        self.nA = self._integer_counts(self.nA)
        self.bD = np.asarray(self.bD, dtype=float)
        self.bA = np.asarray(self.bA, dtype=float)
        self.burst_id = np.asarray(self.burst_id)
        shape = self.nD.shape
        if len(shape) != 1 or shape[0] == 0:
            raise ValueError("Counts must be nonempty 1D arrays.")
        if any(x.shape != shape for x in (self.nA, self.bD, self.bA, self.burst_id)):
            raise ValueError("All count/background/ID arrays must have equal length.")
        if not np.isfinite(self.window_s) or self.window_s <= 0:
            raise ValueError("window_s must be positive, in seconds.")
        if any(not np.isfinite(x).all() or (x < 0).any() for x in (self.bD, self.bA)):
            raise ValueError("Expected background counts must be finite and >=0.")

    @staticmethod
    def _integer_counts(x):
        x = np.asarray(x)
        if not np.isfinite(x).all() or (x < 0).any() or (x != np.floor(x)).any():
            raise ValueError("Use nonnegative RAW integer photon counts.")
        return x.astype(np.int64)

    def take(self, indices):
        """Subsample/resample rows without altering the original counts."""
        return Counts(*(x[indices] for x in
                        (self.nD, self.nA, self.bD, self.bA, self.burst_id)),
                      self.window_s, self.info.copy())


def extract_group(data, group=None, *, ich=0, window_s=0.0005,
                  bg_rates_cps=None) -> Counts:
    """Extract central raw-count windows from Data or Studio FBSData.

    group: None (all currently selected bursts), Boolean mask, integer index
        array or slice. No invented Studio-specific group attribute is needed.
    ich: zero-based spot index. Donor/acceptor detection is selected internally.
    window_s: fixed window duration in seconds, rounded to timestamp ticks.
    bg_rates_cps: None to use d.bg and d.bp; otherwise (D_rate, A_rate), each
        scalar or array of length len(d.mburst[ich]) BEFORE applying group.
        These are raw detector background rates, without a gamma correction.

    The Data object is read only. Neither d.nd nor d.na is read, so corrections
    already applied in FRETBursts do not cause double correction.
    """
    from fretbursts import Ph_sel

    d = data if hasattr(data, "mburst") else getattr(data, "data", None)
    if d is None or not hasattr(d, "mburst"):
        raise TypeError("Pass a FRETBursts Data with bursts, or Studio FBSData.")
    if any(bool(getattr(d, name, False)) for name in ("alternated", "ALEX")):
        raise ValueError(
            "Photon distribution analysis requires non-alternating donor-only excitation."
        )
    if "PAX" in str(getattr(d, "meas_type", "")).upper():
        raise ValueError("PAX is not supported by photon distribution analysis.")
    if not isinstance(ich, (int, np.integer)) or not 0 <= ich < d.nch:
        raise ValueError("ich must be a valid observation-spot index.")
    bursts = d.mburst[ich]
    total = len(bursts.start)
    ids = np.arange(total)
    if group is not None:
        if isinstance(group, slice):
            ids = ids[group]
        else:
            g = np.asarray(group)
            if g.ndim != 1:
                raise ValueError("group must be a 1D mask or integer indices.")
            if g.dtype == bool:
                if g.size != total:
                    raise ValueError("Boolean group mask must match current bursts.")
            elif not np.issubdtype(g.dtype, np.integer) or (g < 0).any() or (g >= total).any():
                raise ValueError("group contains invalid burst indices.")
            ids = ids[g]
    if len(ids) == 0 or np.unique(ids).size != len(ids):
        raise ValueError("Select a nonempty group without duplicate bursts.")
    requested = len(ids)
    n_gapped = 0
    if hasattr(bursts, "gap"):
        gapped = np.asarray(bursts.gap)[ids] != 0
        n_gapped = int(gapped.sum())
        ids = ids[~gapped]
    if len(ids) == 0:
        raise ValueError(
            "Every selected burst contains a gap from Fuse Bursts. "
            "That gap is dark time between two passages, so the central "
            "window can land between them. Those bursts were skipped, "
            "and none remain."
        )
    clk = float(d.clk_p)
    if not np.isfinite(window_s) or window_s <= 0 or not np.isfinite(clk) or clk <= 0:
        raise ValueError("window_s and d.clk_p must be positive seconds.")
    width = int(round(window_s / clk))
    if width < 1:
        raise ValueError("window_s is shorter than one timestamp tick.")
    starts = np.asarray(bursts.start, dtype=np.int64)[ids]
    stops = np.asarray(bursts.stop, dtype=np.int64)[ids]
    keep = stops - starts >= width
    n_short = int((~keep).sum())
    ids, starts, stops = ids[keep], starts[keep], stops[keep]
    if len(ids) == 0:
        if n_gapped:
            raise ValueError(
                "No selected burst is long enough for this window. "
                f"{n_gapped} burst(s) were also skipped because a fused "
                "gap sits inside them."
            )
        raise ValueError("No selected burst is long enough for this window.")
    if n_short:
        warnings.warn(f"Excluded {n_short}/{requested} bursts shorter than the window.")
    left = starts + (stops - starts - width) // 2
    right = left + width
    order = np.argsort(left)
    if np.any(left[order][1:] < right[order][:-1]):
        raise ValueError("Overlapping windows would reuse photons; revise the group.")

    # Retrieve raw photons through documented FRETBursts access methods.
    tD = np.asarray(d.get_ph_times(ich=ich, ph_sel=Ph_sel(Dex="Dem")))
    tA = np.asarray(d.get_ph_times(ich=ich, ph_sel=Ph_sel(Dex="Aem")))
    if any(t.ndim != 1 or np.any(t[1:] < t[:-1]) for t in (tD, tA)):
        raise ValueError("Photon timestamps must be sorted 1D arrays.")
    nD = np.searchsorted(tD, right, side="left") - np.searchsorted(tD, left, side="left")
    nA = np.searchsorted(tA, right, side="left") - np.searchsorted(tA, left, side="left")
    if bg_rates_cps is None:
        if not hasattr(d, "bg") or not hasattr(d, "bp"):
            raise ValueError(
                "Run Calculate Background and burst search before photon distribution analysis."
            )
        periods = np.asarray(d.bp[ich], dtype=int)[ids]
        rates = [np.asarray(d.bg[Ph_sel(Dex=em)][ich], dtype=float)[periods]
                 for em in ("Dem", "Aem")]
    else:
        if len(bg_rates_cps) != 2:
            raise ValueError("bg_rates_cps must be (donor_rate, acceptor_rate).")
        rates = []
        for rate in bg_rates_cps:
            r = np.asarray(rate, dtype=float)
            if r.ndim == 0:
                rates.append(np.full(len(ids), float(r)))
            elif r.shape == (total,):
                rates.append(r[ids])
            else:
                raise ValueError("Rate arrays must match the original burst count.")
    duration = width * clk
    return Counts(nD, nA, rates[0]*duration, rates[1]*duration, ids, duration,
                  {"requested_bursts": requested, "excluded_short": n_short,
                   "excluded_gapped": n_gapped,
                   "retained_bursts": len(ids), "ich": ich,
                   "background": "d.bg/d.bp" if bg_rates_cps is None else "explicit"})


def _poisson_cutoff(mean, log_floor):
    """Largest count whose Poisson log-probability is still above ``log_floor``."""
    if not np.isfinite(mean) or mean <= 0:
        return 0
    limit = int(mean + 20.0 * np.sqrt(mean) + 80.0)
    logp = poisson.logpmf(np.arange(limit + 1), mean)
    keep = np.nonzero(logp >= log_floor)[0]
    if keep.size == 0:
        return int(np.floor(mean))
    return int(keep[-1])


class _Kernel:
    """Cache background counts and marginalize the latent brightness.

    Background counts whose Poisson log-probability is below ``log_floor``
    are omitted. Around a reasonable fit this changes each window's
    log-likelihood by far less than 0.001. ``bg_tail`` remains an optional
    extra cutoff and is not used by the fit window.
    """
    def __init__(self, counts, bg_tail=0.0, log_floor=-40.0):
        if not 0 <= bg_tail < 1e-3:
            raise ValueError("bg_tail must be zero (exact) or less than 1e-3.")
        blocks = []
        work_size = 0
        # Group equal observed count pairs to avoid padding to the largest N.
        pairs = np.column_stack([counts.nD, counts.nA])
        unique, inverse = np.unique(pairs, axis=0, return_inverse=True)
        self.n = len(pairs)
        # Ignore background counts with a negligible Poisson probability.
        # Near a usable fit this shifts each window log-likelihood by << 0.001.
        log_floor = float(log_floor)
        cutoffs = {}

        def cutoff(mean):
            key = float(mean)
            if key not in cutoffs:
                cutoffs[key] = _poisson_cutoff(key, log_floor)
            return cutoffs[key]

        for j, (nd, na) in enumerate(unique):
            rows = np.flatnonzero(inverse == j)
            bd_max, ba_max = int(nd), int(na)
            if bg_tail:
                bd_max = min(bd_max, int(poisson.ppf(1-bg_tail/2, counts.bD[rows].max())))
                ba_max = min(ba_max, int(poisson.ppf(1-bg_tail/2, counts.bA[rows].max())))
            bd_max = min(bd_max, cutoff(counts.bD[rows].max()))
            ba_max = min(ba_max, cutoff(counts.bA[rows].max()))
            # Background mean zero means only b=0 has positive probability.
            if np.all(counts.bD[rows] == 0):
                bd_max = 0
            if np.all(counts.bA[rows] == 0):
                ba_max = 0
            bd, ba = np.meshgrid(np.arange(bd_max+1), np.arange(ba_max+1), indexing="ij")
            sd, sa = nd-bd.ravel(), na-ba.ravel()
            work_size += len(rows)*len(sd)
            if work_size > 10_000_000:
                raise ValueError("Kernel too large: shorten windows, or validate a small bg_tail.")
            base = (poisson.logpmf(bd.ravel()[None, :], counts.bD[rows, None])
                    + poisson.logpmf(ba.ravel()[None, :], counts.bA[rows, None])
                    - gammaln(sd+1)[None, :] - gammaln(sa+1)[None, :])
            blocks.append((rows, sd, sa, base))
        # Ragged background sums, vectorized using segmented reductions.
        # This avoids a Python loop over individual bursts during optimization.
        self.rows = np.concatenate([b[0] for b in blocks])
        self.lengths = np.concatenate([np.full(len(b[0]), len(b[1]), dtype=int) for b in blocks])
        self.offsets = np.r_[0, np.cumsum(self.lengths)[:-1]]
        sd = np.concatenate([np.tile(b[1], len(b[0])) for b in blocks])
        sa = np.concatenate([np.tile(b[2], len(b[0])) for b in blocks])
        self.nt_i = np.asarray(sd + sa, dtype=np.int64)
        self.sd = sd.astype(np.float64, copy=False)
        self.sa = sa.astype(np.float64, copy=False)
        self.nt = self.nt_i.astype(np.float64)
        self.base = np.concatenate([b[3].ravel() for b in blocks])
        work = self.base.size
        self._grid = np.arange(int(self.nt_i.max()) + 1)
        self._shared = np.empty(work, dtype=np.float64)
        self._terms = np.empty(work, dtype=np.float64)
        self._weights = np.empty(work, dtype=np.float64)
        self._scratch = np.empty(work, dtype=np.float64)
        self._scratch2 = np.empty(work, dtype=np.float64)
        self._log_g_nt = np.empty(work, dtype=np.float64)
        self._dig_nt = np.empty(work, dtype=np.float64)
        self._shape_nt = np.empty(work, dtype=np.float64)
        self._shape = None
        self._mean = None

    def _prepare_brightness(self, shape, mean):
        """Cache the parts of the log-likelihood that do not depend on E."""
        if shape == self._shape and mean == self._mean:
            return
        self._shape = shape
        self._mean = mean
        rate = shape / mean
        self._rate = rate
        self._log_rate = np.log(rate)
        self._gln_shape = float(gammaln(shape))
        self._dig_shape = float(digamma(shape))
        np.take(gammaln(shape + self._grid), self.nt_i, out=self._log_g_nt)
        np.take(digamma(shape + self._grid), self.nt_i, out=self._dig_nt)
        np.copyto(self._shared, self.base)
        self._shared += self._log_g_nt
        self._shared += shape * self._log_rate - self._gln_shape
        np.add(self.nt, shape, out=self._shape_nt)

    def state(self, E, shape, mean, cal, gradient=False):
        self._prepare_brightness(shape, mean)
        cD = 1.0 - float(E)
        cA = float(cal.gamma * (E + cal.direct_ratio) + cal.leakage * (1.0 - E))
        cpA = float(cal.gamma - cal.leakage)
        denom = self._rate + cD + cA
        log_cD = np.log(cD)
        log_cA = np.log(cA)
        log_denom = np.log(denom)
        terms = self._terms
        scratch = self._scratch
        scratch2 = self._scratch2
        np.copyto(terms, self._shared)
        np.multiply(self.sd, log_cD, out=scratch)
        terms += scratch
        np.multiply(self.sa, log_cA, out=scratch)
        terms += scratch
        np.multiply(self._shape_nt, log_denom, out=scratch)
        terms -= scratch
        maximum = np.maximum.reduceat(terms, self.offsets)
        repeated = np.repeat(maximum, self.lengths)
        np.subtract(terms, repeated, out=self._weights)
        np.exp(self._weights, out=self._weights)
        norm = np.add.reduceat(self._weights, self.offsets)
        output = np.empty(self.n)
        output[self.rows] = maximum + np.log(norm)
        if not gradient:
            return output
        deriv = np.empty((self.n, 3))
        # d log(signal) / dE
        np.multiply(self.sd, -1.0 / cD, out=scratch)
        np.multiply(self.sa, cpA / cA, out=scratch2)
        scratch += scratch2
        np.multiply(self._shape_nt, (cpA - 1.0) / denom, out=scratch2)
        scratch -= scratch2
        np.multiply(scratch, self._weights, out=scratch2)
        deriv[self.rows, 0] = np.add.reduceat(scratch2, self.offsets) / norm
        # d log(signal) / d shape
        np.copyto(scratch, self._dig_nt)
        scratch -= self._dig_shape - self._log_rate - 1.0 + log_denom
        np.divide(self._shape_nt, denom * self._mean, out=scratch2)
        scratch -= scratch2
        scratch *= shape
        np.multiply(scratch, self._weights, out=scratch2)
        deriv[self.rows, 1] = np.add.reduceat(scratch2, self.offsets) / norm
        # d log(signal) / d mean
        np.multiply(self._shape_nt, self._rate / denom, out=scratch)
        scratch -= shape
        np.multiply(scratch, self._weights, out=scratch2)
        deriv[self.rows, 2] = np.add.reduceat(scratch2, self.offsets) / norm
        return output, deriv


@dataclass
class Fit:
    """State order is increasing E. Fractions refer to retained windows.

    responsibilities[i,k] is the posterior probability of state k for row i;
    it is a probabilistic assignment, not a reconstructed transition trace.
    AIC/BIC comparisons require identical data and calibration across fits.
    """
    efficiencies: np.ndarray
    fractions: np.ndarray
    brightness_shape: float
    brightness_mean: float
    log_likelihood: float
    aic: float
    bic: float
    responsibilities: np.ndarray
    calibration: Calibration
    n_observations: int
    converged_starts: int
    start_nll: np.ndarray
    bound_warning: bool
    bg_tail: float
    model: str = "static"
    exchange_rate: float = 0.0
    window_s: float = 0.0

    @property
    def n_states(self):
        return len(self.efficiencies)

    def label(self):
        if self.model == "dynamic":
            return "Dynamic 2 states"
        if self.n_states == 1:
            return "1 state"
        return f"{self.n_states} states"


def fit_pda(counts: Counts, cal: Calibration, *, n_states=2, n_starts=8,
            initial_E=None, seed=2026, bg_tail=0.0, _kernel=None,
            should_cancel=None, start=None) -> Fit:
    """Fit static discrete states by joint raw-count maximum likelihood.

    n_states: fixed candidate K, 1..5; compare models separately.
    n_starts: independent initializations; lowest converged NLL is retained.
    initial_E: optional K values in (0,1), used for the first initialization.
    seed: reproducible random starts.
    bg_tail: 0 gives exact finite background convolution; e.g. 1e-10 is a
        faster approximation. Validate stability against 0 for final fits.

    Optimizes E[0:K], K-1 softmax logits, log(brightness_shape),
    log(brightness_mean). Analytic gradients include background marginalization.
    Extra random starts stop once two converged fits agree to 0.5 nats,
    so a unimodal fit does not repeat the same search.
    No Gaussian fit to a histogram and no rounding/subtraction of background.
    """
    if not isinstance(n_states, (int, np.integer)) or not 1 <= n_states <= 5:
        raise ValueError("n_states must be an integer from 1 to 5.")
    if not isinstance(n_starts, (int, np.integer)) or n_starts < 1:
        raise ValueError("n_starts must be a positive integer.")
    n = len(counts.nD)
    K = int(n_states)
    if n < max(20, 10*K):
        raise ValueError("Too few windows for this mixture fit.")
    if np.sum(counts.nD+counts.nA) == 0:
        raise ValueError("No photons: FRET efficiencies are not identifiable.")
    if initial_E is not None:
        initial_E = np.asarray(initial_E, dtype=float)
        if initial_E.shape != (K,) or not np.isfinite(initial_E).all() or not ((initial_E > 0) & (initial_E < 1)).all():
            raise ValueError("initial_E must contain K finite values strictly in (0,1).")
    kernel = _kernel if _kernel is not None else _Kernel(counts, bg_tail)

    def unpack(x):
        return x[:K], softmax(np.r_[x[K:2*K-1], 0.0]), np.exp(x[-2]), np.exp(x[-1])

    def objective(x):
        E, f, shape, mean = unpack(x)
        evaluated = [kernel.state(e, shape, mean, cal, gradient=True) for e in E]
        lp = np.column_stack([v[0] for v in evaluated]) + np.log(f)[None, :]
        log_mix = logsumexp(lp, axis=1)
        r = np.exp(lp-log_mix[:, None])
        gradE = np.array([np.dot(r[:, j], evaluated[j][1][:, 0]) for j in range(K)])
        gradlogits = (r.sum(axis=0)-n*f)[:-1]
        gradbrightness = sum((r[:, j, None]*evaluated[j][1][:, 1:]).sum(axis=0)
                             for j in range(K))
        gradbrightness = gradbrightness * np.array([shape, mean])
        return -log_mix.sum(), -np.r_[gradE, gradlogits, gradbrightness]

    signal_mean = max(1.0, np.mean(counts.nD+counts.nA-counts.bD-counts.bA))
    mean_guess = signal_mean/((1+cal.leakage)*0.5 + cal.gamma*(0.5+cal.direct_ratio))
    upper_mean = max(1e4, float(np.max(counts.nD+counts.nA))*100/cal.gamma)
    boxes = _state_boxes(start, K, initial_E)
    bounds = (
        [(lo, hi) for _guess, lo, hi in boxes]
        + [(-12, 12)] * (K - 1)
        + [(np.log(0.03), np.log(300.0)), (np.log(0.01), np.log(upper_mean))]
    )
    rng = np.random.default_rng(seed)
    solutions, history = [], []
    best_fun = np.inf
    n_at_best = 0
    for attempt in range(n_starts):
        if should_cancel is not None and should_cancel():
            raise FitCancelled()
        if attempt == 0:
            es = np.array([guess for guess, _lo, _hi in boxes])
            logits = np.zeros(K - 1)
        else:
            es = np.array([
                rng.uniform(lo, hi) for _guess, lo, hi in boxes
            ])
            logits = rng.normal(0, 0.5, K - 1)
        x0 = np.r_[es, logits, np.log(rng.uniform(1, 5)), np.log(mean_guess)]
        result = minimize(objective, x0, jac=True, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": 200, "ftol": 1e-8, "gtol": 1e-5})
        usable = np.isfinite(getattr(result, "fun", np.nan)) and int(result.nit or 0) > 0
        history.append(result.fun if usable else np.nan)
        if usable:
            solutions.append(result)
            if result.fun < best_fun - 0.5:
                best_fun = result.fun
                n_at_best = 1
            elif result.fun <= best_fun + 0.5:
                n_at_best += 1
            if n_at_best >= 2:
                break
    if not solutions:
        raise RuntimeError(
            "No start converged. Set an efficiency guess inside its low and high bounds."
        )
    best = min(solutions, key=lambda x: x.fun)
    E, f, shape, mean = unpack(best.x)
    order = np.argsort(E)
    E, f = E[order], f[order]
    lp = np.column_stack([kernel.state(e, shape, mean, cal) for e in E])+np.log(f)
    r = np.exp(lp-logsumexp(lp, axis=1)[:, None])
    p = 2*K+1  # K efficiencies + K-1 fractions + two brightness parameters
    at_bound = any(abs(v-lo) < 1e-4 or abs(v-hi) < 1e-4
                   for v, (lo, hi) in zip(best.x, bounds))
    return Fit(E, f, shape, mean, -best.fun, 2*p+2*best.fun,
               p*np.log(n)+2*best.fun, r, cal, n, len(solutions),
               np.asarray(history), at_bound, bg_tail)


class FitCancelled(Exception):
    """A multi-state comparison was stopped before every K finished."""


def compare_models(counts, cal, *, state_counts=(1, 2, 3), n_starts=8,
                   seed=2026, bg_tail=0.0, should_cancel=None):
    """Fit candidate K on exactly the same rows; no automatic state decision.

    should_cancel: optional zero-argument callable checked before each K.
        When it returns true, the comparison stops and raises FitCancelled.
        A fit that has already started runs to completion.
    """
    kernel = _Kernel(counts, bg_tail)
    fits = []
    for k in state_counts:
        if should_cancel is not None and should_cancel():
            raise FitCancelled()
        fits.append(fit_pda(
            counts, cal, n_states=k, n_starts=n_starts,
            seed=seed+k, bg_tail=bg_tail, _kernel=kernel,
            should_cancel=should_cancel,
        ))
    return fits


def _occupation_parts(window_s, rate, equilibrium, n_quad=8):
    """Quadrature of the fraction of a window spent in state 1.

    State 1 leaves at ``rate * (1 - equilibrium)`` and state 2 leaves at
    ``rate * equilibrium``. The two endpoints are windows with no switch.
    Interior nodes are Gauss-Legendre points for paths that switch.
    Returns the fraction in state 1, the log probability of each node,
    and the total probability before renormalization.
    """
    duration = float(window_s)
    if duration <= 0:
        raise ValueError("window_s must be positive.")
    rate = float(rate)
    if rate <= 0 or not np.isfinite(rate):
        raise ValueError("exchange rate must be positive.")
    pi = float(np.clip(equilibrium, 1e-8, 1.0 - 1e-8))
    leave_1 = rate * (1.0 - pi)
    leave_2 = rate * pi
    log_stay_1 = np.log(pi) - leave_1 * duration
    log_stay_2 = np.log(1.0 - pi) - leave_2 * duration
    nodes, weights = np.polynomial.legendre.leggauss(int(n_quad))
    fraction = 0.5 * (nodes + 1.0)
    dx = 0.5 * weights
    time_1 = fraction * duration
    time_2 = (1.0 - fraction) * duration
    argument = 2.0 * np.sqrt(np.maximum(leave_1 * leave_2 * time_1 * time_2, 0.0))
    exponent = -leave_1 * time_1 - leave_2 * time_2 + argument
    bessel_0 = i0e(argument)
    bessel_1 = i1e(argument)
    scale = np.sqrt(leave_1 * leave_2)
    density = np.exp(exponent) * (
        (pi * leave_1 + (1.0 - pi) * leave_2) * bessel_0
        + pi * scale * np.sqrt(time_1 / time_2) * bessel_1
        + (1.0 - pi) * scale * np.sqrt(time_2 / time_1) * bessel_1
    )
    mass = np.maximum(density * duration * dx, 0.0)
    with np.errstate(divide="ignore"):
        log_interior = np.log(mass)
    log_interior[~np.isfinite(log_interior)] = -np.inf
    phi = np.r_[1.0, 0.0, fraction]
    log_mass = np.r_[log_stay_1, log_stay_2, log_interior]
    total = float(np.exp(logsumexp(log_mass)))
    log_mass = log_mass - logsumexp(log_mass)
    return phi, log_mass, total


def _component_likelihood(kernel, calibration, efficiencies, shape, mean, gradient):
    """Log-likelihood of each fixed efficiency, optionally with derivatives."""
    logs = []
    d_efficiency = []
    d_shape = []
    d_mean = []
    for efficiency in efficiencies:
        if gradient:
            log_p, deriv = kernel.state(
                efficiency, shape, mean, calibration, gradient=True,
            )
            logs.append(log_p)
            d_efficiency.append(deriv[:, 0])
            d_shape.append(deriv[:, 1])
            d_mean.append(deriv[:, 2])
        else:
            logs.append(kernel.state(
                efficiency, shape, mean, calibration, gradient=False,
            ))
    stacked = np.column_stack(logs)
    if not gradient:
        return stacked
    return (
        stacked,
        np.column_stack(d_efficiency),
        np.column_stack(d_shape),
        np.column_stack(d_mean),
    )


def fit_dynamic(counts, cal, *, n_starts=8, n_quad=8, seed=2026,
                bg_tail=0.0, _kernel=None, should_cancel=None, start=None):
    """Fit two states that exchange during each fixed window.

    The fitted fraction is the equilibrium occupancy of the lower-efficiency
    state. ``exchange_rate`` is the sum of the two leaving rates, in 1/s.
    A rate much slower than the window matches two static states. A rate
    much faster than the window collapses them to their average.
    """
    n = len(counts.nD)
    if n < 20:
        raise ValueError("Too few windows for a dynamic two-state fit.")
    if np.sum(counts.nD + counts.nA) == 0:
        raise ValueError("No photons: FRET efficiencies are not identifiable.")
    kernel = _kernel if _kernel is not None else _Kernel(counts, bg_tail)
    duration = float(counts.window_s)

    def unpack(x):
        e1, e2 = x[0], x[1]
        pi = 1.0 / (1.0 + np.exp(-x[2]))
        rate = np.exp(x[3])
        shape, mean = np.exp(x[4]), np.exp(x[5])
        return e1, e2, pi, rate, shape, mean

    def objective(x):
        e1, e2, pi, rate, shape, mean = unpack(x)
        phi, log_mass, _total = _occupation_parts(
            duration, rate, pi, n_quad=n_quad,
        )
        efficiencies = phi * e1 + (1.0 - phi) * e2
        logs, d_e, d_shape, d_mean = _component_likelihood(
            kernel, cal, efficiencies, shape, mean, gradient=True,
        )
        mixed = logs + log_mass
        log_mix = logsumexp(mixed, axis=1)
        weights = np.exp(mixed - log_mix[:, None])
        grad_e1 = np.sum(weights * d_e * phi)
        grad_e2 = np.sum(weights * d_e * (1.0 - phi))
        grad_shape = np.sum(weights * d_shape) * shape
        grad_mean = np.sum(weights * d_mean) * mean
        step = 1e-4
        pi_hi = min(pi + step, 1.0 - 1e-8)
        pi_lo = max(pi - step, 1e-8)
        _, mass_hi, _ = _occupation_parts(duration, rate, pi_hi, n_quad=n_quad)
        _, mass_lo, _ = _occupation_parts(duration, rate, pi_lo, n_quad=n_quad)
        d_mass_pi = _finite_difference(mass_hi, mass_lo, pi_hi - pi_lo)
        rate_hi = rate * np.exp(step)
        rate_lo = rate * np.exp(-step)
        _, mass_fast, _ = _occupation_parts(duration, rate_hi, pi, n_quad=n_quad)
        _, mass_slow, _ = _occupation_parts(duration, rate_lo, pi, n_quad=n_quad)
        d_mass_log_rate = _finite_difference(mass_fast, mass_slow, 2.0 * step)
        grad_pi = np.sum(weights * d_mass_pi) * pi * (1.0 - pi)
        grad_rate = np.sum(weights * d_mass_log_rate)
        return (
            -log_mix.sum(),
            -np.array([grad_e1, grad_e2, grad_pi, grad_rate, grad_shape, grad_mean]),
        )

    signal_mean = max(1.0, np.mean(counts.nD + counts.nA - counts.bD - counts.bA))
    mean_guess = signal_mean / ((1 + cal.leakage) * 0.5 + cal.gamma * (0.5 + cal.direct_ratio))
    upper_mean = max(1e4, float(np.max(counts.nD + counts.nA)) * 100 / cal.gamma)
    boxes = _state_boxes(start, 2, None)
    (e1_guess, e1_lo, e1_hi), (e2_guess, e2_lo, e2_hi) = boxes
    if start is None:
        equilibrium = 0.5
        exchanges = 1.0
        exchange_low, exchange_high = 1e-3, 1e3
    else:
        equilibrium = float(start.equilibrium)
        exchanges = float(start.exchanges_per_window)
        exchange_low = float(min(start.exchange_low, start.exchange_high))
        exchange_high = float(max(start.exchange_low, start.exchange_high))
    exchange_low = max(exchange_low, 1e-6)
    exchange_high = max(exchange_high, exchange_low * 1.01)
    equilibrium = float(np.clip(equilibrium, 0.02, 0.98))
    exchanges = float(np.clip(exchanges, exchange_low, exchange_high))
    bounds = [
        (e1_lo, e1_hi),
        (e2_lo, e2_hi),
        (-6.0, 6.0),
        (np.log(exchange_low / duration), np.log(exchange_high / duration)),
        (np.log(0.03), np.log(300.0)),
        (np.log(0.01), np.log(upper_mean)),
    ]
    rng = np.random.default_rng(seed)
    solutions, history = [], []
    best_fun = np.inf
    n_at_best = 0
    for attempt in range(n_starts):
        if should_cancel is not None and should_cancel():
            raise FitCancelled()
        if attempt == 0:
            guess = np.array([
                e1_guess, e2_guess,
                np.log(equilibrium / (1.0 - equilibrium)),
                np.log(exchanges / duration),
                np.log(2.0), np.log(mean_guess),
            ])
        else:
            pi_try = float(np.clip(equilibrium + rng.normal(0.0, 0.1), 0.02, 0.98))
            guess = np.array([
                rng.uniform(e1_lo, e1_hi),
                rng.uniform(e2_lo, e2_hi),
                np.log(pi_try / (1.0 - pi_try)),
                rng.uniform(np.log(exchange_low / duration), np.log(exchange_high / duration)),
                np.log(rng.uniform(1.0, 5.0)),
                np.log(mean_guess),
            ])
        result = minimize(
            objective, guess, jac=True, method="L-BFGS-B", bounds=bounds,
            options={"maxiter": 120, "ftol": 1e-8, "gtol": 1e-4},
        )
        usable = np.isfinite(getattr(result, "fun", np.nan)) and int(result.nit or 0) > 0
        history.append(result.fun if usable else np.nan)
        if usable:
            solutions.append(result)
            if result.fun < best_fun - 0.5:
                best_fun = result.fun
                n_at_best = 1
            elif result.fun <= best_fun + 0.5:
                n_at_best += 1
            if n_at_best >= 2:
                break
    if not solutions:
        raise RuntimeError(
            "The dynamic fit did not converge. Move the efficiency guesses "
            "inside their bounds, or narrow the exchange-rate range."
        )
    best = min(solutions, key=lambda item: item.fun)
    e1, e2, pi, rate, shape, mean = unpack(best.x)
    if e2 < e1:
        e1, e2 = e2, e1
        pi = 1.0 - pi
    phi, log_mass, _total = _occupation_parts(duration, rate, pi, n_quad=n_quad)
    efficiencies = phi * e1 + (1.0 - phi) * e2
    logs = _component_likelihood(
        kernel, cal, efficiencies, shape, mean, gradient=False,
    )
    mixed = logs + log_mass
    log_mix = logsumexp(mixed, axis=1)
    weights = np.exp(mixed - log_mix[:, None])
    expected_low = weights @ phi
    p = 6  # two efficiencies, equilibrium, rate, shape, mean
    at_bound = any(
        abs(value - lo) < 1e-4 or abs(value - hi) < 1e-4
        for value, (lo, hi) in zip(best.x, bounds)
    )
    return Fit(
        np.array([e1, e2]),
        np.array([pi, 1.0 - pi]),
        shape,
        mean,
        -best.fun,
        2 * p + 2 * best.fun,
        p * np.log(n) + 2 * best.fun,
        np.column_stack([expected_low, 1.0 - expected_low]),
        cal,
        n,
        len(solutions),
        np.asarray(history),
        at_bound,
        bg_tail,
        model="dynamic",
        exchange_rate=float(rate),
        window_s=duration,
    )


def fit_selected(counts, cal, models, *, n_starts=8, seed=2026,
                 bg_tail=0.0, should_cancel=None, start=None):
    """Fit the requested static and dynamic models on the same windows."""
    models = tuple(models)
    if not models:
        raise ValueError("Select at least one model.")
    kernel = _Kernel(counts, bg_tail)
    fits = []
    errors = []
    for index, model in enumerate(models):
        if should_cancel is not None and should_cancel():
            raise FitCancelled()
        try:
            if model == "dynamic-2":
                fits.append(fit_dynamic(
                    counts, cal, n_starts=n_starts, seed=seed + 17,
                    bg_tail=bg_tail, _kernel=kernel,
                    should_cancel=should_cancel, start=start,
                ))
            elif model in ("static-1", "static-2", "static-3"):
                n_states = int(model.rsplit("-", 1)[1])
                fits.append(fit_pda(
                    counts, cal, n_states=n_states, n_starts=n_starts,
                    seed=seed + n_states, bg_tail=bg_tail, _kernel=kernel,
                    should_cancel=should_cancel, start=start,
                ))
            else:
                raise ValueError(f"Unknown model {model}.")
        except FitCancelled:
            raise
        except Exception as error:
            name = "Dynamic 2 states" if model == "dynamic-2" else model
            errors.append(f"{name}: {error}")
        del index
    return fits, errors


def fit_caution(fit):
    """Return a short identifiability warning, or None when the fit looks stable."""
    reasons = []
    if fit.bound_warning:
        reasons.append("a parameter is at a bound")
    if np.any(fit.fractions < 0.01):
        reasons.append("a population fraction is below 0.01")
    if fit.n_states > 1 and np.any(np.diff(fit.efficiencies) < 0.02):
        reasons.append("states are closer than 0.02 in E")
    if fit.model == "dynamic" and fit.exchange_rate > 0 and fit.window_s > 0:
        cycles = fit.exchange_rate * fit.window_s
        if cycles < 0.05:
            reasons.append(
                "exchange is too slow to separate from two static states"
            )
        elif cycles > 30:
            reasons.append(
                "exchange is fast enough that the window mostly sees the average"
            )
    if not reasons:
        return None
    return (
        "Check: " + "; ".join(reasons) + ". Identifiability may be poor."
    )


def describe_model_choice(fits):
    """Plain-language comparison of fits that share the same windows."""
    fits = list(fits)
    if not fits:
        return ""
    lines = [
        "What the numbers mean",
        "logL: how well the photon counts match that number of states. Higher is better.",
        "AIC and BIC start from that match and penalize extra states. Lower is better.",
        "BIC penalizes extra states more than AIC. Use it as a guide, then look at the histogram.",
        "A BIC drop of about 10 or more is strong support for the extra state.",
        "A drop of less than about 2 means the simpler model is enough.",
        "Do not keep an extra state that has a tiny fraction or sits on top of another.",
        "",
    ]
    best = min(fits, key=lambda fit: fit.bic)
    lines.append(
        f"Lowest BIC on these windows: {best.label()}. "
        "That is a starting point, not proof of how many conformations are present."
    )
    lines.append("")
    static_fits = sorted(
        (fit for fit in fits if fit.model != 'dynamic'),
        key=lambda item: item.n_states,
    )
    dynamic_fits = [fit for fit in fits if fit.model == 'dynamic']
    previous = None
    for fit in static_fits:
        lines.extend(_describe_one_fit(fit))
        if previous is not None:
            lines.append('  ' + _bic_change(previous, fit))
        caution = fit_caution(fit)
        if caution:
            lines.append(f'  {caution}')
        lines.append('')
        previous = fit
    static_two = next((fit for fit in static_fits if fit.n_states == 2), None)
    static_one = next((fit for fit in static_fits if fit.n_states == 1), None)
    for fit in dynamic_fits:
        lines.extend(_describe_one_fit(fit))
        reference = static_two if static_two is not None else static_one
        if reference is not None:
            delta = reference.bic - fit.bic
            if delta >= 10:
                verdict = (
                    f'BIC is {delta:.0f} lower than {reference.label()}, '
                    'so exchange during the window improves the description.'
                )
            elif delta <= -2:
                verdict = (
                    f'BIC is {-delta:.0f} higher than {reference.label()}. '
                    'Two fixed states describe these windows at least as well.'
                )
            else:
                verdict = (
                    f'BIC is close to {reference.label()}. '
                    'Exchange is not clearly required.'
                )
            lines.append(f'  {verdict}')
        caution = fit_caution(fit)
        if caution:
            lines.append(f'  {caution}')
        lines.append('')
    return '\n'.join(lines).rstrip()


def _describe_one_fit(fit):
    lines = [fit.label()]
    if fit.model == 'dynamic':
        for index, (efficiency, fraction) in enumerate(
            zip(fit.efficiencies, fit.fractions), 1
        ):
            lines.append(
                f'  State {index}: E={efficiency:.2f}, '
                f'equilibrium {100 * fraction:.0f}%'
            )
        if fit.exchange_rate > 0:
            relaxation_ms = 1000.0 / fit.exchange_rate
            cycles = fit.exchange_rate * fit.window_s
            lines.append(
                f'  Exchange: {fit.exchange_rate:.3g} /s '
                f'(relaxation {relaxation_ms:.3g} ms, '
                f'{cycles:.2f} per window)'
            )
    else:
        for index, (efficiency, fraction) in enumerate(
            zip(fit.efficiencies, fit.fractions), 1
        ):
            lines.append(
                f'  State {index}: E={efficiency:.2f}, '
                f'{100 * fraction:.0f}% of windows'
            )
    lines.append(f'  logL={fit.log_likelihood:.1f} (higher is better)')
    lines.append(f'  AIC={fit.aic:.1f}, BIC={fit.bic:.1f} (lower is better)')
    lines.append(
        '  Shared brightness: '
        f'shape={fit.brightness_shape:.3g}, '
        f'mean={fit.brightness_mean:.3g} donor-reference photons per window'
    )
    return lines


def _bic_change(previous, fit):
    delta = previous.bic - fit.bic
    if delta >= 10:
        return (
            f'BIC is {delta:.0f} lower than {previous.label()}, '
            'so the extra state improves the description a lot.'
        )
    if delta >= 2:
        return (
            f'BIC is {delta:.0f} lower than {previous.label()}. '
            'The extra state helps; check that it is a separate peak.'
        )
    if delta >= -2:
        return (
            f'BIC is within {abs(delta):.0f} of {previous.label()}. '
            'The simpler model is enough unless the histogram shows a clear extra peak.'
        )
    return (
        f'BIC is {-delta:.0f} higher than {previous.label()}. '
        'The extra state is not supported.'
    )


def print_report(fit):
    """Print efficiencies, selected-window fractions and fit diagnostics."""
    print(f"\nK={fit.n_states}, windows={fit.n_observations}, "
          f"logL={fit.log_likelihood:.3f}, AIC={fit.aic:.2f}, BIC={fit.bic:.2f}")
    for k, (e, f) in enumerate(zip(fit.efficiencies, fit.fractions), 1):
        print(f"  State {k}: E={e:.5f}, fraction={f:.5f}")
    print(f"  Shared brightness: shape={fit.brightness_shape:.4g}, "
          f"mean={fit.brightness_mean:.4g} donor-reference photons/window")
    print(f"  Converged starts: {fit.converged_starts}/{len(fit.start_nll)}")
    finite = fit.start_nll[np.isfinite(fit.start_nll)]
    print(f"  Converged-start NLL range: {finite.min():.3f} .. {finite.max():.3f}")
    caution = fit_caution(fit)
    if caution:
        print(f"  {caution}")
    print("  Fractions describe retained burst windows; upstream selection is not corrected.")


def bootstrap(counts, fit, *, n_boot=200, n_starts=4, seed=812):
    """Percentile intervals conditional on K, calibrations and the model.

    Resamples complete independent burst windows, including background values.
    Sorting states by E resolves label permutations, but intervals are unreliable
    if peaks merge/split. Repeated measurements/block resampling are needed for
    serial drift or recurrence of the same molecule. Failed fits are reported.
    """
    if not isinstance(n_boot, (int, np.integer)) or n_boot < 20:
        raise ValueError("Use at least 20 bootstrap replicates; 200+ for reporting.")
    if np.unique(counts.burst_id).size != len(counts.burst_id):
        raise ValueError("Bootstrap expects one independent row per original burst.")
    rng = np.random.default_rng(seed)
    values, failed = [], 0
    for _ in range(n_boot):
        subset = counts.take(rng.integers(0, len(counts.nD), len(counts.nD)))
        try:
            r = fit_pda(subset, fit.calibration, n_states=fit.n_states,
                        n_starts=n_starts, initial_E=fit.efficiencies,
                        seed=int(rng.integers(2**31)), bg_tail=fit.bg_tail)
            values.append(np.r_[r.efficiencies, r.fractions])
        except RuntimeError:
            failed += 1
    if len(values) < 0.9*n_boot:
        raise RuntimeError(f"{failed}/{n_boot} bootstrap fits failed; inspect identifiability.")
    q = np.percentile(values, [2.5, 50, 97.5], axis=0).T
    return {"E_ci95_median": q[:fit.n_states],
            "fraction_ci95_median": q[fit.n_states:],
            "column_order": ("lower_2.5%", "median", "upper_97.5%"),
            "successful": len(values), "failed": failed,
            "replicates": np.asarray(values)}


def simulate_counts(n, efficiencies, fractions, cal, *, brightness_shape=3.0,
                    brightness_mean=60.0, bD=0.3, bA=0.2,
                    window_s=0.0005, seed=13):
    """Simulate THIS static generative model; bD/bA scalar or length-n arrays."""
    rng = np.random.default_rng(seed)
    E, f = np.asarray(efficiencies), np.asarray(fractions, dtype=float)
    if E.ndim != 1 or E.shape != f.shape or not ((E > 0) & (E < 1)).all():
        raise ValueError("Supply matching efficiency/fraction vectors, E in (0,1).")
    if not np.isfinite(f).all() or (f < 0).any() or not np.isclose(f.sum(), 1):
        raise ValueError("Fractions must be nonnegative and sum to one.")
    z = rng.choice(len(E), size=n, p=f)
    u = rng.gamma(brightness_shape, brightness_mean/brightness_shape, n)
    bd, ba = np.broadcast_to(bD, (n,)).copy(), np.broadcast_to(bA, (n,)).copy()
    cD = 1-E[z]
    cA = cal.gamma*(E[z]+cal.direct_ratio)+cal.leakage*cD
    nd = rng.poisson(u*cD+bd)
    na = rng.poisson(u*cA+ba)
    return Counts(nd, na, bd, ba, np.arange(n), window_s), z


def replicate_counts(counts, fit, *, repeats=30, seed=422):
    """Draw model windows that reuse the empirical background of ``counts``."""
    predicted, _states = _simulate_replicate(
        counts, fit, repeats=repeats, seed=seed,
    )
    return predicted


def _simulate_replicate(counts, fit, *, repeats, seed):
    if not isinstance(repeats, (int, np.integer)) or repeats < 1:
        raise ValueError("repeats must be a positive integer.")
    idx = np.tile(np.arange(len(counts.nD)), repeats)
    return simulate_counts(
        len(idx), fit.efficiencies, fit.fractions,
        fit.calibration, brightness_shape=fit.brightness_shape,
        brightness_mean=fit.brightness_mean,
        bD=counts.bD[idx], bA=counts.bA[idx],
        window_s=counts.window_s, seed=seed,
    )


def _simulate_dynamic(counts, fit, *, repeats, seed):
    """Draw dynamic windows. State id 0/1 stayed put; 2 exchanged."""
    if not isinstance(repeats, (int, np.integer)) or repeats < 1:
        raise ValueError("repeats must be a positive integer.")
    rng = np.random.default_rng(seed)
    n = len(counts.nD) * int(repeats)
    phi, log_mass, _total = _occupation_parts(
        fit.window_s, fit.exchange_rate, fit.fractions[0],
    )
    choice = rng.choice(len(phi), size=n, p=np.exp(log_mass))
    fraction = phi[choice]
    stayed_low = fraction > 0.98
    stayed_high = fraction < 0.02
    state_ids = np.full(n, 2, dtype=int)
    state_ids[stayed_low] = 0
    state_ids[stayed_high] = 1
    efficiency = fraction * fit.efficiencies[0] + (1.0 - fraction) * fit.efficiencies[1]
    idx = np.tile(np.arange(len(counts.nD)), repeats)
    background_d = counts.bD[idx]
    background_a = counts.bA[idx]
    brightness = rng.gamma(
        fit.brightness_shape,
        fit.brightness_mean / fit.brightness_shape,
        n,
    )
    donor_scale = 1.0 - efficiency
    acceptor_scale = (
        fit.calibration.gamma * (efficiency + fit.calibration.direct_ratio)
        + fit.calibration.leakage * donor_scale
    )
    donor = rng.poisson(brightness * donor_scale + background_d)
    acceptor = rng.poisson(brightness * acceptor_scale + background_a)
    predicted = Counts(
        donor, acceptor, background_d, background_a,
        np.arange(n), counts.window_s,
    )
    return predicted, state_ids


_STATE_COLORS = ("#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2")


def apparent_efficiency(nD, nA, bD, bA, cal):
    """Corrected FRET efficiency of each raw window.

    Background is subtracted, then leakage, gamma, and this module's
    direct-excitation ratio are inverted. Values outside [0, 1] are left
    unchanged so the caller can decide whether to histogram them.
    """
    donor = np.asarray(nD, dtype=float) - np.asarray(bD, dtype=float)
    acceptor = np.asarray(nA, dtype=float) - np.asarray(bA, dtype=float)
    acceptor = acceptor - cal.leakage * donor
    denominator = acceptor + cal.gamma * donor
    with np.errstate(divide="ignore", invalid="ignore"):
        efficiency = acceptor / denominator
    if cal.direct_ratio:
        efficiency = efficiency * (1.0 + cal.direct_ratio) - cal.direct_ratio
    return efficiency


def _in_unit_interval(values):
    values = np.asarray(values, dtype=float)
    return values[np.isfinite(values) & (values >= 0.0) & (values <= 1.0)]


def draw_predictive_check(figure, counts, fit, *, repeats=30, seed=422):
    """Draw the efficiency histogram with each state, plus a brightness check.

    The efficiency is computed for the same fixed windows that were fitted,
    not for the whole burst. Each state curve is that population after shot
    noise and background, scaled to the number of observed windows.
    """
    import matplotlib

    if fit.model == "dynamic":
        predicted, state_ids = _simulate_dynamic(
            counts, fit, repeats=repeats, seed=seed,
        )
        labels = (
            f"No switch, E={fit.efficiencies[0]:.2f}",
            f"No switch, E={fit.efficiencies[1]:.2f}",
            "Exchanged during the window",
        )
    else:
        predicted, state_ids = _simulate_replicate(
            counts, fit, repeats=repeats, seed=seed,
        )
        labels = tuple(
            f"State {state + 1}: E={efficiency:.2f}, {100 * fraction:.0f}%"
            for state, (efficiency, fraction) in enumerate(
                zip(fit.efficiencies, fit.fractions)
            )
        )
    observed_e = apparent_efficiency(
        counts.nD, counts.nA, counts.bD, counts.bA, fit.calibration,
    )
    predicted_e = apparent_efficiency(
        predicted.nD, predicted.nA, predicted.bD, predicted.bA, fit.calibration,
    )
    observed_color = matplotlib.rcParams["axes.edgecolor"]
    model_color = matplotlib.rcParams["text.color"]
    figure.clear()
    efficiency_ax, brightness_ax = figure.subplots(1, 2)
    edges = np.linspace(0, 1, 41)
    efficiency_ax.hist(
        _in_unit_interval(observed_e),
        bins=edges,
        histtype="stepfilled",
        alpha=0.35,
        color=observed_color,
        edgecolor=observed_color,
        label="Observed",
    )
    total_model = np.zeros(len(edges) - 1, dtype=float)
    groups = range(len(labels))
    for state in groups:
        state_e = _in_unit_interval(predicted_e[state_ids == state])
        state_counts, _ = np.histogram(state_e, bins=edges)
        state_counts = state_counts / repeats
        total_model += state_counts
        efficiency_ax.stairs(
            state_counts,
            edges,
            color=_STATE_COLORS[state % len(_STATE_COLORS)],
            linewidth=1.8,
            label=labels[state],
        )
    efficiency_ax.stairs(
        total_model,
        edges,
        color=model_color,
        linewidth=2.4,
        label="Sum of states",
    )
    efficiency_ax.set(
        xlabel="FRET efficiency of each window",
        ylabel="Windows",
        xlim=(0, 1),
        title="Fitted populations",
    )
    efficiency_ax.legend(fontsize=8, frameon=False)

    observed_total = counts.nD + counts.nA
    predicted_total = predicted.nD + predicted.nA
    upper = max(int(observed_total.max()), int(predicted_total.max()))
    count_bins = np.linspace(-0.5, upper + 0.5, 61)
    brightness_ax.hist(
        observed_total, bins=count_bins, density=True, histtype="step",
        color=observed_color, label="Observed",
    )
    brightness_ax.hist(
        predicted_total, bins=count_bins, density=True, histtype="step",
        color="tab:orange", label="Model",
    )
    brightness_ax.set(
        xlabel="Raw total photons per fixed window",
        ylabel="Density",
        title="Brightness check",
    )
    brightness_ax.legend(fontsize=8, frameon=False)
    return figure


def plot_check(counts, fit, *, repeats=30, seed=422):
    """Efficiency histogram with one curve per state, plus a brightness check."""
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(11, 4), constrained_layout=True)
    return draw_predictive_check(
        figure, counts, fit, repeats=repeats, seed=seed,
    )
