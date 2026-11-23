"""Export each configuration as its own file (TUTORIAL_REVIEW_SPEC_2 TR196, D827).

For every chosen configuration, a copy of the part is switched to it, rebuilt
and written to a folder as a part file, STEP, STL or 3MF, named
"<part> <configuration>.<ext>". The open part is not changed. A log file in the
folder lists each configuration and what happened. No Qt: the app runs this
off the UI thread.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fdcad.core.document.model import Document

KINDS = {"fdprt": ".fdprt", "step": ".step", "stl": ".stl", "3mf": ".3mf"}
LOG_NAME = "Export log.txt"


@dataclass
class Outcome:
    """What happened to one configuration."""

    name: str
    path: Path | None
    message: str

    @property
    def ok(self) -> bool:
        """True when its file was written."""
        return self.path is not None


def file_name(base: str, config: str, kind: str) -> str:
    """A safe file name such as "Bracket Long.step"."""
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", f"{base} {config}").strip(" .")
    return (clean or "Part") + KINDS[kind]


def export_configurations(
    doc: Document,
    names: list[str],
    folder: str | Path,
    kind: str,
    base: str,
    cancelled: Callable[[], bool] = lambda: False,
) -> list[Outcome]:
    """Write one file per configuration in ``names`` to ``folder``; returns the outcomes
    in order and writes them to the log file."""
    from fdcad.core import configurations as configs
    from fdcad.core.features.base import FeatureState
    from fdcad.core.io import export, fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    if kind not in KINDS:
        raise ValueError(f"Unknown export kind '{kind}'.")
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    settings = export.MeshSettings.from_data((doc.print_setup or {}).get("mesh_export"))
    out: list[Outcome] = []
    for name in names:
        if cancelled():
            out.append(Outcome(name, None, "Stopped before this configuration."))
            continue
        path = target / file_name(base, name, kind)
        try:
            part = copy.deepcopy(doc)
            configs.activate(part, name)
            if kind == "fdprt":
                fdef.save(part, path)
                out.append(Outcome(name, path, "Saved."))
                continue
            report = RebuildEngine().rebuild(part, cancelled=cancelled)
            body = report.body
            if report.cancelled or body is None:
                out.append(Outcome(name, None, "It has no solid to export. Check its features."))
                continue
            failed = sum(1 for r in report.results.values() if r.state is FeatureState.ERROR)
            if kind == "step":
                export.export_step(body.shape, path)
            elif kind == "stl":
                export.export_stl(body.shape, path, settings)
            else:
                export.export_3mf(body.shape, path, settings=settings, name=f"{base} {name}")
            note = (
                f"Exported; {failed} feature{'s' if failed != 1 else ''} with errors were left "
                "out. Fix them in this configuration."
                if failed
                else "Exported."
            )
            out.append(Outcome(name, path, note))
        except Exception as exc:  # one failed configuration never stops the others
            out.append(Outcome(name, None, f"Failed: {exc}. Check this configuration."))
    lines = [f"{o.name}: {o.message}" + (f" ({o.path.name})" if o.path else "") for o in out]
    (target / LOG_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
