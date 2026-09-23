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


class TemplatePlotWidget(QtWidgets.QWidget):
    """
    Simplest widget with a matplotlib plot area and toolbar
    """
    def __init__(self, parent=None, mpl_width=None, mpl_height=None):
        super().__init__()

        highlightColor = 'white'

        # Let layouts handle sizing
        self.mainLayout = QtWidgets.QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # Create figure with optional size
        if mpl_width is not None and mpl_height is not None:
            self.figure = plt.figure(facecolor=highlightColor, figsize=(mpl_width, mpl_height))
        else:
            self.figure = plt.figure(facecolor=highlightColor)
            
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self._graph_render_scale = 1.0
        self._oversample_timer = QtCore.QTimer(self)
        self._oversample_timer.setSingleShot(True)
        self._oversample_timer.setInterval(_OVERSAMPLE_DEBOUNCE_MS)
        self._oversample_timer.timeout.connect(self._apply_graph_render_scale)
        
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

        self.mainLayout.addWidget(self.toolbar)
        self.mainLayout.addWidget(self.canvas)

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
                self.figure.savefig(filename)
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
