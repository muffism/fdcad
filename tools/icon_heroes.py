"""The hand drawn main tool icons of the Datum look (DECISIONS D1034).

    uv run python tools/icon_heroes.py

The main tools are drawn as small lit solids: light comes from the upper left, so
a left face gets a light tint and a right face a darker one, new material is tinted
in the accent colour and removed material in the cut colour. This script writes
those drawings over the files in ``src/fdcad/ui/icons``. It is kept so the drawings
and their rules stay in one readable place.
"""

from __future__ import annotations

from pathlib import Path

ICONS = Path(__file__).resolve().parents[1] / "src" / "fdcad" / "ui" / "icons"
HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">\n'
    '<g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round">\n'
)
TAIL = "</g>\n</svg>\n"
#: Face tints: lit left face, shaded right face, a plain top, a whole body.
LEFT = 'fill="currentColor" fill-opacity="0.08" stroke="none"'
RIGHT = 'fill="currentColor" fill-opacity="0.22" stroke="none"'
TOP = 'fill="currentColor" fill-opacity="0.03" stroke="none"'
BODY = 'fill="currentColor" fill-opacity="0.12" stroke="none"'
#: New material and removed material.
NEW = 'fill="#ACCENT" fill-opacity="0.3" stroke="none"'
GONE = 'fill="#CUT" fill-opacity="0.3" stroke="none"'
#: The shape from before the tool ran.
GHOST = 'stroke-opacity="0.5" stroke-dasharray="1.5 3"'

#: A block seen from above: its top face, the two faces below it and its edges.
BLOCK_TOP = "M3.75 12 L12 16 L20.25 12 L12 8 Z"
BLOCK_LEFT = "M3.75 12 L12 16 V22 L3.75 18 Z"
BLOCK_RIGHT = "M12 16 L20.25 12 V18 L12 22 Z"
BLOCK_LINES = "M3.75 12 V18 L12 22 L20.25 18 V12 M12 16 V22"
#: An upright cylinder: its whole side, and the shaded right half of the side.
CYLINDER = "M5.25 13 V19.5 A6 2 0 0 0 18.75 19.5 V13 A6 2 0 0 1 5.25 13 Z"
CYLINDER_SHADE = "M12 15 A6 2 0 0 0 18.75 13 V19.5 A6 2 0 0 1 12 21.5 Z"
CYLINDER_LINES = "M5.25 13 V19.5 A6 2 0 0 0 18.75 19.5 V13"
TURN_ARROW = "M4.5 8 A7.5 3 0 0 1 19.5 8 M19.8 5 L19.5 8 L16.6 7.2"

HEROES: dict[str, list[str]] = {
    "sketch.sketch": [
        f'<path d="M3.75 5.25 H17.25 V18.75 H3.75 Z" {BODY}/>',
        '<path d="M14 5.25 H3.75 V18.75 H17.25 V12"/>',
        '<path d="M10 15.5 L10.8 12.7 L18.5 5.25 L20.5 7 L12.8 14.7 Z" '
        'fill="#ACCENT" fill-opacity="0.3" stroke="#ACCENT"/>',
        '<path d="M17 6.5 L19 8.5" stroke="#ACCENT"/>',
    ],
    "feature.extrude": [
        f'<path d="{BLOCK_LEFT}" {LEFT}/>',
        f'<path d="{BLOCK_RIGHT}" {RIGHT}/>',
        f'<path d="{BLOCK_TOP}" {NEW}/>',
        f'<path d="{BLOCK_TOP}"/>',
        f'<path d="{BLOCK_LINES}"/>',
        '<path d="M12 12 V2.5 M9 5.5 L12 2.5 L15 5.5" stroke="#ACCENT"/>',
    ],
    "feature.extruded_cut": [
        f'<path d="{BLOCK_LEFT}" {LEFT}/>',
        f'<path d="{BLOCK_RIGHT}" {RIGHT}/>',
        f'<path d="{BLOCK_TOP}" {TOP}/>',
        f'<path d="{BLOCK_TOP}"/>',
        f'<path d="{BLOCK_LINES}"/>',
        f'<path d="M8 12 L12 14 L16 12 L12 10 Z" {GONE}/>',
        '<path d="M8 12 L12 14 L16 12 L12 10 Z" stroke="#CUT"/>',
        '<path d="M12 2.5 V9.5 M9 6.5 L12 9.5 L15 6.5" stroke="#CUT"/>',
    ],
    "feature.revolve": [
        f'<path d="{CYLINDER}" {LEFT}/>',
        f'<path d="{CYLINDER_SHADE}" {RIGHT}/>',
        f'<ellipse cx="12" cy="13" rx="6" ry="2" {NEW}/>',
        '<ellipse cx="12" cy="13" rx="6" ry="2"/>',
        f'<path d="{CYLINDER_LINES}"/>',
        '<path d="M12 2.5 V9" stroke-dasharray="1.5 3"/>',
        f'<path d="{TURN_ARROW}" stroke="#ACCENT"/>',
    ],
    "feature.revolved_cut": [
        f'<path d="{CYLINDER}" {LEFT}/>',
        f'<path d="{CYLINDER_SHADE}" {RIGHT}/>',
        f'<ellipse cx="12" cy="13" rx="6" ry="2" {TOP}/>',
        '<ellipse cx="12" cy="13" rx="6" ry="2"/>',
        f'<path d="{CYLINDER_LINES}"/>',
        '<ellipse cx="12" cy="13" rx="2.6" ry="0.9" fill="#CUT" fill-opacity="0.3" stroke="#CUT"/>',
        '<path d="M12 2.5 V9" stroke-dasharray="1.5 3"/>',
        f'<path d="{TURN_ARROW}" stroke="#CUT"/>',
    ],
    "feature.hole": [
        f'<path d="M2.25 10 L12 14 V19 L2.25 15 Z" {LEFT}/>',
        f'<path d="M12 14 L21.75 10 V15 L12 19 Z" {RIGHT}/>',
        f'<path d="M2.25 10 L12 6 L21.75 10 L12 14 Z" {TOP}/>',
        '<path d="M2.25 10 L12 6 L21.75 10 L12 14 Z"/>',
        '<path d="M2.25 10 V15 L12 19 L21.75 15 V10 M12 14 V19"/>',
        '<ellipse cx="12" cy="10" rx="4.2" ry="1.8" fill="#CUT" fill-opacity="0.2" stroke="#CUT"/>',
        '<ellipse cx="12" cy="10" rx="2" ry="0.9" fill="#CUT" fill-opacity="0.3" stroke="#CUT"/>',
    ],
    "feature.sweep": [
        f'<path d="M3 17 C3 6 12 2.25 20 2.25 L20 8 C13 7.5 9 10 9 17 Z" {BODY}/>',
        '<circle cx="6" cy="17" r="3" fill="#ACCENT" fill-opacity="0.3" stroke="#ACCENT"/>',
        '<path d="M6 17 C6 8 12 4 20 5" stroke-dasharray="1.5 3"/>',
        '<path d="M3 17 C3 6 12 2.25 20 2.25 M9 17 C9 10 13 7.5 20 8"/>',
    ],
    "feature.loft": [
        f'<path d="M3 17 L10 6 A5 2.5 0 0 0 20 6 L15 17 L9 20 Z" {BODY}/>',
        '<path d="M3 17 L9 20 L15 17 L9 14 Z" fill="#ACCENT" fill-opacity="0.3" stroke="#ACCENT"/>',
        '<ellipse cx="15" cy="6" rx="5" ry="2.5" fill="currentColor" fill-opacity="0.12"/>',
        '<path d="M3 17 L10 6 M15 17 L20 6 M9 20 L13 8.4"/>',
    ],
    "feature.fillet": [
        f'<path d="M3.75 20.25 V10 A6 6 0 0 1 10 3.75 H20.25 V20.25 Z" {BODY}/>',
        '<path d="M3.75 20.25 V10 A6 6 0 0 1 10 3.75 H20.25"/>',
        '<path d="M3.75 20.25 H20.25 V3.75" stroke-opacity="0.5"/>',
        f'<path d="M3.75 8.25 V3.75 H8.25" {GHOST}/>',
        '<path d="M3.75 10 A6 6 0 0 1 10 3.75" stroke="#ACCENT"/>',
        '<path d="M10 10 L6 6" stroke="#ACCENT"/>',
    ],
    "feature.chamfer": [
        f'<path d="M3.75 20.25 V10 L10 3.75 H20.25 V20.25 Z" {BODY}/>',
        '<path d="M3.75 20.25 V10 L10 3.75 H20.25"/>',
        '<path d="M3.75 20.25 H20.25 V3.75" stroke-opacity="0.5"/>',
        f'<path d="M3.75 8.25 V3.75 H8.25" {GHOST}/>',
        '<path d="M3.75 10 L10 3.75" stroke="#ACCENT"/>',
    ],
    "feature.rib": [
        '<path d="M2.25 8.25 L14.25 20.25 H2.25 Z" fill="#ACCENT" fill-opacity="0.3" '
        'stroke="none"/>',
        '<path d="M2.25 20.25 H21 M2.25 20.25 V3.75"/>',
        '<path d="M2.25 8.25 L14.25 20.25" stroke="#ACCENT"/>',
    ],
    "feature.dome": [
        '<path d="M4 15.75 C6 6 18 6 20 15.75 Z" fill="#ACCENT" fill-opacity="0.3" stroke="none"/>',
        f'<path d="M2.25 15.75 V20.25 H21.75 V15.75 Z" {BODY}/>',
        '<path d="M2.25 15.75 V20.25 H21.75 V15.75 Z"/>',
        '<path d="M4 15.75 C6 6 18 6 20 15.75" stroke="#ACCENT"/>',
    ],
    "feature.move_face": [
        f'<path d="M11.25 7 L17.25 9.5 V17.5 L10 20.5 L3.75 18 L11.25 15 Z" {BODY}/>',
        '<path d="M3.75 10 L11.25 7 L11.25 15 L3.75 18 Z" fill="#ACCENT" fill-opacity="0.3" '
        'stroke="#ACCENT"/>',
        '<path d="M11.25 7 L17.25 9.5 M11.25 15 L17.25 17.5 M3.75 18 L10 20.5 L17.25 17.5 V9.5"/>',
        '<path d="M14.25 3.75 H20.25 M18 2.25 L20.25 3.75 L18 5.25" stroke="#ACCENT"/>',
    ],
    "feature.offset_face": [
        f'<path d="M3.75 9 L12 13 V22 L3.75 18 Z" {LEFT}/>',
        f'<path d="M12 13 L20.25 9 V18 L12 22 Z" {RIGHT}/>',
        '<path d="M3.75 9 L12 5 L20.25 9 L12 13 Z" fill="currentColor" fill-opacity="0.03"/>',
        '<path d="M3.75 9 V18 L12 22 L20.25 18 V9 M12 13 V22"/>',
        '<path d="M4 9 L12 5 L20 9 L12 13 Z" transform="translate(0 -3)" fill="#ACCENT" '
        'fill-opacity="0.3" stroke="#ACCENT" stroke-dasharray="1.5 3"/>',
    ],
    "feature.delete_face": [
        f'<path d="M2.25 9 L12 13 V21 L2.25 17 Z" {LEFT}/>',
        f'<path d="M12 13 L21.75 9 V17 L12 21 Z" {GONE}/>',
        '<path d="M2.25 9 L12 5 L21.75 9 V17 L12 21 L2.25 17 Z M2.25 9 L12 13 L21.75 9 '
        'M12 13 V21"/>',
        '<path d="M14.5 10.5 L19 15 M19 10.5 L14.5 15" stroke="#CUT"/>',
    ],
    "feature.shaft_shape": [
        f'<path d="M5.25 6.75 A8.25 8.25 0 1 0 18.75 6.75 Z" {BODY}/>',
        '<path d="M5.25 6.75 A8.25 8.25 0 1 0 18.75 6.75"/>',
        '<path d="M5.25 6.75 H18.75" stroke="#CUT"/>',
        '<circle cx="12" cy="13.5" r="1.5" fill="currentColor" stroke="none"/>',
    ],
    "feature.ring_groove": [
        f'<path d="M6.75 3.75 H17.25 V20.25 H6.75 Z" {BODY}/>',
        '<path d="M6.75 3.75 V20.25 M17.25 3.75 V20.25"/>',
        '<path d="M6.75 9.75 H8.25 V14.25 H6.75 M17.25 9.75 H15.75 V14.25 H17.25" stroke="#CUT"/>',
    ],
    "feature.oring_groove": [
        f'<path d="M6.75 3.75 H17.25 V20.25 H6.75 Z" {BODY}/>',
        '<path d="M6.75 3.75 V20.25 M17.25 3.75 V20.25"/>',
        '<path d="M6.75 9.75 H9.75 V14.25 H6.75 M17.25 9.75 H14.25 V14.25 H17.25"/>',
        '<circle cx="8.25" cy="12" r="1.5" stroke="#CUT" fill="#CUT" fill-opacity="0.3"/>',
        '<circle cx="15.75" cy="12" r="1.5" stroke="#CUT" fill="#CUT" fill-opacity="0.3"/>',
    ],
    # Batch 2: the main tools of the other tabs and the tree's part icon.
    "tree.part": [
        f'<path d="M3.75 7.5 L12 12 V21 L3.75 16.5 Z" {LEFT}/>',
        f'<path d="M12 12 L20.25 7.5 V16.5 L12 21 Z" {RIGHT}/>',
        f'<path d="M12 3 L20.25 7.5 L12 12 L3.75 7.5 Z" {NEW}/>',
        '<path d="M12 3 L20.25 7.5 V16.5 L12 21 L3.75 16.5 V7.5 Z M3.75 7.5 L12 12 L20.25 7.5 '
        'M12 12 V21"/>',
    ],
    "tree.body": [
        f'<path d="M3.75 7.5 L12 12 V21 L3.75 16.5 Z" {LEFT}/>',
        f'<path d="M12 12 L20.25 7.5 V16.5 L12 21 Z" {RIGHT}/>',
        f'<path d="M12 3 L20.25 7.5 L12 12 L3.75 7.5 Z" {NEW}/>',
        '<path d="M12 3 L20.25 7.5 V16.5 L12 21 L3.75 16.5 V7.5 Z M3.75 7.5 L12 12 L20.25 7.5 '
        'M12 12 V21"/>',
    ],
    "feature.primitive": [
        f'<path d="M2.25 12.75 L6.75 15 V21 L2.25 18.75 Z" {LEFT}/>',
        f'<path d="M6.75 15 L11.25 12.75 V18.75 L6.75 21 Z" {RIGHT}/>',
        '<path d="M2.25 12.75 L6.75 10.5 L11.25 12.75 V18.75 L6.75 21 L2.25 18.75 Z '
        'M2.25 12.75 L6.75 15 L11.25 12.75 M6.75 15 V21"/>',
        '<circle cx="16.5" cy="7.5" r="4.5" fill="#ACCENT" fill-opacity="0.3" stroke="#ACCENT"/>',
        '<path d="M12 7.5 A4.5 1.6 0 0 0 21 7.5" stroke="#ACCENT" stroke-opacity="0.6"/>',
    ],
    "feature.import_step": [
        f'<path d="M8.25 11 L15.75 13.5 V20.5 L8.25 18 Z" {LEFT}/>',
        f'<path d="M15.75 13.5 L20.25 11 V18 L15.75 20.5 Z" {RIGHT}/>',
        '<path d="M8.25 11 L15.75 8.5 L20.25 11 V18 L15.75 20.5 L8.25 18 Z '
        'M8.25 11 L15.75 13.5 L20.25 11 M15.75 13.5 V20.5"/>',
        '<path d="M3 3 L9.75 9.75" stroke="#ACCENT"/>',
        '<path d="M6.5 9.75 H9.75 V6" stroke="#ACCENT"/>',
    ],
    "feature.base_flange": [
        f'<path d="M2.25 14 L11.25 17 V19 L2.25 16 Z" {LEFT}/>',
        f'<path d="M11.25 17 L21.75 13 V15 L11.25 19 Z" {RIGHT}/>',
        f'<path d="M2.25 14 L13 10 L21.75 13 L11.25 17 Z" {NEW}/>',
        '<path d="M2.25 14 L13 10 L21.75 13 L11.25 17 Z"/>',
        '<path d="M2.25 14 V16 L11.25 19 L21.75 15 V13 M11.25 17 V19"/>',
    ],
    "feature.edge_flange": [
        f'<path d="M3 16 L11 19 L20.25 15 L12.75 12 Z" {BODY}/>',
        '<path d="M3 16 L11 19 L20.25 15 L12.75 12 Z"/>',
        f'<path d="M12.75 12 V4 L20.25 7 V15 Z" {NEW}/>',
        '<path d="M12.75 12 V4 L20.25 7 V15" stroke="#ACCENT"/>',
        '<path d="M12.75 12 L20.25 15"/>',
    ],
    "feature.sketched_bend": [
        f'<path d="M2 17 L9 20 L14 14 L7 11 Z" {LEFT}/>',
        f'<path d="M14 14 L21 8 L14 5 L7 11 Z" {RIGHT}/>',
        '<path d="M2 17 L9 20 L14 14 L7 11 Z"/>',
        '<path d="M14 14 L21 8 L14 5 L7 11"/>',
        '<path d="M5 12.5 L16 9" stroke="#ACCENT" stroke-dasharray="1.5 3"/>',
    ],
    "feature.miter_flange": [
        f'<path d="M2.25 20.25 V9.75 H12.75 V20.25 Z" {LEFT}/>',
        f'<path d="M12.75 9.75 L21.75 4 V12 L12.75 20.25 Z" {RIGHT}/>',
        '<path d="M2.25 20.25 L12.75 20.25 L21.75 12"/>',
        '<path d="M2.25 20.25 L2.25 9.75 L12.75 9.75 L12.75 20.25"/>',
        '<path d="M12.75 9.75 L21.75 4 L21.75 12"/>',
        '<path d="M12.75 9.75 L12.75 20.25" stroke="#ACCENT"/>',
    ],
    "feature.form_tool": [
        f'<path d="M7 17.25 L9 11.25 H15 L17 17.25 Z" {NEW}/>',
        '<path d="M2 17.25 L7 17.25 L9 11.25 L15 11.25 L17 17.25 L22 17.25"/>',
        '<path d="M9 11.25 L15 11.25" stroke="#ACCENT"/>',
        '<path d="M2 20.25 L22 20.25"/>',
    ],
    "feature.stamp": [
        f'<path d="M6 9.75 L8 15.75 H16 L18 9.75 Z" {NEW}/>',
        '<path d="M2 9.75 L6 9.75 L8 15.75 L16 15.75 L18 9.75 L22 9.75"/>',
        '<path d="M8 15.75 L16 15.75" stroke="#ACCENT"/>',
        '<path d="M12 3 L12 8.25 M9.75 6 L12 8.25 L14.25 6"/>',
    ],
    "evaluate.geometry_check": [
        f'<path d="M2.25 8 L9.75 12 V19 L2.25 15 Z" {LEFT}/>',
        f'<path d="M9.75 12 L17.25 8 V15 L9.75 19 Z" {RIGHT}/>',
        '<path d="M2.25 8 L9.75 4 L17.25 8 L17.25 15 L9.75 19 L2.25 15 Z '
        'M2.25 8 L9.75 12 L17.25 8 M9.75 12 L9.75 19"/>',
        '<circle cx="16.5" cy="16.5" r="3.5" stroke="#ACCENT" fill="#ACCENT" fill-opacity="0.2"/>',
        '<path d="M19 19 L22 22" stroke="#ACCENT"/>',
    ],
    "feature.mounting_boss": [
        f'<path d="M8.25 18.75 V7 A3.75 1.2 0 0 0 15.75 7 V18.75 Z" {NEW}/>',
        '<path d="M2.5 18.75 H21.5"/>',
        '<path d="M8.25 18.75 V7 M15.75 18.75 V7" stroke="#ACCENT"/>',
        '<ellipse cx="12" cy="7" rx="3.75" ry="1.2" stroke="#ACCENT" fill="#ACCENT" '
        'fill-opacity="0.2"/>',
        '<path d="M8.25 13 L4.5 18.75 M15.75 13 L19.5 18.75"/>',
    ],
    "sketch.exit": [
        f'<path d="M3.75 5.25 H12.75 V18.75 H3.75 Z" {BODY}/>',
        '<path d="M13 5.25 H3.75 V18.75 H13"/>',
        '<path d="M10 12 H21 M17.5 8.5 L21 12 L17.5 15.5" stroke="#ACCENT"/>',
    ],
    "feature.flow": [
        '<path d="M3 14.5 C7 14.5 8 3 14 3 C17.5 3 18.5 6 21 6 L21 12 C17.5 12 16.5 9 14 9 '
        f'C10 9 9 21.5 3 21.5 Z" {BODY}/>',
        '<path d="M3 18 C8 18 9 6 14 6 C17 6 18 9 21 9" stroke="#ACCENT"/>',
        '<path d="M3 14.5 C7 14.5 8 3 14 3 C17.5 3 18.5 6 21 6"/>',
        '<path d="M3 21.5 C9 21.5 10 9 14 9 C16.5 9 17.5 12 21 12"/>',
    ],
}


def main() -> int:
    """Write every hero drawing."""
    for name, lines in HEROES.items():
        text = HEAD + "\n".join(lines) + "\n" + TAIL
        (ICONS / f"{name}.svg").write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(HEROES)} icons written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
