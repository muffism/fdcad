"""Remove Fillets panel (TR260, DECISIONS D1410): picked rounds or a radius range,
and an optional new radius."""

from __future__ import annotations

from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm


@form("remove_fillets")
class RemoveFilletsForm(SpecForm):
    """Edits a Remove Fillets feature."""

    first_param = "min_radius"
    layout = (
        G(
            "rounds",
            strings.REMOVE_FILLETS_GROUP,
            strings.REMOVE_FILLETS_TIP,
            (
                F(
                    "faces",
                    strings.REMOVE_FILLETS_FACES,
                    "faces",
                    strings.REMOVE_FILLETS_FACES_TIP,
                    optional=True,
                ),
                F("use_range", strings.REMOVE_FILLETS_RANGE, "bool", strings.REMOVE_FILLETS_TIP),
                F(
                    "min_radius",
                    strings.CHANGE_FILLETS_FROM,
                    "length",
                    "",
                    0.0,
                    when=lambda v: v.get("use_range") is True,
                ),
                F(
                    "max_radius",
                    strings.CHANGE_FILLETS_TO,
                    "length",
                    "",
                    5.0,
                    when=lambda v: v.get("use_range") is True,
                ),
                F(
                    "resize",
                    strings.REMOVE_FILLETS_RESIZE,
                    "bool",
                    strings.REMOVE_FILLETS_RESIZE_TIP,
                ),
                F(
                    "new_radius",
                    strings.CHANGE_FILLETS_NEW,
                    "length",
                    "",
                    1.0,
                    when=lambda v: v.get("resize") is True,
                ),
            ),
        ),
    )
