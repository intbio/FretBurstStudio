"""Window for burst variance analysis of one measurement."""

from __future__ import annotations

from Qt import QtCore, QtWidgets
from Qt.QtCore import Signal

from fretGUI.bva import (
    DEFAULT_ALPHA,
    DEFAULT_BIN_WIDTH,
    DEFAULT_MIN_BURSTS,
    DEFAULT_PHOTONS_PER_WINDOW,
    BvaSettings,
    analyze_measurement,
    draw_bva,
    format_summary,
)
from fretGUI.custom_widgets.plot_widget import TemplatePlotWidget, set_matplotlib_theme

_NOTE = (
    "Blue marks where bursts fall. A darker shade means more bursts with "
    "that proximity ratio and that within-burst standard deviation. "
    "The dashed curve is the shot-noise limit of a static molecule. "
    "The gray band is the upper confidence limit on that curve. "
    "Each triangle is the standard deviation of all photon windows whose "
    "bursts lie in one narrow efficiency bin. A red triangle sits above "
    "the band and indicates within-burst dynamics. "
    "The horizontal axis is the donor-excitation proximity ratio, "
    "acceptor counts divided by all donor-excitation counts."
)

_CONFIDENCE_LEVELS = (
    ("95%", 0.05),
    ("99%", 0.01),
    ("99.9%", DEFAULT_ALPHA),
)


class _BvaSignals(QtCore.QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)


class _BvaRunnable(QtCore.QRunnable):
    """Calculate burst variance off the GUI thread."""

    def __init__(self, data, ich, settings, generation, signals):
        super().__init__()
        self.setAutoDelete(False)
        self.data = data
        self.ich = ich
        self.settings = settings
        self.generation = generation
        self.signals = signals

    def run(self):
        try:
            result = analyze_measurement(
                self.data,
                ich=self.ich,
                settings=self.settings,
            )
        except Exception as error:
            self.signals.failed.emit(self.generation, str(error))
        else:
            self.signals.finished.emit(self.generation, result)


class BvaExplorerWindow(QtWidgets.QDialog):
    """Separate window for burst variance analysis."""

    file_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Burst Variance Analysis")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinMaxButtonsHint
        )
        self.resize(980, 760)

        self._data = None
        self._file_label = None
        self._result = None
        self._updating = False
        self._closing = False
        self._generation = 0
        self._runnable = None
        self._theme_kind = "light"
        self._theme_colors = None
        self._laying_out = False
        self._signals = _BvaSignals(self)
        self._signals.finished.connect(self._on_finished)
        self._signals.failed.connect(self._on_failed)
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._start)

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
        self.photons_spin = QtWidgets.QSpinBox()
        self.photons_spin.setRange(2, 100)
        self.photons_spin.setValue(DEFAULT_PHOTONS_PER_WINDOW)
        self.photons_spin.setToolTip(
            "Photons in each non-overlapping window. "
            "The published analysis uses 5."
        )
        self.bin_width_spin = self._double_spin(
            0.01, 0.2, DEFAULT_BIN_WIDTH, 2, 0.01
        )
        self.bin_width_spin.setToolTip(
            "Width of the efficiency bins used for the average and the "
            "confidence limit. 0.05 gives 20 bins; the bin at 0.5 covers "
            "0.475 to 0.525."
        )
        self.min_bursts_spin = QtWidgets.QSpinBox()
        self.min_bursts_spin.setRange(1, 1_000_000)
        self.min_bursts_spin.setValue(DEFAULT_MIN_BURSTS)
        self.min_bursts_spin.setToolTip(
            "Bins with fewer bursts than this are not averaged and are "
            "not tested."
        )
        self.confidence_combo = QtWidgets.QComboBox()
        for label, alpha in _CONFIDENCE_LEVELS:
            self.confidence_combo.addItem(label, alpha)
        self.confidence_combo.setCurrentIndex(len(_CONFIDENCE_LEVELS) - 1)
        self.confidence_combo.setToolTip(
            "Experiment-wide confidence level. It is Bonferroni-corrected "
            "across the bins that have enough bursts."
        )

        form.addWidget(QtWidgets.QLabel("Photons per window"), 0, 0)
        form.addWidget(self.photons_spin, 0, 1)
        form.addWidget(QtWidgets.QLabel("Bin width"), 0, 2)
        form.addWidget(self.bin_width_spin, 0, 3)
        form.addWidget(QtWidgets.QLabel("Minimum bursts"), 0, 4)
        form.addWidget(self.min_bursts_spin, 0, 5)
        form.addWidget(QtWidgets.QLabel("Confidence"), 0, 6)
        form.addWidget(self.confidence_combo, 0, 7)
        root.addLayout(form)

        self.status_label = QtWidgets.QLabel("No measurement selected.")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.plot_widget = TemplatePlotWidget(mpl_width=8, mpl_height=6)
        self.plot_widget.canvas.mpl_connect("resize_event", self._on_plot_resize)
        root.addWidget(self.plot_widget, 1)

        note = QtWidgets.QLabel(_NOTE)
        note.setWordWrap(True)
        root.addWidget(note)

        self.file_combo.activated.connect(self._on_file_combo_activated)
        self.spot_combo.activated.connect(self._on_spot_changed)
        self.photons_spin.valueChanged.connect(self._on_setting_changed)
        self.bin_width_spin.valueChanged.connect(self._on_setting_changed)
        self.min_bursts_spin.valueChanged.connect(self._on_setting_changed)
        self.confidence_combo.activated.connect(self._on_setting_changed)
        self.spot_label.setVisible(False)
        self.spot_combo.setVisible(False)

    @staticmethod
    def _double_spin(minimum, maximum, value, decimals, step):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setMinimumWidth(90)
        return spin

    def set_theme(self, kind, colors=None):
        self._theme_kind = kind
        self._theme_colors = colors
        set_matplotlib_theme(kind)
        if self._result is not None:
            self._draw(self._result)
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
        """Load a fretbursts measurement and recompute the variance plot."""
        del preserve_view
        self._debounce.stop()
        self._file_label = file_label
        if file_label:
            self.setWindowTitle(f"Burst Variance Analysis — {file_label}")
        else:
            self.setWindowTitle("Burst Variance Analysis")
        self._data = data
        self._configure_spots(data)
        self._start()

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

    def _settings(self):
        alpha = self.confidence_combo.currentData()
        if alpha is None:
            alpha = DEFAULT_ALPHA
        return BvaSettings(
            photons_per_window=int(self.photons_spin.value()),
            bin_width=float(self.bin_width_spin.value()),
            min_bursts=int(self.min_bursts_spin.value()),
            alpha=float(alpha),
        )

    def _on_spot_changed(self):
        if self._updating:
            return
        self._start()

    def _on_setting_changed(self, *_args):
        if self._updating:
            return
        self._debounce.start()

    def _start(self):
        if self._closing:
            return
        self._generation += 1
        generation = self._generation
        if self._data is None:
            self._result = None
            self._clear_plot()
            self.status_label.setText("No measurement selected.")
            return
        self.status_label.setText("Computing burst variance…")
        runnable = _BvaRunnable(
            self._data,
            self._spot_index(),
            self._settings(),
            generation,
            self._signals,
        )
        self._runnable = runnable
        QtCore.QThreadPool.globalInstance().start(runnable)

    def _on_finished(self, generation, result):
        if self._closing or generation != self._generation:
            return
        self._result = result
        self.status_label.setText(format_summary(result))
        self._draw(result)

    def _on_failed(self, generation, message):
        if self._closing or generation != self._generation:
            return
        self._result = None
        self._clear_plot()
        self.status_label.setText(message)

    def _clear_plot(self):
        self.plot_widget.figure.clear()
        self.plot_widget.canvas.draw_idle()

    def _draw(self, result):
        set_matplotlib_theme(self._theme_kind)
        draw_bva(self.plot_widget.figure, result)
        self._layout_plot()
        self.plot_widget.set_theme(self._theme_kind, self._theme_colors)

    def _layout_plot(self):
        if not self.plot_widget.figure.axes:
            return
        self.plot_widget.figure.subplots_adjust(
            left=0.10,
            right=0.98,
            bottom=0.12,
            top=0.96,
        )

    def _on_plot_resize(self, _event):
        if self._laying_out or self._result is None:
            return
        self._laying_out = True
        try:
            self._layout_plot()
        finally:
            self._laying_out = False

    def closeEvent(self, event):
        self._closing = True
        self._debounce.stop()
        self._generation += 1
        super().closeEvent(event)
