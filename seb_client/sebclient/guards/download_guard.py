"""Chặn tải file và chặn in.

Cả hai đều là đường rò rỉ dữ liệu đề thi ra ngoài:

* tải file → thí sinh lưu đề ra USB rồi chia sẻ cho nhau
* in → chụp máy in thành ảnh, hoặc in ra giấy mang về nhà

`QWebEngineProfile.downloadRequested` là nơi chặn tải file đúng nhất: huỷ ở
đó thì không có byte nào ghi xuống đĩa, mạnh hơn nhiền so với chặn sau khi tải.
"""

from __future__ import annotations

import logging

from ..constants import VIOLATION_COPY_PASTE_ATTEMPT
from .base import BaseGuard

logger = logging.getLogger(__name__)


class DownloadGuard(BaseGuard):
    name = "download"
    violation_type = VIOLATION_COPY_PASTE_ATTEMPT

    def install(self) -> None:
        profile = self._window._profile
        profile.downloadRequested.connect(self._on_download_requested)
        self._installed = True
        logger.info("download_guard: da chan tai file")

    def uninstall(self) -> None:
        profile = getattr(self._window, "_profile", None)
        if profile is not None and self._installed:
            try:
                profile.downloadRequested.disconnect(self._on_download_requested)
            except (RuntimeError, TypeError):
                pass
        self._installed = False

    def _on_download_requested(self, item) -> None:
        logger.warning("Chan tai file: %s", item.downloadFileName())
        # cancel() huỷ trước khi dữ liệu được ghi — đây là điểm mấu chốt.
        item.cancel()
        self.report(
            {"detected": "download", "filename": item.downloadFileName(), "mime": item.mimeType()}
        )