"""A rebuild helper for tests (test_remote.py, test_rebuild_helper.py, D2600).

``helper_dies.py <feature id>`` ends without a word when it starts that feature, as a
native fault in the kernel would. ``helper_dies.py slow`` waits half a second before
each feature, so a test can stop it part way.
"""

import os
import sys
import time

from fdcad.core.rebuild import engine, remote

target = sys.argv[1]
real_build = engine._build


def _build(feature, ftype, ctx):  # type: ignore[no-untyped-def]
    if target == "slow":
        time.sleep(0.5)
    elif feature.id == target:
        os._exit(3)
    return real_build(feature, ftype, ctx)


engine._build = _build
raise SystemExit(remote.main())
