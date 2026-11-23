"""A part file with NaN or Infinity in it is damaged (D2671).

FDCAD never writes them (Save refuses), but the JSON reader took them, so a damaged
or hand edited file opened with a nan in a feature, and every rebuild and save of
the part failed on it.
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError


@pytest.mark.parametrize("word", ["NaN", "Infinity", "-Infinity", "1e400", "-2.5e999"])
def test_a_file_with_a_value_that_is_not_a_number_is_damaged(word: str) -> None:
    text = fdef.dumps(new_document())
    damaged = text.replace('"next_id": ', f'"probe": {word}, "next_id": ', 1)
    assert damaged != text
    with pytest.raises(FileFormatError, match="not a number"):
        fdef.loads(damaged)
