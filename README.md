# MDReader

MDReader is a local offline Markdown reader built with PySide6 and Qt WebEngine.

It lets you open a folder of Markdown files, browse them from a tree view, render them in a desktop UI, inspect the document outline, search inside the current file, and run a global search across the whole folder.

## Features

- Open a local folder containing `.md` and `.markdown` files
- Render Markdown with code highlighting and local file links
- Show the current document outline in a side panel
- `Ctrl+F` to search inside the current document
- `Ctrl+Shift+F` to search across all Markdown files in the current folder
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
- `Ctrl+F`: Find in the current document
- `Ctrl+Shift+F`: Global search
- `F3`: Next match in the current document
- `Shift+F3`: Previous match in the current document
- `F11`: Toggle fullscreen
- `Esc`: Exit fullscreen

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
  main_window.py
  file_tree.py
  markdown_renderer.py
  outline_panel.py
  web_view.py
```

## Notes

- The app is designed for local Markdown reading and intentionally blocks external HTTP and HTTPS navigation.
- Global search scans Markdown files under the currently opened root folder.
- File tree titles are derived from the first Markdown heading when available; otherwise the file name is used.
