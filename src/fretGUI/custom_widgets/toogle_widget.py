from Qt.QtWidgets import QPushButton
from Qt.QtCore import QSize, Signal


class IconToggleButton(QPushButton):
    """Переключатель с иконками"""
    
    toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setCheckable(True)
        self.setFixedSize(80, 40)
        self.setIconSize(QSize(24, 24))
        self._update_appearance()
        self.toggled.connect(self._update_appearance)
        
    def _update_appearance(self):
        """Обновляет внешний вид кнопки"""
        if self.isChecked():
            # Можно установить реальные иконки вместо текста
            self.setText("automatic")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #e3f2fd;
                    color: #1565c0;
                    border: 2px solid #90caf9;
                    border-radius: 20px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #bbdefb;
                }
            """)
        else:
            self.setText("static")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #757575;
                    border: 2px solid #e0e0e0;
                    border-radius: 20px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #eeeeee;
                }
            """)