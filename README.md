# FDCAD

FDCAD ("Fully Defined CAD") is an open source parametric part modeler for macOS (Apple Silicon) and Windows. Parts are saved as `.fdprt` files, an open JSON format (`.fdef` before v1.0), and export to STEP, STL and 3MF.

Version 1.0 has sketches with relations and dimensions, features from extrudes and revolves to sweeps, lofts, fillets, shells, holes and patterns, sheet metal, equations and configurations, direct editing, and checks for 3D printing. The node editor (Phase 7) builds geometry from a graph. See `CHANGELOG.md` for the full list and `docs/user_guide` for how to use it.

To report a problem, use Help, Diagnostics, Report a Problem in the app, or open an issue here.

## Install

Download the latest release from the GitHub Releases page.

1. Mac: open the `.dmg` and drag FDCAD to Applications.
2. Windows: run the installer.

### First launch of an unsigned app

FDCAD releases are not signed with a paid developer certificate, so your system warns you the first time.

1. Mac: open FDCAD once. When macOS blocks it, open System Settings, then Privacy and Security, scroll down and click Open Anyway. Confirm, and FDCAD opens normally from then on.
2. Windows: when SmartScreen shows "Windows protected your PC", click More info, then Run anyway.

## Build from source

You need [uv](https://docs.astral.sh/uv/) and Python 3.13.

```
uv sync
uv run fdcad
```

Run the tests with `uv run pytest`. See `CONTRIBUTING.md` for the full developer setup.

## License

FDCAD is free software under the GNU General Public License, version 3 or later. See `LICENSE`. Third party components and their licenses are listed in `THIRD_PARTY_NOTICES.txt`, and `SOURCE_OFFER.md` says how to get the source of the GPL and LGPL components.

FDCAD is not affiliated with or endorsed by Dassault Systèmes or Robert McNeel and Associates; SOLIDWORKS, Rhinoceros and Grasshopper are their trademarks.

Copyright (C) 2026 the FDCAD contributors.
