"""Insert Part: the bodies of another FDCAD part as one feature (TR71, DECISIONS D2420).

Type ``insert_part``. Params:

- ``part_file``: the other part's file path, absolute in memory. A part file stores
  it relative to itself when the other part is in its folder or below (D2625, see
  ``core.io.part_links``). With ``link`` on (the
  default) the file is read and rebuilt at every rebuild of this part, so the
  inserted bodies follow changes to it; the rebuild cache keys on the file's size,
  time and contents. A missing file is an error that says where it looked.
- ``link``: off after Break Link: the bodies come from ``refs.embedded`` (a STEP
  block in this part, FDEF_SPEC 11) and the file is not read again.
- ``keep_bodies``: optional text, the numbers of the source's bodies to bring in
  (from 1), such as "1, 3"; empty for all.
- ``with_sketches`` and ``with_planes``: optional booleans: the source's sketch
  outlines and its own planes come in too, as reference lines in the view.
- Placement as Linked Body Copy (``place``, ``dx`` ... ``rz`` or ``refs.frame``),
  about the source's own origin.

Opening a part never runs code (CLAUDE.md 5 item 10): the source is read as data
with the part file reader, and a part that inserts itself, directly or through
another, is refused. Bodies are new bodies; faces are ``<fid>/part/<name>``. No Qt.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Any

from OCP.gp import gp_Trsf

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

TYPE = "insert_part"
_ACTIVE = threading.local()


def source_path(feature: Feature) -> Path:
    """The source file the feature names."""
    text = str(feature.params.get("part_file", "") or "").strip()
    if not text:
        raise FeatureError(f"{feature.name}: no source part is set. Pick the part to insert.")
    return Path(text).expanduser()


def file_key(path: Path) -> Any:
    """What changes when the file changes: size, time and a hash of its contents."""
    try:
        stat = path.stat()
        digest = hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return ["missing", str(path)]
    return [str(path), stat.st_size, stat.st_mtime_ns, digest]


def keep_numbers(feature: Feature, count: int) -> list[int]:
    """The 0 based body indices to bring in. Raises FeatureError for bad text."""
    text = str(feature.params.get("keep_bodies", "") or "").strip()
    if not text:
        return list(range(count))
    out = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit() or not 1 <= int(part) <= count:
            raise FeatureError(
                f"{feature.name}: the source has {count} bodies; '{part}' is not one of them. "
                f"Enter numbers from 1 to {count}."
            )
        out.append(int(part) - 1)
    return out


def _source_report(feature: Feature) -> Any:
    """The rebuilt source part, read from its file."""
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    path = source_path(feature)
    if not path.is_file():
        raise FeatureError(
            f"{feature.name}: the source part was not found at {path}. Pick the file again, or "
            "break the link to keep the bodies as they are."
        )
    key = os.path.realpath(path)
    stack: list[str] = getattr(_ACTIVE, "stack", [])
    if key in stack:
        raise FeatureError(
            f"{feature.name}: {path.name} inserts itself, through itself or another part. "
            "Pick another part to insert."
        )
    try:
        source = fdef.load(path)
    except Exception as exc:  # a damaged or newer file: say so, never crash
        raise FeatureError(
            f"{feature.name}: {path.name} could not be read ({type(exc).__name__}). Open it in "
            "FDCAD to check it, or pick another part."
        ) from None
    _ACTIVE.stack = [*stack, key]
    try:
        report = RebuildEngine().rebuild(source)
    finally:
        _ACTIVE.stack = stack
    return source, report


def _embedded_shape(feature: Feature, ctx: BuildContext) -> Any:
    from fdcad.core.io.embedded import EmbeddedError, block_bytes
    from fdcad.core.io.step_import import read_step

    try:
        data = block_bytes(ctx.document, feature.refs.get("embedded"), "step", feature.name)
    except EmbeddedError as exc:
        raise FeatureError(str(exc)) from None
    return read_step(data, feature.name).shape


def source_bodies(feature: Feature, ctx: BuildContext) -> tuple[list[Any], list[Any]]:
    """The source's bodies to bring in, and its reference shapes (sketch outlines and
    planes), before placement."""
    from fdcad.core.features.solids import solids

    if feature.params.get("link", True) is False:
        shape = _embedded_shape(feature, ctx)
        return solids(shape), []
    source, report = _source_report(feature)
    if report.body is None:
        from fdcad.core.features.base import FeatureState

        for result in report.results.values():  # say why the source has no bodies
            for issue in result.issues:
                if issue.state is FeatureState.ERROR:
                    raise FeatureError(
                        f"{feature.name}: {source_path(feature).name} does not build: "
                        f"{issue.message}"
                    )
        raise FeatureError(
            f"{feature.name}: {source_path(feature).name} has no bodies. Pick a part with bodies."
        )
    every = solids(report.body.shape)
    bodies = [every[i] for i in keep_numbers(feature, len(every))]
    return bodies, _reference_shapes(feature, source, report)


def _reference_shapes(feature: Feature, source: Document, report: Any) -> list[Any]:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    out: list[Any] = []
    if feature.params.get("with_sketches") is True:
        for f in source.features:
            result = report.results.get(f.id)
            sketch = result.sketch if result is not None else None
            profile = sketch.profile if sketch is not None else None
            for face in profile.faces if profile is not None else []:
                explorer = TopExp_Explorer(face, TopAbs_EDGE)
                while explorer.More():
                    out.append(explorer.Current())
                    explorer.Next()
    if feature.params.get("with_planes") is True:
        from fdcad.core.features.base import Datum
        from fdcad.core.features.pattern_datums import copy_shape

        for f in source.features:
            result = report.results.get(f.id)
            if f.type == "ref_plane" and result is not None and result.plane is not None:
                p = result.plane
                out.append(copy_shape(Datum("plane", p.origin, p.normal, p.x_dir), 20.0))
    return out


@register
class InsertPart(FeatureType):
    """Bodies of another part, linked to its file or kept in this part."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("link", default=True, optional=True),
        ParamSpec("place", choices=("offset", "on_frame"), default="offset", optional=True),
        *(ParamSpec(k, kind=Kind.LENGTH, optional=True) for k in ("dx", "dy", "dz")),
        *(ParamSpec(k, kind=Kind.ANGLE, optional=True) for k in ("rx", "ry", "rz")),
    )

    def key_data(self, feature: Feature, doc: Document, results: dict[str, Any]) -> Any:
        """The source file's state, so the part rebuilds when the file changes."""
        if feature.params.get("link", True) is False:
            return None
        try:
            return file_key(source_path(feature))
        except FeatureError:
            return None

    def _placed(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Any], list[Any], gp_Trsf, list[Issue]]:
        from fdcad.core.features.linked_copy import placement

        bodies, references = source_bodies(feature, ctx)
        trsf, issues = placement(feature, ctx, (0.0, 0.0, 0.0))
        return bodies, references, trsf, issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the source's bodies, placed, as new bodies."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

        from fdcad.core.features.bodies import join
        from fdcad.core.features.solids import compound
        from fdcad.core.naming.names import faces_of, restrict

        bodies, references, trsf, issues = self._placed(feature, ctx)
        if not bodies:
            raise FeatureError(f"{feature.name}: no bodies are chosen. Clear Bodies to Keep.")
        moved = BRepBuilderAPI_Transform(compound(bodies), trsf, True).Shape()
        names = [(f"{feature.id}/part/face{k}", f) for k, f in enumerate(faces_of(moved), start=1)]
        inserted = NamedShape(moved, restrict(names, moved, feature.id))
        body = join([ctx.body, inserted], feature.id) if ctx.body is not None else inserted
        result = FeatureResult(body=body, issues=issues)
        if references:
            result.extras["reference"] = BRepBuilderAPI_Transform(
                compound(references), trsf, True
            ).Shape()
        return result

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The placed bodies, for the preview."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

        from fdcad.core.features.solids import compound

        bodies, _refs, trsf, _issues = self._placed(feature, ctx)
        return NamedShape(BRepBuilderAPI_Transform(compound(bodies), trsf, True).Shape(), [])


def break_link(doc: Document, fid: str) -> tuple[Feature, str, dict[str, Any]]:
    """A copy of insert feature ``fid`` that keeps the source bodies in this part (a STEP
    block), its new block id and the block. The document is not changed. Raises
    FeatureError."""
    import copy

    from fdcad.core.features.solids import compound
    from fdcad.core.io.embedded import make_block, new_block_id
    from fdcad.core.io.save_bodies import step_bytes

    feature = doc.feature(fid)
    if feature.type != TYPE or feature.params.get("link", True) is False:
        raise FeatureError(f"{feature.name} is not a linked part. Pick a linked Insert Part.")
    ctx = BuildContext(doc, None, {}, {})
    bodies, _refs = source_bodies(feature, ctx)
    data = step_bytes(compound(bodies))
    block_id = new_block_id(doc)
    block = make_block("step", f"{source_path(feature).stem}.step", data)
    out = copy.deepcopy(feature)
    out.params["link"] = False
    out.params.pop("keep_bodies", None)  # the block holds only the kept bodies
    out.refs["embedded"] = {"embedded": block_id}
    return out, block_id, block
