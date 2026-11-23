"""User guide checks (PLAN Phase 6, CLAUDE.md sections 7 and 8, DECISIONS D433).

Every page is plain text without em or en dashes or protected product names,
every link points at a file that exists, every page is reachable from the
index, and every command in the app is named somewhere in the guide.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "user_guide"
PAGES = sorted(GUIDE.rglob("*.md"))
FORBIDDEN = (
    "SOLIDWORKS",
    "FeatureManager",
    "PropertyManager",
    "CommandManager",
    "ConfigurationManager",
    "Hole Wizard",
    "Instant3D",
    "SketchXpert",
    "DimXpert",
    "Toolbox",
    "eDrawings",
    "MySolidWorks",
    "Rhinoceros",
    "Rhino",
    "Grasshopper",
    "Gumball",
)
LINK = re.compile(r"\]\(([^)#\s]+)(#[^)]*)?\)")


def test_guide_has_pages() -> None:
    assert len(PAGES) >= 20


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(GUIDE)))
def test_page_style(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    assert chr(0x2014) not in text and chr(0x2013) not in text, "no em or en dashes"
    for word in FORBIDDEN:
        assert re.search(rf"(?i)\b{re.escape(word)}\b", text) is None, word
    assert text.startswith("# "), "each page starts with its title"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(GUIDE)))
def test_links_resolve(page: Path) -> None:
    for target, _ in LINK.findall(page.read_text(encoding="utf-8")):
        if "://" in target:
            continue
        assert (page.parent / target).resolve().exists(), target


def test_every_page_is_reachable_from_the_index() -> None:
    seen: set[Path] = set()
    todo = [GUIDE / "README.md"]
    while todo:
        page = todo.pop()
        if page in seen or not page.exists():
            continue
        seen.add(page)
        for target, _ in LINK.findall(page.read_text(encoding="utf-8")):
            if target.endswith(".md") and "://" not in target:
                todo.append((page.parent / target).resolve())
    assert sorted(set(PAGES) - seen) == []


def test_every_command_is_in_the_guide() -> None:
    from fdcad.ui.input.commands import BY_ID

    text = "\n".join(p.read_text(encoding="utf-8") for p in PAGES)
    missing = sorted(c.label for c in BY_ID.values() if c.label not in text)
    assert missing == []
