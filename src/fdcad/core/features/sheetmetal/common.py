"""Helpers shared by the sheet metal features: finding the sheet and bend sizes."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, FeatureState
from fdcad.core.features.sheetmetal.model import SheetModel, SheetResult

#: Feature types that build or change the sheet model.
SHEET_TYPES = (
    "base_flange",
    "edge_flange",
    "sketched_bend",
    "hem",
    "miter_flange",
    "jog",
    "closed_corner",
    "break_corner",
    "rip",
    "tab_slot",
    "convert_sheet",
    "insert_bends",
    "cross_break",
    "unfold",
    "fold",
    "form_tool",
    "gusset",
    "sheet_tab",
    "edit_bends",
    "sheet_corner_relief",
    "extend_wall",
    "perforation",
    "flat_marks",
)


def value(feature: Feature, name: str, default: float) -> float:
    """A typed number of ``feature``, or ``default`` when it has none."""
    item = feature.params.get(name)
    return item.value if isinstance(item, Param) else default


#: Feature types that start a sheet (TR281, D2312).
STARTERS = ("base_flange", "convert_sheet", "insert_bends")


def folder_id(feature: Feature) -> str:
    """The Sheet Metal folder ``feature`` belongs to, or "" (TR281, D2312)."""
    ref = feature.refs.get("sheet_metal")
    return str(ref.get("feature", "")) if isinstance(ref, dict) else ""


def _same_sheet(model_folder: str, want: str) -> bool:
    """A sheet or a feature without a folder goes with any (one sheet parts, D2312)."""
    return not model_folder or not want or model_folder == want


def latest_sheet(feature: Feature, ctx: BuildContext) -> tuple[SheetResult | None, str | None]:
    """The last good sheet result before ``feature`` of the feature's own Sheet Metal
    folder (TR281, D2312), and the name of a feature after it that changed the part
    without the sheet model (it blocks sheet metal work), if any. Sheet metal features
    of another folder do not block: they work on their own sheet."""
    want = folder_id(feature)
    last: SheetResult | None = None
    for f in ctx.document.features:
        if f.id == feature.id:
            break
        res = ctx.results.get(f.id)
        if (
            isinstance(res, SheetResult)
            and res.state is not FeatureState.ERROR
            and res.sheet is not None
            and _same_sheet(res.sheet.folder, want)
        ):
            last = res
    if last is None or ctx.body is last.body:
        return last, None
    seen = False
    for f in ctx.document.features:
        if f.id == feature.id:
            break
        res = ctx.results.get(f.id)
        if res is last:
            seen = True
            continue
        other_sheet = (
            f.type in (*SHEET_TYPES, "flatten")
            and bool(want)
            and bool(folder_id(f))
            and folder_id(f) != want
        )
        changed = seen and res is not None and res.body is not None and res.body is not last.body
        if changed and not other_sheet and _touches_own(last, res.body):  # type: ignore[union-attr]
            return last, f.name
    return last, None


def _touches_own(last: SheetResult, body: object) -> bool:
    """True when ``body`` no longer holds the sheet's own solid unchanged: the feature
    that made it changed the sheet. A feature that only adds or changes other bodies does
    not (TR281, D2312)."""
    from fdcad.core.features.solids import solids

    own = last.own or last.body
    if own is None:
        return True
    now = solids(body.shape)  # type: ignore[attr-defined]
    return not all(any(s.IsSame(n) for n in now) for s in solids(own.shape))


def own_body(feature: Feature, ctx: BuildContext) -> Any:
    """The sheet's own solid as it stands, without the part's other bodies: the body of a
    feature that changes the sheet model and not the shape (Cross Break, Flat Marks).

    They used to hand back the whole part (D1073). In a part with a second sheet or a
    solid body that was taken for the sheet's own solid: the other bodies were put
    back beside it once more (two bodies became three), and the next feature of the
    sheet then took all of them for its own and dropped them.
    """
    last, _blocker = latest_sheet(feature, ctx)
    if last is None:
        return ctx.body
    return last.own or last.body or ctx.body


def beside_other_bodies(feature: Feature, ctx: BuildContext, shown: Any) -> Any:
    """``shown``, this sheet laid flat or part folded, with the part's other bodies beside
    it (D1075).

    A Flat Pattern that is on showed its own sheet only: in a part of several bodies
    every other body, other sheets among them, was gone from the part and from every
    feature after it, though the features of another sheet go on being built below it
    (D2312).
    """
    from fdcad.core.features.bodies import join
    from fdcad.core.features.solids import compound, solids
    from fdcad.core.naming.names import NamedShape

    body = ctx.body
    last, _blocker = latest_sheet(feature, ctx)
    if body is None or shown is None or last is None:
        return shown
    own = last.own or last.body or body
    mine = solids(own.shape)
    others = [s for s in solids(body.shape) if not any(s.IsSame(m) for m in mine)]
    if others and _touches_own(last, body):  # a cut taken into the sheet (see below)
        others = [s for s in others if not _near(s, own.shape)]
    if not others:
        return shown
    rest = NamedShape(compound(others), list(body.faces))
    return join([shown, rest], feature.id) or shown


def current_sheets(feature: Feature, ctx: BuildContext) -> list[SheetResult]:
    """The latest good result of every sheet of the part whose own solid is in the part
    as that result left it (D1080): the sheets a plain cut may be made square in."""
    from fdcad.core.features.solids import solids

    latest: dict[str, SheetResult] = {}
    for f in ctx.document.features:
        if f.id == feature.id:
            break
        res = ctx.results.get(f.id)
        if (
            isinstance(res, SheetResult)
            and res.state is not FeatureState.ERROR
            and res.sheet is not None
        ):
            latest[res.sheet.folder] = res
    body = ctx.body
    if body is None:
        return []
    now = solids(body.shape)
    out = []
    for res in latest.values():
        own = res.own or res.body
        if own is None or res.sheet is None or res.sheet.unfolded:
            continue
        mine = solids(own.shape)
        if mine and all(any(s.IsSame(n) for n in now) for s in mine):
            out.append(res)
    return out


def with_other_bodies(feature: Feature, ctx: BuildContext, result: object) -> object:
    """``result`` with the part's other bodies put back beside its sheet (TR281, D2312).

    A sheet metal feature builds only its own sheet; the solids of the part that are not
    that sheet (other sheets, solid bodies) are carried on unchanged. The sheet's own
    solid is kept in ``result.own`` so the next feature of the same sheet can tell it
    from the others."""
    if not isinstance(result, SheetResult) or result.sheet is None or result.body is None:
        return result
    if not result.sheet.folder:
        result.sheet.folder = folder_id(feature)
    result.own = result.body
    body = ctx.body
    if body is None:
        return result
    from fdcad.core.features.bodies import join
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.names import NamedShape

    if feature.type == "base_flange":
        others = solids(body.shape)
    elif feature.type in STARTERS:
        others = _not_converted(feature, ctx)
    else:
        last, _blocker = latest_sheet(feature, ctx)
        if last is None:
            return result
        own = last.own or last.body or body
        mine = solids(own.shape)
        others = [s for s in solids(body.shape) if not any(s.IsSame(m) for m in mine)]
        if others and _touches_own(last, body):
            # A cut or other change took the sheet's own solid in (Fold and the Flat
            # Pattern take such cuts in): the changed solid is the sheet, not another
            # body, so only solids apart from the sheet are others.
            others = [s for s in others if not _near(s, own.shape)]
    if feature.type == "form_tool" and feature.refs.get("tool_face"):  # TR279 (D2313)
        from fdcad.core.features.sheetmetal.custom_form import tool_solid_index

        index = tool_solid_index(feature, ctx)
        if index is not None:
            used = solids(body.shape)[index]
            others = [s for s in others if not s.IsSame(used)]
    if not others:
        return result
    from fdcad.core.features.solids import compound

    rest = NamedShape(compound(others), list(body.faces))
    joined = join([result.body, rest], feature.id)
    if joined is not None:
        result.body = joined
    return result


def _near(a: object, b: object) -> bool:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    dist = BRepExtrema_DistShapeShape(a, b)
    return not dist.IsDone() or dist.Value() < 1e-6


def _not_converted(feature: Feature, ctx: BuildContext) -> list[object]:
    """The solids of the part a conversion leaves alone: every one but the solid that holds
    its picked face (D2312)."""
    from fdcad.core.features.solids import solids
    from fdcad.core.naming.resolve import resolve_face

    assert ctx.body is not None
    ref = feature.refs.get("face")
    if not isinstance(ref, dict):
        return []
    try:
        face, _issues = resolve_face(ctx.body, ref, feature.name)
    except FeatureError:
        return []
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    out = []
    for solid in solids(ctx.body.shape):
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        holds = False
        while explorer.More() and not holds:
            holds = explorer.Current().IsSame(face)
            explorer.Next()
        if not holds:
            out.append(solid)
    return out


def no_sheet_message(feature: Feature, ctx: BuildContext) -> str:
    """What to say when ``feature`` finds no good sheet: name the first failed sheet feature
    (the later ones fail because of it)."""
    failed: str | None = None
    for f in ctx.document.features:
        if f.id == feature.id:
            break
        res = ctx.results.get(f.id)
        if f.type in SHEET_TYPES and res is not None and res.state is FeatureState.ERROR:
            failed = f.name
            break
    if failed is not None:
        return f"{feature.name}: {failed} has an error, so there is no sheet. Fix {failed} first."
    return f"{feature.name} needs a sheet metal part. Add a Base Flange first."


def require_sheet(feature: Feature, ctx: BuildContext) -> SheetModel:
    """A copy of the sheet model to build on. Raises FeatureError with what to do."""
    last, blocker = latest_sheet(feature, ctx)
    name = feature.name
    if last is None or last.sheet is None:
        raise FeatureError(no_sheet_message(feature, ctx))
    if blocker is not None:
        raise FeatureError(
            f"{name}: {blocker} is not a sheet metal feature, so the sheet cannot be used "
            f"after it. Move {name} above {blocker}, or suppress {blocker}."
        )
    return last.sheet.copy()


def sheet_kerf(feature: Feature, ctx: BuildContext) -> float:
    """The part's kerf: the Sheet Metal feature's ``kerf`` (mm, 0 when not set). Tab and
    Slot and finger joints draw their slots narrower by it (TR297 item 3, D802)."""
    from fdcad.core.document.model import Param

    ref = feature.refs.get("sheet_metal")
    fids = [ref.get("feature")] if isinstance(ref, dict) else []
    fids += [f.id for f in ctx.document.features if f.type == "sheet_metal"]
    for fid in fids:
        try:
            owner = ctx.document.feature(str(fid))
        except KeyError:
            continue
        kerf = owner.params.get("kerf")
        if isinstance(kerf, Param):
            return max(float(kerf.value), 0.0)
        return 0.0
    return 0.0
