"""Tree folders and feature comments (TUTORIAL_REVIEW_SPEC TR23, DECISIONS D692).

Stored in the part file under ``tree`` (FDEF_SPEC 2 item 15)::

    {"folders": [{"name": "Holes", "features": ["f8", "f10"]}],
     "comments": {"f8": "Clearance for M6"}}

A folder lists top level features of the tree in order. They must be next to
each other: ``runs`` keeps, for each folder, the members from its first one up
to the first one that is no longer next to the others, so a folder never holds
features that are apart. Neither folders nor comments change the part, so they
are not part of the rebuild. Pure Python.
"""

from __future__ import annotations

import copy
from typing import Any

#: Longest folder name and comment.
MAX_NAME = 80
MAX_COMMENT = 2000


class TreeInfoError(ValueError):
    """Folder or comment data is damaged, or a change cannot be made."""


def checked(raw: Any) -> dict[str, Any]:
    """Validated tree data. Raises TreeInfoError when it is damaged."""
    if not isinstance(raw, dict):
        raise TreeInfoError("the tree folders and comments are not an object")
    out: dict[str, Any] = {}
    folder_list = raw.get("folders", [])
    if not isinstance(folder_list, list):
        raise TreeInfoError("the tree folders are not a list")
    clean = []
    for f in folder_list:
        if (
            not isinstance(f, dict)
            or not isinstance(f.get("name"), str)
            or not isinstance(f.get("features"), list)
            or not all(isinstance(i, str) for i in f["features"])
        ):
            raise TreeInfoError("a tree folder is damaged")
        # Keys a newer FDCAD wrote stay (FDEF_SPEC 14.4, audit D5 item 1, D726).
        clean.append({**f, "name": f["name"], "features": list(f["features"])})
    if clean:
        out["folders"] = clean
    comments = raw.get("comments", {})
    if not isinstance(comments, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in comments.items()
    ):
        raise TreeInfoError("the feature comments are damaged")
    if comments:
        out["comments"] = dict(comments)
    for key, value in raw.items():
        if key not in ("folders", "comments"):
            out[key] = value  # unknown keys are kept for a newer FDCAD
    return out


def usable_names(tree: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    """Checked tree data read from a file, each folder with a name ``name_problem``
    accepts: an empty, too long or repeated name (ignoring case) is changed, and each
    change adds a sentence to ``notes`` (audit D5 item 4, D2679)."""
    from fdcad.core.document.names import usable_name

    if not tree.get("folders"):
        return tree
    out = dict(tree)
    out["folders"] = []
    taken: set[str] = set()
    for f in tree["folders"]:
        old = str(f["name"])
        new = usable_name(old, taken, MAX_NAME, "Folder")
        taken.add(new.casefold())
        if not old.strip():
            notes.append(f'A tree folder with no name is now called "{new}".')
        elif new != old.strip():
            why = (
                f"names are at most {MAX_NAME} characters"
                if len(old.strip()) > MAX_NAME
                else "another folder has that name"
            )
            notes.append(f'The tree folder "{old.strip()}" is now called "{new}": {why}.')
        out["folders"].append({**f, "name": new} if new != old else f)
    return out


def folders(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """The folders, in order."""
    return list(tree.get("folders", []))


def comment(tree: dict[str, Any], fid: str) -> str:
    """The comment of a feature, or ""."""
    return str(tree.get("comments", {}).get(fid, ""))


def folder_of(tree: dict[str, Any], fid: str) -> str | None:
    """The name of the folder a feature is in, or None."""
    for f in folders(tree):
        if fid in f["features"]:
            return str(f["name"])
    return None


def runs(tree: dict[str, Any], top_level: list[str]) -> dict[str, str]:
    """Feature id to folder name, for the members that sit next to each other in the
    tree's top level rows (``top_level``, in order)."""
    pos = {fid: i for i, fid in enumerate(top_level)}
    out: dict[str, str] = {}
    for f in folders(tree):
        members = sorted((pos[m], m) for m in f["features"] if m in pos)
        last = None
        for i, m in members:
            if last is not None and i != last + 1:
                break
            out[m] = f["name"]
            last = i
    return out


def _with(tree: dict[str, Any], folder_list: list[dict[str, Any]]) -> dict[str, Any]:
    out = copy.deepcopy(tree)
    if folder_list:
        out["folders"] = folder_list
    else:
        out.pop("folders", None)
    return out


def name_problem(tree: dict[str, Any], name: str, keep: str | None = None) -> str:
    """Why a folder cannot have ``name``, or ""."""
    clean = name.strip()
    if not clean:
        return "Type a name for the folder."
    if len(clean) > MAX_NAME:
        return f"Use a name of {MAX_NAME} characters or less."
    taken = {str(f["name"]).casefold() for f in folders(tree) if f["name"] != keep}
    if clean.casefold() in taken:
        return f"A folder is already called {clean}. Choose another name."
    return ""


def next_name(tree: dict[str, Any]) -> str:
    """The next free name: Folder 1, Folder 2 and so on."""
    used = {str(f["name"]).casefold() for f in folders(tree)}
    n = 1
    while f"folder {n}" in used:
        n += 1
    return f"Folder {n}"


def add_folder(
    tree: dict[str, Any], name: str, members: list[str], top_level: list[str]
) -> dict[str, Any]:
    """A new folder holding ``members``, which must be next to each other in
    ``top_level``. They leave any folder they were in."""
    problem = name_problem(tree, name)
    if problem:
        raise TreeInfoError(problem)
    pos = sorted(top_level.index(m) for m in dict.fromkeys(members) if m in top_level)
    if not pos:
        raise TreeInfoError("Select the features to put in the folder.")
    if pos != list(range(pos[0], pos[-1] + 1)):
        raise TreeInfoError(
            "A folder can only hold features next to each other. Select neighbouring features."
        )
    ordered = [top_level[i] for i in pos]
    kept = [
        {"name": f["name"], "features": [m for m in f["features"] if m not in ordered]}
        for f in folders(tree)
    ]
    kept = [f for f in kept if f["features"]]
    return _with(tree, [*kept, {"name": name.strip(), "features": ordered}])


def rename_folder(tree: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """The folder ``old`` renamed."""
    problem = name_problem(tree, new, keep=old)
    if problem:
        raise TreeInfoError(problem)
    return _with(
        tree,
        [{**f, "name": new.strip()} if f["name"] == old else dict(f) for f in folders(tree)],
    )


def remove_folder(tree: dict[str, Any], name: str) -> dict[str, Any]:
    """Without the folder ``name``; its features stay where they are."""
    return _with(tree, [dict(f) for f in folders(tree) if f["name"] != name])


def set_comment(tree: dict[str, Any], fid: str, text: str) -> dict[str, Any]:
    """With the comment of ``fid`` set (an empty text removes it)."""
    clean = text.strip()
    if len(clean) > MAX_COMMENT:
        raise TreeInfoError(f"Use a comment of {MAX_COMMENT} characters or less.")
    out = copy.deepcopy(tree)
    comments = dict(out.get("comments", {}))
    if clean:
        comments[fid] = clean
    else:
        comments.pop(fid, None)
    if comments:
        out["comments"] = comments
    else:
        out.pop("comments", None)
    return out


def forget(tree: dict[str, Any], gone: set[str]) -> dict[str, Any]:
    """Without deleted features in folders and comments (empty folders go)."""
    kept = [
        {"name": f["name"], "features": [m for m in f["features"] if m not in gone]}
        for f in folders(tree)
    ]
    out = _with(tree, [f for f in kept if f["features"]])
    comments = {k: v for k, v in out.get("comments", {}).items() if k not in gone}
    if comments:
        out["comments"] = comments
    else:
        out.pop("comments", None)
    return out
