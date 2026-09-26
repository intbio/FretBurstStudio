"""Fast windowed photon timetrace explorer with burst table."""

from __future__ import annotations

import numpy as np
import fretbursts
from matplotlib.widgets import SpanSelector
from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import Signal
from NodeGraphQt import NodeBaseWidget
from fretGUI.custom_widgets.plot_widget import TemplatePlotWidget

MAX_BINS = 20_000
BURST_COLOR = "#BBBBBB"
SELECTED_BURST_COLOR = "#2F6FED"
RULER_COLOR = "#F4A261"
DONOR_COLOR = "#2CA02C"
ACCEPTOR_COLOR = "#D62728"
AA_COLOR = "#9467BD"
TABLE_COLUMNS = (
    "#",
    "t_start",
    "t_stop",
    "width_ms",
    "size_raw",
    "brightness_kcps",
    "S/B",
    "E",
    "S",
)
TABLE_SELECTED_BG = QtGui.QColor(47, 111, 237, 90)
TABLE_SELECTED_FG = QtGui.QColor(20, 20, 20)
BURST_INDEX_ROLE = QtCore.Qt.UserRole + 1
# Non-zero arrow slots parked in the margin so Linux can still drag the handle.
SCROLL_GUTTER = 16
SCROLL_REDRAW_MS = 40
_ICON_BUTTON_SIZE = 32

_BG_PAIRS = (
    ("nd", "bg_dd"),
    ("na", "bg_ad"),
    ("naa", "bg_aa"),
)


def _nice_tick_step(span, target_ticks=8):
    """Return a round step size for ~target_ticks across ``span``."""
    if span <= 0:
        return 1.0
    raw = span / max(target_ticks, 1)
    if raw <= 0:
        return 1.0
    magnitude = 10 ** np.floor(np.log10(raw))
    residual = raw / magnitude
    if residual <= 1.0:
        nice = 1.0
    elif residual <= 2.0:
        nice = 2.0
    elif residual <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * magnitude


def _blank_icon_pixmap(size):
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    return pixmap


def _ruler_icon(color="#202020", size=20):
    """Ruler glyph drawn in code so the app needs no image file."""
    pixmap = _blank_icon_pixmap(size)
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
    baseline = size - 4
    painter.drawLine(1, baseline, size - 2, baseline)
    tick_heights = (11, 6, 6, 11, 6, 6, 11)
    span = size - 4
    last = len(tick_heights) - 1
    for index, height in enumerate(tick_heights):
        x = 2 + int(round(index * span / last))
        painter.drawLine(x, baseline, x, baseline - height)
    painter.end()
    return QtGui.QIcon(pixmap)


def _arrow_icon(direction, color, size=20):
    """Filled triangle. Qt's standard arrows become solid circles when recolored."""
    pixmap = _blank_icon_pixmap(size)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))
    margin = 3
    mid = size / 2.0
    if direction == "left":
        points = (
            (size - margin, margin),
            (margin, mid),
            (size - margin, size - margin),
        )
    else:
        points = (
            (margin, margin),
            (size - margin, mid),
            (margin, size - margin),
        )
    painter.drawPolygon(QtGui.QPolygonF([
        QtCore.QPointF(x, y) for x, y in points
    ]))
    painter.end()
    return QtGui.QIcon(pixmap)


def _save_icon(color, size=20):
    """Down arrow into a tray. The standard save pixmap collapses to a square."""
    pixmap = _blank_icon_pixmap(size)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    ink = QtGui.QColor(color)
    pen = QtGui.QPen(ink)
    pen.setWidth(2)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    painter.setPen(pen)
    mid = size / 2.0
    painter.drawLine(QtCore.QPointF(mid, 2), QtCore.QPointF(mid, size - 9))
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(ink)
    painter.drawPolygon(QtGui.QPolygonF([
        QtCore.QPointF(mid - 5, size - 12),
        QtCore.QPointF(mid + 5, size - 12),
        QtCore.QPointF(mid, size - 6),
    ]))
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawPolyline(QtGui.QPolygonF([
        QtCore.QPointF(3, size - 6),
        QtCore.QPointF(3, size - 3),
        QtCore.QPointF(size - 3, size - 3),
        QtCore.QPointF(size - 3, size - 6),
    ]))
    painter.end()
    return QtGui.QIcon(pixmap)


def _icon_button(icon, tooltip):
    button = QtWidgets.QToolButton()
    button.setIcon(icon)
    button.setIconSize(QtCore.QSize(20, 20))
    button.setToolTip(tooltip)
    button.setAutoRaise(False)
    button.setFixedSize(_ICON_BUTTON_SIZE, _ICON_BUTTON_SIZE)
    return button


def _tinted_icon(icon, color, size=18):
    """Recolor a standard icon so it stays visible on light and dark buttons."""
    pixmap = icon.pixmap(QtCore.QSize(size, size))
    if pixmap.isNull():
        return icon
    tinted = QtGui.QPixmap(pixmap.size())
    tinted.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QtGui.QColor(color))
    painter.end()
    return QtGui.QIcon(tinted)


def brightness_kcps(size_raw, width_ms):
    """Burst size over duration, in kcps. None when duration is missing or zero."""
    if size_raw is None or width_ms is None:
        return None
    width_s = float(width_ms) * 1e-3
    if width_s <= 0:
        return None
    return float(size_raw) / width_s / 1000.0


def signal_to_background(df, row):
    """Background-corrected counts divided by background counts.

    Uses nd/na/naa and bg_dd/bg_ad/bg_aa when those columns exist.
    None when background is missing or zero.
    """
    signal = 0.0
    background = 0.0
    used = False
    for signal_col, bg_col in _BG_PAIRS:
        if signal_col not in df.columns or bg_col not in df.columns:
            continue
        signal += float(df[signal_col].iloc[row])
        background += float(df[bg_col].iloc[row])
        used = True
    if not used or background <= 0:
        return None
    return (signal - background) / background


class NumericTableItem(QtWidgets.QTableWidgetItem):
    """Sort by the numeric value stored in UserRole, not the display text."""

    def __lt__(self, other):
        left = self.data(QtCore.Qt.UserRole)
        right = other.data(QtCore.Qt.UserRole) if other is not None else None
        if left is None and right is None:
            return super().__lt__(other)
        if left is None:
            return True
        if right is None:
            return False
        try:
            return float(left) < float(right)
        except (TypeError, ValueError):
            return super().__lt__(other)


class TimeScrollAxis(QtWidgets.QWidget):
    """Tick marks + time labels under the timetrace scrollbar (0 … time_max)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._time_max = 1.0
        self._inset = SCROLL_GUTTER
        self.setMinimumHeight(28)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )

    def set_time_max(self, time_max):
        self._time_max = max(float(time_max), 1e-6)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        # Match the scrollbar groove: 1px border plus the parked arrow gutters.
        inset = self._inset
        rect = self.rect().adjusted(1 + inset, 0, -1 - inset, 0)
        w = max(rect.width(), 1)
        t_max = self._time_max

        painter.setPen(QtGui.QPen(QtGui.QColor("#888888")))
        painter.drawLine(rect.left(), 2, rect.right(), 2)

        step = _nice_tick_step(t_max, target_ticks=8)
        ticks = np.arange(0.0, t_max + step * 0.5, step)
        if len(ticks) == 0 or ticks[-1] < t_max * 0.98:
            ticks = np.append(ticks, t_max)

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        for t in ticks:
            x = rect.left() + int(round((t / t_max) * (w - 1)))
            painter.setPen(QtGui.QPen(QtGui.QColor("#666666")))
            painter.drawLine(x, 2, x, 10)
            label = f"{t:.0f} s" if t_max >= 20 else f"{t:.1f} s"
            if abs(t - t_max) < step * 0.25:
                label = f"{t_max:.1f} s" if t_max < 20 else f"{t_max:.0f} s"
            tw = metrics.horizontalAdvance(label)
            tx = x - tw // 2
            tx = max(0, min(tx, self.width() - tw))
            painter.setPen(QtGui.QPen(QtGui.QColor("#333333")))
            painter.drawText(tx, 24, label)


class OpenExplorerButtonWidget(QtWidgets.QWidget):
    clicked = Signal()

    def __init__(self, parent=None, text="Open Timetrace Explorer"):
        # Must not parent to NodeGraphQt graphics items (not QWidgets).
        super().__init__(None)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.button = QtWidgets.QPushButton(text, self)
        layout.addWidget(self.button)
        self.button.clicked.connect(self.clicked.emit)


class OpenExplorerButtonWrapper(NodeBaseWidget):
    """NodeGraphQt wrapper for the Open Timetrace Explorer button."""

    def __init__(self, parent=None, text="Open Timetrace Explorer"):
        super().__init__(parent)
        self.set_label("")
        self._btn_widget = OpenExplorerButtonWidget(text=text)
        self.set_custom_widget(self._btn_widget)

    @property
    def clicked(self):
        return self._btn_widget.clicked

    def get_value(self):
        return None

    def set_value(self, value):
        return None


def compute_binned_trace(ph_times, tmin, tmax, binwidth, clk_p, max_bins=MAX_BINS):
    """
    Histogram photon timestamps in [tmin, tmax] (seconds).

    Bin edges are locked to a global grid starting at t=0 with spacing
    ``binwidth``, so panning (Next/Prev) does not shift the histogram phase.

    Returns (x_seconds, counts, effective_binwidth_seconds).
    """
    if ph_times is None or len(ph_times) == 0 or tmax <= tmin or binwidth <= 0:
        return np.array([]), np.array([]), binwidth

    n_bins_needed = int(np.ceil((tmax - tmin) / binwidth))
    if n_bins_needed > max_bins:
        binwidth = (tmax - tmin) / max_bins

    # Snap view to bin boundaries measured from absolute t=0
    t0 = np.floor(tmin / binwidth) * binwidth
    t1 = np.ceil(tmax / binwidth) * binwidth
    if t1 <= t0:
        t1 = t0 + binwidth

    n_bins = max(1, int(np.round((t1 - t0) / binwidth)))
    bins_s = t0 + np.arange(n_bins + 1, dtype=float) * binwidth
    bins_clk = bins_s / clk_p

    i0, i1 = np.searchsorted(ph_times, [bins_clk[0], bins_clk[-1]])
    counts, _ = np.histogram(ph_times[i0:i1], bins=bins_clk)
    x = bins_s[:-1] + 0.5 * binwidth
    return x, counts, binwidth


def _streams_for_data(d):
    streams = [
        (fretbursts.Ph_sel(Dex="Dem"), False, "DexDem", DONOR_COLOR),
        (fretbursts.Ph_sel(Dex="Aem"), True, "DexAem", ACCEPTOR_COLOR),
    ]
    if getattr(d, "alternated", False):
        streams.append((fretbursts.Ph_sel(Aex="Aem"), True, "AexAem", AA_COLOR))
    return streams


def _photons_in_window(ph_times, t0, t1, clk_p):
    if ph_times is None or len(ph_times) == 0 or t1 <= t0 or clk_p <= 0:
        return 0
    i0, i1 = np.searchsorted(ph_times, [t0 / clk_p, t1 / clk_p])
    return int(max(0, i1 - i0))


class TimetraceExplorerWindow(QtWidgets.QDialog):
    """Separate window: burst table + windowed timetrace plot."""

    file_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Timetrace Explorer")
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinMaxButtonsHint
        )
        self.resize(1100, 700)

        self._data = None
        self._ich = 0
        self._df_bursts = None
        self._updating_controls = False
        self._ruler_mode = False
        self._ruler_span = None
        self._span_selector = None
        self._last_auto_ymax = 1.0

        self._scroll_redraw_timer = QtCore.QTimer(self)
        self._scroll_redraw_timer.setSingleShot(True)
        self._scroll_redraw_timer.timeout.connect(self.redraw)

        self._build_ui()
        self._wire_signals()

    def set_theme(self, kind, colors=None):
        self.plot_widget.set_theme(kind, colors)
        if colors and "text" in colors:
            color = QtGui.QColor(*colors["text"])
        else:
            color = self.palette().color(QtGui.QPalette.ButtonText)
        self._apply_icon_colors(color)

    def _apply_icon_colors(self, color):
        self.prev_btn.setIcon(_arrow_icon("left", color))
        self.next_btn.setIcon(_arrow_icon("right", color))
        self.ruler_check.setIcon(_ruler_icon(color))
        self.save_btn.setIcon(_save_icon(color))
        self.refresh_btn.setIcon(_tinted_icon(self._refresh_source, color))

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.file_combo = QtWidgets.QComboBox()
        self.file_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.file_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.file_combo.setFixedWidth(280)

        style = QtWidgets.QApplication.style()
        ink = self.palette().color(QtGui.QPalette.ButtonText)
        self.prev_btn = _icon_button(
            _arrow_icon("left", ink),
            "Previous burst",
        )
        self.next_btn = _icon_button(
            _arrow_icon("right", ink),
            "Next burst",
        )
        self.fit_btn = QtWidgets.QPushButton("Fit to selected")

        self.span_spin = QtWidgets.QDoubleSpinBox()
        self.span_spin.setRange(0.01, 1e6)
        self.span_spin.setDecimals(3)
        self.span_spin.setSingleStep(0.5)
        self.span_spin.setValue(2.0)

        self.t_center_spin = QtWidgets.QDoubleSpinBox()
        self.t_center_spin.setRange(0.0, 1e9)
        self.t_center_spin.setDecimals(4)
        self.t_center_spin.setSingleStep(0.1)
        self.t_center_spin.setValue(0.0)

        self.binwidth_spin = QtWidgets.QDoubleSpinBox()
        self.binwidth_spin.setRange(0.01, 1000.0)
        self.binwidth_spin.setDecimals(3)
        self.binwidth_spin.setSingleStep(0.1)
        self.binwidth_spin.setValue(1.0)

        self.cps_check = QtWidgets.QCheckBox("Show kcps")
        self.cps_check.setToolTip("Plot kcps (10³ counts/s) instead of counts per bin")

        self.y_lock_check = QtWidgets.QCheckBox("Lock Y")
        self.y_lock_check.setToolTip(
            "Fix the vertical range on both channels (positive and negative)"
        )

        self.y_max_spin = QtWidgets.QDoubleSpinBox()
        self.y_max_spin.setRange(0.01, 1e9)
        self.y_max_spin.setDecimals(2)
        self.y_max_spin.setSingleStep(1.0)
        self.y_max_spin.setValue(10.0)
        self.y_max_spin.setEnabled(False)
        self.y_max_spin.setToolTip(
            "Maximum |Y| for both channels, in the current plot units "
            "(counts/bin or kcps)"
        )

        self.ruler_check = _icon_button(
            _ruler_icon(ink),
            "Drag a time window on the plot to count photons and intensity",
        )
        self.ruler_check.setCheckable(True)
        self.ruler_check.setStyleSheet(
            """
            QToolButton:checked {
                background-color: palette(highlight);
                border: 1px solid palette(highlight);
            }
            QToolButton:!checked {
                background-color: palette(button);
                border: 1px solid palette(mid);
            }
            """
        )

        self._refresh_source = style.standardIcon(
            QtWidgets.QStyle.SP_BrowserReload
        )
        self.refresh_btn = _icon_button(
            self._refresh_source,
            "Refresh",
        )
        self.save_btn = _icon_button(
            _save_icon(ink),
            "Save image",
        )
        self._apply_icon_colors(ink)

        # Row 1: pick a file and step through bursts. Row 2: plot appearance.
        browse_row = QtWidgets.QHBoxLayout()
        browse_row.setSpacing(8)
        browse_row.addWidget(QtWidgets.QLabel("File:"))
        browse_row.addWidget(self.file_combo)
        browse_row.addWidget(self.prev_btn)
        browse_row.addWidget(self.next_btn)
        browse_row.addWidget(self.fit_btn)
        browse_row.addWidget(QtWidgets.QLabel("Span (s):"))
        browse_row.addWidget(self.span_spin)
        browse_row.addWidget(QtWidgets.QLabel("t center (s):"))
        browse_row.addWidget(self.t_center_spin)
        browse_row.addStretch(1)

        display_row = QtWidgets.QHBoxLayout()
        display_row.setSpacing(8)
        display_row.addWidget(QtWidgets.QLabel("Binwidth (ms):"))
        display_row.addWidget(self.binwidth_spin)
        display_row.addWidget(self.cps_check)
        display_row.addWidget(self.y_lock_check)
        display_row.addWidget(self.y_max_spin)
        display_row.addWidget(self.ruler_check)
        display_row.addWidget(self.refresh_btn)
        display_row.addWidget(self.save_btn)
        display_row.addStretch(1)

        layout.addLayout(browse_row)
        layout.addLayout(display_row)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        self.table = QtWidgets.QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(TABLE_COLUMNS))
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Expanding,
        )
        # Qt's header defaults to column 0, descending. Set ascending before
        # sorting is enabled so the first sort (and the first header click
        # toggle) starts from low to high.
        self.table.horizontalHeader().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.table.setSortingEnabled(True)
        splitter.addWidget(self.table)

        plot_panel = QtWidgets.QWidget()
        plot_panel.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        plot_layout = QtWidgets.QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)

        self.plot_widget = TemplatePlotWidget(
            parent=self,
            mpl_width=7.0,
            mpl_height=4.0,
            retain_limits=False,
        )
        self.plot_widget.toolbar.setVisible(False)
        self.plot_widget.keep_view_check.setVisible(False)

        self.time_scroll = QtWidgets.QScrollBar(QtCore.Qt.Horizontal)
        self.time_scroll.setToolTip("Browse timetrace (independent of burst selection)")
        self.time_scroll.setMinimumHeight(24)
        gutter = SCROLL_GUTTER
        self.time_scroll.setStyleSheet(
            f"""
            QScrollBar:horizontal {{
                height: 24px;
                background: palette(base);
                margin: 0px {gutter}px 0px {gutter}px;
                border: 1px solid palette(mid);
            }}
            QScrollBar::handle:horizontal {{
                background: palette(highlight);
                min-width: 40px;
                border-radius: 3px;
                border: 1px solid palette(mid);
            }}
            QScrollBar::handle:horizontal:hover {{
                background: palette(light);
            }}
            QScrollBar::add-line:horizontal {{
                width: {gutter}px;
                height: 24px;
                subcontrol-position: right;
                subcontrol-origin: margin;
                border: none;
                background: none;
            }}
            QScrollBar::sub-line:horizontal {{
                width: {gutter}px;
                height: 24px;
                subcontrol-position: left;
                subcontrol-origin: margin;
                border: none;
                background: none;
            }}
            QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {{
                width: 0px;
                height: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: palette(alternate-base);
            }}
            """
        )

        scroll_legend = TimeScrollAxis(self)
        self.scroll_axis = scroll_legend

        plot_layout.addWidget(self.plot_widget, stretch=1)
        plot_layout.addWidget(self.time_scroll)
        plot_layout.addWidget(self.scroll_axis)
        splitter.addWidget(plot_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 640])

        layout.addWidget(splitter, stretch=1)

    def _wire_signals(self):
        self.binwidth_spin.valueChanged.connect(self._on_controls_changed)
        self.span_spin.valueChanged.connect(self._on_controls_changed)
        self.t_center_spin.valueChanged.connect(self._on_controls_changed)
        self.cps_check.toggled.connect(self._on_controls_changed)
        self.y_lock_check.toggled.connect(self._on_y_lock_toggled)
        self.y_max_spin.valueChanged.connect(self._on_controls_changed)
        self.refresh_btn.clicked.connect(self.redraw)
        self.save_btn.clicked.connect(self.plot_widget._custom_save_figure)
        self.prev_btn.clicked.connect(self._goto_prev_burst)
        self.next_btn.clicked.connect(self._goto_next_burst)
        self.fit_btn.clicked.connect(self._fit_to_selected)
        self.ruler_check.toggled.connect(self._on_ruler_toggled)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        self.time_scroll.valueChanged.connect(self._on_scrollbar_changed)
        self.time_scroll.sliderReleased.connect(self._on_slider_released)
        self.file_combo.activated.connect(self._on_file_combo_activated)
        self.plot_widget.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.plot_widget.canvas.mpl_connect("scroll_event", self._on_plot_scroll)

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
        if self._updating_controls or index < 0:
            return
        self.file_changed.emit(self.file_combo.itemText(index))

    def set_data(self, data, ich=0, preserve_view=False):
        """Load a fretbursts.Data object and refresh table + plot."""
        prev_center = float(self.t_center_spin.value())
        prev_span = float(self.span_spin.value())
        prev_binwidth = float(self.binwidth_spin.value())
        prev_burst = self._selected_burst_index()

        self._data = data
        self._ich = ich
        self._df_bursts = None

        if data is None:
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            self.table.setSortingEnabled(True)
            self.status_label.setText("No data.")
            self._clear_plot()
            self._sync_scrollbar_range()
            return

        has_bursts = "mburst" in data
        if has_bursts:
            try:
                self._df_bursts = fretbursts.bext.burst_data(data, include_bg=True)
                if "spot" in self._df_bursts.columns:
                    self._df_bursts = self._df_bursts[
                        self._df_bursts["spot"] == ich
                    ].reset_index(drop=True)
            except Exception as exc:
                self._df_bursts = None
                self.status_label.setText(f"Could not build burst table: {exc}")
                has_bursts = False

        self._populate_table()

        if preserve_view:
            self._updating_controls = True
            self.binwidth_spin.setValue(prev_binwidth)
            self.span_spin.setValue(prev_span)
            self.t_center_spin.setValue(prev_center)
            self._updating_controls = False
            visual = self._visual_row_for_burst(prev_burst)
            if visual is not None:
                self.table.blockSignals(True)
                self.table.selectRow(visual)
                self.table.blockSignals(False)
                self._apply_table_row_highlight(visual)
            self._update_selected_burst_status()
        elif self._df_bursts is not None and len(self._df_bursts) > 0:
            t0 = float(self._df_bursts["t_start"].iloc[0])
            t1 = float(self._df_bursts["t_stop"].iloc[0])
            self._set_t_center((t0 + t1) / 2.0, redraw=False)
            self._set_burst_count_status()
            first = self._visual_row_for_burst(0)
            if first is not None:
                self.table.selectRow(first)
        else:
            self._set_t_center(0.0, redraw=False)
            if not has_bursts:
                self.status_label.setText(
                    "No bursts in data — showing photons only. Run burst search first."
                )
            else:
                self.status_label.setText("Burst table empty — showing photons only.")

        self.table.setEnabled(self._df_bursts is not None and len(self._df_bursts) > 0)
        self._sync_scrollbar_range()
        self.redraw()
        if self._ruler_span is not None:
            self._update_ruler_status()

    def _set_burst_count_status(self):
        if self._df_bursts is not None:
            self.status_label.setText(f"{len(self._df_bursts)} bursts")
        else:
            self.status_label.setText("No bursts")

    def _format_window_status(self, t0, t1, prefix=None):
        """Same photon and intensity line used by the ruler and a selected burst."""
        t0 = float(t0)
        t1 = float(t1)
        duration = max(t1 - t0, 0.0)
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(
            f"region {t0:.4f}–{t1:.4f} s ({duration * 1000.0:.2f} ms)"
        )
        if self._data is None:
            return " | ".join(parts)
        d = self._data
        clk_p = float(d.clk_p)
        ich = self._ich
        for ph_sel, _invert, label, _color in _streams_for_data(d):
            try:
                ph = d.get_ph_times(ich, ph_sel=ph_sel)
            except Exception:
                continue
            n_ph = _photons_in_window(ph, t0, t1, clk_p)
            kcps = (n_ph / duration / 1000.0) if duration > 0 else 0.0
            parts.append(f"{label}: {n_ph} ph, {kcps:.2f} kcps")
        return " | ".join(parts)

    def _update_selected_burst_status(self):
        if self._ruler_span is not None:
            self._update_ruler_status()
            return
        burst_index = self._selected_burst_index()
        if (
            burst_index is None
            or self._df_bursts is None
            or self._data is None
            or burst_index < 0
            or burst_index >= len(self._df_bursts)
        ):
            self._set_burst_count_status()
            return
        t0 = float(self._df_bursts["t_start"].iloc[burst_index])
        t1 = float(self._df_bursts["t_stop"].iloc[burst_index])
        self.status_label.setText(
            self._format_window_status(
                t0,
                t1,
                prefix=f"burst {burst_index}",
            )
        )

    def _column_values(self, df, row):
        width_ms = float(df["width_ms"].iloc[row]) if "width_ms" in df.columns else None
        size_raw = float(df["size_raw"].iloc[row]) if "size_raw" in df.columns else None
        bright = brightness_kcps(size_raw, width_ms)
        sb = signal_to_background(df, row)
        e_val = float(df["E"].iloc[row]) if "E" in df.columns else None
        s_val = float(df["S"].iloc[row]) if "S" in df.columns else None
        t_start = float(df["t_start"].iloc[row])
        t_stop = float(df["t_stop"].iloc[row])
        return [
            (str(row), float(row)),
            (f"{t_start:.4f}", t_start),
            (f"{t_stop:.4f}", t_stop),
            (f"{width_ms:.3f}" if width_ms is not None else "", width_ms),
            (f"{size_raw:.0f}" if size_raw is not None else "", size_raw),
            (f"{bright:.2f}" if bright is not None else "", bright),
            (f"{sb:.2f}" if sb is not None else "", sb),
            (f"{e_val:.3f}" if e_val is not None else "", e_val),
            (f"{s_val:.3f}" if s_val is not None else "", s_val),
        ]

    def _populate_table(self):
        header = self.table.horizontalHeader()
        if header.isSortIndicatorShown() and header.sortIndicatorSection() >= 0:
            sort_section = header.sortIndicatorSection()
            sort_order = header.sortIndicatorOrder()
        else:
            sort_section = 0
            sort_order = QtCore.Qt.AscendingOrder

        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._df_bursts is None or len(self._df_bursts) == 0:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(True)
            return

        df = self._df_bursts
        self.table.setRowCount(len(df))
        for row in range(len(df)):
            for col, (text, sort_value) in enumerate(self._column_values(df, row)):
                item = NumericTableItem(text)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setData(QtCore.Qt.UserRole, sort_value)
                item.setData(BURST_INDEX_ROLE, int(row))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(sort_section, sort_order)
        self.table.blockSignals(False)

    def _time_max(self):
        if self._data is None:
            return 1.0
        return max(float(getattr(self._data, "time_max", 1.0) or 1.0), 1e-3)

    def _scroll_scale(self):
        """Scrollbar integer units per second (ms)."""
        return 1000.0

    def _sync_scrollbar_range(self):
        """Update scrollbar so handle width matches view span on the time axis.

        Qt maps handle size as pageStep / (maximum - minimum + pageStep).
        Setting maximum = time_max - span makes the groove represent time_max
        and the handle represent span, matching the tick axis below.
        Scroll value is the left edge of the view (tmin), not t_center.
        """
        scale = self._scroll_scale()
        time_max = self._time_max()
        span = min(float(self.span_spin.value()), time_max)
        span = max(span, 1e-3)
        center = float(self.t_center_spin.value())

        page = max(1, int(round(span * scale)))
        max_val = max(0, int(round(time_max * scale)) - page)
        single = max(1, page // 20)

        tmin = center - span / 2.0
        tmin = max(0.0, min(tmin, time_max - span))
        value = max(0, min(max_val, int(round(tmin * scale))))

        self._updating_controls = True
        self.time_scroll.setMinimum(0)
        self.time_scroll.setMaximum(max_val)
        self.time_scroll.setPageStep(page)
        self.time_scroll.setSingleStep(single)
        self.time_scroll.setValue(value)
        self.t_center_spin.setMaximum(max(time_max, 1.0))
        self._updating_controls = False
        self._update_scroll_legend()

    def _update_scroll_legend(self):
        self.scroll_axis.set_time_max(self._time_max())

    def _on_scrollbar_changed(self, value):
        if self._updating_controls:
            return
        span = float(self.span_spin.value())
        tmin = float(value) / self._scroll_scale()
        self._set_t_center(tmin + span / 2.0, redraw=True, from_scroll=True)

    def _on_slider_released(self):
        self._scroll_redraw_timer.stop()
        self.redraw()

    def _request_redraw(self):
        if self.time_scroll.isSliderDown():
            self._scroll_redraw_timer.start(SCROLL_REDRAW_MS)
            return
        self._scroll_redraw_timer.stop()
        self.redraw()

    def _view_limits(self):
        span = float(self.span_spin.value())
        center = float(self.t_center_spin.value())
        tmin = max(0.0, center - span / 2.0)
        tmax = center + span / 2.0
        if self._data is not None:
            time_max = self._time_max()
            tmax = min(tmax, time_max)
            if tmax <= tmin:
                tmax = min(tmin + span, time_max) if time_max > tmin else tmin + span
        return tmin, tmax

    def _set_t_center(self, value, redraw=True, from_scroll=False):
        self._updating_controls = True
        self.t_center_spin.setValue(float(value))
        if not from_scroll:
            scale = self._scroll_scale()
            time_max = self._time_max()
            span = min(float(self.span_spin.value()), time_max)
            span = max(span, 1e-3)
            tmin = float(value) - span / 2.0
            tmin = max(0.0, min(tmin, time_max - span))
            max_val = self.time_scroll.maximum()
            self.time_scroll.setValue(max(0, min(max_val, int(round(tmin * scale)))))
        self._updating_controls = False
        self._update_scroll_legend()
        if redraw:
            self._request_redraw()

    def _on_controls_changed(self, *_args):
        if self._updating_controls:
            return
        # Span / center edits from spinboxes: keep scrollbar in sync.
        sender = self.sender()
        if sender in (self.span_spin, self.t_center_spin, self.binwidth_spin):
            self._sync_scrollbar_range()
        self.redraw()

    def _on_y_lock_toggled(self, checked):
        self.y_max_spin.setEnabled(checked)
        if checked:
            self._updating_controls = True
            self.y_max_spin.setValue(max(float(self._last_auto_ymax), 0.01))
            self._updating_controls = False
        if not self._updating_controls:
            self.redraw()

    def _selected_visual_row(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return rows[0].row()

    def _burst_index_for_row(self, visual_row):
        if visual_row is None:
            return None
        item = self.table.item(visual_row, 0)
        if item is None:
            return None
        value = item.data(BURST_INDEX_ROLE)
        if value is None:
            return None
        return int(value)

    def _selected_burst_index(self):
        return self._burst_index_for_row(self._selected_visual_row())

    def _visual_row_for_burst(self, burst_index):
        if burst_index is None:
            return None
        for row in range(self.table.rowCount()):
            if self._burst_index_for_row(row) == int(burst_index):
                return row
        return None

    def _on_table_selection(self):
        visual = self._selected_visual_row()
        self._apply_table_row_highlight(visual)
        burst_index = self._burst_index_for_row(visual)
        if burst_index is None or self._df_bursts is None:
            self._update_selected_burst_status()
            return
        if burst_index < 0 or burst_index >= len(self._df_bursts):
            self._update_selected_burst_status()
            return
        t0 = float(self._df_bursts["t_start"].iloc[burst_index])
        t1 = float(self._df_bursts["t_stop"].iloc[burst_index])
        mid = (t0 + t1) / 2.0
        width_s = max(t1 - t0, 0.0)
        span = float(self.span_spin.value())
        if width_s > 0 and span < width_s * 3:
            self._updating_controls = True
            self.span_spin.setValue(max(width_s * 5.0, 0.1))
            self._updating_controls = False
        self._set_t_center(mid, redraw=True)
        self._update_selected_burst_status()

    def _burst_index_at_time(self, t):
        """Return burst row index containing time ``t``, or None."""
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return None
        starts = self._df_bursts["t_start"].to_numpy(dtype=float)
        stops = self._df_bursts["t_stop"].to_numpy(dtype=float)
        hits = np.flatnonzero((starts <= t) & (t <= stops))
        if len(hits) == 0:
            return None
        if len(hits) == 1:
            return int(hits[0])
        # Prefer the narrowest overlapping burst.
        widths = stops[hits] - starts[hits]
        return int(hits[int(np.argmin(widths))])

    def _on_plot_click(self, event):
        if self._ruler_mode:
            return
        if event.button != 1 or event.inaxes is None or event.xdata is None:
            return
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        burst_index = self._burst_index_at_time(float(event.xdata))
        if burst_index is None:
            return
        visual = self._visual_row_for_burst(burst_index)
        if visual is None:
            return
        if self._selected_visual_row() == visual:
            self._apply_table_row_highlight(visual)
            item = self.table.item(visual, 0)
            if item is not None:
                self.table.scrollToItem(item)
            self.redraw()
            return
        self.table.selectRow(visual)
        item = self.table.item(visual, 0)
        if item is not None:
            self.table.scrollToItem(item)

    def _on_plot_scroll(self, event):
        """Wheel: zoom span. Ctrl+wheel: pan left/right."""
        if event.inaxes is None:
            return
        step = float(getattr(event, "step", 0) or 0)
        if step == 0:
            return

        modifiers = QtWidgets.QApplication.keyboardModifiers()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        time_max = self._time_max()
        span = float(self.span_spin.value())

        if ctrl:
            # Pan: scroll up -> earlier time, scroll down -> later time
            delta = -0.25 * span * step
            new_center = float(self.t_center_spin.value()) + delta
            half = span / 2.0
            new_center = max(half, min(max(time_max - half, half), new_center))
            self._set_t_center(new_center, redraw=True)
            return

        # Zoom span (scroll up = zoom in)
        factor = 0.8 if step > 0 else 1.25
        new_span = max(0.01, min(time_max, span * factor))
        if abs(new_span - span) < 1e-12:
            return

        if event.xdata is not None:
            tmin, tmax = self._view_limits()
            width = max(tmax - tmin, 1e-12)
            rel = (float(event.xdata) - tmin) / width
            rel = min(max(rel, 0.0), 1.0)
            new_tmin = float(event.xdata) - rel * new_span
            new_center = new_tmin + new_span / 2.0
        else:
            new_center = float(self.t_center_spin.value())

        half = new_span / 2.0
        new_center = max(half, min(max(time_max - half, half), new_center))

        self._updating_controls = True
        self.span_spin.setValue(new_span)
        self._updating_controls = False
        self._sync_scrollbar_range()
        self._set_t_center(new_center, redraw=True)

    def _apply_table_row_highlight(self, selected_row):
        """Paint selected row blue so it stays obvious with alternating colors."""
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                if selected_row is not None and row == selected_row:
                    item.setBackground(TABLE_SELECTED_BG)
                    item.setForeground(TABLE_SELECTED_FG)
                else:
                    item.setBackground(QtGui.QBrush())
                    item.setForeground(QtGui.QBrush())

    def _goto_prev_burst(self):
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        row = self._selected_visual_row()
        if row is None:
            row = 0
        else:
            row = max(0, row - 1)
        self.table.selectRow(row)
        item = self.table.item(row, 0)
        if item is not None:
            self.table.scrollToItem(item)

    def _goto_next_burst(self):
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        n = self.table.rowCount()
        row = self._selected_visual_row()
        if row is None:
            row = 0
        else:
            row = min(n - 1, row + 1)
        self.table.selectRow(row)
        item = self.table.item(row, 0)
        if item is not None:
            self.table.scrollToItem(item)

    def _fit_to_selected(self):
        burst_index = self._selected_burst_index()
        if burst_index is None or self._df_bursts is None:
            return
        if burst_index < 0 or burst_index >= len(self._df_bursts):
            return
        t0 = float(self._df_bursts["t_start"].iloc[burst_index])
        t1 = float(self._df_bursts["t_stop"].iloc[burst_index])
        width_s = max(t1 - t0, 1e-3)
        self._updating_controls = True
        self.span_spin.setValue(width_s * 10.0)
        self._updating_controls = False
        self._set_t_center((t0 + t1) / 2.0, redraw=True)

    def _on_ruler_toggled(self, checked):
        self._ruler_mode = bool(checked)
        if not self._ruler_mode:
            self._ruler_span = None
            self._update_selected_burst_status()
        self.redraw()

    def _on_ruler_span(self, t0, t1):
        t0 = float(t0)
        t1 = float(t1)
        if t1 < t0:
            t0, t1 = t1, t0
        if t1 - t0 < 1e-6:
            return
        self._ruler_span = (t0, t1)
        self._update_ruler_status()
        self.redraw()

    def _update_ruler_status(self):
        if self._ruler_span is None or self._data is None:
            return
        t0, t1 = self._ruler_span
        self.status_label.setText(self._format_window_status(t0, t1))

    def _clear_span_selector(self):
        selector = self._span_selector
        self._span_selector = None
        if selector is None:
            return
        try:
            selector.disconnect_events()
        except Exception:
            pass

    def _install_span_selector(self, ax):
        self._clear_span_selector()
        if not self._ruler_mode:
            return
        self._span_selector = SpanSelector(
            ax,
            self._on_ruler_span,
            "horizontal",
            useblit=False,
            props=dict(alpha=0.25, facecolor=RULER_COLOR),
            interactive=False,
            button=1,
            minspan=1e-4,
        )

    def _clear_plot(self):
        self._clear_span_selector()
        fig = self.plot_widget.figure
        fig.clear()
        self.plot_widget.canvas.draw_idle()

    def redraw(self):
        if self._data is None:
            self._clear_plot()
            return

        d = self._data
        ich = self._ich
        clk_p = float(d.clk_p)
        tmin, tmax = self._view_limits()
        binwidth = float(self.binwidth_spin.value()) * 1e-3  # ms -> s

        self._clear_span_selector()
        fig = self.plot_widget.figure
        fig.clear()
        ax = fig.add_subplot(111)

        # Burst spans overlapping the view; selected burst highlighted.
        selected_burst = self._selected_burst_index()
        if self._df_bursts is not None and len(self._df_bursts) > 0:
            starts = self._df_bursts["t_start"].to_numpy(dtype=float)
            stops = self._df_bursts["t_stop"].to_numpy(dtype=float)
            mask = (starts < tmax) & (stops > tmin)
            for idx in np.flatnonzero(mask):
                if selected_burst is not None and int(idx) == int(selected_burst):
                    continue
                s, e = float(starts[idx]), float(stops[idx])
                ax.axvspan(s, e, color=BURST_COLOR, alpha=0.45, zorder=0)
            if selected_burst is not None and 0 <= selected_burst < len(starts):
                s = float(starts[selected_burst])
                e = float(stops[selected_burst])
                if s < tmax and e > tmin:
                    ax.axvspan(
                        s, e,
                        color=SELECTED_BURST_COLOR,
                        alpha=0.55,
                        zorder=1,
                    )
                    ax.axvline(s, color=SELECTED_BURST_COLOR, lw=1.2, zorder=2)
                    ax.axvline(e, color=SELECTED_BURST_COLOR, lw=1.2, zorder=2)

        if self._ruler_span is not None:
            rs, re = self._ruler_span
            ax.axvspan(rs, re, color=RULER_COLOR, alpha=0.35, zorder=3)
            ax.axvline(rs, color=RULER_COLOR, lw=1.2, zorder=4)
            ax.axvline(re, color=RULER_COLOR, lw=1.2, zorder=4)

        ymax = 1.0
        use_kcps = self.cps_check.isChecked()
        for ph_sel, invert, label, color in _streams_for_data(d):
            try:
                mask = d.get_ph_mask(ich, ph_sel=ph_sel)
                if mask is not None and not np.any(mask):
                    continue
                ph = d.get_ph_times(ich, ph_sel=ph_sel)
            except Exception:
                continue
            if ph is None or len(ph) == 0:
                continue

            x, counts, eff_bw = compute_binned_trace(ph, tmin, tmax, binwidth, clk_p)
            if len(x) == 0:
                continue
            # Use effective binwidth in case it was widened by the max-bins cap.
            if use_kcps and eff_bw > 0:
                scale = 1.0 / (eff_bw * 1000.0)  # counts/bin -> kcps
            else:
                scale = 1.0
            y_vals = counts.astype(float) * scale
            y = -y_vals if invert else y_vals
            ax.plot(x, y, drawstyle="steps-mid", label=label, lw=0.9, color=color)
            ymax = max(ymax, float(np.max(np.abs(y_vals))))

        self._last_auto_ymax = ymax * 1.1
        if self.y_lock_check.isChecked():
            y_limit = max(float(self.y_max_spin.value()), 0.01)
        else:
            y_limit = self._last_auto_ymax

        ax.set_xlim(tmin, tmax)
        ax.set_ylim(-y_limit, y_limit)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("kcps" if use_kcps else "Counts / bin")
        ax.axhline(0, color="k", lw=0.5)
        ax.legend(loc="upper right", fontsize=8)
        self._install_span_selector(ax)
        self._update_scroll_legend()
        self.plot_widget.canvas.draw_idle()
