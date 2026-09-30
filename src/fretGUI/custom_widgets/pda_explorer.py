"""Photon-distribution window: static states and two-state exchange."""

from __future__ import annotations

import threading
import warnings

import numpy as np
from Qt import QtCore, QtWidgets
from Qt.QtCore import Signal

from fretGUI.custom_widgets.plot_widget import TemplatePlotWidget, set_matplotlib_theme
from fretGUI.static_pda import (
    Calibration,
    FitCancelled,
    FitStart,
    describe_model_choice,
    draw_predictive_check,
    extract_group,
    fit_selected,
)

_NOTE = (
    "The histogram is the FRET efficiency of each short window, not the "
    "whole-burst efficiency. Static curves are fixed states. The dynamic "
    "model also draws windows that switched during the bin. The heavier "
    "curve is the sum and should follow the filled histogram."
)


def _channel_factor(data, name, ich, default):
    """Read a scalar correction, or the value for one spot."""
    if data is None:
        return default
    try:
        value = getattr(data, name)
    except Exception:
        return default
    if value is None:
        return default
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return default
    if array.size == 0:
        return default
    if array.ndim == 0:
        number = float(array)
    else:
        flat = np.ravel(array)
        number = float(flat[ich] if ich < flat.size else flat[0])
    if not np.isfinite(number):
        return default
    if name == "gamma":
        return number if number > 0 else default
    return number if number >= 0 else default


class _FitSignals(QtCore.QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int)


class _PdaFitRunnable(QtCore.QRunnable):
    """Fit the selected static and dynamic models off the GUI thread."""

    def __init__(self, counts, calibration, models, generation, cancel_event, signals, start):
        super().__init__()
        self.setAutoDelete(False)
        self.counts = counts
        self.calibration = calibration
        self.models = tuple(models)
        self.start = start
        self.generation = generation
        self.cancel_event = cancel_event
        self.signals = signals

    def run(self):
        try:
            fits, errors = fit_selected(
                self.counts,
                self.calibration,
                self.models,
                n_starts=8,
                should_cancel=self.cancel_event.is_set,
                start=self.start,
            )
        except FitCancelled:
            self.signals.cancelled.emit(self.generation)
        except Exception as error:
            self.signals.failed.emit(self.generation, str(error))
        else:
            self.signals.succeeded.emit(self.generation, (fits, errors))


class PdaExplorerWindow(QtWidgets.QDialog):
    """Separate window for static and dynamic photon-distribution fits."""

    file_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photon Distribution Analysis")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinMaxButtonsHint
        )
        self.resize(1100, 760)

        self._data = None
        self._file_label = None
        self._counts = None
        self._fits = None
        self._loaded_gamma = None
        self._loaded_leakage = None
        self._updating = False
        self._busy = False
        self._restart = False
        self._closing = False
        self._generation = 0
        self._cancel = threading.Event()
        self._runnable = None
        self._theme_kind = "light"
        self._theme_colors = None
        self._laying_out = False
        self._signals = _FitSignals(self)
        self._signals.succeeded.connect(self._on_succeeded)
        self._signals.failed.connect(self._on_failed)
        self._signals.cancelled.connect(self._on_cancelled)

        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(QtWidgets.QLabel("File"))
        self.file_combo = QtWidgets.QComboBox()
        self.file_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        file_row.addWidget(self.file_combo, 1)
        self.spot_label = QtWidgets.QLabel("Spot")
        self.spot_combo = QtWidgets.QComboBox()
        file_row.addWidget(self.spot_label)
        file_row.addWidget(self.spot_combo)
        root.addLayout(file_row)

        form = QtWidgets.QGridLayout()
        self.window_spin = self._spin(0.05, 50.0, 0.5, 3, 0.1, " ms")
        self.window_spin.setToolTip(
            "Length of the central window taken from each burst. "
            "Bursts shorter than this are excluded."
        )
        self.gamma_spin = self._spin(0.01, 20.0, 1.0, 3, 0.01)
        self.gamma_spin.setToolTip(
            "Gamma correction, prefilled from the measurement. "
            "Editing it here does not change the pipeline."
        )
        self.leakage_spin = self._spin(0.0, 2.0, 0.0, 4, 0.001)
        self.leakage_spin.setToolTip(
            "Donor bleed-through into the acceptor channel, "
            "prefilled from the measurement. Editing it here does not "
            "change the pipeline."
        )
        self.direct_spin = self._spin(0.0, 2.0, 0.0, 4, 0.001)
        self.direct_spin.setToolTip(
            "Acceptor/donor absorption cross-section at the donor laser. "
            "This is not the ALEX Direct ex. correction. "
            "Use 0 when direct acceptor excitation is negligible."
        )
        form.addWidget(QtWidgets.QLabel("Window"), 0, 0)
        form.addWidget(self.window_spin, 0, 1)
        form.addWidget(QtWidgets.QLabel("Gamma"), 0, 2)
        form.addWidget(self.gamma_spin, 0, 3)
        form.addWidget(QtWidgets.QLabel("Leakage"), 0, 4)
        form.addWidget(self.leakage_spin, 0, 5)
        form.addWidget(QtWidgets.QLabel("Direct excitation"), 0, 6)
        form.addWidget(self.direct_spin, 0, 7)
        root.addLayout(form)

        self.preview_label = QtWidgets.QLabel("No measurement selected.")
        self.preview_label.setWordWrap(True)
        root.addWidget(self.preview_label)

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(QtWidgets.QLabel("Models"))
        self._model_boxes = []
        for key, text, checked, tip in (
            (
                "static-1",
                "1 state",
                True,
                "One FRET efficiency. The width is only shot noise and background.",
            ),
            (
                "static-2",
                "2 states",
                True,
                "Two fixed FRET efficiencies. Each window stays in one state.",
            ),
            (
                "static-3",
                "3 states",
                False,
                "Three fixed FRET efficiencies.",
            ),
            (
                "dynamic-2",
                "Dynamic 2 states",
                True,
                "Two states that can exchange during the window. "
                "Also fits the exchange rate.",
            ),
        ):
            box = QtWidgets.QCheckBox(text)
            box.setChecked(checked)
            box.setToolTip(tip)
            model_row.addWidget(box)
            self._model_boxes.append((key, box))
        model_row.addStretch(1)
        root.addLayout(model_row)

        guess_grid = QtWidgets.QGridLayout()
        for column, title in enumerate(("Guess", "Low", "High"), start=1):
            guess_grid.addWidget(QtWidgets.QLabel(title), 0, column)
        self._efficiency_spins = []
        defaults = ((0.2, 0.01, 0.99), (0.5, 0.01, 0.99), (0.8, 0.01, 0.99))
        efficiency_tip = (
            "First try starts at Guess and stays between Low and High. "
            "1 state uses E1. 2 states and Dynamic use E1 and E2. "
            "3 states uses E1, E2, and E3."
        )
        for row, (name, values) in enumerate(zip(("E1", "E2", "E3"), defaults), start=1):
            label = QtWidgets.QLabel(name)
            label.setToolTip(efficiency_tip)
            guess_grid.addWidget(label, row, 0)
            spins = []
            for column, value in enumerate(values, start=1):
                spin = self._spin(0.0, 1.0, value, 2, 0.01)
                spin.setToolTip(efficiency_tip)
                guess_grid.addWidget(spin, row, column)
                spins.append(spin)
            self._efficiency_spins.append(tuple(spins))
        fraction_tip = "Starting equilibrium occupancy of the lower-efficiency state."
        fraction_label = QtWidgets.QLabel("Low-state fraction")
        fraction_label.setToolTip(fraction_tip)
        self._equilibrium_spin = self._spin(0.02, 0.98, 0.5, 2, 0.05)
        self._equilibrium_spin.setToolTip(fraction_tip)
        guess_grid.addWidget(fraction_label, 4, 0)
        guess_grid.addWidget(self._equilibrium_spin, 4, 1)
        rate_tip = (
            "Dynamic model only. Guess and bounds for how many exchanges "
            "occur during one window. 1 means the relaxation time equals the window."
        )
        rate_label = QtWidgets.QLabel("Exchanges / window")
        rate_label.setToolTip(rate_tip)
        guess_grid.addWidget(rate_label, 5, 0)
        self._exchange_spins = []
        for column, value in enumerate((1.0, 0.001, 1000.0), start=1):
            spin = self._spin(0.0001, 10000.0, value, 3, 0.1)
            spin.setToolTip(rate_tip)
            guess_grid.addWidget(spin, 5, column)
            self._exchange_spins.append(spin)
        root.addLayout(guess_grid)

        button_row = QtWidgets.QHBoxLayout()
        self.fit_btn = QtWidgets.QPushButton("Fit")
        self.fit_btn.setEnabled(False)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setEnabled(False)
        button_row.addWidget(self.fit_btn)
        button_row.addWidget(QtWidgets.QLabel("Show model"))
        button_row.addWidget(self.model_combo)
        button_row.addStretch(1)
        root.addLayout(button_row)

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMaximumHeight(280)
        root.addWidget(self.results)

        self.plot_widget = TemplatePlotWidget(mpl_width=10, mpl_height=3.6)
        self.plot_widget.canvas.mpl_connect("resize_event", self._on_plot_resize)
        root.addWidget(self.plot_widget, 1)

        note = QtWidgets.QLabel(_NOTE)
        note.setWordWrap(True)
        root.addWidget(note)

        self.file_combo.activated.connect(self._on_file_combo_activated)
        self.spot_combo.activated.connect(self._on_spot_changed)
        self.window_spin.valueChanged.connect(self._on_window_changed)
        for spin in (self.gamma_spin, self.leakage_spin, self.direct_spin):
            spin.valueChanged.connect(self._on_calibration_changed)
        self.fit_btn.clicked.connect(self._on_fit_clicked)
        self.model_combo.activated.connect(self._draw_selected)
        self.spot_label.setVisible(False)
        self.spot_combo.setVisible(False)

    @staticmethod
    def _spin(minimum, maximum, value, decimals, step, suffix=""):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        if suffix:
            spin.setSuffix(suffix)
        spin.setMinimumWidth(90)
        return spin

    def set_theme(self, kind, colors=None):
        self._theme_kind = kind
        self._theme_colors = colors
        set_matplotlib_theme(kind)
        if self._fits:
            self._draw_selected()
        else:
            self.plot_widget.set_theme(kind, colors)

    def set_files(self, labels, current=None):
        """Fill the file combo. Does not emit ``file_changed``."""
        labels = [str(label) for label in labels]
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItems(labels)
        if current is not None:
            index = self.file_combo.findText(str(current))
            if index >= 0:
                self.file_combo.setCurrentIndex(index)
        self.file_combo.blockSignals(False)

    def _on_file_combo_activated(self, index):
        if self._updating or index < 0:
            return
        self.file_changed.emit(self.file_combo.itemText(index))

    def set_data(self, data, file_label=None, preserve_view=False):
        """Load a fretbursts Data object and refresh the burst-window summary."""
        label_changed = file_label != self._file_label
        self._file_label = file_label
        self._data = data
        self._configure_spots(data)
        self._apply_calibration_from_data(
            data,
            force=label_changed or not preserve_view,
        )
        self._invalidate_results()
        self._refresh_preview()

    def _configure_spots(self, data):
        nch = 1
        if data is not None:
            try:
                nch = max(1, int(getattr(data, "nch", 1) or 1))
            except (TypeError, ValueError):
                nch = 1
        show = nch > 1
        self.spot_label.setVisible(show)
        self.spot_combo.setVisible(show)
        current = self.spot_combo.currentIndex()
        self.spot_combo.blockSignals(True)
        self.spot_combo.clear()
        for ich in range(nch):
            self.spot_combo.addItem(f"Spot {ich + 1}", ich)
        if 0 <= current < nch:
            self.spot_combo.setCurrentIndex(current)
        self.spot_combo.blockSignals(False)

    def _spot_index(self):
        index = self.spot_combo.currentIndex()
        if index < 0:
            return 0
        value = self.spot_combo.itemData(index)
        return int(value) if value is not None else 0

    def _window_s(self):
        return float(self.window_spin.value()) * 1e-3

    def _calibration(self):
        return Calibration(
            gamma=float(self.gamma_spin.value()),
            leakage=float(self.leakage_spin.value()),
            direct_ratio=float(self.direct_spin.value()),
        )

    def _spin_matches(self, spin, value):
        if value is None:
            return True
        tolerance = max(float(spin.singleStep()) * 0.51, 1e-9)
        return abs(float(spin.value()) - float(value)) <= tolerance

    def _apply_calibration_from_data(self, data, force):
        ich = self._spot_index()
        gamma = _channel_factor(data, "gamma", ich, 1.0)
        leakage = _channel_factor(data, "leakage", ich, 0.0)
        user_edited = (
            not self._spin_matches(self.gamma_spin, self._loaded_gamma)
            or not self._spin_matches(self.leakage_spin, self._loaded_leakage)
        )
        if not force and user_edited:
            return
        self._updating = True
        self.gamma_spin.setValue(gamma)
        self.leakage_spin.setValue(leakage)
        self._updating = False
        self._loaded_gamma = float(self.gamma_spin.value())
        self._loaded_leakage = float(self.leakage_spin.value())

    def _on_spot_changed(self):
        if self._updating:
            return
        self._apply_calibration_from_data(self._data, force=True)
        self._invalidate_results()
        self._refresh_preview()

    def _on_window_changed(self):
        if self._updating:
            return
        self._invalidate_results()
        self._refresh_preview()

    def _on_calibration_changed(self):
        if self._updating:
            return
        self._invalidate_results()

    def _refresh_preview(self):
        self._counts = None
        if self._data is None:
            self.preview_label.setText("No measurement selected.")
            self.fit_btn.setEnabled(False)
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                counts = extract_group(
                    self._data,
                    ich=self._spot_index(),
                    window_s=self._window_s(),
                )
        except Exception as error:
            self.preview_label.setText(str(error))
            self.fit_btn.setEnabled(False)
            return
        self._counts = counts
        info = counts.info
        requested = info.get("requested_bursts", len(counts.nD))
        short = info.get("excluded_short", 0)
        gapped = info.get("excluded_gapped", 0)
        retained = info.get("retained_bursts", len(counts.nD))
        summary = (
            f"Bursts: {requested} requested, {short} shorter than the window, "
            f"{retained} retained."
        )
        if gapped:
            summary += (
                f" {gapped} skipped because Fuse Bursts left a dark gap "
                "inside them; a central window can land in that gap."
            )
        self.preview_label.setText(summary)
        self.fit_btn.setEnabled(True)

    def _invalidate_results(self):
        self._fits = None
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.setEnabled(False)
        self.model_combo.blockSignals(False)
        self.results.clear()
        self._clear_plot()
        if self._busy:
            self._restart = False
            self._cancel.set()
            self._generation += 1
            self.fit_btn.setText("Cancelling…")

    def _clear_plot(self):
        self.plot_widget.figure.clear()
        self.plot_widget.canvas.draw_idle()

    def _fit_start(self):
        return FitStart(
            efficiencies=tuple(
                (guess.value(), low.value(), high.value())
                for guess, low, high in self._efficiency_spins
            ),
            equilibrium=float(self._equilibrium_spin.value()),
            exchanges_per_window=float(self._exchange_spins[0].value()),
            exchange_low=float(self._exchange_spins[1].value()),
            exchange_high=float(self._exchange_spins[2].value()),
        )

    def _selected_models(self):
        return [key for key, box in self._model_boxes if box.isChecked()]

    def _on_fit_clicked(self):
        if self._counts is None or self._closing:
            return
        if self._busy:
            self._restart = True
            self._cancel.set()
            self.fit_btn.setText("Cancelling…")
            return
        self._launch()

    def _launch(self):
        self._restart = False
        models = self._selected_models()
        if not models:
            self.fit_btn.setText("Fit")
            self.results.setPlainText("Select at least one model.")
            return
        try:
            calibration = self._calibration()
        except ValueError as error:
            self.fit_btn.setText("Fit")
            self.results.setPlainText(str(error))
            return
        self._cancel = threading.Event()
        self._busy = True
        self._generation += 1
        self.fit_btn.setText("Fitting…")
        names = [box.text() for key, box in self._model_boxes if key in models]
        self.results.setPlainText("Fitting " + ", ".join(names) + "…")
        runnable = _PdaFitRunnable(
            self._counts,
            calibration,
            models,
            self._generation,
            self._cancel,
            self._signals,
            self._fit_start(),
        )
        self._runnable = runnable
        QtCore.QThreadPool.globalInstance().start(runnable)

    def _on_succeeded(self, generation, fits):
        self._finish_worker(generation, fits, None)

    def _on_failed(self, generation, message):
        self._finish_worker(generation, None, message)

    def _on_cancelled(self, generation):
        self._finish_worker(generation, None, None)

    def _finish_worker(self, generation, fits, error):
        if self._closing:
            self._busy = False
            return
        if generation != self._generation:
            self._busy = False
            if self._restart:
                self._launch()
            else:
                self.fit_btn.setText("Fit")
            return
        self._busy = False
        self.fit_btn.setText("Fit")
        if self._restart:
            self._launch()
            return
        if error:
            self.results.setPlainText(error)
            return
        if not fits:
            return
        fit_list, fit_errors = fits
        if not fit_list:
            self.results.setPlainText(
                "\n".join(fit_errors) or "No model converged."
            )
            return
        self._show_fits(fit_list, fit_errors)

    def _show_fits(self, fits, errors=None):
        self._fits = list(fits)
        best_bic = min(fit.bic for fit in self._fits)
        preferred = 0
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for index, fit in enumerate(self._fits):
            label = fit.label()
            if fit.bic == best_bic:
                label += " (lowest BIC)"
                preferred = index
            self.model_combo.addItem(label, index)
        self.model_combo.setCurrentIndex(preferred)
        self.model_combo.setEnabled(True)
        self.model_combo.blockSignals(False)
        text = self._format_results(self._fits)
        if errors:
            text += "\n\n" + "\n".join(errors)
        self.results.setPlainText(text)
        self._draw_selected()

    def _format_results(self, fits):
        return describe_model_choice(fits)

    def _draw_selected(self, *_args):
        if not self._fits or self._counts is None:
            return
        index = self.model_combo.currentIndex()
        if index < 0 or index >= len(self._fits):
            return
        try:
            draw_predictive_check(
                self.plot_widget.figure,
                self._counts,
                self._fits[index],
            )
        except Exception as error:
            self.results.appendPlainText(f"\nCould not draw the check: {error}")
            return
        self._layout_plots()
        self.plot_widget.set_theme(self._theme_kind, self._theme_colors)

    def _layout_plots(self):
        if len(self.plot_widget.figure.axes) < 2:
            return
        self.plot_widget.figure.subplots_adjust(
            left=0.07,
            right=0.98,
            bottom=0.18,
            top=0.88,
            wspace=0.35,
        )

    def _on_plot_resize(self, _event):
        if self._laying_out:
            return
        self._laying_out = True
        try:
            self._layout_plots()
        finally:
            self._laying_out = False

    def closeEvent(self, event):
        self._closing = True
        self._restart = False
        self._cancel.set()
        self._generation += 1
        super().closeEvent(event)
