"""Write the sample parts and their golden results.

Run ``uv run python -m fdcad.samples.make`` after changing a sample. The test
suite checks that the saved files match these builders and the golden results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io import fdef
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.parts import SAMPLES
from fdcad.samples.parts_phase4 import GOLDEN_TOLERANCES

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "samples"
GOLDEN = ROOT / "tests" / "golden" / "samples.json"


def measure(shape: TopoDS_Shape) -> dict[str, Any]:
    """Volume, face and edge counts and the optimal bounding box (PLAN 10 item 2)."""
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    counts = {}
    for key, kind in (("faces", TopAbs_FACE), ("edges", TopAbs_EDGE)):
        m = ShapeMap()
        TopExp.MapShapes_s(shape, kind, m)
        counts[key] = m.Extent()
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return {
        "volume": props.Mass(),
        **counts,
        "bbox": [round(v, 6) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())],
    }


def main() -> None:
    """Save every sample and its golden result."""
    SAMPLE_DIR.mkdir(exist_ok=True)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    golden: dict[str, Any] = {}
    for name, build in SAMPLES.items():
        doc = build()
        fdef.save(doc, SAMPLE_DIR / f"{name}{fdef.PART_SUFFIX}")
        report = RebuildEngine().rebuild(doc)
        assert report.body is not None, name
        golden[name] = measure(report.body.shape)
        if report.body_count != 1:  # multibody samples record how many bodies (D292)
            golden[name]["bodies"] = report.body_count
        golden[name].update(GOLDEN_TOLERANCES.get(name, {}))  # deformed samples (D394)
        print(f"{name}: {golden[name]}")
    GOLDEN.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
