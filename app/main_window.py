from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.file_tree import ALLOWED_SUFFIXES, FileTreePanel
from app.markdown_renderer import MarkdownRenderer
from app.outline_panel import OutlinePanel
from app.web_view import MarkdownWebView


class SearchResultsPanel(QWidget):
    file_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.title_label = QLabel("Global Search")
        self.title_label.setObjectName("panelTitle")

        self.summary_label = QLabel("Enter a keyword and press Enter to search all Markdown files in the current folder.")
        self.summary_label.setWordWrap(True)

        self.list_widget = QListWidget(self)
        self.list_widget.setWordWrap(True)
        self.list_widget.itemActivated.connect(self._handle_item_activated)
        self.list_widget.itemClicked.connect(self._handle_item_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.list_widget, 1)

    def show_hint(self, message: str) -> None:
        self.summary_label.setText(message)
        self.list_widget.clear()

    def set_results(self, query: str, results: list[dict[str, str]]) -> None:
        self.list_widget.clear()
        self.summary_label.setText(f'"{query}" matched {len(results)} document(s).')

        for result in results:
            lines = [result["title"], result["relative_path"]]
            if result["snippet"]:
                lines.append(result["snippet"])

            item = QListWidgetItem("\n".join(lines))
            item.setData(Qt.UserRole, result["file_path"])
            item.setToolTip(result["file_path"])
            self.list_widget.addItem(item)

    def _handle_item_activated(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.file_selected.emit(file_path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_file_path = ""
        self.renderer = MarkdownRenderer()

        self.setWindowTitle("MDReader - Local Offline Markdown Reader")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)

        self._build_actions()
        self._build_toolbar()
        self._build_ui()
        self._apply_styles()

        welcome = self.renderer.render_welcome()
        self.viewer.set_markdown_html(welcome.html)
        self.statusBar().showMessage("Choose a local folder to start reading.")

    def _build_actions(self) -> None:
        self.open_folder_action = QAction("Open Folder", self)
        self.open_folder_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_folder_action.triggered.connect(self.open_folder)

        self.find_in_document_action = QAction("Find in Document", self)
        self.find_in_document_action.setShortcut(QKeySequence.Find)
        self.find_in_document_action.triggered.connect(lambda: self._activate_search("document"))
        self.addAction(self.find_in_document_action)

        self.find_globally_action = QAction("Global Search", self)
        self.find_globally_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.find_globally_action.triggered.connect(lambda: self._activate_search("global"))
        self.addAction(self.find_globally_action)

        self.find_next_action = QAction("Find Next", self)
        self.find_next_action.setShortcut(QKeySequence("F3"))
        self.find_next_action.triggered.connect(self._search_next_in_document)
        self.addAction(self.find_next_action)

        self.find_previous_action = QAction("Find Previous", self)
        self.find_previous_action.setShortcut(QKeySequence("Shift+F3"))
        self.find_previous_action.triggered.connect(self._search_previous_in_document)
        self.addAction(self.find_previous_action)

        self.windowed_action = QAction("Windowed", self)
        self.windowed_action.setShortcut(QKeySequence("Ctrl+1"))
        self.windowed_action.triggered.connect(self.showNormal)

        self.maximized_action = QAction("Maximized", self)
        self.maximized_action.setShortcut(QKeySequence("Ctrl+2"))
        self.maximized_action.triggered.connect(self.showMaximized)

        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.triggered.connect(self._toggle_fullscreen)

        self.exit_fullscreen_action = QAction("Exit Fullscreen", self)
        self.exit_fullscreen_action.setShortcut(QKeySequence("Esc"))
        self.exit_fullscreen_action.triggered.connect(self._exit_fullscreen)
        self.addAction(self.exit_fullscreen_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(toolbar.iconSize())
        toolbar.addAction(self.open_folder_action)
        toolbar.addSeparator()
        toolbar.addAction(self.find_in_document_action)
        toolbar.addAction(self.find_globally_action)
        toolbar.addSeparator()
        toolbar.addAction(self.windowed_action)
        toolbar.addAction(self.maximized_action)
        toolbar.addAction(self.fullscreen_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _build_ui(self) -> None:
        self.file_tree = FileTreePanel(self)
        self.file_tree.file_selected.connect(self.open_markdown_file)

        self.outline_panel = OutlinePanel(self)
        self.outline_panel.heading_selected.connect(self._scroll_to_heading)

        self.search_results_panel = SearchResultsPanel(self)
        self.search_results_panel.file_selected.connect(self._open_global_search_result)

        self.viewer = MarkdownWebView(self)
        self.viewer.markdown_link_requested.connect(self._handle_markdown_link)
        self.viewer.status_message.connect(self.statusBar().showMessage)

        self.document_label = QLabel("No file opened")
        self.document_label.setObjectName("documentTitle")

        self.search_mode_combo = QComboBox(self)
        self.search_mode_combo.addItem("Current Document", "document")
        self.search_mode_combo.addItem("Global Search", "global")
        self.search_mode_combo.currentIndexChanged.connect(self._update_search_mode_ui)

        self.search_input = QLineEdit(self)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._handle_search_text_changed)
        self.search_input.returnPressed.connect(self._handle_search_return_pressed)

        self.search_prev_button = QPushButton("Previous", self)
        self.search_prev_button.clicked.connect(self._search_previous_in_document)

        self.search_next_button = QPushButton("Next", self)
        self.search_next_button.clicked.connect(self._search_next_in_document)

        self.search_exec_button = QPushButton("Search", self)
        self.search_exec_button.clicked.connect(self._run_active_search)

        self.search_close_button = QPushButton("Close", self)
        self.search_close_button.clicked.connect(self._close_search_bar)

        self.search_bar = QWidget(self)
        self.search_bar.setObjectName("searchBar")
        self.search_bar.hide()
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(8)
        search_layout.addWidget(self.search_mode_combo)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_prev_button)
        search_layout.addWidget(self.search_next_button)
        search_layout.addWidget(self.search_exec_button)
        search_layout.addWidget(self.search_close_button)

        center_panel = QWidget(self)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)
        center_layout.addWidget(self.document_label)
        center_layout.addWidget(self.search_bar)
        center_layout.addWidget(self.viewer, 1)

        self.right_tabs = QTabWidget(self)
        self.right_tabs.addTab(self.outline_panel, "Outline")
        self.right_tabs.addTab(self.search_results_panel, "Search Results")

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.file_tree)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.right_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 7)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([300, 820, 360])

        self.setCentralWidget(splitter)
        self._update_search_mode_ui()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #eef3f8;
            }

            QToolBar {
                spacing: 8px;
                padding: 8px 12px;
                background: #f8fbff;
                border-bottom: 1px solid #d8e1ec;
            }

            QToolButton, QPushButton, QComboBox, QLineEdit {
                padding: 8px 12px;
                border: 1px solid #d8e1ec;
                border-radius: 10px;
                background: white;
            }

            QToolButton:hover, QPushButton:hover {
                background: #ecfeff;
                border-color: #99f6e4;
            }

            QSplitter::handle {
                background: #d8e1ec;
                width: 2px;
            }

            QTreeView, QTreeWidget, QWebEngineView, QListWidget, QTabWidget::pane {
                background: white;
                border: 1px solid #d8e1ec;
                border-radius: 14px;
            }

            QTreeView::item, QTreeWidget::item, QListWidget::item {
                padding: 6px 4px;
            }

            QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
                background: #dff8f3;
                color: #0f172a;
            }

            QLabel#panelTitle {
                color: #475569;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1px;
                text-transform: uppercase;
            }

            QLabel#documentTitle, QWidget#searchBar {
                padding: 12px 14px;
                border: 1px solid #d8e1ec;
                border-radius: 14px;
                background: white;
                color: #0f172a;
            }

            QLabel#documentTitle {
                font-size: 15px;
                font-weight: 600;
            }

            QTabBar::tab {
                padding: 8px 14px;
                margin-right: 4px;
                border: 1px solid #d8e1ec;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                background: #f8fbff;
            }

            QTabBar::tab:selected {
                background: white;
                color: #0f172a;
            }

            QStatusBar {
                background: #f8fbff;
                border-top: 1px solid #d8e1ec;
            }
            """
        )

    def open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a Markdown Folder", str(Path.home()))
        if not folder:
            return

        self.file_tree.set_root_path(folder)
        self.search_results_panel.show_hint("Enter a keyword and press Enter to search all Markdown files in the current folder.")
        self.statusBar().showMessage(f"Loaded folder: {folder}")

    def open_markdown_file(self, file_path: str) -> None:
        result = self.renderer.render_file(file_path)
        self.current_file_path = file_path
        self.document_label.setText(result.title)
        self.document_label.setToolTip(file_path)
        self.viewer.set_markdown_html(result.html, file_path)
        self.outline_panel.load_outline(result.outline)
        self.file_tree.refresh_file_title(file_path)
        self.statusBar().showMessage(f"Opened: {file_path}")

        if self._search_mode() == "document" and self.search_bar.isVisible():
            self._run_document_search(self.search_input.text().strip())

    def _handle_markdown_link(self, file_path: str) -> None:
        resolved_path = str(Path(file_path).resolve())
        if not Path(resolved_path).exists():
            QMessageBox.warning(self, "File Not Found", f"Target file does not exist:\n{resolved_path}")
            return

        self.file_tree.select_file(resolved_path)
        self.open_markdown_file(resolved_path)

    def _scroll_to_heading(self, heading_id: str) -> None:
        self.viewer.scroll_to_heading(heading_id)

    def _activate_search(self, mode: str) -> None:
        if mode == "document" and not self.current_file_path:
            self.statusBar().showMessage("Open a Markdown document before searching within the current file.")
            return

        if mode == "global" and not self.file_tree.root_path:
            self.statusBar().showMessage("Open a Markdown folder before running a global search.")
            return

        self.search_bar.show()
        index = self.search_mode_combo.findData(mode)
        if index >= 0:
            self.search_mode_combo.setCurrentIndex(index)

        self.search_input.setFocus()
        self.search_input.selectAll()

        if mode == "global":
            self.right_tabs.setCurrentWidget(self.search_results_panel)
        elif self.search_input.text().strip():
            self._run_document_search(self.search_input.text().strip())

    def _close_search_bar(self) -> None:
        self.search_bar.hide()
        self.viewer.clear_find()
        self.statusBar().showMessage("Search bar closed.")

    def _handle_search_text_changed(self, text: str) -> None:
        query = text.strip()
        if self._search_mode() != "document":
            if not query:
                self.search_results_panel.show_hint("Enter a keyword and press Enter to search all Markdown files in the current folder.")
            return

        if not query:
            self.viewer.clear_find()
            self.statusBar().showMessage("Cleared the current document search.")
            return

        self._run_document_search(query)

    def _handle_search_return_pressed(self) -> None:
        if self._search_mode() == "global":
            self._run_global_search()
            return

        self._search_next_in_document()

    def _run_active_search(self) -> None:
        if self._search_mode() == "global":
            self._run_global_search()
        else:
            self._run_document_search(self.search_input.text().strip())

    def _search_next_in_document(self) -> None:
        if self._search_mode() != "document":
            return
        self._run_document_search(self.search_input.text().strip())

    def _search_previous_in_document(self) -> None:
        if self._search_mode() != "document":
            return
        self._run_document_search(self.search_input.text().strip(), backward=True)

    def _run_document_search(self, query: str, *, backward: bool = False) -> None:
        if not self.current_file_path:
            return

        if not query:
            self.viewer.clear_find()
            return

        self.viewer.find_text(
            query,
            backward=backward,
            callback=lambda result, needle=query: self._update_document_search_status(needle, result),
        )

    def _update_document_search_status(self, query: str, result) -> None:
        match_count = result.numberOfMatches()
        if match_count == 0:
            self.statusBar().showMessage(f'No matches found for "{query}" in the current document.')
            return

        self.statusBar().showMessage(
            f'Found {match_count} match(es) for "{query}" in the current document. Current match: {result.activeMatch()}.'
        )

    def _run_global_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.search_results_panel.show_hint("Enter a keyword to run a global search.")
            self.right_tabs.setCurrentWidget(self.search_results_panel)
            return

        if not self.file_tree.root_path:
            self.statusBar().showMessage("Open a Markdown folder before running a global search.")
            return

        root = Path(self.file_tree.root_path)
        normalized_query = query.casefold()
        results: list[dict[str, str]] = []

        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue

            try:
                text = MarkdownRenderer.read_text_file(path)
            except OSError:
                continue

            title = MarkdownRenderer.extract_title(text, path.name)
            plain_text = MarkdownRenderer.extract_plain_text(text)
            title_match = normalized_query in title.casefold()
            content_index = plain_text.casefold().find(normalized_query)
            if not title_match and content_index < 0:
                continue

            results.append(
                {
                    "title": title,
                    "relative_path": str(path.relative_to(root)),
                    "file_path": str(path.resolve()),
                    "snippet": self._build_search_snippet(plain_text, content_index),
                    "title_rank": "0" if title_match else "1",
                }
            )

        results.sort(key=lambda item: (item["title_rank"], item["relative_path"].casefold()))
        for item in results:
            item.pop("title_rank", None)

        self.right_tabs.setCurrentWidget(self.search_results_panel)
        if results:
            self.search_results_panel.set_results(query, results)
            self.statusBar().showMessage(f"Global search complete: found {len(results)} matching document(s).")
        else:
            self.search_results_panel.show_hint(f'No Markdown documents contain "{query}".')
            self.statusBar().showMessage(f'Global search complete: no matches for "{query}".')

    def _open_global_search_result(self, file_path: str) -> None:
        self.file_tree.select_file(file_path)
        self.open_markdown_file(file_path)

        query = self.search_input.text().strip()
        if query:
            self._run_document_search(query)

    def _update_search_mode_ui(self) -> None:
        is_document_mode = self._search_mode() == "document"
        self.search_prev_button.setVisible(is_document_mode)
        self.search_next_button.setVisible(is_document_mode)
        self.search_exec_button.setText("Search" if not is_document_mode else "Find")
        self.search_input.setPlaceholderText(
            "Search within the current document. Press Enter or F3 for the next match."
            if is_document_mode
            else "Search across all Markdown documents in the current folder."
        )

    def _search_mode(self) -> str:
        return self.search_mode_combo.currentData() or "document"

    def _build_search_snippet(self, plain_text: str, match_index: int) -> str:
        if not plain_text:
            return ""

        if match_index < 0:
            snippet = plain_text[:120]
            return snippet + ("..." if len(plain_text) > 120 else "")

        start = max(match_index - 36, 0)
        end = min(match_index + 84, len(plain_text))
        snippet = plain_text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(plain_text):
            snippet += "..."
        return snippet

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
