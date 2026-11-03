"""FretBurstStudio logo with blinking molecules and shining burst profiles."""

import math
from pathlib import Path

from Qt import QtCore, QtGui, QtWidgets

_LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "fb_logo.png"

# Centers and radii are fractions of the 450 px logo width.
# The teal profile shines with the teal circle, the orange reflection with the orange one.
_MOLECULES = (
    {
        "center": (0.449, 0.120),
        "radius": 0.079,
        "color": "#ff6600",
        "phase": 0.0,
    },
    {
        "center": (0.160, 0.409),
        "radius": 0.078,
        "color": "#2c89a0",
        "phase": math.pi,
    },
)

_FRAME_MS = 33
_PEAK_GLOW = QtGui.QColor("#8fd0de")
_STROKE_GLOW = QtGui.QColor("#d8f6fb")
_REFLECTION_GLOW = QtGui.QColor("#ffb088")


class AnimatedLogo(QtWidgets.QWidget):
    """Logo on white. The molecule disks blink, and the burst profiles shine with them."""

    def __init__(self, parent=None, display_width=280):
        super().__init__(parent)
        self._display_width = int(display_width)
        self.setFixedSize(self._display_width, self._display_width)
        self._base = QtGui.QImage()
        self._peak_fill = QtGui.QImage()
        self._peak_stroke = QtGui.QImage()
        self._reflection = QtGui.QImage()
        self._load()
        self._clock = QtCore.QElapsedTimer()
        self._clock.start()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(_FRAME_MS)
        self._timer.timeout.connect(self.update)

    def showEvent(self, event):
        self._clock.restart()
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _seconds(self):
        return self._clock.elapsed() / 1000.0

    def _wave(self, phase):
        return 0.5 + 0.5 * math.sin(self._seconds() * 2.4 + phase)

    def _load(self):
        image = QtGui.QImage(str(_LOGO_PATH))
        if image.isNull():
            self._base = image
            return
        image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
        self._clear_molecules(image)
        self._base = image
        self._build_glows(image)

    def _clear_molecules(self, image):
        """Remove the baked-in disks so the animated circles can replace them."""
        width = image.width()
        height = image.height()
        clear = QtGui.QColor(0, 0, 0, 0)
        for molecule in _MOLECULES:
            center_x = molecule["center"][0] * width
            center_y = molecule["center"][1] * width
            # Stay inside the disk. The connecting curve begins just outside it.
            radius = molecule["radius"] * width + 0.75
            radius_sq = radius * radius
            x0 = max(0, int(center_x - radius))
            x1 = min(width - 1, int(center_x + radius) + 1)
            y0 = max(0, int(center_y - radius))
            y1 = min(height - 1, int(center_y + radius) + 1)
            for y in range(y0, y1 + 1):
                dy = y - center_y
                for x in range(x0, x1 + 1):
                    dx = x - center_x
                    if dx * dx + dy * dy <= radius_sq:
                        image.setPixelColor(x, y, clear)

    def _build_glows(self, image):
        """Masks of the burst fill, its outline, and the orange reflection."""
        width = image.width()
        height = image.height()
        self._peak_fill = self._blank(width, height)
        self._peak_stroke = self._blank(width, height)
        self._reflection = self._blank(width, height)
        for y in range(height):
            for x in range(width):
                color = image.pixelColor(x, y)
                if self._is_peak_fill(color):
                    self._paint_glow(self._peak_fill, x, y, _PEAK_GLOW, color.alpha())
                elif self._is_peak_stroke(color, x, y):
                    self._paint_glow(self._peak_stroke, x, y, _STROKE_GLOW, color.alpha())
                elif self._is_reflection(color, y):
                    self._paint_glow(
                        self._reflection, x, y, _REFLECTION_GLOW, color.alpha()
                    )

    def _blank(self, width, height):
        image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
        image.fill(QtCore.Qt.transparent)
        return image

    def _paint_glow(self, image, x, y, color, alpha):
        glow = QtGui.QColor(color)
        glow.setAlpha(alpha)
        image.setPixelColor(x, y, glow)

    def _is_peak_fill(self, color):
        """Light interior of the main burst, above the baseline."""
        return (
            color.alpha() > 20
            and color.red() > 160
            and color.green() > 190
            and color.blue() > 200
        )

    def _is_peak_stroke(self, color, x, y):
        """Teal outline of the burst. Skips the baseline bar and the molecule."""
        if color.alpha() < 20 or y >= 278 or x < 220:
            return False
        return (
            color.red() < 110
            and color.green() > 90
            and color.blue() > 110
        )

    def _is_reflection(self, color, y):
        """Pale orange mirror of the burst, under the orange bar."""
        if color.alpha() < 20 or y < 320:
            return False
        red = color.red()
        green = color.green()
        blue = color.blue()
        if red > 230 and green < 150 and blue < 60:
            return False
        return red > 170 and green > 80 and blue < 200 and red > green > blue

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QtGui.QColor("white"))
        if not self._base.isNull():
            target = QtCore.QRectF(self.rect())
            painter.drawImage(target, self._base)
            teal = self._wave(math.pi)
            orange = self._wave(0.0)
            self._draw_glow(painter, self._peak_fill, target, 0.22 + 0.78 * teal)
            self._draw_glow(painter, self._peak_stroke, target, 0.15 + 0.7 * teal)
            self._draw_glow(painter, self._reflection, target, 0.2 + 0.8 * orange)
        self._paint_molecules(painter, float(self.width()))
        painter.end()

    def _draw_glow(self, painter, image, target, opacity):
        if image.isNull() or opacity <= 0:
            return
        painter.setOpacity(opacity)
        painter.drawImage(target, image)
        painter.setOpacity(1.0)

    def _paint_molecules(self, painter, scale):
        painter.setPen(QtCore.Qt.NoPen)
        for molecule in _MOLECULES:
            wave = self._wave(molecule["phase"])
            color = QtGui.QColor(molecule["color"])
            color.setAlphaF(0.35 + 0.65 * wave)
            painter.setBrush(color)
            center_x = molecule["center"][0] * scale
            center_y = molecule["center"][1] * scale
            radius = molecule["radius"] * scale * (0.96 + 0.08 * wave)
            painter.drawEllipse(QtCore.QPointF(center_x, center_y), radius, radius)
