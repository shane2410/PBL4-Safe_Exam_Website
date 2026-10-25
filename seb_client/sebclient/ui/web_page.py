"""QWebEnginePage đã gia cố.

`QWebEngineSettings.InspectElementEnabled` đã bị Qt 6.12 gỡ bỏ, nên không còn
cách "tắt DevTools bằng thuộc tính". Cách đúng là chặn ở tầng page: ghi đè
`triggerAction` để mọi action nguy hiểm của Chromium đều bị chặn trước khi tới
trình duyệt.

Đây là lớp phòng thủ thứ hai sau `keyboard_guard`: kể cả khi thí sinh gọi được
API nội bộ của trang, action vẫn bị chặn ở đây.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtWebEngineCore import QWebEnginePage

from ..constants import (
    VIOLATION_COPY_PASTE_ATTEMPT,
    VIOLATION_DEVTOOLS_DETECTED,
)

logger = logging.getLogger(__name__)

ActionReporter = Callable[[str, dict], None]

W = QWebEnginePage.WebAction

# action -> loại vi phạm sẽ báo
BLOCKED_ACTIONS: dict[QWebEnginePage.WebAction, str] = {
    W.InspectElement: VIOLATION_DEVTOOLS_DETECTED,
    W.ViewSource: VIOLATION_DEVTOOLS_DETECTED,
    W.SavePage: VIOLATION_COPY_PASTE_ATTEMPT,
    W.DownloadImageToDisk: VIOLATION_COPY_PASTE_ATTEMPT,
    W.DownloadLinkToDisk: VIOLATION_COPY_PASTE_ATTEMPT,
    W.DownloadMediaToDisk: VIOLATION_COPY_PASTE_ATTEMPT,
    W.CopyImageToClipboard: VIOLATION_COPY_PASTE_ATTEMPT,
    W.CopyLinkToClipboard: VIOLATION_COPY_PASTE_ATTEMPT,
    W.CopyMediaUrlToClipboard: VIOLATION_COPY_PASTE_ATTEMPT,
    W.Copy: VIOLATION_COPY_PASTE_ATTEMPT,
    W.Cut: VIOLATION_COPY_PASTE_ATTEMPT,
    W.Paste: VIOLATION_COPY_PASTE_ATTEMPT,
    W.OpenLinkInNewWindow: VIOLATION_DEVTOOLS_DETECTED,
    W.OpenLinkInNewBackgroundTab: VIOLATION_DEVTOOLS_DETECTED,
}


class GuardedWebEnginePage(QWebEnginePage):
    """Page chặn action nguy hiểm và báo vi phạm qua callback."""

    def __init__(self, profile, parent=None, reporter: ActionReporter | None = None):
        super().__init__(profile, parent)
        self._reporter = reporter

    def set_reporter(self, reporter: ActionReporter | None) -> None:
        self._reporter = reporter

    def triggerAction(self, action, checked=False):  # noqa: N802 - chữ ký bắt buộc
        violation_type = BLOCKED_ACTIONS.get(action)
        if violation_type is not None:
            logger.info("Chan web action %s (%s)", action.name, violation_type)
            if self._reporter:
                self._reporter(
                    violation_type,
                    {"detected": "web_action", "action": action.name},
                )
            return
        super().triggerAction(action, checked)