from Qt import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from NodeGraphQt import NodeBaseWidget




class TemplatePlotWidget(QtWidgets.QWidget):
    '''
    Simplest widget with a matplotlib plot area and toolbar
    '''
    def __init__(self, parent=None):
        super().__init__()
        
        highlightColor = str('white')
        self.setFixedSize(2000, 2000)
        self.mainLayout = QtWidgets.QVBoxLayout(self)   
        self.mainLayout.setSpacing(10)
        self.figure = plt.figure(facecolor=highlightColor)
        self.canvas = FigureCanvas(self.figure)
        
        self.toolbar = NavigationToolbar(self.canvas)
        self.mainLayout.addWidget(self.canvas)
        self.mainLayout.addWidget(self.toolbar)
    
        
class TemplatePlotWidgetWtapper(NodeBaseWidget):
    '''
    Provides Widget for opening multiple files
    '''
    def __init__(self, parent=None, fretData=None):
        super().__init__(parent)
        self.plot_widget = TemplatePlotWidget(parent=parent)
        self.set_custom_widget(self.plot_widget)
        self.fretData=fretData
    
        self.plot_widget.figure.clf()

        
    def get_value(self):
        return self.fretData
    
    def set_value(self, fretData):
        self.fretData = fretData