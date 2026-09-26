from Qt.QtWidgets import QCheckBox
from fretGUI.singletons import NodeStateManager


class AutoRunCheckBox(QCheckBox):
    """Checkbox that switches the graph between static and auto-run."""

    def __init__(self, parent=None):
        super().__init__("Auto Run", parent)
        self.setChecked(False)
        NodeStateManager().node_status = self.isChecked()

    def set_theme(self, kind, colors):
        """Checkboxes follow the application palette."""
