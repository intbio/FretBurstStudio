from Qt import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from NodeGraphQt import NodeBaseWidget
import matplotlib
import os

# Default for saves when a figure has not synced yet; live figures set DPI per widget.
matplotlib.rcParams['savefig.dpi'] = 150

# Absolute margins for labels/ticks (in inches)
_ABS_MARGINS_IN = dict(left=0.8, right=0.25, bottom=0.5, top=0.25)
_MAX_GRAPH_OVERSAMPLE = 3.0
_OVERSAMPLE_DEBOUNCE_MS = 80
_DARK_MPL_STYLE = dict(plt.style.library['dark_background'])
_DARK_MPL_STYLE.update({
    'axes.facecolor': '#303030',
    'figure.facecolor': '#303030',
    'savefig.facecolor': '#303030',
})
_LIGHT_MPL_STYLE = {
    key: matplotlib.rcParams[key]
    for key in _DARK_MPL_STYLE
}
_ACTIVE_MPL_THEME = 'light'


def set_matplotlib_theme(kind):
    """Set defaults for axes created after a GUI theme change."""
    global _ACTIVE_MPL_THEME
    if kind == _ACTIVE_MPL_THEME:
        return
    style = _DARK_MPL_STYLE if kind == 'dark' else _LIGHT_MPL_STYLE
    matplotlib.rcParams.update(style)
    matplotlib.rcParams['savefig.dpi'] = 150
    _ACTIVE_MPL_THEME = kind


class TemplatePlotWidget(QtWidgets.QWidget):
    """
    Simplest widget with a matplotlib plot area and toolbar
    """
    def __init__(
        self,
        parent=None,
        mpl_width=None,
        mpl_height=None,
        retain_limits=False,
    ):
        super().__init__()
        self._retain_limits_enabled = False
        self._retain_cid = None
        self._home_overridden = False

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        # Let layouts handle sizing
        self.mainLayout = QtWidgets.QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # Create figure with optional size
        if mpl_width is not None and mpl_height is not None:
            self.figure = plt.figure(facecolor='none', figsize=(mpl_width, mpl_height))
        else:
            self.figure = plt.figure(facecolor='none')
            
        self.canvas = FigureCanvas(self.figure)
        self.figure.patch.set_alpha(0)
        self.canvas.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.canvas.setAutoFillBackground(False)
        self.canvas.setStyleSheet('background: transparent;')
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.canvas.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.toolbar.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.toolbar.setAutoFillBackground(False)
        self.toolbar.setStyleSheet(
            'QToolBar { background: transparent; border: 0; }'
        )
        # Keep Matplotlib's toolbar independent from the application theme.
        # Its source icons are black and remain clear over both node colors.
        toolbar_palette = self.toolbar.palette()
        toolbar_palette.setColor(QtGui.QPalette.Window, QtGui.QColor('white'))
        toolbar_palette.setColor(QtGui.QPalette.Button, QtGui.QColor('white'))
        toolbar_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('black'))
        toolbar_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('black'))
        self.toolbar.setPalette(toolbar_palette)
        for _, _, image_name, callback in self.toolbar.toolitems:
            if image_name:
                action = self.toolbar._actions.get(callback)
                if action is not None:
                    action.setIcon(self.toolbar._icon(image_name))
        self._toolbar_left_inset = 0
        self._hide_history_actions()
        self._toolbar_left_spacer = QtWidgets.QWidget()
        self._toolbar_left_spacer.setFixedWidth(0)
        self._graph_render_scale = 1.0
        self._oversample_timer = QtCore.QTimer(self)
        self._oversample_timer.setSingleShot(True)
        self._oversample_timer.setInterval(_OVERSAMPLE_DEBOUNCE_MS)
        self._oversample_timer.timeout.connect(self._apply_graph_render_scale)
        self._drawn_axes = ()
        self._retained_limits = []
        self._default_limits = []

        # Method 1: Try to find save action by iterating actions
        save_action = None
        for action in self.toolbar.actions():
            tooltip = action.toolTip().lower() if hasattr(action, 'toolTip') else ''
            text = action.text().lower() if hasattr(action, 'text') else ''
            if 'save' in tooltip or 'save' in text:
                save_action = action
                print(f"DEBUG: Found save action by tooltip/text: {action.toolTip()}")
                break
        
        # Method 2: Try accessing via _actions dict if it exists
        if save_action is None and hasattr(self.toolbar, '_actions'):
            if 'save_figure' in self.toolbar._actions:
                save_action = self.toolbar._actions['save_figure']
                print(f"DEBUG: Found save action via _actions dict")
        
        # Method 3: Try finding by objectName
        if save_action is None:
            for action in self.toolbar.actions():
                if hasattr(action, 'objectName') and 'save' in action.objectName().lower():
                    save_action = action
                    print(f"DEBUG: Found save action by objectName: {action.objectName()}")
                    break
        
        if save_action:
            # Disconnect all existing connections
            try:
                save_action.triggered.disconnect()
            except TypeError:
                # No connections to disconnect
                pass
            # Connect to our custom method
            save_action.triggered.connect(self._custom_save_figure)
            print(f"DEBUG: Successfully reconnected save action")
        else:
            print(f"DEBUG: Could not find save action, trying method override only")
            # Fallback: override the method
            self.toolbar.save_figure = self._custom_save_figure
        
        # make them expand with the parent
        self.canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.toolbar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )

        self._apply_absolute_margins()
        self.canvas.mpl_connect("resize_event", self._on_canvas_resize)

        self.keep_view_check = QtWidgets.QCheckBox("Keep view")
        self.keep_view_check.setToolTip(
            "Restore the current zoom and pan after the plot updates. "
            "Unchecking recalculates the plot."
        )
        self.keep_view_check.setChecked(bool(retain_limits))
        self.keep_view_check.toggled.connect(self._on_keep_view_toggled)

        toolbar_row = QtWidgets.QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(4)
        toolbar_row.addWidget(self._toolbar_left_spacer)
        toolbar_row.addWidget(self.keep_view_check)
        toolbar_row.addWidget(self.toolbar, stretch=1)
        self.mainLayout.addLayout(toolbar_row)
        self.mainLayout.addWidget(self.canvas)
        self._set_limit_retention(self.keep_view_check.isChecked())

    def _on_keep_view_toggled(self, checked):
        self._set_limit_retention(bool(checked))

    def _set_limit_retention(self, enabled):
        """Keep the current axes limits across replots only while enabled."""
        self._retain_limits_enabled = bool(enabled)
        if self._retain_limits_enabled:
            if self._retain_cid is None:
                self._retain_cid = self.canvas.mpl_connect(
                    "draw_event",
                    self._retain_plot_limits,
                )
            axes = tuple(self.figure.axes)
            if axes:
                self._drawn_axes = axes
                self._retained_limits = [
                    (ax.get_xlim(), ax.get_ylim())
                    for ax in axes
                ]
        elif self._retain_cid is not None:
            self.canvas.mpl_disconnect(self._retain_cid)
            self._retain_cid = None
        self._set_home_override(self._retain_limits_enabled)

    def _set_home_override(self, enabled):
        """Use the recalculated view for Home while limit retention is on."""
        home_action = self.toolbar._actions.get('home')
        if home_action is None:
            return
        if enabled and not self._home_overridden:
            try:
                home_action.triggered.disconnect()
            except TypeError:
                pass
            home_action.triggered.connect(self._reset_plot_limits)
            self._home_overridden = True
        elif not enabled and self._home_overridden:
            try:
                home_action.triggered.disconnect()
            except TypeError:
                pass
            home_action.triggered.connect(self.toolbar.home)
            self._home_overridden = False

    def _retain_plot_limits(self, event):
        """Restore view limits when a replot replaces this widget's axes."""
        axes = tuple(self.figure.axes)
        if not axes:
            # Keep the previous view while the figure is temporarily empty.
            return

        axes_changed = self._drawn_axes and axes != self._drawn_axes
        if axes_changed and self._retained_limits:
            self._default_limits = [
                (ax.get_xlim(), ax.get_ylim())
                for ax in axes
            ]
            for ax, (xlim, ylim) in zip(axes, self._retained_limits):
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
            self._drawn_axes = axes
            self.canvas.draw_idle()
            return

        if not self._drawn_axes:
            self._default_limits = [
                (ax.get_xlim(), ax.get_ylim())
                for ax in axes
            ]
        self._drawn_axes = axes
        self._retained_limits = [
            (ax.get_xlim(), ax.get_ylim())
            for ax in axes
        ]

    def _reset_plot_limits(self):
        """Restore the limits produced by the most recent recalculation."""
        if not self._default_limits:
            return
        axes = tuple(self.figure.axes)
        for ax, (xlim, ylim) in zip(axes, self._default_limits):
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
        self._drawn_axes = axes
        self._retained_limits = list(self._default_limits)
        self.canvas.draw_idle()

    def set_theme(self, kind, colors=None):
        """Apply the active theme to existing and future Matplotlib axes."""
        set_matplotlib_theme(kind)
        self.figure.patch.set_alpha(0)

        axes_facecolor = matplotlib.rcParams['axes.facecolor']
        axes_edgecolor = matplotlib.rcParams['axes.edgecolor']
        text_color = matplotlib.rcParams['text.color']
        tick_color = matplotlib.rcParams['xtick.color']
        grid_color = matplotlib.rcParams['grid.color']

        for ax in self.figure.axes:
            ax.set_facecolor(axes_facecolor)
            ax.title.set_color(text_color)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            ax.tick_params(axis='both', colors=tick_color)
            for spine in ax.spines.values():
                spine.set_color(axes_edgecolor)
            for grid_line in [*ax.get_xgridlines(), *ax.get_ygridlines()]:
                grid_line.set_color(grid_color)
            for text in ax.texts:
                text.set_color(text_color)

            legend = ax.get_legend()
            if legend is not None:
                legend_facecolor = matplotlib.rcParams['legend.facecolor']
                if legend_facecolor == 'inherit':
                    legend_facecolor = axes_facecolor
                legend_edgecolor = matplotlib.rcParams['legend.edgecolor']
                if legend_edgecolor == 'inherit':
                    legend_edgecolor = axes_edgecolor
                legend.get_frame().set_facecolor(
                    legend_facecolor
                )
                legend.get_frame().set_edgecolor(
                    legend_edgecolor
                )
                for legend_text in legend.get_texts():
                    legend_text.set_color(text_color)

        self.canvas.draw_idle()

    def _hide_history_actions(self):
        """Hide view-history arrows that resemble graph navigation controls."""
        for action in self.toolbar.actions():
            action_name = action.text().replace('&', '').strip().lower()
            if action_name in {'back', 'forward'}:
                action.setVisible(False)

    def set_toolbar_left_inset(self, pixels):
        """Move Keep view and the toolbar past the input port name."""
        inset = max(0, int(round(pixels)))
        if inset == self._toolbar_left_inset:
            return
        self._toolbar_left_inset = inset
        self._toolbar_left_spacer.setFixedWidth(inset)

    def _apply_absolute_margins(self):
        w, h = self.figure.get_size_inches()
        w = max(w, 0.01)
        h = max(h, 0.01)
        left = _ABS_MARGINS_IN['left'] / w
        right = 1 - _ABS_MARGINS_IN['right'] / w
        bottom = _ABS_MARGINS_IN['bottom'] / h
        top = 1 - _ABS_MARGINS_IN['top'] / h
        # Avoid inverted margins on tiny canvases
        if left >= right or bottom >= top:
            return
        self.figure.subplots_adjust(left=left, right=right, bottom=bottom, top=top)

    def _on_canvas_resize(self, event):
        # FigureCanvasQTAgg has already updated the figure using Qt's device
        # pixel ratio. Only update our margins here so HiDPI rendering is kept.
        self._apply_absolute_margins()
        event.canvas.draw_idle()

    def set_graph_scale(self, scale):
        """Request enough canvas pixels for the current node-graph zoom."""
        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = 1.0
        self._graph_render_scale = min(
            max(scale, 1.0),
            _MAX_GRAPH_OVERSAMPLE,
        )

        target_ratio = (
            max(float(self.canvas.devicePixelRatioF()), 1.0)
            * self._graph_render_scale
        )
        if abs(self.canvas.device_pixel_ratio - target_ratio) < 0.01:
            return
        self._oversample_timer.start()

    def _apply_graph_render_scale(self):
        """Apply graph oversampling after zoom interaction has settled."""
        target_ratio = (
            max(float(self.canvas.devicePixelRatioF()), 1.0)
            * self._graph_render_scale
        )
        if not self.canvas._set_device_pixel_ratio(target_ratio):
            return

        # Match Matplotlib's own HiDPI update path: resizing recalculates the
        # backing Agg buffer while preserving the canvas's logical dimensions.
        resize_event = QtGui.QResizeEvent(
            self.canvas.size(),
            self.canvas.size(),
        )
        self.canvas.resizeEvent(resize_event)
        
    
    def _custom_save_figure(self, *args, **kwargs):
        """
        Custom save figure method that opens a file dialog with all matplotlib-supported formats.
        """
        print("DEBUG: _custom_save_figure called")
        
        # Get all supported file formats from matplotlib
        file_filter = (
            "PNG files (*.png);;"
            "PDF files (*.pdf);;"
            "PostScript files (*.ps);;"
            "EPS files (*.eps);;"
            "SVG files (*.svg);;"
            "JPEG files (*.jpg *.jpeg);;"
            "TIFF files (*.tif *.tiff);;"
            "WebP files (*.webp);;"
            "PGF files (*.pgf);;"
            "Raw RGBA files (*.raw);;"
            "All files (*)"
        )
        
        cwd = os.getcwd()
        
        from Qt.QtWidgets import QApplication
        parent_window = QApplication.activeWindow()
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            parent_window,
            "Save Figure",
            cwd,
            filter=file_filter
        )
        print(f"DEBUG: getSaveFileName returned: filename={filename}, filter={selected_filter}")
        
        # Save the figure if a filename was provided
        if filename:
            try:
                self.figure.savefig(filename, facecolor='white')
                print("DEBUG: Figure saved successfully")
            except Exception as e:
                print(f"DEBUG: Exception saving figure: {e}")
                import traceback
                traceback.print_exc()
                QtWidgets.QMessageBox.warning(
                    parent_window if parent_window else self,
                    "Save Error",
                    f"Failed to save figure:\n{str(e)}"
                )
   
        
class TemplatePlotWidgetWtapper(NodeBaseWidget):
    '''
    Provides Widget for opening multiple files
    '''
    def __init__(self, parent=None, fretData=None, mpl_width=None, mpl_height=None):
        super().__init__(parent)
        self.set_label('')
        self.plot_widget = TemplatePlotWidget(parent=parent, mpl_width=mpl_width, mpl_height=mpl_height)
        self.set_custom_widget(self.plot_widget)
        self.fretData=fretData
        
    def get_value(self):
        return None
    
    def set_value(self, fretData):
        return None


def _is_plot_widget(widget):
    while widget is not None:
        if isinstance(widget, TemplatePlotWidget):
            return True
        widget = widget.parentWidget()
    return False


def plot_widget_under(global_pos):
    """Return True when a screen position is over a matplotlib plot widget."""
    return _is_plot_widget(QtWidgets.QApplication.widgetAt(global_pos))


def plot_area_at(viewer, view_pos):
    """Return True when a graph view position is over a matplotlib plot widget."""
    viewport = viewer.viewport()
    global_pos = viewport.mapToGlobal(view_pos)
    if plot_widget_under(global_pos):
        return True

    scene_pos = viewer.mapToScene(view_pos)
    for item in viewer.scene().items(scene_pos):
        if not isinstance(item, QtWidgets.QGraphicsProxyWidget):
            continue
        widget = item.widget()
        if widget is None:
            continue
        local_pos = item.mapFromScene(scene_pos).toPoint()
        if _is_plot_widget(widget.childAt(local_pos)) or _is_plot_widget(widget):
            return True
    return False


class PlotContextMenuGuard(QtCore.QObject):
    """Block the node-graph context menu when it would cover matplotlib controls."""

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.ContextMenu:
            return False
        viewer = self.parent()
        if plot_widget_under(event.globalPos()):
            event.accept()
            return True
        pos = event.pos()
        if obj is viewer.viewport():
            viewport_pos = pos
        else:
            viewport_pos = viewer.viewport().mapFrom(obj, pos)
        if plot_area_at(viewer, viewport_pos):
            event.accept()
            return True
        return False


def install_plot_context_menu_guard(viewer):
    """Keep right-clicks on plot canvases from opening the graph menu."""
    existing = getattr(viewer, '_plot_context_menu_guard', None)
    if existing is not None:
        return existing
    guard = PlotContextMenuGuard(viewer)
    viewer.installEventFilter(guard)
    viewer.viewport().installEventFilter(guard)
    viewer._plot_context_menu_guard = guard
    return guard
