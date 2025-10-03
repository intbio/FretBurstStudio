from Qt import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from NodeGraphQt import NodeBaseWidget
import fretbursts




class TemplatePlotWidget(QtWidgets.QWidget):
    '''
    Simplest widget with a matplotlib plot area and toolbar
    '''
    def __init__(self, parent=None):
        super().__init__()
        
        highlightColor = str('white')
        self.setFixedSize(600, 400)
        self.mainLayout = QtWidgets.QVBoxLayout(self)   
        self.mainLayout.setSpacing(10)
        self.figure = plt.figure(facecolor=highlightColor)
        self.canvas = FigureCanvas(self.figure)
        
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.mainLayout.addWidget(self.canvas)
        self.mainLayout.addWidget(self.toolbar)
        # self.updateBtn=QtWidgets.QPushButton('Update')
        # self.settingsScrollArea = QtWidgets.QScrollArea()
        # self.setWidgetResizable(True)
    
        
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
        # self.ax1 = self.plot_widget.figure.add_subplot(211)
        # self.ax2 = self.plot_widget.figure.add_subplot(212)
        # self.ax.plot([1,2,6,2])
        # fretbursts.dplot(self.fretData, fretbursts.hist_bg, show_fit=True, ax=ax)        
        # fretbursts.dplot(self.fretData, fretbursts.timetrace_bg, ax=ax)
        # # ax2.set_title('')
        # self.plot_widget.canvas.draw()
        # self.setEnabled(True)
        
    # def update_plot(self, time_s, tail_min_us, method='Auto'):
    #     # self.setEnabled(False)
    #     if method == 'Auto':
    #         self.fretData.calc_bg(fretbursts.bg.exp_fit, time_s=time_s,
    #                                 tail_min_us='auto')     
    #     elif method =='Manual':
    #         self.fretData.calc_bg(fretbursts.bg.exp_fit, time_s=time_s,
    #                                 tail_min_us=tail_min_us)

        
    def get_value(self):
        return self.fretData
    
    def set_value(self, fretData):
        self.fretData = fretData
