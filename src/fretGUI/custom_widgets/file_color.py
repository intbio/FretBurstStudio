"""File plot colors shared by loaders, lists, and Matplotlib.

Matplotlib writes alpha last (`#RRGGBBAA`). Qt reads eight hex digits as
`#AARRGGBB` and drops alpha from `QColor.name()`. Keep the Matplotlib form
in the data, and give Qt panes a solid preview so a graphics-proxy node
never gets a translucent stylesheet.
"""

import re

from Qt import QtGui


_HEX_COLOR = re.compile(
    r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$'
)


def qcolor_from_file_color(color):
    """Parse a stored file color without Qt's eight-digit channel swap."""
    if isinstance(color, QtGui.QColor):
        return QtGui.QColor(color) if color.isValid() else QtGui.QColor()
    if isinstance(color, (tuple, list)) and len(color) in (3, 4):
        qcolor = QtGui.QColor(*color)
        return qcolor if qcolor.isValid() else QtGui.QColor()

    text = str(color or '').strip()
    match = _HEX_COLOR.match(text)
    if match is None:
        qcolor = QtGui.QColor(text)
        return qcolor if qcolor.isValid() else QtGui.QColor()

    digits = match.group(1)
    if len(digits) == 3:
        digits = ''.join(channel * 2 for channel in digits)
    red = int(digits[0:2], 16)
    green = int(digits[2:4], 16)
    blue = int(digits[4:6], 16)
    alpha = 255 if len(digits) == 6 else int(digits[6:8], 16)
    return QtGui.QColor(red, green, blue, alpha)


def file_color_hex(color, keep_opaque_alpha=False):
    """Matplotlib hex. Opaque colors stay `#RRGGBB` unless alpha was set to 255."""
    qcolor = (
        color if isinstance(color, QtGui.QColor) else qcolor_from_file_color(color)
    )
    if not qcolor.isValid():
        return '#000000'
    rgb = '#{:02x}{:02x}{:02x}'.format(qcolor.red(), qcolor.green(), qcolor.blue())
    if qcolor.alpha() == 255 and not keep_opaque_alpha:
        return rgb
    return '{}{:02x}'.format(rgb, qcolor.alpha())


def has_explicit_alpha(color):
    """True when the stored color includes an alpha byte, even if it is 255."""
    match = _HEX_COLOR.match(str(color or '').strip())
    return match is not None and len(match.group(1)) == 8


def explicit_file_alpha(color):
    """Alpha chosen for this color, or None when the color does not set one.

    Six-digit colors are the default cycle and leave each plot's own alpha
    alone. Eight-digit colors, including `#RRGGBBff`, are an explicit choice.
    """
    if has_explicit_alpha(color):
        return int(str(color).strip()[-2:], 16) / 255.0
    qcolor = qcolor_from_file_color(color)
    if not qcolor.isValid() or qcolor.alpha() >= 255:
        return None
    return qcolor.alpha() / 255.0


def opaque_preview(color, base):
    """Composite `color` over an opaque base. The result has alpha 255."""
    src = qcolor_from_file_color(color)
    if not src.isValid():
        src = QtGui.QColor('#888888')
    dst = base if isinstance(base, QtGui.QColor) else qcolor_from_file_color(base)
    if not isinstance(dst, QtGui.QColor) or not dst.isValid():
        dst = QtGui.QColor('#ffffff')

    alpha = src.alpha()
    inverse = 255 - alpha

    def channel(src_value, dst_value):
        return (src_value * alpha + dst_value * inverse + 127) // 255

    return QtGui.QColor(
        channel(src.red(), dst.red()),
        channel(src.green(), dst.green()),
        channel(src.blue(), dst.blue()),
        255,
    )
