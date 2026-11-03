"""About FretBurstStudio: logo, source link, citations, and licenses."""

from Qt import QtCore, QtGui, QtWidgets

from fretGUI.custom_widgets.animated_logo import AnimatedLogo
from fretGUI.version import __version__


def _about_html(link_color):
    return f"""
<p style="font-size: 16px; margin-bottom: 0;"><b>FretBurstStudio</b></p>
<p style="margin-top: 4px;">Version {__version__}<br>
Dmitry Ryabov and Grigory Armeev</p>
<p><b>Source</b><br>
<a href="https://github.com/intbio/FretBurstStudio" style="color: {link_color};">intbio/FretBurstStudio</a></p>
<p><b>FRETBursts</b> — burst analysis library, GNU GPL v2<br>
<a href="https://github.com/OpenSMFS/FRETBursts" style="color: {link_color};">OpenSMFS/FRETBursts</a><br>
Ingargiola A, Lerner E, Chung S, Weiss S, Michalet X (2016)
FRETBursts: An Open Source Toolkit for Analysis of Freely-Diffusing
Single-Molecule FRET. PLoS ONE 11(8): e0160716.
<a href="https://doi.org/10.1371/journal.pone.0160716" style="color: {link_color};">doi:10.1371/journal.pone.0160716</a></p>
<p><b>fcsfiles</b> 2014.10.10 — Christoph Gohlke and the Regents of the
University of California. BSD 3-Clause.<br>
<a href="https://github.com/cgohlke/fcsfiles" style="color: {link_color};">cgohlke/fcsfiles</a></p>
<p><b>License</b><br>
FretBurstStudio is licensed under the
<a href="https://www.gnu.org/licenses/gpl-3.0.html" style="color: {link_color};">GNU General Public License v3</a>.</p>
"""


class AboutDialog(QtWidgets.QDialog):
    """Credits dialog. Text follows the application palette; the logo plate stays white."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About FretBurstStudio")
        self.setModal(True)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)

        plate = QtWidgets.QFrame()
        plate.setStyleSheet(
            "QFrame { background-color: white; border-radius: 16px; }"
        )
        plate_layout = QtWidgets.QVBoxLayout(plate)
        plate_layout.setContentsMargins(12, 12, 12, 12)
        self._logo = AnimatedLogo(plate, display_width=260)
        plate_layout.addWidget(self._logo, alignment=QtCore.Qt.AlignHCenter)
        root.addWidget(plate, alignment=QtCore.Qt.AlignHCenter)

        link = self.palette().color(QtGui.QPalette.Highlight).name()
        body = QtWidgets.QLabel(_about_html(link))
        body.setWordWrap(True)
        body.setTextFormat(QtCore.Qt.RichText)
        body.setOpenExternalLinks(True)
        body.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        body.setMinimumWidth(440)
        body.setMinimumHeight(body.heightForWidth(440))
        root.addWidget(body)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
