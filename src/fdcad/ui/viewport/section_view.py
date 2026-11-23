"""Section view clipping for the 3D view (PHASE2_SPEC P2.13, D253).

The section is drawn by the viewer's clipping planes, so it is display only:
the part is never cut (P2.13 item 4) and no kernel work runs while the plane
moves. The planes form one chain, so only the region in front of every plane
is cut away. Caps fill the cut in a colour.
"""

from __future__ import annotations

from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.Graphic3d import Graphic3d_ClipPlane
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB

from fdcad.core.section import CutPlane


def _color(hex_text: str) -> Quantity_Color:
    text = hex_text.lstrip("#")
    r, g, b = (int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return Quantity_Color(r, g, b, Quantity_TOC_sRGB)


def clip_chain(
    planes: list[CutPlane], show_cap: bool, cap_color: str | None = None
) -> Graphic3d_ClipPlane | None:
    """One chain of clipping planes for ``planes``, or None for no section.

    The viewer keeps the side a clipping plane's normal points to, so each plane
    is given the reversed normal: the material in front of the section plane goes.
    """
    head: Graphic3d_ClipPlane | None = None
    last: Graphic3d_ClipPlane | None = None
    for p in planes:
        n = p.normal
        clip = Graphic3d_ClipPlane(gp_Pln(gp_Pnt(*p.origin), gp_Dir(-n[0], -n[1], -n[2])))
        clip.SetCapping(show_cap)
        clip.SetCappingColor(_color(cap_color or p.color))
        clip.SetOn(True)
        if last is None:
            head = clip
        else:
            last.SetChainNextPlane(clip)
        last = clip
    return head


def clip_chains(
    zones: list[list[CutPlane]], show_cap: bool, cap_color: str | None = None
) -> list[Graphic3d_ClipPlane]:
    """One chain per zone cut away (TR355, D1603): the viewer cuts away what any chain
    cuts, so several separate zones go at once."""
    out = [clip_chain(z, show_cap, cap_color) for z in zones]
    return [c for c in out if c is not None]
