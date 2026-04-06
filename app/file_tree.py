from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import QFileSystemModel, QLabel, QTreeView, QVBoxLayout, QWidget

from app.markdown_renderer import MarkdownRenderer


ALLOWED_SUFFIXES = {".md", ".markdown"}


class MarkdownFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title_cache: dict[str, str] = {}

    def clear_title_cache(self) -> None:
        self._title_cache.clear()

    def refresh_title(self, file_path: str) -> None:
        normalized_path = str(Path(file_path).resolve())
        self._title_cache[normalized_path] = self._resolve_title(normalized_path)
        index = self.index(normalized_path)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ToolTipRole])

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.column() != 0:
            return super().data(index, role)

        file_path = self.filePath(index)
        if role == Qt.ToolTipRole:
            if self.isDir(index):
                return file_path

            title = self._get_cached_title(file_path)
            if title != Path(file_path).name:
                return f"{title}\n{file_path}"
            return file_path

        if role == Qt.DisplayRole and not self.isDir(index):
            return self._get_cached_title(file_path)

        return super().data(index, role)

    def _get_cached_title(self, file_path: str) -> str:
        normalized_path = str(Path(file_path).resolve())
        if normalized_path not in self._title_cache:
            self._title_cache[normalized_path] = self._resolve_title(normalized_path)
        return self._title_cache[normalized_path]

    def _resolve_title(self, file_path: str) -> str:
        path = Path(file_path)
        try:
            text = MarkdownRenderer.read_text_file(path)
        except OSError:
            return path.name
        return MarkdownRenderer.extract_title(text, path.name)


class MarkdownFileFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        if source_model.isDir(index):
            return True

        suffix = Path(source_model.filePath(index)).suffix.lower()
        return suffix in ALLOWED_SUFFIXES


class FileTreePanel(QWidget):
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""

        self.title_label = QLabel("Files")
        self.title_label.setObjectName("panelTitle")

        self.model = MarkdownFileSystemModel(self)
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.model.setResolveSymlinks(False)

        self.proxy_model = MarkdownFileFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setRecursiveFilteringEnabled(False)

        self.tree = QTreeView()
        self.tree.setModel(self.proxy_model)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setWordWrap(False)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setTextElideMode(Qt.ElideMiddle)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree.clicked.connect(self._handle_clicked)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.tree, 1)

    @property
    def root_path(self) -> str:
        return self._root_path

    def set_root_path(self, folder_path: str) -> None:
        self._root_path = folder_path
        self.model.clear_title_cache()
        source_index = self.model.setRootPath(folder_path)
        proxy_index = self.proxy_model.mapFromSource(source_index)
        self.tree.setRootIndex(proxy_index)

        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)

        self.tree.expandToDepth(0)

    def refresh_file_title(self, file_path: str) -> None:
        self.model.refresh_title(file_path)

    def refresh_root(self) -> None:
        if self._root_path:
            self.set_root_path(self._root_path)

    def current_path(self) -> str:
        proxy_index = self.tree.currentIndex()
        if not proxy_index.isValid():
            return ""

        source_index = self.proxy_model.mapToSource(proxy_index)
        if not source_index.isValid():
            return ""

        return self.model.filePath(source_index)

    def clear_selection(self) -> None:
        self.tree.clearSelection()
        self.tree.setCurrentIndex(QModelIndex())

    def select_file(self, file_path: str) -> None:
        source_index = self.model.index(file_path)
        if not source_index.isValid():
            return

        proxy_index = self.proxy_model.mapFromSource(source_index)
        if not proxy_index.isValid():
            return

        parent_index = proxy_index.parent()
        while parent_index.isValid():
            self.tree.expand(parent_index)
            parent_index = parent_index.parent()

        self.tree.setCurrentIndex(proxy_index)
        self.tree.scrollTo(proxy_index)

    def _handle_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self.proxy_model.mapToSource(proxy_index)
        if not source_index.isValid():
            return

        if self.model.isDir(source_index):
            if self.tree.isExpanded(proxy_index):
                self.tree.collapse(proxy_index)
            else:
                self.tree.expand(proxy_index)
            return

        self.file_selected.emit(self.model.filePath(source_index))
