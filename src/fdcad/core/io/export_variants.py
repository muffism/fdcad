"""Batch export over variable values (TUTORIAL_REVIEW_SPEC_2 TR368, DECISIONS D904).

Pick global variables and, for each, a list ("10, 20, 30") or a range ("10..30 step
5"). Every combination is set on a copy of the part, rebuilt and written to a folder
as STEP, STL, 3MF or a part file, named from a template such as
"{part} {width}x{height}". The open part is not changed. A log in the folder lists
each combination and what happened. No Qt: the app runs this off the UI thread.
"""

from __future__ import annotations

import copy
import itertools
import re
from collections.abc import Callable
from pathlib import Path

from fdcad.core.document.model import Document
from fdcad.core.io.export_configs import KINDS, LOG_NAME, Outcome

#: The most combinations one batch makes.
MAX_COMBINATIONS = 500
_RANGE = re.compile(
    r"^\s*(-?[\d.]+)\s*\.\.\s*(-?[\d.]+)\s*(?:step\s*(-?[\d.]+))?\s*$", re.IGNORECASE
)


class BatchError(ValueError):
    """The values or template cannot be used; the message says what to change."""


def parse_values(text: str) -> list[str]:
    """The values typed for one variable: a comma list, or a range "a..b step s"."""
    m = _RANGE.match(text)
    if m:
        start, stop = float(m.group(1)), float(m.group(2))
        step = float(m.group(3)) if m.group(3) else (1.0 if stop >= start else -1.0)
        if step == 0 or (stop - start) / step < 0:
            raise BatchError(f'The range "{text}" never reaches its end. Check the step.')
        count = round((stop - start) / step) + 1
        if count > MAX_COMBINATIONS:
            raise BatchError(f'The range "{text}" has too many values. Use a larger step.')
        return [f"{start + i * step:g}" for i in range(count)]
    values = [v.strip() for v in text.split(",") if v.strip()]
    if not values:
        raise BatchError("A variable has no values. Type a list such as 10, 20, 30.")
    return values


def combinations(values: dict[str, list[str]]) -> list[dict[str, str]]:
    """Every combination of the values, first variable changing slowest."""
    names = list(values)
    out = [dict(zip(names, combo, strict=True)) for combo in itertools.product(*values.values())]
    if len(out) > MAX_COMBINATIONS:
        raise BatchError(
            f"{len(out)} combinations is too many (at most {MAX_COMBINATIONS}). Use fewer values."
        )
    return out


def name_for(template: str, part: str, combo: dict[str, str], kind: str) -> str:
    """A safe file name from the template, such as "Box 40x20.step"."""
    fields = {"part": part, **combo}
    try:
        text = template.format(**fields)
    except (KeyError, IndexError, ValueError) as exc:
        raise BatchError(
            f"The name template uses {exc}, which is not the part or a chosen variable. "
            "Change the template."
        ) from exc
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return (clean or "Part") + KINDS[kind]


def default_template(names: list[str]) -> str:
    """ "{part} width{width} height{height}" for the chosen variables."""
    return "{part} " + " ".join(f"{n}{{{n}}}" for n in names)


def export_variants(
    doc: Document,
    combos: list[dict[str, str]],
    folder: str | Path,
    kind: str,
    part: str,
    template: str,
    cancelled: Callable[[], bool] = lambda: False,
) -> list[Outcome]:
    """Write one file per combination; returns the outcomes in order and writes the log."""
    from fdcad.core.features.base import FeatureState
    from fdcad.core.io import export, fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    if kind not in KINDS:
        raise BatchError(f"Unknown export kind '{kind}'.")
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    settings = export.MeshSettings.from_data((doc.print_setup or {}).get("mesh_export"))
    engine = RebuildEngine()  # one engine, so unchanged features are reused between files
    out: list[Outcome] = []
    for combo in combos:
        label = ", ".join(f"{k} = {v}" for k, v in combo.items())
        if cancelled():
            out.append(Outcome(label, None, "Stopped before this combination."))
            continue
        try:
            path = target / name_for(template, part, combo, kind)
            work = copy.deepcopy(doc)
            for var in work.variables:
                if var.name in combo:
                    var.expr = combo[var.name]
            if kind == "fdprt":
                fdef.save(work, path)
                out.append(Outcome(label, path, "Saved."))
                continue
            report = engine.rebuild(work, cancelled=cancelled)
            body = report.body
            if report.variable_error:
                out.append(Outcome(label, None, f"{report.variable_error} Check the values."))
                continue
            if report.cancelled or body is None:
                out.append(Outcome(label, None, "It has no solid to export. Check the values."))
                continue
            failed = sum(1 for r in report.results.values() if r.state is FeatureState.ERROR)
            if kind == "step":
                export.export_step(body.shape, path)
            elif kind == "stl":
                export.export_stl(body.shape, path, settings)
            else:
                export.export_3mf(body.shape, path, settings=settings, name=path.stem)
            note = (
                f"Exported; {failed} feature{'s' if failed != 1 else ''} failed with these "
                "values and were left out. Check the values."
                if failed
                else "Exported."
            )
            out.append(Outcome(label, path, note))
        except BatchError:
            raise
        except Exception as exc:  # one failed combination never stops the others
            out.append(Outcome(label, None, f"Failed: {exc}. Check these values."))
    lines = [f"{o.name}: {o.message}" + (f" ({o.path.name})" if o.path else "") for o in out]
    (target / LOG_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
