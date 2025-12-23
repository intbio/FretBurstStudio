from Qt import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from NodeGraphQt import NodeBaseWidget
import matplotlib
matplotlib.rcParams['figure.dpi'] = 96
matplotlib.rcParams['savefig.dpi'] = 96
import os


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

        self.mainLayout.addWidget(self.canvas)
        self.mainLayout.addWidget(self.toolbar)
    
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