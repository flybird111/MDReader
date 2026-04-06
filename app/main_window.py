from pathlib import Path
import shutil

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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

from app.editor_panel import MarkdownEditorPanel
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
        self.current_file_encoding = "utf-8"
        self.loaded_file_text = ""
        self.current_view_mode = "preview"
        self._scroll_sync_guard = False
        self._last_split_sizes = [520, 620]
        self.renderer = MarkdownRenderer()
        self.preview_zoom_factor = 1.0

        self.preview_refresh_timer = QTimer(self)
        self.preview_refresh_timer.setInterval(180)
        self.preview_refresh_timer.setSingleShot(True)
        self.preview_refresh_timer.timeout.connect(self._render_editor_contents)

        self.setWindowTitle("MDReader - Local Offline Markdown Reader")
        self.resize(1560, 940)
        self.setMinimumSize(1180, 720)

        self._build_actions()
        self._build_toolbar()
        self._build_ui()
        self._apply_styles()
        self._set_view_mode("preview")

        welcome = self.renderer.render_welcome()
        self.viewer.set_markdown_html(welcome.html)
        self.statusBar().showMessage("Choose a local folder to start reading.")

    def _build_actions(self) -> None:
        self.open_folder_action = QAction("Open Folder", self)
        self.open_folder_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_folder_action.triggered.connect(self.open_folder)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_current_file)
        self.save_action.setEnabled(False)
        self.addAction(self.save_action)

        self.add_file_action = QAction("Add File", self)
        self.add_file_action.triggered.connect(self.add_markdown_file)
        self.add_file_action.setEnabled(False)
        self.addAction(self.add_file_action)

        self.add_folder_action = QAction("Add Folder", self)
        self.add_folder_action.triggered.connect(self.add_folder)
        self.add_folder_action.setEnabled(False)
        self.addAction(self.add_folder_action)

        self.delete_path_action = QAction("Delete", self)
        self.delete_path_action.triggered.connect(self.delete_selected_path)
        self.delete_path_action.setEnabled(False)
        self.addAction(self.delete_path_action)

        self.rename_path_action = QAction("Rename", self)
        self.rename_path_action.setShortcut(QKeySequence("F2"))
        self.rename_path_action.triggered.connect(self.rename_selected_path)
        self.rename_path_action.setEnabled(False)
        self.addAction(self.rename_path_action)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo_edit)
        self.undo_action.setEnabled(False)
        self.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self._redo_edit)
        self.redo_action.setEnabled(False)
        self.addAction(self.redo_action)

        self.preview_mode_action = QAction("Preview", self)
        self.preview_mode_action.setCheckable(True)
        self.preview_mode_action.triggered.connect(lambda checked: checked and self._set_view_mode("preview"))

        self.edit_mode_action = QAction("Edit", self)
        self.edit_mode_action.setCheckable(True)
        self.edit_mode_action.triggered.connect(lambda checked: checked and self._set_view_mode("edit"))

        self.edit_only_mode_action = QAction("Edit Only", self)
        self.edit_only_mode_action.setCheckable(True)
        self.edit_only_mode_action.triggered.connect(lambda checked: checked and self._set_view_mode("edit_only"))

        self.view_mode_group = QActionGroup(self)
        self.view_mode_group.setExclusive(True)
        for action in (self.preview_mode_action, self.edit_mode_action, self.edit_only_mode_action):
            self.view_mode_group.addAction(action)
            action.setEnabled(False)

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

        self.focus_editor_action = QAction("Focus Editor", self)
        self.focus_editor_action.setShortcut(QKeySequence("Ctrl+E"))
        self.focus_editor_action.triggered.connect(self.editor_panel_focus)
        self.addAction(self.focus_editor_action)

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl+=")])
        self.zoom_in_action.triggered.connect(self._zoom_in)
        self.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcuts([QKeySequence.ZoomOut, QKeySequence("Ctrl+-")])
        self.zoom_out_action.triggered.connect(self._zoom_out)
        self.addAction(self.zoom_out_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(toolbar.iconSize())
        toolbar.addAction(self.open_folder_action)
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.add_file_action)
        toolbar.addAction(self.add_folder_action)
        toolbar.addAction(self.rename_path_action)
        toolbar.addAction(self.delete_path_action)
        toolbar.addSeparator()
        toolbar.addAction(self.preview_mode_action)
        toolbar.addAction(self.edit_mode_action)
        toolbar.addAction(self.edit_only_mode_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.find_in_document_action)
        toolbar.addAction(self.find_globally_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _build_ui(self) -> None:
        self.file_tree = FileTreePanel(self)
        self.file_tree.file_selected.connect(self.open_markdown_file)

        self.outline_panel = OutlinePanel(self)
        self.outline_panel.heading_selected.connect(self._scroll_to_heading)

        self.search_results_panel = SearchResultsPanel(self)
        self.search_results_panel.file_selected.connect(self._open_global_search_result)

        self.editor_panel = MarkdownEditorPanel(self)
        self.editor_panel.content_changed.connect(self._handle_editor_content_changed)
        self.editor_panel.save_requested.connect(self.save_current_file)
        self.editor_panel.editor.verticalScrollBar().valueChanged.connect(self._sync_preview_to_editor_scroll)

        self.viewer = MarkdownWebView(self)
        self.viewer.markdown_link_requested.connect(self._handle_markdown_link)
        self.viewer.status_message.connect(self.statusBar().showMessage)
        self.viewer.installEventFilter(self)
        if self.viewer.focusProxy() is not None:
            self.viewer.focusProxy().installEventFilter(self)

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

        self.editor_preview_splitter = QSplitter(Qt.Horizontal, self)
        self.editor_preview_splitter.setChildrenCollapsible(False)
        self.editor_preview_splitter.addWidget(self.editor_panel)
        self.editor_preview_splitter.addWidget(self.viewer)
        self.editor_preview_splitter.setStretchFactor(0, 5)
        self.editor_preview_splitter.setStretchFactor(1, 6)
        self.editor_preview_splitter.setSizes([520, 620])

        center_panel = QWidget(self)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)
        center_layout.addWidget(self.document_label)
        center_layout.addWidget(self.search_bar)
        center_layout.addWidget(self.editor_preview_splitter, 1)

        self.right_tabs = QTabWidget(self)
        self.right_tabs.addTab(self.outline_panel, "Outline")
        self.right_tabs.addTab(self.search_results_panel, "Search Results")

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.file_tree)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.right_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([300, 980, 360])

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

            QToolButton:checked {
                background: #dff8f3;
                border-color: #14b8a6;
                color: #0f172a;
            }

            QPlainTextEdit {
                background: white;
                border: 1px solid #d8e1ec;
                border-radius: 14px;
                padding: 12px;
                color: #0f172a;
                selection-background-color: #99f6e4;
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
        if not self._maybe_save_changes():
            return

        folder = QFileDialog.getExistingDirectory(self, "Choose a Markdown Folder", str(Path.home()))
        if not folder:
            return

        self.file_tree.set_root_path(folder)
        self.search_results_panel.show_hint("Enter a keyword and press Enter to search all Markdown files in the current folder.")
        self.add_file_action.setEnabled(True)
        self.add_folder_action.setEnabled(True)
        self.rename_path_action.setEnabled(True)
        self.delete_path_action.setEnabled(True)
        self.statusBar().showMessage(f"Loaded folder: {folder}")

    def open_markdown_file(self, file_path: str) -> bool:
        resolved_path = str(Path(file_path).resolve())
        if resolved_path != self.current_file_path and not self._maybe_save_changes():
            if self.current_file_path:
                self.file_tree.select_file(self.current_file_path)
            return False

        try:
            text, encoding = MarkdownRenderer.read_text_file_with_encoding(resolved_path)
        except OSError as exc:
            QMessageBox.warning(self, "Read Error", f"Failed to open the file:\n{exc}")
            return False

        self.preview_refresh_timer.stop()
        self.current_file_path = resolved_path
        self.current_file_encoding = encoding
        self.loaded_file_text = text
        self.editor_panel.set_editor_enabled(True)
        self.editor_panel.load_text(text)
        self.save_action.setEnabled(True)
        self.undo_action.setEnabled(True)
        self.redo_action.setEnabled(True)
        self._set_view_mode_actions_enabled(True)
        self._set_view_mode("preview")
        self._render_editor_contents()
        self.statusBar().showMessage(f"Opened: {resolved_path}")

        if self._search_mode() == "document" and self.search_bar.isVisible():
            query = self.search_input.text().strip()
            if query:
                QTimer.singleShot(0, lambda needle=query: self._run_document_search(needle))

        return True

    def save_current_file(self) -> bool:
        if not self.current_file_path:
            self.statusBar().showMessage("Open a Markdown file before saving.")
            return False

        text = self.editor_panel.text()
        previous_encoding = self.current_file_encoding

        try:
            self.current_file_encoding = MarkdownRenderer.write_text_file(
                self.current_file_path,
                text,
                self.current_file_encoding,
            )
        except OSError as exc:
            QMessageBox.warning(self, "Save Error", f"Failed to save the file:\n{exc}")
            return False

        self.loaded_file_text = text
        self.editor_panel.mark_saved()
        self._render_editor_contents()
        self.file_tree.refresh_file_title(self.current_file_path)
        self._set_view_mode("preview")

        if previous_encoding != self.current_file_encoding:
            self.statusBar().showMessage(
                f"Saved: {self.current_file_path} (switched to {self.current_file_encoding} encoding)."
            )
        else:
            self.statusBar().showMessage(f"Saved: {self.current_file_path}")
        return True

    def add_markdown_file(self) -> None:
        parent_dir = self._selected_directory_path()
        if not parent_dir:
            self.statusBar().showMessage("Open a folder before creating a Markdown file.")
            return

        file_name, accepted = QInputDialog.getText(
            self,
            "Add Markdown File",
            "File name:",
            text="new-note.md",
        )
        if not accepted or not file_name.strip():
            return

        normalized_name = file_name.strip()
        if Path(normalized_name).suffix.lower() not in ALLOWED_SUFFIXES:
            normalized_name += ".md"

        target_path = parent_dir / normalized_name
        if target_path.exists():
            QMessageBox.warning(self, "File Exists", f"The file already exists:\n{target_path}")
            return

        initial_title = MarkdownRenderer.extract_title("", target_path.stem.replace("-", " ").replace("_", " ").title())
        initial_content = f"# {initial_title}\n\n"

        try:
            MarkdownRenderer.write_text_file(target_path, initial_content, "utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Create File Error", f"Failed to create the file:\n{exc}")
            return

        self.file_tree.refresh_root()
        self.file_tree.select_file(str(target_path.resolve()))
        self.open_markdown_file(str(target_path.resolve()))
        self._set_view_mode("edit")
        self.statusBar().showMessage(f"Created file: {target_path}")

    def add_folder(self) -> None:
        parent_dir = self._selected_directory_path()
        if not parent_dir:
            self.statusBar().showMessage("Open a folder before creating a subfolder.")
            return

        folder_name, accepted = QInputDialog.getText(
            self,
            "Add Folder",
            "Folder name:",
            text="new-folder",
        )
        if not accepted or not folder_name.strip():
            return

        target_path = parent_dir / folder_name.strip()
        if target_path.exists():
            QMessageBox.warning(self, "Folder Exists", f"The folder already exists:\n{target_path}")
            return

        try:
            target_path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            QMessageBox.warning(self, "Create Folder Error", f"Failed to create the folder:\n{exc}")
            return

        self.file_tree.refresh_root()
        self.statusBar().showMessage(f"Created folder: {target_path}")

    def delete_selected_path(self) -> None:
        target = self._selected_tree_path()
        if not target:
            self.statusBar().showMessage("Select a file or folder to delete.")
            return

        resolved_target = target.resolve()
        root = Path(self.file_tree.root_path).resolve() if self.file_tree.root_path else None
        if root is None:
            return

        try:
            resolved_target.relative_to(root)
        except ValueError:
            QMessageBox.warning(self, "Delete Blocked", "Only items inside the current root folder can be deleted.")
            return

        if resolved_target == root:
            QMessageBox.warning(self, "Delete Blocked", "The current root folder cannot be deleted from inside the app.")
            return

        label = "folder" if resolved_target.is_dir() else "file"
        answer = QMessageBox.question(
            self,
            f"Delete {label.title()}",
            f"Delete this {label}?\n{resolved_target}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        if self.current_file_path:
            current_path = Path(self.current_file_path).resolve()
            if current_path == resolved_target or resolved_target in current_path.parents:
                if self._has_unsaved_changes():
                    discard = QMessageBox.question(
                        self,
                        "Discard Unsaved Changes",
                        "The selected item contains the currently open document. Delete it and discard unsaved changes?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if discard != QMessageBox.Yes:
                        return

        try:
            if resolved_target.is_dir():
                shutil.rmtree(resolved_target)
            else:
                resolved_target.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Delete Error", f"Failed to delete the selected item:\n{exc}")
            return

        if self.current_file_path:
            current_path = Path(self.current_file_path).resolve()
            if current_path == resolved_target or resolved_target in current_path.parents:
                self._clear_current_document_state()

        self.file_tree.refresh_root()
        self.file_tree.clear_selection()
        self.statusBar().showMessage(f"Deleted: {resolved_target}")

    def rename_selected_path(self) -> None:
        target = self._selected_tree_path()
        if not target:
            self.statusBar().showMessage("Select a file or folder to rename.")
            return

        resolved_target = target.resolve()
        root = Path(self.file_tree.root_path).resolve() if self.file_tree.root_path else None
        if root is None:
            return

        try:
            resolved_target.relative_to(root)
        except ValueError:
            QMessageBox.warning(self, "Rename Blocked", "Only items inside the current root folder can be renamed.")
            return

        new_name, accepted = QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            text=resolved_target.name,
        )
        if not accepted or not new_name.strip():
            return

        normalized_name = new_name.strip()
        if normalized_name == resolved_target.name:
            return

        destination = resolved_target.with_name(normalized_name)
        if destination.exists():
            QMessageBox.warning(self, "Rename Error", f"An item with this name already exists:\n{destination}")
            return

        try:
            resolved_target.rename(destination)
        except OSError as exc:
            QMessageBox.warning(self, "Rename Error", f"Failed to rename the selected item:\n{exc}")
            return

        self._remap_paths_after_rename(resolved_target, destination)

        if resolved_target == root:
            self.file_tree.set_root_path(str(destination))
        else:
            self.file_tree.refresh_root()

        if self.current_file_path:
            self._render_editor_contents()
            self.document_label.setToolTip(self.current_file_path)

        if destination.is_file():
            self.file_tree.select_file(str(destination.resolve()))
        elif self.current_file_path:
            self.file_tree.select_file(self.current_file_path)

        self.statusBar().showMessage(f"Renamed: {resolved_target.name} -> {destination.name}")

    def editor_panel_focus(self) -> None:
        if self.current_file_path:
            if self.current_view_mode == "preview":
                self._set_view_mode("edit")
            self.editor_panel.focus_editor()

    def _undo_edit(self) -> None:
        if not self.current_file_path:
            return
        self.editor_panel.editor.undo()

    def _redo_edit(self) -> None:
        if not self.current_file_path:
            return
        self.editor_panel.editor.redo()

    def _zoom_in(self) -> None:
        self._apply_zoom_step(1)

    def _zoom_out(self) -> None:
        self._apply_zoom_step(-1)

    def _apply_zoom_step(self, direction: int) -> None:
        step = 0.1 if direction > 0 else -0.1
        next_zoom = max(0.5, min(3.0, self.preview_zoom_factor + step))
        if abs(next_zoom - self.preview_zoom_factor) < 1e-9:
            return

        self.preview_zoom_factor = next_zoom
        self.viewer.setZoomFactor(self.preview_zoom_factor)
        if direction > 0:
            self.editor_panel.editor.zoomIn(1)
        else:
            self.editor_panel.editor.zoomOut(1)
        self.statusBar().showMessage(f"Zoom: {int(round(self.preview_zoom_factor * 100))}%")

    def _handle_markdown_link(self, file_path: str) -> None:
        resolved_path = str(Path(file_path).resolve())
        if not Path(resolved_path).exists():
            QMessageBox.warning(self, "File Not Found", f"Target file does not exist:\n{resolved_path}")
            return

        self.file_tree.select_file(resolved_path)
        self.open_markdown_file(resolved_path)

    def _handle_editor_content_changed(self) -> None:
        if not self.current_file_path:
            return

        self._update_document_label()
        self.preview_refresh_timer.start()

    def _render_editor_contents(self) -> None:
        if not self.current_file_path:
            return

        scroll_ratio = self.editor_panel.scroll_ratio()
        result = self.renderer.render_text(self.editor_panel.text(), Path(self.current_file_path).name)
        self.viewer.set_markdown_html(result.html, self.current_file_path, scroll_ratio=scroll_ratio)
        self.outline_panel.load_outline(result.outline)
        self._update_document_label(result.title)
        self.setWindowTitle(f"{result.title} - MDReader")

        if self._search_mode() == "document" and self.search_bar.isVisible():
            query = self.search_input.text().strip()
            if query:
                QTimer.singleShot(0, lambda needle=query: self._run_document_search(needle))

    def _update_document_label(self, title: str | None = None) -> None:
        if not self.current_file_path:
            self.document_label.setText("No file opened")
            self.document_label.setToolTip("")
            return

        actual_title = title or MarkdownRenderer.extract_title(self.editor_panel.text(), Path(self.current_file_path).name)
        suffix = " *" if self._has_unsaved_changes() else ""
        self.document_label.setText(f"{actual_title}{suffix}")
        self.document_label.setToolTip(self.current_file_path)

    def _scroll_to_heading(self, heading_id: str) -> None:
        self.viewer.scroll_to_heading(heading_id)

    def _set_view_mode_actions_enabled(self, enabled: bool) -> None:
        for action in (self.preview_mode_action, self.edit_mode_action, self.edit_only_mode_action):
            action.setEnabled(enabled)

    def _set_view_mode(self, mode: str) -> None:
        previous_mode = self.current_view_mode
        self.current_view_mode = mode

        if mode == "preview":
            if self.editor_panel.isVisible() and self.viewer.isVisible():
                self._last_split_sizes = self.editor_preview_splitter.sizes()
            self.editor_panel.hide()
            self.viewer.show()
        elif mode == "edit":
            self.editor_panel.show()
            self.viewer.show()
            self.editor_preview_splitter.setSizes(self._last_split_sizes)
        else:
            if self.editor_panel.isVisible() and self.viewer.isVisible():
                self._last_split_sizes = self.editor_preview_splitter.sizes()
            self.editor_panel.show()
            self.viewer.hide()

        action_map = {
            "preview": self.preview_mode_action,
            "edit": self.edit_mode_action,
            "edit_only": self.edit_only_mode_action,
        }
        for name, action in action_map.items():
            action.blockSignals(True)
            action.setChecked(name == mode)
            action.blockSignals(False)

        if mode in {"edit", "edit_only"} and self.current_file_path:
            self.editor_panel.focus_editor()
            if previous_mode == "preview":
                QTimer.singleShot(0, self._sync_editor_to_preview_scroll)

    def _sync_preview_to_editor_scroll(self) -> None:
        if self._scroll_sync_guard or self.current_view_mode != "edit":
            return
        self.viewer.set_scroll_ratio(self.editor_panel.scroll_ratio())

    def _sync_editor_to_preview_scroll(self) -> None:
        if self._scroll_sync_guard or self.current_view_mode != "edit":
            return
        self.viewer.get_scroll_ratio(self._apply_preview_scroll_ratio)

    def _apply_preview_scroll_ratio(self, ratio) -> None:
        if ratio is None or self.current_view_mode != "edit":
            return

        self._scroll_sync_guard = True
        try:
            self.editor_panel.set_scroll_ratio(float(ratio))
        finally:
            self._scroll_sync_guard = False

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
        opened = self.open_markdown_file(file_path)
        if not opened:
            return

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

    def _selected_tree_path(self) -> Path | None:
        selected_path = self.file_tree.current_path()
        if selected_path:
            return Path(selected_path)

        if self.current_file_path:
            return Path(self.current_file_path)

        if self.file_tree.root_path:
            return Path(self.file_tree.root_path)

        return None

    def _selected_directory_path(self) -> Path | None:
        target = self._selected_tree_path()
        if target is None:
            return None
        if target.is_dir():
            return target
        return target.parent

    def _remap_paths_after_rename(self, old_path: Path, new_path: Path) -> None:
        old_resolved = old_path.resolve()
        new_resolved = new_path.resolve()

        if self.current_file_path:
            current_resolved = Path(self.current_file_path).resolve()
            if current_resolved == old_resolved:
                self.current_file_path = str(new_resolved)
            else:
                try:
                    relative_path = current_resolved.relative_to(old_resolved)
                except ValueError:
                    pass
                else:
                    self.current_file_path = str((new_resolved / relative_path).resolve())

        if self.file_tree.root_path:
            root_resolved = Path(self.file_tree.root_path).resolve()
            if root_resolved == old_resolved:
                self.file_tree._root_path = str(new_resolved)

    def _clear_current_document_state(self) -> None:
        self.preview_refresh_timer.stop()
        self.current_file_path = ""
        self.current_file_encoding = "utf-8"
        self.loaded_file_text = ""
        self.editor_panel.load_text("")
        self.editor_panel.set_editor_enabled(False)
        self.save_action.setEnabled(False)
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.rename_path_action.setEnabled(bool(self.file_tree.root_path))
        self._set_view_mode_actions_enabled(False)
        self._set_view_mode("preview")
        welcome = self.renderer.render_welcome()
        self.viewer.set_markdown_html(welcome.html)
        self.outline_panel.load_outline([])
        self.document_label.setText("No file opened")
        self.document_label.setToolTip("")
        self.setWindowTitle("MDReader - Local Offline Markdown Reader")

    def _has_unsaved_changes(self) -> bool:
        if not self.current_file_path:
            return False
        return self.editor_panel.text() != self.loaded_file_text

    def _maybe_save_changes(self) -> bool:
        if not self.current_file_path or not self._has_unsaved_changes():
            return True

        file_name = Path(self.current_file_path).name
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            f'Save changes to "{file_name}" before continuing?',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if answer == QMessageBox.Save:
            return self.save_current_file()
        if answer == QMessageBox.Cancel:
            return False
        return True

    def eventFilter(self, watched, event) -> bool:
        viewer_proxy = self.viewer.focusProxy()
        if watched in {self.viewer, viewer_proxy} and event.type() == QEvent.Type.Wheel and self.current_view_mode == "edit":
            QTimer.singleShot(0, self._sync_editor_to_preview_scroll)
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:
        if self._maybe_save_changes():
            event.accept()
        else:
            event.ignore()
