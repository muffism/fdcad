"""A configuration built on a copy, for a preview that does not make it active (TR197
item 2, D2101). Kernel work: run it off the UI thread. No Qt."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document


@dataclass
class Preview:
    """The built shape of one configuration (None when it has none), its part colour
    and how many features failed."""

    name: str
    shape: Any
    color: str
    failed: int


def build(doc: Document, name: str, cancelled: Callable[[], bool] = lambda: False) -> Preview:
    """Build configuration ``name`` of a copy of ``doc``. The part itself is not changed.
    Raises ConfigurationError when there is no such configuration."""
    from fdcad.core.features.base import FeatureState
    from fdcad.core.rebuild.engine import RebuildEngine

    part = copy.deepcopy(doc)
    if name not in configs.names(part):
        raise configs.ConfigurationError(
            f'There is no configuration named "{name}". Pick one in the configurations panel.'
        )
    configs.activate(part, name)
    report = RebuildEngine().rebuild(part, cancelled=cancelled)
    failed = sum(1 for r in report.results.values() if r.state is FeatureState.ERROR)
    shape = report.body.shape if report.body is not None and not report.cancelled else None
    return Preview(name, shape, str(configs.get_value(part, configs.PART_COLOR)), failed)


def colours_vary(doc: Document) -> bool:
    """True when face, feature and body colours are set per configuration."""
    return configs.PART_COLORS in configs.configured_paths(doc)


def set_colours_vary(doc: Document, on: bool) -> None:
    """Set face, feature and body colours per configuration (each starts with the
    current colours), or share them again (every configuration takes the current ones)."""
    if not on:
        configs.unconfigure(doc, configs.PART_COLORS)
        return
    configs.sync_active(doc)
    current = configs.get_value(doc, configs.PART_COLORS)
    for item in configs.items(doc):
        item["overrides"][configs.PART_COLORS] = copy.deepcopy(current)
    configs.normalize(doc)
