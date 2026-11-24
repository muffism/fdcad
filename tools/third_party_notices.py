"""Write FDCAD's third party notices and source offer from the recorded inventory (D2860).

The facts live in ``packaging/notices/*.toml``: one ``[[component]]`` per shipped
project, with its version, licence, copyright lines, the licence texts it needs
(files under ``packaging/licenses``) and the bundle files it covers. This script
turns them into ``THIRD_PARTY_NOTICES.txt`` and ``SOURCE_OFFER.md`` at the
repository root. No network is needed.

    uv run python tools/third_party_notices.py write
    uv run python tools/third_party_notices.py check
    uv run python tools/third_party_notices.py inventory dist/FDCAD
    uv run python tools/third_party_notices.py inventory dist/FDCAD --record \\
        packaging/notices/inventory-windows.txt
    uv run python tools/third_party_notices.py inventory dist/FDCAD.app --record \\
        packaging/notices/inventory-macos.txt
    uv run python tools/third_party_notices.py check-dist dist/FDCAD

``check`` fails when the written files are out of date. ``check-dist`` fails when a
binary or data folder in a build has no component that covers it.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICES_DIR = ROOT / "packaging" / "notices"
LICENSES_DIR = ROOT / "packaging" / "licenses"
NOTICES_FILE = "THIRD_PARTY_NOTICES.txt"
SOURCE_OFFER_FILE = "SOURCE_OFFER.md"
PLATFORMS = ("windows", "macos")
#: Files a build is made of that carry code: Windows, macOS and Linux style.
BINARY_SUFFIXES = (".dll", ".pyd", ".so", ".dylib", ".exe")
#: Folders a build puts in front of every path. They are left out of the patterns.
PREFIXES = ("_internal/", "Contents/Frameworks/", "Contents/Resources/", "Contents/MacOS/")
RULE = "-" * 78


@dataclass
class Component:
    """One shipped project, as recorded in ``packaging/notices``."""

    id: str
    name: str
    version: str
    license: str
    copyright: list[str]
    texts: list[str]
    files: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=lambda: list(PLATFORMS))
    part_of: str = ""
    version_note: str = ""
    homepage: str = ""
    source: list[str] = field(default_factory=list)
    copyleft: bool = False
    modified: str = ""
    choice: str = ""
    credit: str = ""
    notes: str = ""
    kind: str = ""

    @property
    def version_text(self) -> str:
        """The version with how it was found, when that is not plain."""
        return f"{self.version} ({self.version_note})" if self.version_note else self.version


@dataclass
class Notices:
    """Every component, in file order, and the offer settings."""

    components: list[Component]
    offer: dict[str, str]

    def by_id(self) -> dict[str, Component]:
        """Components by id."""
        return {c.id: c for c in self.components}

    def children(self, parent: str) -> list[Component]:
        """Components recorded as part of ``parent``."""
        return [c for c in self.components if c.part_of == parent]


def load(folder: Path = NOTICES_DIR) -> Notices:
    """Read every ``*.toml`` in ``folder``: ``components.toml`` first, then the rest by name."""
    files = sorted(folder.glob("*.toml"), key=lambda p: (p.name != "components.toml", p.name))
    components: list[Component] = []
    offer: dict[str, str] = {}
    for path in files:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        offer.update(data.get("offer", {}))
        components += [Component(**entry) for entry in data.get("component", [])]
    ids = [c.id for c in components]
    doubles = sorted({i for i in ids if ids.count(i) > 1})
    if doubles:
        raise ValueError(f"component ids used twice: {', '.join(doubles)}")
    known = set(ids)
    for c in components:
        if c.part_of and c.part_of not in known:
            raise ValueError(f"{c.id}: part_of names an unknown component '{c.part_of}'")
        for platform in c.platforms:
            if platform not in PLATFORMS:
                raise ValueError(f"{c.id}: unknown platform '{platform}'")
        for text in c.texts:
            if not (LICENSES_DIR / text).is_file():
                raise ValueError(f"{c.id}: licence text {text} is not in packaging/licenses")
    return Notices(components, offer)


# Inventory ------------------------------------------------------------------------------


def logical_path(relative: str) -> str:
    """A bundle path without the folder the build puts in front of it."""
    for prefix in PREFIXES:
        if relative.startswith(prefix):
            return relative[len(prefix) :]
    return relative


def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    # A macOS framework keeps its library as a file named like the framework.
    parts = path.parts
    return len(parts) >= 4 and parts[-4] == path.name + ".framework" and parts[-3] == "Versions"


def inventory(dist: Path) -> list[str]:
    """Every binary, zip archive and data folder of a build, as logical paths.

    ``dist`` is the folder build (``dist/FDCAD``) or the app (``dist/FDCAD.app``).
    A data folder is a folder with no binary anywhere below it; only the topmost
    such folders are listed, with a trailing slash.
    """
    items: set[str] = set()
    has_binary: set[Path] = set()
    for path in sorted(dist.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(dist)
        if _is_binary(rel):
            items.add(logical_path(rel.as_posix()))
            has_binary.update(rel.parents)
        elif rel.suffix.lower() == ".zip":
            items.add(logical_path(rel.as_posix()))
    for path in sorted(dist.rglob("*")):
        if path.is_symlink() or not path.is_dir():
            continue
        rel = path.relative_to(dist)
        if rel in has_binary or rel.as_posix() + "/" in PREFIXES:
            continue
        if rel.parent not in has_binary and rel.parent != Path("."):
            continue  # a folder inside a data folder
        if rel.as_posix() in ("Contents", "Contents/_CodeSignature"):
            continue
        items.add(logical_path(rel.as_posix() + "/"))
    return sorted(i for i in items if i and i != "/")


def file_version(path: Path) -> str:
    """The version a Windows file states in its version resource, or ``-``."""
    try:
        import pefile  # type: ignore[import-untyped]  # dev dependency, Windows builds only
    except ImportError:
        return "-"
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
        for info in getattr(pe, "FileInfo", None) or []:
            for entry in info:
                for table in getattr(entry, "StringTable", None) or []:
                    value = table.entries.get(b"ProductVersion") or table.entries.get(
                        b"FileVersion"
                    )
                    if value:
                        return str(value.decode(errors="replace")).strip()
    except Exception:
        return "-"
    return "-"


def record(dist: Path, out: Path, note: str) -> None:
    """Write the inventory of ``dist`` to ``out``, with each file's stated version."""
    by_logical: dict[str, Path] = {}
    for path in dist.rglob("*"):
        if path.is_file() and not path.is_symlink():
            by_logical[logical_path(path.relative_to(dist).as_posix())] = path
    lines = [
        "# The files and data folders of an FDCAD build (tools/third_party_notices.py).",
        f"# {note}",
        "# Each line: the path inside the build, then the version the file states (or -).",
    ]
    for item in inventory(dist):
        found = by_logical.get(item)
        lines.append(f"{item}\t{file_version(found) if found else '-'}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def read_inventory(path: Path) -> list[str]:
    """The paths of a recorded inventory file."""
    rows = path.read_text(encoding="utf-8").splitlines()
    return [r.split("\t")[0] for r in rows if r.strip() and not r.startswith("#")]


def covers(component: Component, item: str) -> bool:
    """Whether one of the component's file patterns matches ``item`` (case blind)."""
    return any(fnmatch.fnmatch(item.lower(), p.lower()) for p in component.files)


def unmatched(items: list[str], notices: Notices, platform: str) -> list[str]:
    """The items no component for ``platform`` covers."""
    usable = [c for c in notices.components if platform in c.platforms]
    return [i for i in items if not any(covers(c, i) for c in usable)]


def unused(items: list[str], notices: Notices, platform: str) -> list[str]:
    """Components for ``platform`` with file patterns that match nothing in ``items``."""
    return [
        c.id
        for c in notices.components
        if platform in c.platforms and c.files and not any(covers(c, i) for i in items)
    ]


# Rendering -------------------------------------------------------------------------------


def _read(text: str) -> str:
    body = (LICENSES_DIR / text).read_text(encoding="utf-8", errors="replace")
    return body.replace("\r\n", "\n").replace("\r", "\n").strip("\n") + "\n"


def _key(body: str) -> str:
    """The same text with other spacing or line breaks has the same key."""
    return hashlib.sha256(" ".join(body.split()).encode("utf-8")).hexdigest()


def _wrap(label: str, value: str, width: int = 78) -> list[str]:
    """``value`` as lines of at most ``width``, after ``label`` and then indented."""
    lines: list[str] = []
    line = label
    for word in value.split():
        fresh = line == label or line.isspace()
        if not fresh and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = " " * len(label) + word
        else:
            line = f"{line}{word}" if fresh else f"{line} {word}"
    lines.append(line.rstrip())
    return lines


def _ordered(notices: Notices) -> list[tuple[str, Component]]:
    """Components numbered as they appear: top level 1, 2 and their parts 1.1, 1.2."""
    rows: list[tuple[str, Component]] = []

    def walk(parent: str, prefix: str) -> None:
        for n, c in enumerate(notices.children(parent), start=1):
            number = f"{prefix}{n}"
            rows.append((number, c))
            walk(c.id, number + ".")

    tops = [c for c in notices.components if not c.part_of and c.kind != "self"]
    for n, c in enumerate(tops, start=1):
        rows.append((str(n), c))
        walk(c.id, f"{n}.")
    return rows


def platforms_text(c: Component) -> str:
    """The platforms a component ships on, in words."""
    names = {"windows": "Windows", "macos": "macOS"}
    return " and ".join(names[p] for p in c.platforms)


def render_notices(notices: Notices, gpl_text: str) -> str:
    """The text of ``THIRD_PARTY_NOTICES.txt``."""
    rows = _ordered(notices)
    use: dict[str, list[str]] = {}
    for _number, c in rows:
        for text in c.texts:
            use.setdefault(_key(_read(text)), []).append(c.id)
    gpl_key = _key(gpl_text)
    shared: dict[str, str] = {}  # key -> first file with that text
    for _number, c in rows:
        for text in c.texts:
            k = _key(_read(text))
            if k != gpl_key and len(set(use[k])) > 1:
                shared.setdefault(k, text)
    self_entry = next(c for c in notices.components if c.kind == "self")
    out = [
        "FDCAD THIRD PARTY NOTICES",
        "=========================",
        "",
        f"{self_entry.name} {self_entry.version}",
        *self_entry.copyright,
        *_wrap("", self_entry.notes),
        "",
        *_wrap(
            "",
            "The FDCAD installers and app bundles also contain the third party "
            "components below. Each one keeps its own licence. This file gives, for "
            "each component, its version, licence, copyright lines and the full licence "
            "text. A text that several components use is printed once, in part 3, and "
            "named where it is used. The GNU GPL version 3 is the LICENSE file beside "
            "this file. How to get the source code of the components under the GNU GPL "
            f"or LGPL is in {SOURCE_OFFER_FILE}, also beside this file.",
        ),
        "",
        "This file is written by tools/third_party_notices.py from packaging/notices.",
        "",
        RULE,
        "PART 1. REQUIRED CREDITS",
        RULE,
        "",
    ]
    credits = [c.credit for _number, c in rows if c.credit]
    for credit in dict.fromkeys(credits):  # each credit once, in order
        out += _wrap("- ", credit)
    out += ["", RULE, "PART 2. COMPONENTS", RULE, "", "Contents:", ""]
    for number, c in rows:
        indent = "  " * number.count(".")
        out.append(f"{indent}{number}. {c.name} {c.version}".rstrip())
    for number, c in rows:
        out += ["", RULE, f"{number}. {c.name}", RULE]
        out += _wrap("Version:    ", c.version_text)
        out += _wrap("Licence:    ", c.license)
        if c.choice:
            out += _wrap("Choice:     ", c.choice)
        for n, line in enumerate(c.copyright or ["None stated."]):
            out += _wrap("Copyright:  " if n == 0 else "            ", line)
        out += _wrap("Platforms:  ", platforms_text(c))
        if c.files:
            out += _wrap("Files:      ", ", ".join(c.files))
        if c.part_of:
            parent = notices.by_id()[c.part_of]
            out += _wrap("Part of:    ", parent.name)
        if c.homepage:
            out += _wrap("Home page:  ", c.homepage)
        for n, url in enumerate(c.source):
            out += _wrap("Source:     " if n == 0 else "            ", url)
        if c.modified:
            out += _wrap("Modified:   ", c.modified)
        if c.notes:
            out += _wrap("Notes:      ", c.notes)
        names = []
        for text in c.texts:
            k = _key(_read(text))
            if k == gpl_key:
                names.append("GNU GPL version 3: the LICENSE file beside this file")
            elif k in shared:
                names.append(f"{shared[k]} (part 3)")
            else:
                names.append(f"{text} (below)")
        if names:
            out += _wrap("Texts:      ", "; ".join(names))
        for text in c.texts:
            k = _key(_read(text))
            if k != gpl_key and k not in shared:
                out += ["", f"--- {text} ---", "", _read(text).rstrip("\n")]
    out += ["", RULE, "PART 3. SHARED LICENCE TEXTS", RULE]
    for k, text in shared.items():
        users = sorted(set(use[k]))
        out += ["", f"=== {text} ===", *_wrap("Used by: ", ", ".join(users)), ""]
        out.append(_read(text).rstrip("\n"))
    out.append("")
    return "\n".join(out)


def render_source_offer(notices: Notices) -> str:
    """The text of ``SOURCE_OFFER.md``."""
    self_entry = next(c for c in notices.components if c.kind == "self")
    o = notices.offer
    lines = [
        "# FDCAD source offer",
        "",
        "FDCAD is free software under the GNU General Public License, version 3 or later "
        "(GPL v3). Some of the components bundled with it are under the GNU GPL or the "
        "GNU Lesser General Public License (LGPL). Those licences give you the right to "
        "the source code. This file says where to get it.",
        "",
        "This file is written by `tools/third_party_notices.py` from `packaging/notices`.",
        "",
        "## 1. FDCAD's own source",
        "",
        o["fdcad_source"],
        "",
        "### Written offer",
        "",
        o["written_offer"],
        "",
        "## 2. The GPL and LGPL components",
        "",
        "FDCAD made no changes to any component below. Each is shipped as the party named "
        "built it from the project's release. Where that builder applied patches or its own "
        "build files, the entry says so, and those patches and build files are part of the "
        "source it names.",
        "",
    ]
    for number, c in _ordered(notices):
        if not c.copyleft:
            continue
        lines += [f"### {c.name} {c.version}", ""]
        lines.append(f"- Licence: {c.license}")
        if c.choice:
            lines.append(f"- Licence that applies: {c.choice}")
        lines.append(f"- Shipped on: {platforms_text(c)}")
        if c.files:
            lines.append("- Files: " + ", ".join(f"`{p}`" for p in c.files))
        for url in c.source:
            lines.append(f"- Source: {url}")
        lines.append(f"- Changes: {c.modified or 'None. FDCAD did not change it.'}")
        lines.append(f"- Notice: {NOTICES_FILE}, entry {number}")
        lines.append("")
    lines += [
        "## 3. Replacing the LGPL libraries",
        "",
        o["relinking"],
        "",
        "## 4. Where these files are",
        "",
        o["where"],
        "",
        f"FDCAD {self_entry.version}. {self_entry.copyright[0]}.",
        "",
    ]
    return "\n".join(lines)


def outputs(notices: Notices | None = None, root: Path = ROOT) -> dict[str, str]:
    """The two files this script writes, by name, as they should be now."""
    n = notices or load()
    gpl = (root / "LICENSE").read_text(encoding="utf-8")
    return {NOTICES_FILE: render_notices(n, gpl), SOURCE_OFFER_FILE: render_source_offer(n)}


def stale(root: Path = ROOT) -> list[str]:
    """The written files that differ from what the notices data gives."""
    return [
        name
        for name, body in outputs(root=root).items()
        if not (root / name).is_file() or (root / name).read_text(encoding="utf-8") != body
    ]


def _platform_of(dist: Path) -> str:
    return "macos" if dist.suffix == ".app" or (dist / "Contents").is_dir() else "windows"


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("write", help=f"write {NOTICES_FILE} and {SOURCE_OFFER_FILE}")
    sub.add_parser("check", help="fail when the written files are out of date")
    inv = sub.add_parser("inventory", help="list the binaries and data folders of a build")
    inv.add_argument("dist", type=Path)
    inv.add_argument("--record", type=Path, help="write the list to this file")
    inv.add_argument("--note", default="", help="a line saying which build was listed")
    chk = sub.add_parser("check-dist", help="fail when a build file has no notice entry")
    chk.add_argument("dist", type=Path)
    args = parser.parse_args(argv)

    if args.command == "write":
        for name, body in outputs().items():
            (ROOT / name).write_text(body, encoding="utf-8", newline="\n")
            print(f"wrote {name}")
        return 0
    if args.command == "check":
        old = stale()
        for name in old:
            print(f"{name} is out of date: run tools/third_party_notices.py write")
        return 1 if old else 0
    if args.command == "inventory":
        if args.record:
            record(args.dist, args.record, args.note or f"Listed from {args.dist.as_posix()}.")
            print(f"recorded {args.record}")
        else:
            print("\n".join(inventory(args.dist)))
        return 0
    platform = _platform_of(args.dist)
    missing = unmatched(inventory(args.dist), load(), platform)
    for item in missing:
        print(f"no notice entry covers {item}")
    print(f"{len(missing)} build files without a notice entry ({platform})")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
