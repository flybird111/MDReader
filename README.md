# MDReader

MDReader is a local offline Markdown reader built with PySide6 and Qt WebEngine.

It lets you open a folder of Markdown files, browse them from a tree view, edit them in a desktop UI, render them live, inspect the document outline, search inside the current file, and run a global search across the whole folder.

## Features

- Open a local folder containing `.md` and `.markdown` files
- Create and delete Markdown files and folders inside the current root folder
- Rename files and folders directly inside the current root folder
- Edit Markdown files directly inside the app with a live preview
- Switch between `Preview`, split `Edit`, and `Edit Only` modes from the top toolbar
- Use a compact toolbar plus `File / Edit / View / Help` menus for most commands
- Save updates back to the original file with `Ctrl+S`
- Undo and redo edits with `Ctrl+Z` and `Ctrl+Y`
- Paste rich text from the web and convert it to Markdown automatically
- Choose `Paste as Plain Text` or `Paste as Formatted Text` from the editor right-click menu
- Use file tree context menus for file and folder actions such as open, create, rename, delete, and refresh
- Render Markdown with code highlighting and local file links
- Show the current document outline in a side panel
- Insert common Markdown structures such as headings, bold text, underline, colored text, inline code, code blocks, tables, and horizontal rules
- `Ctrl+F` to search inside the current document
- `Ctrl+Shift+F` to search across all Markdown files in the current folder
- `Ctrl++` and `Ctrl+-` to zoom editor and preview text
- Show document titles in the file tree instead of raw file names for leaf Markdown nodes
- Block external web navigation to keep the reader offline-first

## Requirements

- Python 3.10+
- Supported desktop platforms:
  - Windows
  - macOS Apple Silicon
  - Ubuntu Linux

## Platform Notes

- On macOS, standard shortcuts such as Open, Save, Undo, Redo, and Find follow the native `Command` key behavior through Qt.
- The app is designed to run natively on Apple Silicon when built with a native arm64 Python environment.
- Ubuntu support is provided through the same PySide6 and Qt WebEngine stack used on Windows and macOS.

## Install

Create and activate a virtual environment if you want an isolated setup, then install dependencies.

Windows / macOS / Ubuntu:

```bash
python -m pip install -r requirements.txt
```

## Run

Windows / macOS / Ubuntu:

```bash
python main.py
```

## Shortcuts

- `Ctrl+O`: Open a folder
- `Ctrl+S`: Save the current Markdown file
- `Ctrl+Z`: Undo
- `Ctrl+Y`: Redo
- `Ctrl+E`: Focus the editor
- `Ctrl+F`: Find in the current document
- `Ctrl+Shift+F`: Global search
- `Ctrl++`: Zoom in
- `Ctrl+-`: Zoom out
- `F3`: Next match in the current document
- `Shift+F3`: Previous match in the current document

## Build

The repository includes a PyInstaller spec file that works across supported desktop platforms.

```bash
pyinstaller MDReader.spec
```

Build outputs:

- Windows: `dist/MDReader.exe`
- macOS: `dist/MDReader.app`
- Ubuntu: `dist/MDReader`

For best results on macOS Apple Silicon, build on a native Apple Silicon Python environment so the generated app stays arm64.

## Project Structure

```text
main.py
MDReader.spec
requirements.txt
app/
  editor_panel.py
  main_window.py
  file_tree.py
  markdown_renderer.py
  outline_panel.py
  web_view.py
```

## Notes

- The app is designed for local Markdown reading and intentionally blocks external HTTP and HTTPS navigation.
- The editor works on Markdown source directly and updates the preview automatically as you type.
- Rich text pasted from sources such as ChatGPT is converted to Markdown before insertion whenever HTML content is available in the clipboard.
- The editor context menu includes both plain-text paste and formatted-text paste options.
- The UI and shortcut mappings are tuned to behave more naturally on Windows, macOS, and Ubuntu desktop environments.
- Underline and text color are inserted using inline HTML, which is supported by the built-in renderer.
- Global search scans Markdown files under the currently opened root folder.
- File tree titles are derived from the first Markdown heading when available; otherwise the file name is used.
