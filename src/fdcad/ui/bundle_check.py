"""Checks that a built app carries every data file it needs (packaging, PLAN Phase 0 and 1).

The release workflow starts the packaged app with ``FDCAD_BUNDLE_CHECK`` set to a
file path; the app writes what is missing there and quits. It is never set in
normal use. The same checks run in the test suite on the source checkout.
"""

from __future__ import annotations

from PySide6.QtGui import QImage, QImageReader

from fdcad.samples.location import sample_dir, sample_files
from fdcad.ui.icons import icon, icon_path, listed_names
from fdcad.ui.themes.style import image

#: The Phase 1 sample parts (PLAN section 9, Phase 1).
SAMPLES = ("bracket", "plate_with_holes", "turned_shaft", "generated_200")


def bundle_problems() -> list[str]:
    """What is missing from this installation. Empty when everything is there."""
    problems: list[str] = []
    try:
        names = listed_names()
    except OSError:
        return ["The icon list (fdcad/ui/icons/NAMES.md) is missing. Reinstall FDCAD."]
    missing = [n for n in names if not icon_path(n).is_file()]
    if missing:
        problems.append(
            f"Icon files are missing ({len(missing)}), for example {missing[0]}.svg. "
            "Reinstall FDCAD."
        )
    elif any(icon(n).isNull() for n in names):
        problems.append(
            "Some icons do not draw. The SVG support of Qt may be missing. Reinstall FDCAD."
        )
    formats = {bytes(f.data()).decode() for f in QImageReader.supportedImageFormats()}
    if "svg" not in formats:
        problems.append(
            "Qt cannot read SVG images (imageformats/qsvg plugin missing). Reinstall FDCAD."
        )
    elif QImage(image("check", "#000000")).isNull():
        problems.append("Theme images do not load. Reinstall FDCAD.")
    found = {p.stem for p in sample_files()}
    lost = [s for s in SAMPLES if s not in found]
    if lost:
        problems.append(f"Sample parts are missing: {', '.join(lost)}. Reinstall FDCAD.")
    graphs = sample_dir() / "graphs"
    if not any(graphs.glob("*.fdprt")):
        problems.append("The node editor samples (samples/graphs) are missing. Reinstall FDCAD.")
    return problems
