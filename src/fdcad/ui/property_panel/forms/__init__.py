"""Property panel forms for Phase 2 features. Importing this package registers them."""

from fdcad.ui.property_panel.forms import (
    chamfer_form,
    curve_forms,
    draft_form,
    fastening_forms,
    fillet_form,
    hole_form,
    loft_form,
    pipe_forms,
    point_curve_form,
    print_forms,
    shape_forms,
    shell_form,
    sketch3d_form,
    sweep_form,
    thread_forms,
)
from fdcad.ui.property_panel.forms.base import FORMS, FeatureForm

__all__ = [
    "FORMS",
    "FeatureForm",
    "chamfer_form",
    "curve_forms",
    "draft_form",
    "fastening_forms",
    "fillet_form",
    "hole_form",
    "loft_form",
    "pipe_forms",
    "point_curve_form",
    "print_forms",
    "shape_forms",
    "shell_form",
    "sketch3d_form",
    "sweep_form",
    "thread_forms",
]
