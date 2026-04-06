import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import markdown
from pygments.formatters import HtmlFormatter


SCRIPT_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed)[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
EVENT_HANDLER_RE = re.compile(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
JAVASCRIPT_URL_RE = re.compile(
    r"""(?P<attr>\b(?:href|src)\s*=\s*)(['"])\s*javascript:.*?\2""",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
ATX_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
SETEXT_HEADING_RE = re.compile(r"^\s*(.+?)\s*\n[=-]{2,}\s*$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")
MARKDOWN_DECORATION_RE = re.compile(r"[*_`~#>\-\[\]\(\)!]+")


@dataclass
class RenderResult:
    html: str
    outline: list[dict[str, Any]]
    title: str


class MarkdownRenderer:
    def __init__(self) -> None:
        self._formatter = HtmlFormatter(style="friendly")

    def render_welcome(self) -> RenderResult:
        content = """
        <section class="empty-state">
          <h1>Local Offline Markdown Reader</h1>
          <p>Click "Open Folder" in the top-left corner and choose a directory that contains <code>.md</code> or <code>.markdown</code> files.</p>
          <p>The left side shows the file tree, the center shows the rendered document, and the right side shows the outline of the current file.</p>
        </section>
        """
        return RenderResult(self._build_html("MDReader", content), [], "MDReader")

    def render_file(self, file_path: str) -> RenderResult:
        path = Path(file_path)

        try:
            text, _ = self.read_text_file_with_encoding(path)
        except OSError as exc:
            message = f"Failed to read the file: {html.escape(str(exc))}"
            return self._build_message_result(path.name, message)

        return self.render_text(text, path.name)

    def render_text(self, text: str, title_hint: str = "Untitled") -> RenderResult:
        if not text.strip():
            return self._build_message_result(title_hint, "This file is empty.")

        md = markdown.Markdown(
            extensions=["extra", "codehilite", "toc", "sane_lists"],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "pygments_style": "friendly",
                    "noclasses": False,
                },
                "toc": {
                    "permalink": False,
                },
            },
            output_format="html5",
        )

        body_html = md.convert(text)
        safe_body = self._sanitize_html(body_html)
        title = self.extract_title(text, title_hint)
        return RenderResult(
            html=self._build_html(title, safe_body),
            outline=md.toc_tokens,
            title=title,
        )

    @staticmethod
    def read_text_file(path: Path | str) -> str:
        return MarkdownRenderer.read_text_file_with_encoding(path)[0]

    @staticmethod
    def read_text_file_with_encoding(path: Path | str) -> tuple[str, str]:
        path = Path(path)
        for encoding in ("utf-8", "gbk"):
            try:
                return path.read_text(encoding=encoding), encoding
            except UnicodeDecodeError:
                continue

        try:
            return path.read_text(encoding="utf-8", errors="ignore"), "utf-8"
        except OSError:
            return path.read_text(encoding="gbk", errors="ignore"), "gbk"

    @staticmethod
    def write_text_file(path: Path | str, text: str, encoding: str = "utf-8") -> str:
        path = Path(path)
        try:
            path.write_text(text, encoding=encoding)
            return encoding
        except UnicodeEncodeError:
            path.write_text(text, encoding="utf-8")
            return "utf-8"

    @classmethod
    def extract_title(cls, text: str, fallback: str) -> str:
        for pattern in (ATX_HEADING_RE, SETEXT_HEADING_RE):
            match = pattern.search(text)
            if not match:
                continue

            title = cls._cleanup_markdown_text(match.group(1))
            if title:
                return title

        return fallback

    @classmethod
    def extract_plain_text(cls, text: str) -> str:
        content = MARKDOWN_LINK_RE.sub(r"\1", text)
        content = TAG_RE.sub(" ", content)
        content = re.sub(r"^\s{0,3}#{1,6}\s*", "", content, flags=re.MULTILINE)
        content = MARKDOWN_DECORATION_RE.sub(" ", content)
        return re.sub(r"\s+", " ", html.unescape(content)).strip()

    def _build_message_result(self, title: str, message: str) -> RenderResult:
        content = f"""
        <section class="empty-state">
          <h1>{html.escape(title)}</h1>
          <p>{message}</p>
        </section>
        """
        return RenderResult(self._build_html(title, content), [], title)

    def _sanitize_html(self, content: str) -> str:
        content = SCRIPT_TAG_RE.sub("", content)
        content = EVENT_HANDLER_RE.sub("", content)
        content = JAVASCRIPT_URL_RE.sub(r"\g<attr>\2#\2", content)
        return content

    def flatten_outline(self, outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        def walk(nodes: list[dict[str, Any]]) -> None:
            for node in nodes:
                items.append(
                    {
                        "level": node.get("level", 1),
                        "id": node.get("id", ""),
                        "name": self._strip_tags(node.get("name", "")),
                        "children": node.get("children", []),
                    }
                )
                walk(node.get("children", []))

        walk(outline)
        return items

    def _strip_tags(self, value: str) -> str:
        return html.unescape(TAG_RE.sub("", value or "")).strip()

    @staticmethod
    def _cleanup_markdown_text(value: str) -> str:
        value = MARKDOWN_LINK_RE.sub(r"\1", value or "")
        value = TAG_RE.sub("", value)
        value = MARKDOWN_DECORATION_RE.sub(" ", value)
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _build_html(self, title: str, body_html: str) -> str:
        css = self._formatter.get_style_defs(".codehilite")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #d8e1ec;
      --accent: #0f766e;
      --accent-soft: #e6fffb;
      --quote: #eff6ff;
      --code-bg: #f7fafc;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      padding: 28px;
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.08), transparent 28%),
        linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
      color: var(--text);
      font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "Ubuntu", "Cantarell", "Microsoft YaHei", sans-serif;
      line-height: 1.7;
    }}

    .page {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 36px;
      background: var(--panel);
      border: 1px solid rgba(216, 225, 236, 0.9);
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
    }}

    .empty-state {{
      padding: 48px 24px;
      text-align: center;
      color: var(--muted);
    }}

    h1, h2, h3, h4, h5, h6 {{
      margin: 1.4em 0 0.65em;
      color: #0f172a;
      line-height: 1.3;
      scroll-margin-top: 24px;
    }}

    h1 {{
      margin-top: 0;
      font-size: 2rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.4em;
    }}

    h2 {{
      font-size: 1.5rem;
      padding-bottom: 0.25em;
      border-bottom: 1px dashed var(--border);
    }}

    p, ul, ol, blockquote, pre, table {{
      margin: 0 0 1em;
    }}

    ul, ol {{
      padding-left: 1.6em;
    }}

    blockquote {{
      padding: 12px 16px;
      margin-left: 0;
      border-left: 4px solid var(--accent);
      background: var(--quote);
      color: #334155;
      border-radius: 10px;
    }}

    a {{
      color: var(--accent);
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
    }}

    code {{
      padding: 0.15em 0.35em;
      border-radius: 6px;
      background: var(--code-bg);
      font-family: "Cascadia Code", "SFMono-Regular", "Menlo", "Consolas", "Liberation Mono", monospace;
      font-size: 0.92em;
    }}

    pre {{
      overflow-x: auto;
      border-radius: 14px;
      border: 1px solid #e2e8f0;
    }}

    pre code {{
      padding: 0;
      background: transparent;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 12px;
      border: 1px solid #dbe4ee;
      display: block;
      overflow-x: auto;
    }}

    thead {{
      background: #eef6ff;
    }}

    th, td {{
      padding: 10px 12px;
      border: 1px solid #dbe4ee;
      text-align: left;
      vertical-align: top;
    }}

    img {{
      max-width: 100%;
      height: auto;
      display: block;
      margin: 18px auto;
      border-radius: 14px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
    }}

    hr {{
      border: 0;
      border-top: 1px solid var(--border);
      margin: 2em 0;
    }}

    {css}
  </style>
</head>
<body>
  <main class="page">
    {body_html}
  </main>
  <script>
    window.scrollToHeading = function (id) {{
      const target = document.getElementById(id);
      if (target) {{
        target.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }};

    document.addEventListener("click", function (event) {{
      const link = event.target.closest("a");
      if (!link) {{
        return;
      }}

      const href = link.getAttribute("href") || "";
      if (href.startsWith("#")) {{
        event.preventDefault();
        window.scrollToHeading(href.slice(1));
      }}
    }});
  </script>
</body>
</html>"""
