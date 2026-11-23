"""Part templates (TUTORIAL_REVIEW_SPEC_2 TR217, DECISIONS D833).

A template is a part file with no features of its own: the units, global
variables, part colour, print and mesh export settings, material and custom
properties of the part it was saved from, plus the name of the printer profile
in use. New Part can start from one. Templates live in a folder of FDCAD's data
folder, one ``.fdprt`` file each, named by the template.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

from fdcad.core.document.model import Document, new_document

SUFFIX = ".fdprt"
#: ``Document.extra`` key holding the printer profile name of a template.
PRINTER = "template_printer"
#: Part level appearance keys a template keeps; face, feature and body colours name
#: items of the old part, so they are left out.
_APPEARANCE = ("part_color",)


def template_from(doc: Document, printer: str = "") -> Document:
    """A new part holding ``doc``'s settings and none of its features."""
    out = new_document(doc.units)
    out.variables = copy.deepcopy(doc.variables)
    out.appearance = {k: copy.deepcopy(v) for k, v in doc.appearance.items() if k in _APPEARANCE}
    setup = {k: copy.deepcopy(v) for k, v in (doc.print_setup or {}).items() if k != "down_face"}
    out.print_setup = setup
    out.material = copy.deepcopy(doc.material)
    out.properties = copy.deepcopy(doc.properties)
    if printer:
        out.extra[PRINTER] = printer
    return out


def clean_name(name: str) -> str:
    """A template name usable as a file name. Raises ValueError with what to do."""
    clean = " ".join(re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name).split()).strip(" .")
    if not clean:
        raise ValueError("Enter a template name.")
    return clean


def save_template(doc: Document, folder: str | Path, name: str, printer: str = "") -> Path:
    """Save ``doc``'s settings as template ``name`` in ``folder``; returns the file."""
    from fdcad.core.io import fdef

    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    path = target / (clean_name(name) + SUFFIX)
    fdef.save(template_from(doc, printer), path)
    return path


def list_templates(folder: str | Path) -> list[tuple[str, Path]]:
    """The templates in ``folder`` as (name, file), sorted by name."""
    target = Path(folder)
    if not target.is_dir():
        return []
    found = [(p.stem, p) for p in target.iterdir() if p.suffix.lower() == SUFFIX]
    return sorted(found, key=lambda item: item[0].lower())


def new_from_template(path: str | Path) -> tuple[Document, str]:
    """A new part from a template file, and the printer profile name it names ("" for
    none). Raises FileFormatError or OSError like opening a part."""
    from fdcad.core.io import fdef

    loaded = fdef.load(path)
    doc = template_from(loaded)  # a template file with features still starts empty
    printer = loaded.extra.get(PRINTER)
    return doc, printer if isinstance(printer, str) else ""
