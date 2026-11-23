"""Shared helpers for the test plan run: test parts, sessions, picks."""

from __future__ import annotations

import math
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.getcwd())

from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from PySide6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])

from tests.core.features.test_features import add_extrude, add_sketch, rect  # noqa: E402

from fdcad.core.document.model import Document, Feature, Param, new_document  # noqa: E402
from fdcad.core.sketch.model import Circle, Sketch, sketch_to_data  # noqa: E402
from fdcad.ui.session import DocumentSession  # noqa: E402


def pump(sec: float = 0.05) -> None:
    end = time.time() + sec
    while time.time() < end:
        APP.processEvents()
        time.sleep(0.005)


def volume(shape: Any) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


def centre(shape: Any) -> tuple[float, float, float]:
    props = GProp_GProps()
    if shape.ShapeType() == TopAbs_FACE:
        BRepGProp.SurfaceProperties_s(shape, props)
    else:
        BRepGProp.LinearProperties_s(shape, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def length(edge: Any) -> float:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    return props.Mass()


def subshapes(shape: Any, kind: Any) -> list[Any]:
    out: list[Any] = []
    e = TopExp_Explorer(shape, kind)
    while e.More():
        s = e.Current()
        if not any(s.IsSame(o) for o in out):
            out.append(s)
        e.Next()
    return out


def faces(shape: Any) -> list[Any]:
    return subshapes(shape, TopAbs_FACE)


def edges(shape: Any) -> list[Any]:
    return subshapes(shape, TopAbs_EDGE)


def t1() -> tuple[Document, str]:
    """T1 Block: 100 x 60 centred on the Top plane, 20 high (volume 120000)."""
    doc = new_document()
    s = Sketch()
    rect(s, -50, -30, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f3"})
    return doc, add_extrude(doc, sk, 20.0)


def t2() -> tuple[Document, str]:
    """T2 Cylinder: diameter 40 on the Top plane, 60 high (volume 75398)."""
    doc = new_document()
    s = Sketch()
    c = s.add_point(0, 0)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, 20.0)
    sk = add_sketch(doc, s, {"feature": "f3"})
    return doc, add_extrude(doc, sk, 60.0)


def session_for(doc: Document) -> DocumentSession:
    session = DocumentSession(doc)
    session.request_rebuild()
    session.wait(60000)
    pump(0.2)
    return session


def top_face(body: Any, axis: int = 1) -> Any:
    return max(faces(body), key=lambda f: centre(f)[axis])


def top_edges(body: Any, axis: int = 1) -> list[Any]:
    face = top_face(body, axis)
    return sorted(edges(face), key=lambda e: -length(e))


def side_faces(body: Any, axis: int = 1) -> list[Any]:
    out = []
    for f in faces(body):
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
        from OCP.TopoDS import TopoDS

        s = BRepAdaptor_Surface(TopoDS.Face(f))
        if s.GetType() != GeomAbs_Plane:
            continue
        n = s.Plane().Axis().Direction()
        if abs((n.X(), n.Y(), n.Z())[axis]) < 1e-6:
            out.append(f)
    return out


__all__ = [
    "APP",
    "Feature",
    "Param",
    "centre",
    "edges",
    "faces",
    "length",
    "math",
    "pump",
    "session_for",
    "side_faces",
    "sketch_to_data",
    "t1",
    "t2",
    "top_edges",
    "top_face",
    "volume",
]
