"""Sketch editing operations behind the Phase 2 sketch tools (PHASE2_SPEC P2.8).

Each operation changes a :class:`~fdcad.core.sketch.model.Sketch` in place and
reports what it removed, so the tool can name it in the status bar. The caller
takes the undo checkpoint (CLAUDE.md rule 3). No Qt.
"""
