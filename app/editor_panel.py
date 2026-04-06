import re

from PySide6.QtCore import QMimeData, QSignalBlocker, Signal
from PySide6.QtGui import QContextMenuEvent, QFontDatabase, QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication, QColorDialog, QGridLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class MarkdownTextEdit(QPlainTextEdit):
    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        if source.hasHtml() or source.hasText():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasHtml():
            markdown = self._html_to_markdown(source.html())
            if markdown:
                self.textCursor().insertText(markdown)
                return
        super().insertFromMimeData(source)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.createStandardContextMenu()
        clipboard = QApplication.clipboard()

        plain_action = menu.addAction("Paste as Plain Text")
        plain_action.triggered.connect(self.paste_plain_text)
        plain_action.setEnabled(bool(clipboard.mimeData().hasText()))

        formatted_action = menu.addAction("Paste as Formatted Text")
        formatted_action.triggered.connect(self.paste_formatted_text)
        formatted_action.setEnabled(bool(clipboard.mimeData().hasHtml() or clipboard.mimeData().hasText()))

        menu.exec(event.globalPos())

    def paste_plain_text(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.textCursor().insertText(text)

    def paste_formatted_text(self) -> None:
        mime_data = QApplication.clipboard().mimeData()
        if mime_data is None:
            return

        if mime_data.hasHtml():
            markdown = self._html_to_markdown(mime_data.html())
            if markdown:
                self.textCursor().insertText(markdown)
                return

        if mime_data.hasText():
            self.textCursor().insertText(mime_data.text())

    def _html_to_markdown(self, html: str) -> str:
        document = QTextDocument()
        document.setHtml(html)
        markdown = document.toMarkdown().replace("\r\n", "\n")

        # QTextDocument tends to emit very large blank gaps for some pasted rich text.
        markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)

        # Repair a known edge case where a closing code fence can collapse into a table row.
        markdown = markdown.replace("|```", "|\n\n```")

        return markdown.strip("\n")


class MarkdownEditorPanel(QWidget):
    content_changed = Signal()
    save_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.title_label = QLabel("Editor")
        self.title_label.setObjectName("panelTitle")

        self.editor = MarkdownTextEdit(self)
        self.editor.setPlaceholderText("Open a Markdown file to start editing.")
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setTabStopDistance(32)
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.editor.textChanged.connect(self.content_changed)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 0, 0, 0)
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(8)

        controls = [
            ("Save", self.save_requested.emit),
            ("H1", lambda: self.prefix_selected_lines("# ")),
            ("H2", lambda: self.prefix_selected_lines("## ")),
            ("H3", lambda: self.prefix_selected_lines("### ")),
            ("Bold", lambda: self.wrap_selection("**", "**", "bold text")),
            ("Underline", lambda: self.wrap_selection("<u>", "</u>", "underlined text")),
            ("Color", self.insert_colored_text),
            ("Inline Code", lambda: self.wrap_selection("`", "`", "code")),
            ("Code Block", self.insert_code_block),
            ("Table", self.insert_table),
            ("Divider", self.insert_divider),
        ]

        for index, (label, handler) in enumerate(controls):
            button = QPushButton(label, self)
            button.clicked.connect(handler)
            row = index // 4
            col = index % 4
            button_grid.addWidget(button, row, col)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addLayout(button_grid)
        layout.addWidget(self.editor, 1)

        self.set_editor_enabled(False)

    def set_editor_enabled(self, enabled: bool) -> None:
        self.editor.setEnabled(enabled)
        if enabled:
            self.editor.setPlaceholderText("Edit Markdown here. Rich text paste is converted to Markdown automatically.")
        else:
            self.editor.setPlaceholderText("Open a Markdown file to start editing.")

        for button in self.findChildren(QPushButton):
            button.setEnabled(enabled)

    def load_text(self, text: str) -> None:
        blocker = QSignalBlocker(self.editor)
        self.editor.setPlainText(text)
        del blocker
        self.editor.document().setModified(False)

    def text(self) -> str:
        return self.editor.toPlainText()

    def has_unsaved_changes(self) -> bool:
        return self.editor.document().isModified()

    def mark_saved(self) -> None:
        self.editor.document().setModified(False)

    def focus_editor(self) -> None:
        self.editor.setFocus()

    def scroll_ratio(self) -> float:
        bar = self.editor.verticalScrollBar()
        maximum = bar.maximum()
        if maximum <= 0:
            return 0.0
        return bar.value() / maximum

    def set_scroll_ratio(self, ratio: float) -> None:
        bar = self.editor.verticalScrollBar()
        maximum = bar.maximum()
        if maximum <= 0:
            bar.setValue(0)
            return
        safe_ratio = max(0.0, min(1.0, float(ratio)))
        bar.setValue(int(round(maximum * safe_ratio)))

    def wrap_selection(self, prefix: str, suffix: str, placeholder: str) -> None:
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        content = selected_text or placeholder
        cursor.insertText(f"{prefix}{content}{suffix}")

        if not selected_text:
            start = cursor.position() - len(suffix) - len(content)
            end = start + len(content)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)

    def prefix_selected_lines(self, prefix: str) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.LineUnderCursor)

        selected_text = cursor.selectedText().replace("\u2029", "\n")
        if not selected_text.strip():
            selected_text = "Heading"

        updated_lines = []
        for line in selected_text.split("\n"):
            if not line.strip():
                updated_lines.append(prefix.rstrip())
                continue

            leading_spaces = re.match(r"^\s*", line).group(0)
            stripped_line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line).strip()
            updated_lines.append(f"{leading_spaces}{prefix}{stripped_line}")
        cursor.insertText("\n".join(updated_lines))

    def insert_colored_text(self) -> None:
        color = QColorDialog.getColor(parent=self, title="Choose Text Color")
        if not color.isValid():
            return

        hex_color = color.name()
        self.wrap_selection(
            f'<span style="color: {hex_color};">',
            "</span>",
            "colored text",
        )

    def insert_code_block(self) -> None:
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n").strip() or "code"
        block = f"```text\n{selected_text}\n```"
        cursor.insertText(block)

    def insert_table(self) -> None:
        table = "\n| Column 1 | Column 2 |\n| --- | --- |\n| Value 1 | Value 2 |\n"
        self.editor.textCursor().insertText(table)

    def insert_divider(self) -> None:
        self.editor.textCursor().insertText("\n---\n")
