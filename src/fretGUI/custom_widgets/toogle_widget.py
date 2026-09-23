from Qt.QtWidgets import QPushButton
from Qt.QtCore import QSize, Signal
from fretGUI.singletons import NodeStateManager


class IconToggleButton(QPushButton):
    """Переключатель с иконками"""
    
    toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._theme_colors = {
            'button': (245, 245, 245),
            'button_hover': (238, 238, 238),
            'text': (117, 117, 117),
            'grid': (224, 224, 224),
            'highlight': (144, 202, 249),
            'highlighted_text': (21, 101, 192),
        }
        self.setCheckable(True)
        self.setFixedSize(80, 40)
        self.setIconSize(QSize(24, 24))
        self.setText("Auto Run")
        self._update_appearance()
        self.toggled.connect(self._update_appearance)
        self.setChecked(False)
        NodeStateManager().node_status = self.isChecked()

    def set_theme(self, kind, colors):
        self._theme_colors = colors
        self._update_appearance()
        
        
    def _update_appearance(self):
        """Обновляет внешний вид кнопки"""
        colors = self._theme_colors
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgb{colors['highlight']};
                    color: rgb{colors['highlighted_text']};
                    border: 2px solid rgb{colors['highlight']};
                    border-radius: 20px;
                    font-weight: bold;
                    padding: 5px;
                }}
                QPushButton:hover {{
                    background-color: rgb{colors['button_hover']};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgb{colors['button']};
                    color: rgb{colors['text']};
                    border: 2px solid rgb{colors['grid']};
                    border-radius: 20px;
                    font-weight: bold;
                    padding: 5px;
                }}
                QPushButton:hover {{
                    background-color: rgb{colors['button_hover']};
                }}
            """)