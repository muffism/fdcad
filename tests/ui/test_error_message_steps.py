"""Error messages say what failed and what to do next (CLAUDE.md 8.4, bug hunt B5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.features.preview import PREVIEW_NEXT
from fdcad.core.io import fdef
from fdcad.core.io.fdef import DAMAGED_NEXT
from fdcad.core.io.migrations import FileFormatError
from fdcad.ui import (
    strings,
    strings_config,
    strings_extra,
    strings_import,
    strings_phase3,
    strings_phase4,
    strings_print,
    strings_sheetmetal,
)
from tests.core.test_message_next_steps import has_next_step

#: Words that start the "what to do" sentence of a message.
NEXT_STEP = (
    "Check",
    "Rebuild",
    "Add",
    "Point",
    "Open",
    "Choose",
    "Change",
    "Pick",
    "Close",
)


def _has_next_step(message: str) -> bool:
    sentences = [s.strip() for s in message.split(". ") if s.strip()]
    return len(sentences) >= 2 and sentences[-1].split()[0] in NEXT_STEP


@pytest.mark.parametrize(
    "message",
    [
        strings.EXPORT_FAILED.format(reason="disk full"),
        strings_print.FLAT_FAILED.format(reason="disk full"),
        strings_print.VOLUME_FAILED.format(reason="no body"),
        strings_print.OVERHANG_FAILED.format(reason="no body"),
        strings_print.WALL_FAILED.format(reason="no body"),
        strings_print.ESTIMATE_FAILED.format(reason="no body"),
        strings_print.CHECK_FAILED.format(reason="no body"),
        strings_phase3.NEEDS_BODIES.format(tool="Combine"),
        strings_extra.SELECT_OTHER_EMPTY,
        f"Preview failed (ValueError). {PREVIEW_NEXT}",
    ],
)
def test_messages_say_what_to_do(message: str) -> None:
    assert _has_next_step(message), message
    assert chr(0x2013) not in message and chr(0x2014) not in message


@pytest.mark.parametrize("content", [b"[]", b"{not json", b"\xff\xfe\x00"])
def test_unreadable_part_files_say_what_to_do(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "bad.fdef"
    path.write_bytes(content)
    with pytest.raises(FileFormatError) as info:
        fdef.load(path)
    message = str(info.value)
    assert _has_next_step(message), message
    assert message.endswith(("Choose a .fdprt file.", DAMAGED_NEXT))


#: Templates that add a fixed next step after a reason from outside FDCAD.
_STEP_AFTER_REASON = [
    strings.OPEN_FAILED_SYSTEM.format(name="a.fdef", reason="{r}"),
    strings.SAVE_FAILED.format(name="a.fdef", reason="{r}"),
    strings.EXPORT_FAILED.format(reason="{r}"),
    strings.DRAFT_ASSIST_FAILED.format(reason="{r}"),
    strings_import.READ_FAILED.format(name="a.stl", reason="{r}"),
    strings_print.SLICER_FAILED.format(reason="{r}"),
    strings_print.FLAT_FAILED.format(reason="{r}"),
    strings_print.DRAFT_FAILED.format(reason="{r}"),
    strings_config.TABLE_CSV_UNREADABLE.format(reason="{r}"),
    strings_sheetmetal.BEND_TABLE_UNREADABLE.format(error="{r}"),
    strings_sheetmetal.GAUGE_UNREADABLE.format(error="{r}"),
    strings_sheetmetal.EXPORT_FLAT_FAILED.format(error="{r}"),
    strings_sheetmetal.BUILD123D_FAILED.format(error="{r}"),
]


@pytest.mark.parametrize("template", _STEP_AFTER_REASON)
@pytest.mark.parametrize(
    "reason",
    [
        OSError(13, "Permission denied."),
        ValueError("The value is wrong."),
        ValueError("trailing space. "),
    ],
)
def test_outside_reasons_never_give_two_full_stops(template: str, reason: Exception) -> None:
    message = template.replace("{r}", strings.clause(reason))
    assert ".." not in message, message
    assert has_next_step(message), message


@pytest.mark.parametrize(
    "template",
    [
        strings.OPEN_FAILED.format(name="a.fdef", reason="{r}"),
        strings.EXPORT_REFUSED.format(reason="{r}"),
        strings.VARIABLE_ERROR.format(reason="{r}"),
        strings_phase4.FAV_IMPORT_FAILED.format(error="{r}"),
        strings_config.EQ_NOT_APPLIED.format(message="{r}"),
        strings_config.TABLE_NOT_APPLIED.format(message="{r}"),
    ],
)
def test_fdcad_reasons_end_the_message(template: str) -> None:
    """FDCAD's own reasons hold their next step, so the wrapper adds nothing after them."""
    message = template.replace("{r}", "The file is damaged. Open a backup copy.")
    assert message.endswith("Open a backup copy.")
    assert ".." not in message


def test_clause_uses_the_system_text_without_a_full_stop() -> None:
    assert strings.clause(OSError(2, "No such file or directory", "x.fdef")) == (
        "No such file or directory"
    )
    assert strings.clause(ValueError("Bad value.")) == "Bad value"
    assert strings.clause(ValueError("")) == "ValueError"
