"""Compare the installed version with the latest GitHub release."""

import json
import urllib.error
import urllib.request

from Qt import QtCore, QtGui, QtWidgets

from fretGUI.version import __version__

_API_URL = "https://api.github.com/repos/intbio/FretBurstStudio/releases/latest"
_USER_AGENT = "FretBurstStudio-update-check"
_TIMEOUT_SECONDS = 5
_SETTINGS_KEY = "dismissedUpdateTag"


def parse_version(text):
    """Numeric parts of a version tag, ignoring a leading ``v``."""
    raw = str(text or "").strip()
    if raw[:1].lower() == "v":
        raw = raw[1:]
    parts = []
    for piece in raw.split("."):
        digits = []
        for char in piece:
            if not char.isdigit():
                break
            digits.append(char)
        if not digits:
            break
        parts.append(int("".join(digits)))
    return tuple(parts)


def is_newer(latest, current):
    """True when ``latest`` is a higher numeric version than ``current``."""
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if not latest_parts or not current_parts:
        return False
    width = max(len(latest_parts), len(current_parts))
    latest_parts = latest_parts + (0,) * (width - len(latest_parts))
    current_parts = current_parts + (0,) * (width - len(current_parts))
    return latest_parts > current_parts


def fetch_latest_release():
    """Latest stable GitHub release, or None when the body has no tag.

    Network and HTTP errors propagate so the caller can ignore them.
    """
    request = urllib.request.Request(
        _API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        return None
    name = payload.get("name") or tag
    url = payload.get("html_url") or ""
    return {
        "tag": tag.strip(),
        "name": str(name).strip() or tag.strip(),
        "url": str(url).strip(),
    }


def _settings():
    return QtCore.QSettings("FretBurstStudio", "FretBurstStudio")


def dismissed_tag():
    return str(_settings().value(_SETTINGS_KEY, "") or "")


def remember_dismissed_tag(tag):
    settings = _settings()
    settings.setValue(_SETTINGS_KEY, tag)
    settings.sync()


class UpdateCheckWorker(QtCore.QThread):
    """Fetch the latest release without blocking the GUI thread."""

    result_ready = QtCore.Signal(object)
    check_failed = QtCore.Signal()

    def run(self):
        try:
            release = fetch_latest_release()
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            self.check_failed.emit()
            return
        self.result_ready.emit(release)


def show_update_dialog(parent, release):
    """Offer the release page, and remember the tag when the user defers."""
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Information)
    box.setWindowTitle("Update available")
    box.setTextFormat(QtCore.Qt.PlainText)
    box.setText(
        f"FretBurstStudio {release['tag']} is available.\n"
        f"You have version {__version__}.\n\n"
        f"{release['name']}"
    )
    open_button = None
    if release.get("url"):
        open_button = box.addButton(
            "Open release page",
            QtWidgets.QMessageBox.AcceptRole,
        )
    later_button = box.addButton("Later", QtWidgets.QMessageBox.RejectRole)
    box.setDefaultButton(later_button)
    box.exec()
    clicked = box.clickedButton()
    if open_button is not None and clicked is open_button:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(release["url"]))
        return
    if clicked is later_button:
        remember_dismissed_tag(release["tag"])


class UpdateChecker(QtCore.QObject):
    """Background check owned by the main window."""

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self._window = parent_window
        self._worker = None
        self._report_result = False

    def start(self, manual=False):
        """Ask GitHub for the latest release.

        A check already in flight is kept. A manual request made while it
        runs still reports the result when that request finishes.
        """
        if manual:
            self._report_result = True
        if self._worker is not None:
            return
        worker = UpdateCheckWorker(self)
        worker.result_ready.connect(self._on_result)
        worker.check_failed.connect(self._on_failed)
        worker.finished.connect(self._clear_worker)
        self._worker = worker
        worker.start()

    def _take_manual(self):
        manual = self._report_result
        self._report_result = False
        return manual

    def shutdown(self):
        """Wait out a request so the thread is not destroyed while running."""
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(_TIMEOUT_SECONDS * 1000 + 1000)

    def _clear_worker(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_result(self, release):
        manual = self._take_manual()
        if release is None or not is_newer(release.get("tag"), __version__):
            if manual:
                QtWidgets.QMessageBox.information(
                    self._window,
                    "Check for updates",
                    f"You are up to date.\n\nInstalled version: {__version__}",
                )
            return
        if not manual and dismissed_tag() == release["tag"]:
            return
        if self._window is None:
            return
        show_update_dialog(self._window, release)

    def _on_failed(self):
        self._take_manual()
