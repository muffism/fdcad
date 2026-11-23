"""PyInstaller entry script: start FDCAD, or a rebuild helper process (D2600)."""

import sys

if len(sys.argv) > 1 and sys.argv[1] == "--rebuild-helper":
    from fdcad.core.rebuild.remote import main as helper

    raise SystemExit(helper())

from fdcad.app import main

raise SystemExit(main())
