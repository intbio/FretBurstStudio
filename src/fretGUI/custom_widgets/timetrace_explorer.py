"""Fast windowed photon timetrace explorer with burst table."""

from __future__ import annotations

import numpy as np
import fretbursts
from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import Signal
from NodeGraphQt import NodeBaseWidget
from custom_widgets.plot_widget import TemplatePlotWidget

MAX_BINS = 20_000
BURST_COLOR = "#BBBBBB"
SELECTED_BURST_COLOR = "#2F6FED"
DONOR_COLOR = "#2CA02C"
ACCEPTOR_COLOR = "#D62728"
AA_COLOR = "#9467BD"
TABLE_COLUMNS = ("#", "t_start", "t_stop", "width_ms", "size_raw", "E", "S")
TABLE_SELECTED_BG = QtGui.QColor(47, 111, 237, 90)
TABLE_SELECTED_FG = QtGui.QColor(20, 20, 20)


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


class TimeScrollAxis(QtWidgets.QWidget):
    """Tick marks + time labels under the timetrace scrollbar (0 … time_max)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._time_max = 1.0
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
        # Align with scrollbar inner track (1px border, no arrow gutters).
        rect = self.rect().adjusted(1, 0, -1, 0)
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
            # Keep first/last labels inside the widget.
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


class TimetraceExplorerWindow(QtWidgets.QDialog):
    """Separate window: burst table + windowed timetrace plot."""

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

        self._build_ui()
        self._wire_signals()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QtWidgets.QLabel("Binwidth (ms):"))
        self.binwidth_spin = QtWidgets.QDoubleSpinBox()
        self.binwidth_spin.setRange(0.01, 1000.0)
        self.binwidth_spin.setDecimals(3)
        self.binwidth_spin.setSingleStep(0.1)
        self.binwidth_spin.setValue(1.0)
        controls.addWidget(self.binwidth_spin)

        controls.addWidget(QtWidgets.QLabel("Span (s):"))
        self.span_spin = QtWidgets.QDoubleSpinBox()
        self.span_spin.setRange(0.01, 1e6)
        self.span_spin.setDecimals(3)
        self.span_spin.setSingleStep(0.5)
        self.span_spin.setValue(2.0)
        controls.addWidget(self.span_spin)

        controls.addWidget(QtWidgets.QLabel("t center (s):"))
        self.t_center_spin = QtWidgets.QDoubleSpinBox()
        self.t_center_spin.setRange(0.0, 1e9)
        self.t_center_spin.setDecimals(4)
        self.t_center_spin.setSingleStep(0.1)
        self.t_center_spin.setValue(0.0)
        controls.addWidget(self.t_center_spin)

        self.cps_check = QtWidgets.QCheckBox("Show kcps")
        self.cps_check.setToolTip("Plot kcps (10³ counts/s) instead of counts per bin")
        controls.addWidget(self.cps_check)

        self.prev_btn = QtWidgets.QPushButton("Prev burst")
        self.next_btn = QtWidgets.QPushButton("Next burst")
        self.fit_btn = QtWidgets.QPushButton("Fit to selected")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.save_btn = QtWidgets.QPushButton("Save image")
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.fit_btn)
        controls.addWidget(self.refresh_btn)
        controls.addWidget(self.save_btn)
        controls.addStretch(1)

        layout.addLayout(controls)

        self.status_label = QtWidgets.QLabel("")
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
        self.table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background-color: rgba(47, 111, 237, 120);
                color: #101010;
            }
            """
        )
        splitter.addWidget(self.table)

        plot_panel = QtWidgets.QWidget()
        plot_layout = QtWidgets.QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)

        self.plot_widget = TemplatePlotWidget(parent=self, mpl_width=7.0, mpl_height=4.0)
        self.plot_widget.toolbar.setVisible(False)

        self.time_scroll = QtWidgets.QScrollBar(QtCore.Qt.Horizontal)
        self.time_scroll.setToolTip("Browse timetrace (independent of burst selection)")
        self.time_scroll.setMinimumHeight(24)
        self.time_scroll.setStyleSheet(
            """
            QScrollBar:horizontal {
                height: 24px;
                background: #E8E8E8;
                margin: 0px;
                border: 1px solid #B0B0B0;
            }
            QScrollBar::handle:horizontal {
                background: #6A9FD8;
                min-width: 40px;
                border-radius: 3px;
                border: 1px solid #3F7FBF;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4F8FC8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
                background: none;
                border: none;
            }
            QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
                width: 0px;
                height: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: #F2F2F2;
            }
            """
        )

        scroll_legend = TimeScrollAxis(self)
        self.scroll_axis = scroll_legend

        plot_layout.addWidget(self.plot_widget, stretch=1)
        plot_layout.addWidget(self.time_scroll)
        plot_layout.addWidget(self.scroll_axis)
        splitter.addWidget(plot_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, stretch=1)

    def _wire_signals(self):
        self.binwidth_spin.valueChanged.connect(self._on_controls_changed)
        self.span_spin.valueChanged.connect(self._on_controls_changed)
        self.t_center_spin.valueChanged.connect(self._on_controls_changed)
        self.cps_check.toggled.connect(self._on_controls_changed)
        self.refresh_btn.clicked.connect(self.redraw)
        self.save_btn.clicked.connect(self.plot_widget._custom_save_figure)
        self.prev_btn.clicked.connect(self._goto_prev_burst)
        self.next_btn.clicked.connect(self._goto_next_burst)
        self.fit_btn.clicked.connect(self._fit_to_selected)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        self.time_scroll.valueChanged.connect(self._on_scrollbar_changed)
        self.plot_widget.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.plot_widget.canvas.mpl_connect("scroll_event", self._on_plot_scroll)

    def set_data(self, data, ich=0, preserve_view=False):
        """Load a fretbursts.Data object and refresh table + plot."""
        prev_center = float(self.t_center_spin.value())
        prev_span = float(self.span_spin.value())
        prev_binwidth = float(self.binwidth_spin.value())
        prev_row = self._selected_row()

        self._data = data
        self._ich = ich
        self._df_bursts = None

        if data is None:
            self.table.setRowCount(0)
            self.status_label.setText("No data.")
            self._clear_plot()
            self._sync_scrollbar_range()
            return

        has_bursts = "mburst" in data
        if has_bursts:
            try:
                self._df_bursts = fretbursts.bext.burst_data(data)
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
            if (
                self._df_bursts is not None
                and len(self._df_bursts) > 0
                and prev_row is not None
                and prev_row < len(self._df_bursts)
            ):
                self.table.blockSignals(True)
                self.table.selectRow(prev_row)
                self.table.blockSignals(False)
                self._apply_table_row_highlight(prev_row)
            self.status_label.setText(
                f"{len(self._df_bursts)} bursts" if self._df_bursts is not None else "No bursts"
            )
        elif self._df_bursts is not None and len(self._df_bursts) > 0:
            t0 = float(self._df_bursts["t_start"].iloc[0])
            t1 = float(self._df_bursts["t_stop"].iloc[0])
            self._set_t_center((t0 + t1) / 2.0, redraw=False)
            self.status_label.setText(f"{len(self._df_bursts)} bursts")
            self.table.selectRow(0)
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

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._df_bursts is None or len(self._df_bursts) == 0:
            self.table.blockSignals(False)
            return

        df = self._df_bursts
        self.table.setRowCount(len(df))
        for row in range(len(df)):
            values = [
                str(row),
                f"{df['t_start'].iloc[row]:.4f}",
                f"{df['t_stop'].iloc[row]:.4f}",
                f"{df['width_ms'].iloc[row]:.3f}" if "width_ms" in df.columns else "",
                f"{df['size_raw'].iloc[row]:.0f}" if "size_raw" in df.columns else "",
                f"{df['E'].iloc[row]:.3f}" if "E" in df.columns else "",
                f"{df['S'].iloc[row]:.3f}" if "S" in df.columns else "",
            ]
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
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
        self._set_t_center(tmin + span / 2.0, redraw=True)

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

    def _set_t_center(self, value, redraw=True):
        self._updating_controls = True
        self.t_center_spin.setValue(float(value))
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
            self.redraw()

    def _on_controls_changed(self, *_args):
        if self._updating_controls:
            return
        # Span / center edits from spinboxes: keep scrollbar in sync.
        sender = self.sender()
        if sender in (self.span_spin, self.t_center_spin, self.binwidth_spin):
            self._sync_scrollbar_range()
        self.redraw()

    def _selected_row(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return rows[0].row()

    def _on_table_selection(self):
        row = self._selected_row()
        self._apply_table_row_highlight(row)
        if row is None or self._df_bursts is None:
            return
        t0 = float(self._df_bursts["t_start"].iloc[row])
        t1 = float(self._df_bursts["t_stop"].iloc[row])
        mid = (t0 + t1) / 2.0
        width_s = max(t1 - t0, 0.0)
        span = float(self.span_spin.value())
        if width_s > 0 and span < width_s * 3:
            self._updating_controls = True
            self.span_spin.setValue(max(width_s * 5.0, 0.1))
            self._updating_controls = False
        self._set_t_center(mid, redraw=True)

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
        if event.button != 1 or event.inaxes is None or event.xdata is None:
            return
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        row = self._burst_index_at_time(float(event.xdata))
        if row is None:
            return
        if self._selected_row() == row:
            # Already selected — still ensure table row is visible / highlighted.
            self._apply_table_row_highlight(row)
            item = self.table.item(row, 0)
            if item is not None:
                self.table.scrollToItem(item)
            self.redraw()
            return
        self.table.selectRow(row)
        item = self.table.item(row, 0)
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
        row = self._selected_row()
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        if row is None:
            row = 0
        else:
            row = max(0, row - 1)
        self.table.selectRow(row)

    def _goto_next_burst(self):
        row = self._selected_row()
        if self._df_bursts is None or len(self._df_bursts) == 0:
            return
        n = len(self._df_bursts)
        if row is None:
            row = 0
        else:
            row = min(n - 1, row + 1)
        self.table.selectRow(row)

    def _fit_to_selected(self):
        row = self._selected_row()
        if row is None or self._df_bursts is None:
            return
        t0 = float(self._df_bursts["t_start"].iloc[row])
        t1 = float(self._df_bursts["t_stop"].iloc[row])
        width_s = max(t1 - t0, 1e-3)
        self._updating_controls = True
        self.span_spin.setValue(width_s * 10.0)
        self._updating_controls = False
        self._set_t_center((t0 + t1) / 2.0, redraw=True)

    def _clear_plot(self):
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

        fig = self.plot_widget.figure
        fig.clear()
        ax = fig.add_subplot(111)

        # Burst spans overlapping the view; selected burst highlighted.
        if self._df_bursts is not None and len(self._df_bursts) > 0:
            starts = self._df_bursts["t_start"].to_numpy(dtype=float)
            stops = self._df_bursts["t_stop"].to_numpy(dtype=float)
            mask = (starts < tmax) & (stops > tmin)
            selected_row = self._selected_row()
            for idx in np.flatnonzero(mask):
                s, e = float(starts[idx]), float(stops[idx])
                if selected_row is not None and int(idx) == int(selected_row):
                    continue
                ax.axvspan(s, e, color=BURST_COLOR, alpha=0.45, zorder=0)
            if selected_row is not None and 0 <= selected_row < len(starts):
                s = float(starts[selected_row])
                e = float(stops[selected_row])
                if s < tmax and e > tmin:
                    ax.axvspan(
                        s, e,
                        color=SELECTED_BURST_COLOR,
                        alpha=0.55,
                        zorder=1,
                    )
                    ax.axvline(s, color=SELECTED_BURST_COLOR, lw=1.2, zorder=2)
                    ax.axvline(e, color=SELECTED_BURST_COLOR, lw=1.2, zorder=2)

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

        ax.set_xlim(tmin, tmax)
        ax.set_ylim(-ymax * 1.1, ymax * 1.1)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("kcps" if use_kcps else "Counts / bin")
        ax.axhline(0, color="k", lw=0.5)
        ax.legend(loc="upper right", fontsize=8)
        self._update_scroll_legend()
        self.plot_widget.canvas.draw_idle()
