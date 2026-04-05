from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class LocalOnlyRequestInterceptor(QWebEngineUrlRequestInterceptor):
    ALLOWED_SCHEMES = {"file", "data", "qrc", "about", ""}

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        scheme = info.requestUrl().scheme().lower()
        if scheme not in self.ALLOWED_SCHEMES:
            info.block(True)


class MarkdownWebPage(QWebEnginePage):
    markdown_link_requested = Signal(str)
    status_message = Signal(str)

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if nav_type != QWebEnginePage.NavigationTypeLinkClicked:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        scheme = url.scheme().lower()
        if scheme in {"http", "https"}:
            self.status_message.emit("External web links are blocked. This app only allows local offline access.")
            return False

        if url.isLocalFile():
            local_path = Path(url.toLocalFile())
            if local_path.suffix.lower() in {".md", ".markdown"}:
                self.markdown_link_requested.emit(str(local_path))
                return False

            QDesktopServices.openUrl(url)
            return False

        if scheme not in {"file", "data", "qrc", "about", ""}:
            self.status_message.emit("Blocked a non-local link request.")
            return False

        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class MarkdownWebView(QWebEngineView):
    markdown_link_requested = Signal(str)
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        profile = QWebEngineProfile("MDReaderProfile", self)
        profile.setHttpCacheType(QWebEngineProfile.NoCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)

        interceptor = LocalOnlyRequestInterceptor(profile)
        profile.setUrlRequestInterceptor(interceptor)

        page = MarkdownWebPage(profile, self)
        page.markdown_link_requested.connect(self.markdown_link_requested)
        page.status_message.connect(self.status_message)
        self.setPage(page)

        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)

    def set_markdown_html(self, html_content: str, file_path: str | None = None) -> None:
        base_url = QUrl()
        if file_path:
            base_folder = str(Path(file_path).resolve().parent)
            if not base_folder.endswith(("\\", "/")):
                base_folder += "/"
            base_url = QUrl.fromLocalFile(base_folder)
        self.setHtml(html_content, base_url)

    def scroll_to_heading(self, heading_id: str) -> None:
        script = f"window.scrollToHeading({heading_id!r});"
        self.page().runJavaScript(script)

    def find_text(
        self,
        text: str,
        *,
        backward: bool = False,
        callback=None,
    ) -> None:
        if not text:
            self.page().findText("")
            return

        flags = QWebEnginePage.FindFlag(0)
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward

        if callback is None:
            self.page().findText(text, flags)
            return

        self.page().findText(text, flags, callback)

    def clear_find(self) -> None:
        self.page().findText("")
