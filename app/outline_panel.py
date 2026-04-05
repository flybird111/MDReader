from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class OutlinePanel(QWidget):
    heading_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title_label = QLabel("Outline")
        self.title_label.setObjectName("panelTitle")

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setTextElideMode(Qt.ElideRight)
        self.tree.itemClicked.connect(self._handle_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.tree, 1)

        self.show_empty_state()

    def load_outline(self, outline: list[dict[str, Any]]) -> None:
        self.tree.clear()

        if not outline:
            self.show_empty_state()
            return

        self.tree.setUpdatesEnabled(False)
        for node in outline:
            self.tree.addTopLevelItem(self._create_item(node))
        self.tree.expandAll()
        self.tree.setUpdatesEnabled(True)

    def show_empty_state(self) -> None:
        self.tree.clear()
        item = QTreeWidgetItem(["No headings found in the current document"])
        item.setDisabled(True)
        self.tree.addTopLevelItem(item)

    def _create_item(self, node: dict[str, Any]) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.get("name", "Untitled heading")])
        item.setToolTip(0, node.get("name", ""))
        item.setData(0, Qt.UserRole, node.get("id", ""))
        for child in node.get("children", []):
            item.addChild(self._create_item(child))
        return item

    def _handle_item_clicked(self, item: QTreeWidgetItem) -> None:
        heading_id = item.data(0, Qt.UserRole)
        if heading_id:
            self.heading_selected.emit(heading_id)
