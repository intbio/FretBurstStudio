from Qt import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from NodeGraphQt import NodeBaseWidget
import matplotlib
matplotlib.rcParams['figure.dpi'] = 96
matplotlib.rcParams['savefig.dpi'] = 96




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
        self.toolbar = NavigationToolbar(self.canvas)

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