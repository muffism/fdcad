"""Find the user guide section for a tool (TR380 item 2, D1002).

Plain file reading, no Qt: the guide is a folder of Markdown pages. A heading
that names the tool wins, then a heading that contains its name, then a page
that names it in bold.
"""

from __future__ import annotations

from pathlib import Path


def _plain(text: str) -> str:
    return text.replace("*", "").replace("`", "").strip().lower()


def _pages(folder: Path) -> list[Path]:
    pages = sorted(folder.glob("*.md"))
    return [p for p in pages if p.name != "README.md"] + sorted(folder.glob("*/*.md"))


def find_topic(folder: Path, labels: list[str]) -> tuple[Path, str] | None:
    """The page and the heading (or bold label) for the first label found, or None."""
    pages = []
    for page in _pages(folder):
        try:
            pages.append((page, page.read_text(encoding="utf-8").splitlines()))
        except OSError:
            continue
    for label in labels:
        want = _plain(label)
        if not want:
            continue
        headings = [
            (page, line.lstrip("#").strip())
            for page, lines in pages
            for line in lines
            if line.startswith("#")
        ]
        for page, heading in headings:
            if _plain(heading) == want:
                return page, heading.replace("*", "")
        for page, heading in headings:
            if want in _plain(heading):
                return page, heading.replace("*", "")
        for page, lines in pages:
            if any(f"**{label}**".lower() in line.lower() for line in lines):
                return page, label
    return None
