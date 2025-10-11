from Qt import QtWidgets


class ProgressBar(QtWidgets.QProgressBar):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_nodes = 0
    
    def on_calculation_begin(self, total_nodes: int):
        self.reset()
        self.setValue(0)
        print(f"BEGIN {self.value()} total {total_nodes}")
        self.setRange(0, total_nodes)
        
        
    def on_calculation_finished(self):
        print("FINISHED")
        self.reset()

    
    def on_calculation_processed(self):
        cur_value = self.value()
        self.setValue(cur_value + 1)
        print(f"PROCESSED {cur_value}")
            
    