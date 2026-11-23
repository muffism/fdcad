"""Final `.fdef` schema review (PLAN Phase 6, DECISIONS D430).

Every key the writer puts in a file is documented in FDEF_SPEC.md, and every key
name FDEF_SPEC.md documents exists in the code. The writer output of every sample
part and every schema fixture is walked, so a new key cannot ship undocumented.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest

from fdcad.core.io import fdef
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_SAMPLE_DIR
from fdcad.samples.make import SAMPLE_DIR

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "FDEF_SPEC.md"
SRC = ROOT / "src" / "fdcad"
FIXTURES = ROOT / "tests" / "fixtures"

FILES = sorted(
    [*SAMPLE_DIR.glob("*.fdprt"), *GRAPH_SAMPLE_DIR.glob("*.fdprt"), *FIXTURES.rglob("*.fdef")]
)

#: Objects whose keys are names chosen by the part (ids, face names, value paths),
#: not schema keys. Matched against the end of the key path.
MAP_PATHS = (
    ("appearance", "faces"),
    ("appearance", "features"),
    ("appearance", "bodies"),
    ("embedded",),
    ("overrides",),
    ("comments",),
    ("measure_to",),
)


@cache
def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


@cache
def documented() -> tuple[frozenset[str], tuple[re.Pattern[str], ...]]:
    """Key names FDEF_SPEC.md documents, and patterns for keys with placeholders."""
    text = spec_text()
    names: set[str] = set()
    patterns: list[re.Pattern[str]] = []
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.removeprefix("refs.")
        if re.fullmatch(r"[a-z][a-z0-9_]*", token):
            names.add(token)
        elif re.fullmatch(r"[a-z0-9_]*(<[a-z]>[a-z0-9_]*)+", token):
            patterns.append(re.compile(re.sub(r"<[a-z]>", r"\\d+", token)))
    # Keys in the JSON examples.
    names.update(re.findall(r'"([a-z][a-z0-9_]*)"\s*:', text))
    # Ranges written as `length2` to `length8`.
    for stem, lo, hi in re.findall(r"`([a-z_]+)(\d+)` to `\1(\d+)`", text):
        names.update(f"{stem}{i}" for i in range(int(lo), int(hi) + 1))
    return frozenset(names), tuple(patterns)


def is_documented(key: str) -> bool:
    names, patterns = documented()
    return key in names or any(p.fullmatch(key) for p in patterns)


def _keys(value: object, path: tuple[str, ...] = ()) -> Iterator[tuple[str, tuple[str, ...]]]:
    if isinstance(value, dict):
        is_map = any(path[-len(m) :] == m for m in MAP_PATHS)
        for k, v in value.items():
            if not is_map:
                yield k, path
            yield from _keys(v, (*path, "*" if is_map else k))
    elif isinstance(value, list):
        for v in value:
            yield from _keys(v, path)


#: Files that hold unknown keys on purpose (FDEF_SPEC 14 item 4).
UNKNOWN_KEY_FILES = {"unknown_keys"}
#: Samples whose feature types wait for their FDEF_SPEC section. Strict, so the test
#: reports when the section is added and the entry can go. Empty since D1079.
PENDING_SPEC: set[str] = set()


def _cases(skip: frozenset[str] = frozenset(UNKNOWN_KEY_FILES)) -> list[object]:
    return [
        pytest.param(p, marks=pytest.mark.xfail(strict=True, reason="owner adds the spec section"))
        if p.stem in PENDING_SPEC
        else p
        for p in FILES
        if p.stem not in skip
    ]


@pytest.mark.parametrize("path", _cases(), ids=lambda p: p.stem)
def test_every_written_key_is_in_the_spec(path: Path) -> None:
    written = json.loads(fdef.dumps(fdef.load(path)))
    missing = sorted({f"{'.'.join(p)}.{k}" for k, p in _keys(written) if not is_documented(k)})
    assert missing == [], "add these keys to FDEF_SPEC.md"


@cache
def code_strings() -> tuple[frozenset[str], tuple[str, ...]]:
    """String constants in the source, and the literal parts of f strings."""
    consts: set[str] = set()
    parts: set[str] = set()
    for p in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.JoinedStr):
                parts.update(v.value for v in node.values if isinstance(v, ast.Constant))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                consts.add(node.value)
    return frozenset(consts), tuple(sorted(parts))


def _code_has(token: str) -> bool:
    consts, parts = code_strings()
    if "<" not in token:
        return token in consts
    # `radius_<k>` is written with an f string such as f"radius_{k}".
    stem = token.split("<", 1)[0]
    return any(p.startswith(stem) or p.endswith(stem) for p in parts) or stem in consts


#: Names the spec mentions in backticks that are not file keys or values.
NOT_KEYS = {
    "migrate_1_to_2",  # a function name (section 15), tested below
    "b1",  # example embedded block ids (section 11); ids are made as f"b{n}"
    "b2",
    "j",  # a placeholder in prose
    "null",  # the JSON value
    "offset_face",  # section 5.3.11 says there is no such type
}

#: Keys the code builds with f strings whose literal parts do not match the stem.
BUILT_KEYS = {
    "length8": 'f"length{k}" (sheet metal edge flange)',
    "start_direction": 'f"{end}_direction" (loft)',
    "end_direction": 'f"{end}_direction" (loft)',
}


def test_every_spec_key_exists_in_code() -> None:
    tokens = set(re.findall(r"`([^`\n]+)`", spec_text()))
    keys = {t.removeprefix("refs.") for t in tokens}
    keys = {t for t in keys if re.fullmatch(r"[a-z][a-z0-9_]*(<[a-z]>[a-z0-9_]*)*", t)}
    values = {t.strip('"') for t in tokens if re.fullmatch(r'"[a-z0-9_]+"', t)}
    missing = sorted(t for t in (keys | values) - NOT_KEYS - set(BUILT_KEYS) if not _code_has(t))
    assert missing == [], "the spec documents keys or values the code never uses"


def test_named_migration_exists() -> None:
    from fdcad.core.io.migrations import MIGRATIONS, migrate_1_to_2

    assert MIGRATIONS[1] is migrate_1_to_2


def test_built_keys_are_built_in_code() -> None:
    _, parts = code_strings()
    assert "length" in parts
    assert "_direction" in parts


#: Feature types whose spec heading names them in words, keyed to a heading word.
TITLE_TYPES = {
    "extrude": "Extrude parameters",
    "revolve": "Revolve parameters",
    "fillet": "Fillet parameters",
    "chamfer": "Chamfer parameters",
    "shell": "Shell parameters",
    "draft": "Draft parameters",
    "sweep": "Sweep parameters",
    "loft": "Loft parameters",
    "import_step": "Imported STEP body",
    "import_mesh": "Imported mesh",
    "split_for_print": "Split for printing",
    "hole": "Hole parameters",
    "cosmetic_thread": "Cosmetic thread parameters",
    "modeled_thread": "Modelled thread parameters",
    "mounting_boss": "Mounting boss parameters",
    "snap_hook": "Snap hook parameters",
    "snap_groove": "Snap hook groove parameters",
    "lip_groove": "Lip and groove parameters",
    "vent": "Vent parameters",
    "rib": "Rib parameters",
    "dome": "Dome parameters",
    "wrap": "Wrap parameters",
}


@cache
def type_sections() -> dict[str, str]:
    """Spec text of each feature type: every subsection of section 5 naming it."""
    text = spec_text()
    body = text[text.index("## 5. Features") : text.index("## 6. Sketches")]
    chunks = re.split(r"^#{3,4} ", body, flags=re.M)
    sections: dict[str, str] = {}
    for chunk in chunks:
        for t in set(re.findall(r"`([a-z_][a-z0-9_]*)`", chunk)):  # sketch3d has a digit
            sections[t] = sections.get(t, "") + chunk
    # Headings that name their type in words only.
    for t, title in TITLE_TYPES.items():
        sections[t] = sections.get(t, "") + next(c for c in chunks if title in c.split("\n")[0])
    # 5.3.3 Selected regions is shared by Extrude and Revolve.
    regions = next(c for c in chunks if c.startswith("5.3.3 Selected regions"))
    for t in ("extrude", "revolve"):
        sections[t] += regions
    sections["sketch"] = text[text.index("## 6. Sketches") : text.index("## 7. References")]
    sections["graph_body"] = text[text.index("## 12A.") : text.index("## 13.")]
    return sections


def _documented_in(key: str, section: str) -> bool:
    if f"`{key}`" in section or f"`refs.{key}`" in section or f'"{key}"' in section:
        return True
    for token in re.findall(r"`(?:refs\.)?([a-z0-9_]*<[a-z]>[a-z0-9_<>]*)`", section):
        if re.fullmatch(re.sub(r"<[a-z]>", r"\\d+", token), key):
            return True
    return any(
        stem == key.rstrip("0123456789") and int(lo) <= int(key[len(stem) :] or 0) <= int(hi)
        for stem, lo, hi in re.findall(r"`([a-z_]+)(\d+)` to `\1(\d+)`", section)
    )


@pytest.mark.parametrize("path", _cases(frozenset()), ids=lambda p: p.stem)
def test_feature_keys_are_in_their_type_section(path: Path) -> None:
    written = json.loads(fdef.dumps(fdef.load(path)))
    sections = type_sections()
    missing = set()
    for feature in written["features"]:
        ftype = feature["type"]
        if ftype in ("origin", "plane"):
            continue
        section = sections.get(ftype)
        assert section is not None, f"feature type {ftype} has no spec section"
        for group in ("params", "refs"):
            for key in feature[group]:
                if not _documented_in(key, section):
                    missing.add(f"{ftype}.{group}.{key}")
    assert sorted(missing) == [], "document these keys in the type's FDEF_SPEC section"


def test_every_parameter_of_every_feature_type_is_in_its_section() -> None:
    """D1079: the tests above walk the sample files, so a parameter no sample writes
    could ship without a word in the spec. Forty three feature types had such
    parameters, and sixty four had no section at all. Every registered type now has a
    section, and every parameter of its table is named in it."""
    from fdcad.core import features  # noqa: F401  (registers every type)
    from fdcad.core.features.base import REGISTRY

    sections = type_sections()
    missing = []
    for name in sorted(REGISTRY):
        if name in ("origin", "plane"):
            continue
        section = sections.get(name)
        if section is None:
            missing.append(f"{name}: no section")
            continue
        for spec in getattr(REGISTRY[name], "params", ()):
            if not _documented_in(spec.name, section):
                missing.append(f"{name}.{spec.name}")
    assert missing == [], "add these to FDEF_SPEC.md"


#: A reference the feature module reads: ``refs.get("x")``, ``refs["x"]`` or a helper
#: called as ``resolve_faces(feature, ctx, "x")``.
_REF_READ = re.compile(
    r'refs(?:\.get\(|\[)\s*"([a-z_0-9]+)"'
    r'|\b(?:resolve_\w+|\w+_of)\(\s*feature,\s*ctx,\s*"([a-z_0-9]+)"'
)


def test_every_choice_and_reference_of_every_feature_type_is_in_its_section() -> None:
    """D2631: D1079 named every parameter, but 36 types had choice values and 10 had
    references read by their code that their sections did not name. Every value of a
    choice parameter, and every reference its module reads, is now in its section."""
    import inspect

    from fdcad.core import features  # noqa: F401  (registers every type)
    from fdcad.core.features.base import REGISTRY

    sections = type_sections()
    missing = []
    for name in sorted(REGISTRY):
        if name in ("origin", "plane"):
            continue
        section = sections.get(name, "")
        for spec in getattr(REGISTRY[name], "params", ()):
            for choice in spec.choices:
                if f"`{choice}`" not in section and f'"{choice}"' not in section:
                    missing.append(f"{name}.{spec.name} = {choice}")
        source = inspect.getsource(inspect.getmodule(type(REGISTRY[name])))
        for ref in sorted({a or b for a, b in _REF_READ.findall(source)}):
            if not _documented_in(ref, section):
                missing.append(f"{name}.refs.{ref}")
    assert missing == [], "add these to FDEF_SPEC.md"
