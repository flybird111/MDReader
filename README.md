# MDReader

MDReader is a local offline Markdown reader built with PySide6 and Qt WebEngine.

It lets you open a folder of Markdown files, browse them from a tree view, edit them in a desktop UI, render them live, inspect the document outline, search inside the current file, and run a global search across the whole folder.

## Features

- Open a local folder containing `.md` and `.markdown` files
- Edit Markdown files directly inside the app with a live preview
- Switch between `Preview`, split `Edit`, and `Edit Only` modes from the top toolbar
- Save updates back to the original file with `Ctrl+S`
- Undo and redo edits with `Ctrl+Z` and `Ctrl+Y`
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
- Windows is the primary target environment in this project

## Install

Create and activate a virtual environment if you want an isolated setup, then install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
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

## Build an EXE

The repository already includes a PyInstaller spec file:

```powershell
pyinstaller MDReader.spec
```

The built executable will be generated under `dist\`.

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
- Underline and text color are inserted using inline HTML, which is supported by the built-in renderer.
- Global search scans Markdown files under the currently opened root folder.
- File tree titles are derived from the first Markdown heading when available; otherwise the file name is used.
