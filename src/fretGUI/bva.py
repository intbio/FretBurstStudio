"""Burst variance analysis, following Torella et al., Biophys. J. 2011.

Donor-excitation photons are split into non-overlapping windows of n photons.
The proximity ratio of a window or a burst is the uncorrected acceptor fraction

    E* = N_A / N_Dex

Background, gamma, and leakage are left in the counts, as in the paper.
s_i is the population standard deviation of the windows inside one burst.
Bursts are then grouped by their whole-burst E*. s_E* is the population
standard deviation of every window in a group, around one grand mean. The
confidence limit is the Bonferroni upper tail of that statistic when every
window is an independent binomial draw at the bin center.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binom

DEFAULT_PHOTONS_PER_WINDOW = 5
DEFAULT_BIN_WIDTH = 0.05
DEFAULT_MIN_BURSTS = 50
DEFAULT_ALPHA = 0.001
DEFAULT_REPLICATES = 200_000


@dataclass(frozen=True)
class BvaSettings:
    """Controls for one burst-variance calculation."""

    photons_per_window: int = DEFAULT_PHOTONS_PER_WINDOW
    bin_width: float = DEFAULT_BIN_WIDTH
    min_bursts: int = DEFAULT_MIN_BURSTS
    alpha: float = DEFAULT_ALPHA
    replicates: int = DEFAULT_REPLICATES
    seed: int | None = None


@dataclass(frozen=True)
class WindowStats:
    """Per-burst proximity ratio and window standard deviation."""

    E: np.ndarray
    s_i: np.ndarray
    window_E: np.ndarray
    window_burst: np.ndarray
    n_short: int


@dataclass(frozen=True)
class BinnedDeviation:
    """Pooled window standard deviation on every E* bin."""

    centers: np.ndarray
    s_E: np.ndarray
    n_bursts: np.ndarray
    n_windows: np.ndarray


@dataclass(frozen=True)
class BvaResult:
    """Density, binned standard deviations, and upper confidence limits."""

    n: int
    bin_width: float
    alpha: float
    E: np.ndarray
    s_i: np.ndarray
    centers: np.ndarray
    s_E: np.ndarray
    upper: np.ndarray
    bin_bursts: np.ndarray
    bin_windows: np.ndarray
    dynamic_score: float
    info: dict
    kde_x: np.ndarray | None = None
    kde_y: np.ndarray | None = None
    kde_z: np.ndarray | None = None


def shot_noise(E, n):
    """Shot-noise standard deviation of an n-photon window, eq. 4."""
    E = np.asarray(E, dtype=float)
    n = int(n)
    if n < 1:
        raise ValueError("Window size must be at least 1 photon.")
    return np.sqrt(np.clip(E * (1.0 - E), 0.0, None) / n)


def bin_grid(width):
    """Equal E* bins that tile (0, 1].

    A requested width of 0.05 gives 20 bins centered on 0.05, 0.10, ..., 1.00.
    The bin centered on 0.5 is then [0.475, 0.525).
    """
    width = float(width)
    if not np.isfinite(width) or width <= 0.0 or width > 1.0:
        raise ValueError("Bin width must be between 0 and 1.")
    n_bins = max(int(round(1.0 / width)), 1)
    step = 1.0 / n_bins
    centers = np.arange(1, n_bins + 1, dtype=float) / n_bins
    half = step / 2.0
    return centers, half, step


def assign_bins(E, width):
    """Return the bin index of each E*, or -1 when E* falls outside the grid."""
    centers, half, step = bin_grid(width)
    values = np.asarray(E, dtype=float).reshape(-1)
    left = centers - half
    index = np.searchsorted(left, values, side="right") - 1
    assigned = np.full(values.shape, -1, dtype=int)
    valid = (index >= 0) & (index < centers.size)
    if not np.any(valid):
        return assigned, centers
    chosen = index[valid]
    in_span = values[valid] < left[chosen] + step
    assigned_valid = np.full(chosen.shape, -1, dtype=int)
    assigned_valid[in_span] = chosen[in_span]
    assigned[valid] = assigned_valid
    return assigned, centers


def window_statistics(acceptor, istart, istop, n):
    """Population standard deviation of non-overlapping n-photon windows.

    Burst E* uses every donor-excitation photon. s_i uses only complete
    windows, so a short remainder changes E* and not s_i. Bursts with fewer
    than n photons are omitted and counted in ``n_short``.
    """
    acceptor = np.asarray(acceptor)
    if acceptor.ndim != 1:
        raise ValueError("Acceptor mask must be one-dimensional.")
    istart = np.asarray(istart, dtype=np.int64).reshape(-1)
    istop = np.asarray(istop, dtype=np.int64).reshape(-1)
    if istart.shape != istop.shape:
        raise ValueError("Burst start and stop indexes do not match.")
    n = int(n)
    if n < 2:
        raise ValueError("Window size must be at least 2 photons.")
    if istart.size and (
        np.any(istart < 0) or np.any(istop >= acceptor.size)
    ):
        raise ValueError(
            "Burst indexes fall outside the donor-excitation photon stream."
        )

    lengths = istop - istart + 1
    n_windows = np.zeros(istart.shape, dtype=np.int64)
    positive = lengths > 0
    n_windows[positive] = lengths[positive] // n
    keep = n_windows >= 1
    n_short = int(np.count_nonzero(~keep))
    if not np.any(keep):
        empty = np.array([], dtype=float)
        empty_i = np.array([], dtype=np.int64)
        return WindowStats(empty, empty.copy(), empty.copy(), empty_i, n_short)

    istart = istart[keep]
    istop = istop[keep]
    lengths = lengths[keep]
    n_windows = n_windows[keep]
    flags = np.asarray(acceptor, dtype=np.int8)
    cumulative = np.empty(flags.size + 1, dtype=np.int64)
    cumulative[0] = 0
    np.cumsum(flags, out=cumulative[1:])

    E = (cumulative[istop + 1] - cumulative[istart]) / lengths.astype(float)
    group, offset = _group_offsets(n_windows)
    starts = np.repeat(istart, n_windows) + offset * n
    acceptor_counts = cumulative[starts + n] - cumulative[starts]
    window_E = acceptor_counts / float(n)
    sum_E = np.bincount(group, weights=window_E, minlength=istart.size)
    sum_E2 = np.bincount(
        group, weights=window_E * window_E, minlength=istart.size
    )
    s_i = _std_from_sums(sum_E, sum_E2, n_windows.astype(float))
    return WindowStats(E, s_i, window_E, group, n_short)


def binned_standard_deviation(E, window_E, window_burst, bin_width):
    """Pooled standard deviation of windows whose bursts fall in each E* bin."""
    E = np.asarray(E, dtype=float).reshape(-1)
    window_E = np.asarray(window_E, dtype=float).reshape(-1)
    window_burst = np.asarray(window_burst, dtype=np.int64).reshape(-1)
    if window_E.shape != window_burst.shape:
        raise ValueError("Window values and burst indexes do not match.")
    if window_burst.size and (
        np.any(window_burst < 0) or np.any(window_burst >= E.size)
    ):
        raise ValueError("A window points at a burst that does not exist.")

    assigned, centers = assign_bins(E, bin_width)
    n_bins = centers.size
    n_bursts = np.bincount(assigned[assigned >= 0], minlength=n_bins)
    if window_burst.size == 0:
        s_E = np.full(n_bins, np.nan)
        n_windows = np.zeros(n_bins, dtype=int)
        return BinnedDeviation(centers, s_E, n_bursts, n_windows)

    window_bin = assigned[window_burst]
    use = window_bin >= 0
    n_windows = np.bincount(window_bin[use], minlength=n_bins)
    sum_E = np.bincount(
        window_bin[use], weights=window_E[use], minlength=n_bins
    )
    sum_E2 = np.bincount(
        window_bin[use],
        weights=window_E[use] * window_E[use],
        minlength=n_bins,
    )
    s_E = np.full(n_bins, np.nan)
    present = n_windows > 0
    s_E[present] = _std_from_sums(
        sum_E[present], sum_E2[present], n_windows[present].astype(float)
    )
    return BinnedDeviation(centers, s_E, n_bursts, n_windows)


def confidence_limits(centers, n_windows, n, alpha, family, replicates, rng):
    """Upper tail of the pooled standard deviation under a static binomial.

    ``family`` is the number of bins tested in the experiment. The per-bin
    tail probability is alpha / family (Bonferroni).
    """
    centers = np.asarray(centers, dtype=float).reshape(-1)
    n_windows = np.asarray(n_windows, dtype=np.int64).reshape(-1)
    if centers.shape != n_windows.shape:
        raise ValueError("Confidence limits need one window count per bin.")
    alpha = float(alpha)
    family = int(family)
    replicates = int(replicates)
    n = int(n)
    if not 0.0 < alpha < 1.0:
        raise ValueError("Confidence level must be between 0 and 1.")
    if family < 1:
        raise ValueError("Bonferroni correction needs at least one bin.")
    if replicates < 1:
        raise ValueError("Monte Carlo needs at least one replicate.")
    if n < 2:
        raise ValueError("Window size must be at least 2 photons.")

    probability = 1.0 - alpha / family
    upper = np.empty(centers.size, dtype=float)
    for index, (center, windows) in enumerate(zip(centers, n_windows)):
        upper[index] = _monte_carlo_upper(
            int(windows),
            n,
            success=float(center),
            quantile=probability,
            replicates=replicates,
            rng=rng,
        )
    return upper


def dynamic_score(s_E, upper):
    """Sum of squared excesses of s_E* above the confidence limit, eq. 8."""
    excess = np.asarray(s_E, dtype=float) - np.asarray(upper, dtype=float)
    excess = excess[np.isfinite(excess) & (excess > 0.0)]
    if excess.size == 0:
        return 0.0
    return float(np.sum(excess * excess))


def analyze_bursts(
    acceptor,
    istart,
    istop,
    settings=None,
    requested_bursts=None,
    excluded_gapped=0,
):
    """Windows, binned s_E*, and confidence limits for one photon stream."""
    settings = _checked_settings(settings)
    stats = window_statistics(
        acceptor, istart, istop, settings.photons_per_window
    )
    requested = (
        int(stats.E.size + stats.n_short)
        if requested_bursts is None
        else int(requested_bursts)
    )
    info = {
        "requested_bursts": requested,
        "excluded_short": int(stats.n_short),
        "excluded_gapped": int(excluded_gapped),
        "kept_bursts": int(stats.E.size),
        "bins_above": 0,
        "replicates": int(settings.replicates),
    }
    binned = binned_standard_deviation(
        stats.E, stats.window_E, stats.window_burst, settings.bin_width
    )
    shown = binned.n_bursts >= settings.min_bursts
    centers = binned.centers[shown]
    s_E = binned.s_E[shown]
    bin_bursts = binned.n_bursts[shown]
    bin_windows = binned.n_windows[shown]
    if centers.size == 0:
        upper = np.array([], dtype=float)
        score = 0.0
    else:
        rng = np.random.default_rng(settings.seed)
        upper = confidence_limits(
            centers,
            bin_windows,
            settings.photons_per_window,
            settings.alpha,
            centers.size,
            settings.replicates,
            rng,
        )
        score = dynamic_score(s_E, upper)
        info["bins_above"] = int(np.count_nonzero(s_E > upper))
    kde_x, kde_y, kde_z = _kde_grid(
        stats.E,
        stats.s_i,
        _axis_limit(settings.photons_per_window, stats.s_i, s_E, upper),
    )
    return BvaResult(
        n=settings.photons_per_window,
        bin_width=float(bin_grid(settings.bin_width)[2]),
        alpha=settings.alpha,
        E=stats.E,
        s_i=stats.s_i,
        centers=centers,
        s_E=s_E,
        upper=upper,
        bin_bursts=bin_bursts,
        bin_windows=bin_windows,
        dynamic_score=score,
        info=info,
        kde_x=kde_x,
        kde_y=kde_y,
        kde_z=kde_z,
    )


def analyze_measurement(data, ich=0, settings=None):
    """Run burst variance analysis on one spot of a fretbursts measurement."""
    settings = _checked_settings(settings)
    ich = int(ich)
    istart, istop, acceptor, excluded_gapped, requested = _extract_spot(
        data, ich
    )
    if requested == 0 or istart is None:
        info = {
            "requested_bursts": int(requested),
            "excluded_short": 0,
            "excluded_gapped": int(excluded_gapped),
            "kept_bursts": 0,
            "bins_above": 0,
            "replicates": int(settings.replicates),
        }
        empty = np.array([], dtype=float)
        empty_i = np.array([], dtype=int)
        return BvaResult(
            n=settings.photons_per_window,
            bin_width=float(bin_grid(settings.bin_width)[2]),
            alpha=settings.alpha,
            E=empty,
            s_i=empty.copy(),
            centers=empty.copy(),
            s_E=empty.copy(),
            upper=empty.copy(),
            bin_bursts=empty_i,
            bin_windows=empty_i.copy(),
            dynamic_score=0.0,
            info=info,
        )
    return analyze_bursts(
        acceptor,
        istart,
        istop,
        settings,
        requested_bursts=requested,
        excluded_gapped=excluded_gapped,
    )


def format_summary(result):
    """One-line description of the bursts kept and the bins above the limit."""
    info = result.info
    text = (
        f"Bursts: {info['requested_bursts']} requested, "
        f"{info['excluded_short']} shorter than {result.n} photons, "
        f"{info['excluded_gapped']} with a fusion gap, "
        f"{info['kept_bursts']} kept."
    )
    if result.centers.size == 0:
        return (
            text
            + " No bin has enough bursts for an average or a confidence limit."
        )
    percent = (1.0 - result.alpha) * 100.0
    percent_text = f"{percent:.1f}".rstrip("0").rstrip(".")
    return (
        text
        + f" {info['bins_above']} of {result.centers.size} bins are above "
        + f"the {percent_text}% confidence limit. "
        + f"Dynamic score: {result.dynamic_score:.4g}."
    )


def _kde_grid(E, s_i, ymax):
    """Kernel-density grid of the burst cloud, or nothing if it is too small."""
    finite = np.isfinite(E) & np.isfinite(s_i)
    x = np.asarray(E, dtype=float)[finite]
    y = np.asarray(s_i, dtype=float)[finite]
    if x.size < 5 or np.ptp(x) < 1e-9 or np.ptp(y) < 1e-9:
        return None, None, None
    if x.size > 6000:
        chosen = np.random.default_rng(0).choice(x.size, 6000, replace=False)
        x = x[chosen]
        y = y[chosen]
    from scipy.stats import gaussian_kde

    try:
        density = gaussian_kde(np.vstack([x, y]))
    except np.linalg.LinAlgError:
        return None, None, None
    x_grid = np.linspace(0.0, 1.0, 80)
    y_grid = np.linspace(0.0, float(ymax), 80)
    xx, yy = np.meshgrid(x_grid, y_grid)
    values = density(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
    peak = float(np.nanmax(values))
    if not np.isfinite(peak) or peak <= 0.0:
        return None, None, None
    return x_grid, y_grid, values


def y_limit(result):
    """Axis limit that keeps the shot-noise peak and any dynamic points."""
    return _axis_limit(result.n, result.s_i, result.s_E, result.upper)


def _axis_limit(n, s_i, s_E, upper):
    floor = 1.0 / np.sqrt(n)
    peaks = [floor]
    for values in (s_i, s_E, upper):
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size:
            peaks.append(float(np.max(finite)) * 1.05)
    return max(peaks)


def _blue_density_cmap(n_colors):
    """One blue, more opaque where the kernel density is higher."""
    from matplotlib.colors import ListedColormap

    blue = (0.16, 0.40, 0.70)
    alphas = np.linspace(0.14, 0.90, n_colors)
    return ListedColormap([(*blue, float(alpha)) for alpha in alphas])


def draw_bva(figure, result):
    """Draw the blue density, shot-noise curve, confidence band, and s_E*."""
    import matplotlib

    figure.clear()
    ax = figure.add_subplot(111)
    ymax = y_limit(result)
    if result.kde_z is not None:
        peak = float(np.nanmax(result.kde_z))
        n_bands = 16
        levels = np.linspace(0.05 * peak, peak, n_bands)
        density = ax.contourf(
            result.kde_x,
            result.kde_y,
            result.kde_z,
            levels=levels,
            cmap=_blue_density_cmap(n_bands - 1),
            zorder=1,
        )
        density.set_edgecolor("none")
        density.set_linewidth(0)

    curve = np.linspace(0.0, 1.0, 201)
    ink = matplotlib.rcParams["text.color"]
    ax.plot(
        curve,
        shot_noise(curve, result.n),
        color=ink,
        linestyle="--",
        linewidth=1.8,
        label="shot noise",
        zorder=3,
    )
    if result.centers.size:
        percent = (1.0 - result.alpha) * 100.0
        percent_text = f"{percent:.1f}".rstrip("0").rstrip(".")
        half = float(result.bin_width) / 2.0
        labeled = False
        for center, limit in zip(result.centers, result.upper):
            ax.fill_between(
                [max(0.0, float(center) - half), min(1.0, float(center) + half)],
                0.0,
                float(limit),
                color="0.5",
                alpha=0.28,
                linewidth=0,
                label=None if labeled else f"{percent_text}% limit",
                zorder=1,
            )
            labeled = True
        above = result.s_E > result.upper
        if np.any(~above):
            ax.plot(
                result.centers[~above],
                result.s_E[~above],
                linestyle="none",
                marker="^",
                color=ink,
                markersize=7,
                label=r"$s_{E^*}$",
                zorder=4,
            )
        if np.any(above):
            ax.plot(
                result.centers[above],
                result.s_E[above],
                linestyle="none",
                marker="^",
                color="#d62728",
                markersize=7,
                label="above limit",
                zorder=4,
            )
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, ymax)
    ax.set_xlabel(r"$E^*$")
    ax.set_ylabel(r"$s_i$")
    ax.text(
        0.02,
        0.98,
        f"n = {result.n}\n{result.info['kept_bursts']} bursts",
        transform=ax.transAxes,
        va="top",
        ha="left",
    )
    ax.legend(loc="upper right", frameon=True)
    return ax


def _checked_settings(settings):
    if settings is None:
        settings = BvaSettings()
    photons = int(settings.photons_per_window)
    min_bursts = int(settings.min_bursts)
    replicates = int(settings.replicates)
    alpha = float(settings.alpha)
    if photons < 2:
        raise ValueError("Window size must be at least 2 photons.")
    if min_bursts < 1:
        raise ValueError("Minimum bursts per bin must be at least 1.")
    if replicates < 1:
        raise ValueError("Monte Carlo needs at least one replicate.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("Confidence level must be between 0 and 1.")
    bin_grid(settings.bin_width)
    if (
        photons == settings.photons_per_window
        and min_bursts == settings.min_bursts
        and replicates == settings.replicates
    ):
        return settings
    return BvaSettings(
        photons_per_window=photons,
        bin_width=settings.bin_width,
        min_bursts=min_bursts,
        alpha=alpha,
        replicates=replicates,
        seed=settings.seed,
    )


def _extract_spot(data, ich):
    import fretbursts

    nch = 1
    try:
        nch = max(1, int(getattr(data, "nch", 1) or 1))
    except (TypeError, ValueError):
        nch = 1
    if ich < 0 or ich >= nch:
        raise ValueError(f"Spot {ich + 1} is not in this measurement.")
    bursts_by_spot = getattr(data, "mburst", None)
    if bursts_by_spot is None or ich >= len(bursts_by_spot):
        raise ValueError("No bursts. Run burst search before variance analysis.")
    bursts = bursts_by_spot[ich]
    if bursts is None:
        raise ValueError("No bursts. Run burst search before variance analysis.")

    all_times = np.asarray(data.get_ph_times(ich=ich))
    ph_sel = fretbursts.Ph_sel
    dex_mask = _as_bool_mask(
        data.get_ph_mask(ich=ich, ph_sel=ph_sel(Dex="DAem")),
        all_times.size,
    )
    aem_mask = _as_bool_mask(
        data.get_ph_mask(ich=ich, ph_sel=ph_sel(Dex="Aem")),
        all_times.size,
    )
    acceptor = aem_mask[dex_mask]
    if acceptor.size == 0:
        raise ValueError("This measurement has no donor-excitation photons.")

    requested = _burst_count(bursts)
    bursts, excluded_gapped = _drop_gapped(bursts)
    if _burst_count(bursts) == 0:
        return None, None, acceptor, excluded_gapped, requested
    # Burst search stores indexes into the full timestamp array
    # (FRETBursts index_allph=True). Selecting donor-excitation photons
    # by those indexes stays valid when a burst starts or ends in the
    # acceptor period. recompute_index_reduce walks off the array there.
    istart, istop = _bounds_on_dex(bursts, dex_mask)
    return istart, istop, acceptor, excluded_gapped, requested


def _bounds_on_dex(bursts, dex_mask):
    """Donor-excitation indexes of bursts stored on the full timestamp array."""
    dex_mask = np.asarray(dex_mask, dtype=bool)
    dex_index = np.flatnonzero(dex_mask)
    istart = np.asarray(bursts.istart, dtype=np.int64).reshape(-1)
    istop = np.asarray(bursts.istop, dtype=np.int64).reshape(-1)
    if istart.shape != istop.shape:
        raise ValueError("Burst start and stop indexes do not match.")
    if istart.size and (
        np.any(istart < 0) or np.any(istop >= dex_mask.size)
    ):
        raise ValueError("Burst indexes fall outside the photon stream.")
    left = np.searchsorted(dex_index, istart, side="left")
    right = np.searchsorted(dex_index, istop, side="right") - 1
    dex_start = np.zeros(istart.shape, dtype=np.int64)
    dex_stop = np.full(istart.shape, -1, dtype=np.int64)
    if istart.size:
        keep = (right >= left) & (left < dex_index.size)
        dex_start[keep] = left[keep]
        dex_stop[keep] = right[keep]
    return dex_start, dex_stop


def _as_bool_mask(mask, size):
    if isinstance(mask, slice):
        out = np.zeros(size, dtype=bool)
        out[mask] = True
        return out
    array = np.asarray(mask)
    if array.dtype == np.bool_ and array.shape == (size,):
        return array
    if array.dtype == np.bool_ and array.ndim == 0:
        return np.full(size, bool(array), dtype=bool)
    raise TypeError("Photon mask could not be aligned to the timestamps.")


def _burst_count(bursts):
    count = getattr(bursts, "num_bursts", None)
    if count is not None and not callable(count):
        return int(count)
    istart = getattr(bursts, "istart", None)
    if istart is not None and not callable(istart):
        return int(np.asarray(istart).reshape(-1).size)
    return sum(1 for _ in bursts)


def _drop_gapped(bursts):
    gap = getattr(bursts, "gap", None)
    if gap is None or callable(gap):
        return bursts, 0
    gap = np.asarray(gap)
    if gap.size == 0:
        return bursts, 0
    keep = gap <= 0
    excluded = int(gap.size - np.count_nonzero(keep))
    if excluded == 0:
        return bursts, 0
    return bursts[keep], excluded


def _group_offsets(counts):
    counts = np.asarray(counts, dtype=np.int64)
    total = int(counts.sum())
    if total == 0:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty.copy()
    group = np.repeat(np.arange(counts.size, dtype=np.int64), counts)
    group_start = np.cumsum(counts) - counts
    offset = np.arange(total, dtype=np.int64) - np.repeat(group_start, counts)
    return group, offset


def _std_from_sums(sum_x, sum_x2, count):
    mean = sum_x / count
    variance = sum_x2 / count - mean * mean
    return np.sqrt(np.maximum(variance, 0.0))


def _monte_carlo_upper(n_windows, n, success, quantile, replicates, rng):
    if n_windows <= 1:
        return 0.0
    success = float(np.clip(success, 0.0, 1.0))
    outcomes = np.arange(n + 1)
    weights = np.asarray(binom.pmf(outcomes, n, success), dtype=float)
    weights = np.clip(weights, 0.0, None)
    total = float(weights.sum())
    if not np.isfinite(total) or total <= 0.0:
        weights = np.zeros(n + 1, dtype=float)
        weights[int(round(success * n))] = 1.0
    else:
        weights /= total
    counts = rng.multinomial(int(n_windows), weights, size=int(replicates))
    values = outcomes / float(n)
    mean = counts @ values / float(n_windows)
    second = counts @ (values * values) / float(n_windows)
    samples = np.sqrt(np.maximum(second - mean * mean, 0.0))
    return _upper_quantile(samples, quantile)


def _upper_quantile(samples, probability):
    ordered = np.sort(np.asarray(samples, dtype=float))
    if ordered.size == 0:
        return np.nan
    rank = int(np.ceil(float(probability) * ordered.size)) - 1
    rank = min(max(rank, 0), ordered.size - 1)
    return float(ordered[rank])
