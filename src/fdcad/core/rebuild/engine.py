"""Incremental rebuild engine (PLAN section 5 item 4, section 11.3 items 1 and 2).

Each feature result is cached under a key made from the feature's own data, the
keys of the features it references and, when it uses the part, the key of the
part it starts from. After an edit only features whose key changed rebuild;
everything else is reused. Exceptions never escape (CLAUDE.md rule 7) and a
failed feature is skipped without collapsing the rest (PLAN 5A item 8).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from fdcad.core.cache.memory import ResultCache
from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.document.rollback import rolled_back
from fdcad.core.features import REGISTRY
from fdcad.core.features.base import (
    KEEP_SEPARATE_BODY,
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    without_kept_body_warning,
)
from fdcad.core.features.modify import lost_cause
from fdcad.core.features.solids import measured_volumes
from fdcad.core.io.fdef import feature_to_json_data
from fdcad.core.kernel import configure
from fdcad.core.naming.names import NamedShape
from fdcad.core.rebuild.values import refresh_values
from fdcad.core.units import ExpressionError, Kind

if TYPE_CHECKING:
    from fdcad.core.equations.engine import Solution

Progress = Callable[[int, int, str], None]
_TOPOLOGY_KINDS = {"face", "edge", "vertex"}


def document_variables(
    doc: Document, solution: Solution | None = None
) -> dict[str, tuple[Kind, float]]:
    """Every name a formula can use: global variables and feature values (D390).

    Pass the ``solution`` already made for ``doc`` to avoid solving twice (D432).
    Raises ExpressionError when a global variable has an error.
    """
    from fdcad.core.equations.engine import namespace, namespace_from

    return namespace(doc) if solution is None else namespace_from(doc, solution)


def _feature_refs(value: Any) -> list[str]:
    """Feature ids a ``refs`` value points at, at any depth."""
    out: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("feature"), str):
            out.append(value["feature"])
        for v in value.values():
            out.extend(_feature_refs(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_feature_refs(v))
    return out


def _uses_body(value: Any) -> bool:
    """True when ``refs`` points at faces, edges or vertices of the part."""
    if isinstance(value, dict):
        if value.get("kind") in _TOPOLOGY_KINDS:
            return True
        return any(_uses_body(v) for v in value.values())
    if isinstance(value, list):
        return any(_uses_body(v) for v in value)
    return False


@dataclass
class RebuildReport:
    """What a rebuild did."""

    results: dict[str, FeatureResult]
    rebuilt: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    cancelled: bool = False
    #: Features whose modelled threads were shown as cosmetic marks (TR347, D1921).
    simplified: list[str] = field(default_factory=list)
    variable_error: str | None = None
    seconds: float = 0.0
    body_count: int = 0
    #: Groups of identical bodies by Solid Bodies index, two or more each (TR308).
    body_groups: list[list[int]] = field(default_factory=list)
    #: Sketch id to its curves as 3D edges, filled after the rebuild for display (C1).
    sketch_edges: dict[str, Any] = field(default_factory=dict)
    #: Construction curves of sketches that show them in the part, by sketch id, for
    #: Convert Entities in later sketches (TR339, D1703).
    construction_edges: dict[str, Any] = field(default_factory=dict)
    #: The cosmetic thread pattern of every built feature, for display (P4.2).
    thread_edges: Any = None
    #: Graph id to the result of running its driving outputs (Phase 7).
    graphs: dict[str, Any] = field(default_factory=dict)
    #: What the changed feature did (TR290), filled by the rebuild worker, or None.
    change: Any = None
    #: The first feature that failed, when later features built on the part before it
    #: (TR352): the part shown is then not the one the tree describes.
    failed_at: str | None = None
    #: Expected value checks after this rebuild (TR359), filled by the rebuild worker.
    checks: list[Any] = field(default_factory=list)
    #: Variables whose value is not one they allow (TR274), as messages.
    variable_warnings: list[str] = field(default_factory=list)

    @property
    def body(self) -> NamedShape | None:
        """The finished part: the body of the last feature that built."""
        for result in reversed(self.results.values()):
            if result.body is not None:
                return result.body
        return None

    def slowest(self, count: int = 10) -> list[tuple[str, float]]:
        """Feature ids and build times, slowest first (rebuild statistics panel)."""
        times = [(fid, r.seconds) for fid, r in self.results.items() if fid in self.rebuilt]
        return sorted(times, key=lambda t: t[1], reverse=True)[:count]


class RebuildEngine:
    """Rebuilds documents and keeps results for the next rebuild."""

    def __init__(self, cache: ResultCache | None = None) -> None:
        configure()
        # An empty cache is falsy (it has a length), so ``cache or ...`` threw away a
        # cache passed in with its own limit and made a new one (D1065).
        self.cache = cache if cache is not None else ResultCache()
        #: Use Only Fully Defined Sketches (TR36 item 6, D763): a preference, off by default.
        self.full_sketches_only = False
        #: Simplify threads while editing (TR347, D1921): a preference, off by default;
        #: the part's own ``extra["simplify_threads"]`` wins when set.
        self.simplify_threads = False
        #: One rebuild with every thread modelled (Force Rebuild), then back (D1921).
        self.real_once = False
        #: The kept results of features above the freeze bar (TR98, D2507).
        self.frozen_results: dict[str, FeatureResult] = {}
        #: Called just before a feature is built (not for cached results) and once
        #: when a rebuild ends, however it ends. The app's crash guard notes the
        #: feature in a file, so a native fault in the kernel can be traced to it
        #: on the next start (D1035). Errors in them never stop a rebuild.
        self.on_build: Callable[[Feature], None] | None = None
        self.on_done: Callable[[], None] | None = None
        #: Each feature's data and the seconds its result took to build, from the last
        #: rebuild: how long the next one will take (``remote.estimate``, D2600).
        self.built: dict[str, tuple[Any, float]] = {}
        #: Keys of stored results on disk that hold this part's recent features, newest
        #: first: a rebuild in the helper process starts from them (D2600).
        self.history_keys: list[str] = []

    def rebuild(
        self,
        doc: Document,
        progress: Progress | None = None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> RebuildReport:
        """Bring every feature up to date, up to the rollback bar."""
        try:
            with measured_volumes():  # each shape measured once per rebuild (D2661)
                return self._rebuild(doc, progress, cancelled)
        finally:
            if self.on_done is not None:
                with contextlib.suppress(Exception):
                    self.on_done()

    def _rebuild(
        self,
        doc: Document,
        progress: Progress | None,
        cancelled: Callable[[], bool],
    ) -> RebuildReport:
        started = time.perf_counter()
        report = RebuildReport(results={})
        from fdcad.core.equations.engine import solve

        solution = solve(doc)
        try:
            variables = document_variables(doc, solution)
        except ExpressionError as exc:
            variables = dict(solution.namespace)
            report.variable_error = str(exc)
        refresh_values(doc, solution=solution)
        equation_errors = _equation_errors(doc, solution.errors)
        from fdcad.core.equations.allowed import problems

        report.variable_warnings = problems(doc)  # TR274: values outside what is allowed

        body: NamedShape | None = None
        body_key = ""
        # Features below the rollback bar never build, also when the feature just
        # above the bar is suppressed and so never reaches the break below.
        below_bar = set(rolled_back(doc))
        from fdcad.core.document.freeze import frozen

        frozen_ids = set(frozen(doc))
        active = [f for f in doc.features if not f.suppressed and f.id not in below_bar]
        from fdcad.core.features.linked_copy import deferred_order

        active = deferred_order(active)  # linked copies follow the whole part (TR154, D2417)
        flat_only = _flat_only(active)
        saved = SavedNumbers(doc, solution.values)  # D2626: the numbers the file keeps
        driver = _graph_driver(doc, cancelled)
        simplify = simplifies_threads(doc, self.simplify_threads)  # TR347 (D1921)
        if self.real_once:
            simplify, self.real_once = False, False
        for index, feature in enumerate(active):
            if cancelled():
                report.cancelled = True
                break
            if progress is not None:
                progress(index, len(active), feature.name)
            if driver is not None:
                variables, drove = _run_graphs(driver, feature, report, variables)
                if drove:
                    saved.changed()
            if feature.id in flat_only:
                report.results[feature.id] = _flat_only_result(feature, body)
                if doc.rollback == feature.id:
                    break
                continue
            ftype = REGISTRY.get(feature.type)
            uses_body = ftype is not None and (
                ftype.makes_solid or _uses_body(feature.refs) or ftype.reads_body(feature)
            )
            thin = simplify and has_modelled_thread(feature)  # TR347 (D1921)
            data: Any = None
            unsaved: str | None = None
            try:
                extra = ftype.key_data(feature, doc, report.results) if ftype else None
                if thin:
                    extra = [extra, "simplified threads"]
                data = saved.data(feature)
                key = self._key(feature, report.results, body_key if uses_body else "", extra, data)
            except (ValueError, TypeError):  # a value the file cannot keep (D2671)
                key, unsaved = "", unsaved_value(feature)
            cached = self.cache.get(key) if unsaved is None else None
            if feature.id in frozen_ids and unsaved is None:  # TR98 (D2507): last result
                kept = self.frozen_results.get(feature.id)
                if kept is not None:
                    key, cached = kept.key, kept
            problem = unsaved
            if problem is None and driver is not None:
                problem = driver.problems.get(feature.id)
            if problem is None and self.full_sketches_only:
                problem = _under_defined(feature, doc, report.results)
            if problem is not None:  # the graph cycle rule (PLAN Phase 7), TR36 item 6
                code = UNSAVED_VALUE if unsaved is not None else ""
                issue = Issue(FeatureState.ERROR, problem, code=code)
                result = FeatureResult(body=body, issues=[issue])
                result.key = key
                report.rebuilt.append(feature.id)
            elif cached is not None:
                result = cached if uses_body else replace(cached, body=body)
                report.reused.append(feature.id)
            else:
                work = saved.document()
                ctx = BuildContext(
                    work,
                    body,
                    report.results,
                    variables,
                    cancelled,
                    owner=feature.name,
                    simplify_threads=thin,
                )
                if self.on_build is not None:
                    with contextlib.suppress(Exception):
                        self.on_build(feature)
                t0 = time.perf_counter()
                result = _build(saved.feature(feature.id), ftype, ctx)
                result.seconds = time.perf_counter() - t0
                result.key = key
                report.rebuilt.append(feature.id)
                self.cache.put(key, result, body)  # D1065: sized by what it added
            if thin:
                report.simplified.append(feature.id)
            if feature.id in equation_errors:
                result = replace(result, issues=[*result.issues, equation_errors[feature.id]])
            result = without_kept_body_warning(feature, result)
            report.results[feature.id] = result
            if unsaved is None:
                self.built[feature.id] = (data, result.seconds)
            else:
                self.built.pop(feature.id, None)
            if feature.id in frozen_ids and result.state is not FeatureState.ERROR:
                self.frozen_results.setdefault(feature.id, result)
            elif feature.id not in frozen_ids:
                self.frozen_results.pop(feature.id, None)
            if _store_measured(doc, feature, result):
                variables, equation_errors, solved = _resolve_after_measure(doc, report)
                saved.changed(solved)  # values further down may have changed
            if result.state is not FeatureState.ERROR and uses_body:
                body, body_key = result.body, key
            if doc.rollback == feature.id:
                break
        from fdcad.core.rebuild.causes import add_causes

        add_causes(doc, active, report.results)  # name what took a lost face away (TR288)
        from fdcad.core.rebuild.split_faces import add_split_faces

        add_split_faces(doc, active, report.results)  # a picked face that split (D2628)
        _mark_not_rebuilt(active, report)  # TR352
        _drop_joined_body_warnings(active, report)  # D1047
        final = report.body
        if final is not None:
            from fdcad.core.features.solids import solids

            bodies = solids(final.shape)
            report.body_count = len(bodies)
            from fdcad.core.body_groups import identical_groups

            report.body_groups = identical_groups(bodies)  # TR308 (D958)
        if doc.properties:  # the part's own values for property formulas (TR82, D810)
            _store_part_measures(doc, final)
        report.seconds = time.perf_counter() - started
        return report

    @staticmethod
    def _key(
        feature: Feature,
        results: dict[str, FeatureResult],
        body_key: str,
        extra: Any = None,
        saved: Any = None,
    ) -> str:
        data = dict(to_json_data_feature(feature) if saved is None else saved)
        # Keeping a separate body only hides a warning (D527): it never changes geometry.
        data = {k: v for k, v in data.items() if k != KEEP_SEPARATE_BODY}
        deps = sorted(
            (fid, results[fid].key) for fid in set(_feature_refs(feature.refs)) if fid in results
        )
        parts: list[Any] = [data, deps, body_key]
        if extra is not None:  # data a feature reads from outside its own entry
            parts.append(extra)
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def simplifies_threads(doc: Document, default: bool) -> bool:
    """True when modelled threads show as cosmetic marks (TR347, D1921): the part's own
    setting, ``extra["simplify_threads"]``, else the app's ``default``."""
    own = doc.extra.get("simplify_threads")
    return own if isinstance(own, bool) else default


def has_modelled_thread(feature: Feature) -> bool:
    """True for a Thread, or a tapped hole with a modelled thread."""
    if feature.type == "modeled_thread":
        return True
    return feature.type == "hole" and feature.params.get("modeled_thread") is True


#: Issue code of a feature that built on the part from before a failed feature (TR352).
NOT_REBUILT = "not_rebuilt"

#: Issue code of a feature holding a value the part file cannot keep (D2671).
UNSAVED_VALUE = "unsaved_value"


def unsaved_value(feature: Feature) -> str:
    """The error for ``feature`` when it holds a value the part file cannot keep, such
    as nan or an infinite number (D2671): what failed, and what to do next."""
    for where, item in [*feature.params.items(), *feature.data.items(), ("refs", feature.refs)]:
        value = _first_not_finite(item)
        if value is not None:
            what = "is not a number" if math.isnan(value) else "is too large"
            return (
                f"{feature.name} failed: its value {where} {what} ({value}). Type a new "
                "value for it, or undo the change that set it."
            )
    return (
        f"{feature.name} failed: it holds a value of a kind the part file cannot keep. "
        "Undo the last change, then rebuild."
    )


def _first_not_finite(value: Any) -> float | None:
    """The first nan or infinite number in ``value``, at any depth, or None."""
    if isinstance(value, Param):
        value = value.value
    if isinstance(value, float):
        return None if math.isfinite(value) else value
    items: Iterable[Any] = ()
    if isinstance(value, dict):
        items = value.values()
    elif isinstance(value, list | tuple):
        items = value
    for item in items:
        found = _first_not_finite(item)
        if found is not None:
            return found
    return None


def _drop_joined_body_warnings(active: list[Feature], report: RebuildReport) -> None:
    """Take the "created a separate body" warning off a feature whose body a later
    feature joined to the part (D1047).

    A frame is built tube by tube: the head tube stands alone until the top tube
    reaches it. The warning stayed on the head tube for good, though the part was one
    body again. It goes when any later feature leaves fewer bodies than the feature
    with the warning did. Results are kept for the next rebuild, so the report gets a
    copy without the warning and the kept result is not changed: the warning is back
    when the joining feature is deleted or suppressed.
    """
    from fdcad.core.features.solids import solids

    def count(fid: str) -> int | None:
        result = report.results.get(fid)
        if result is None or result.body is None or result.state is FeatureState.ERROR:
            return None
        return len(solids(result.body.shape))

    for index, feature in enumerate(active):
        result = report.results.get(feature.id)
        if result is None or not any(i.code == "separate_body" for i in result.issues):
            continue
        own = count(feature.id)
        if own is None:
            continue
        later = [count(f.id) for f in active[index + 1 :]]
        if any(n is not None and n < own for n in later):
            kept = [i for i in result.issues if i.code != "separate_body"]
            report.results[feature.id] = replace(result, issues=kept)


def _mark_not_rebuilt(active: list[Feature], report: RebuildReport) -> None:
    """After the first failed solid feature, every later solid feature built on the part
    from before it. Mark each one, and the report, so nobody takes that part as the real
    one (TR352, D881)."""
    failed: Feature | None = None
    for feature in active:
        result = report.results.get(feature.id)
        ftype = REGISTRY.get(feature.type)
        if result is None or ftype is None or not ftype.makes_solid:
            continue
        if failed is None:
            if result.state is FeatureState.ERROR:
                failed = feature
                report.failed_at = feature.id
            continue
        if result.state is FeatureState.ERROR:
            continue
        note = Issue(
            FeatureState.WARNING,
            f"{feature.name} is not rebuilt: {failed.name} failed above it, so it was built "
            f"on the part from before {failed.name}. Fix {failed.name} first.",
            code=NOT_REBUILT,
        )
        report.results[feature.id] = replace(result, issues=[*result.issues, note])


def _flat_only(active: list[Feature]) -> set[str]:
    """Features below a Flat Pattern that is off: they apply to the flat state only (D339).

    With several sheets (TR281, D2312) a Flat Pattern holds only for the features of
    its own Sheet Metal folder: a feature of another folder below it is built as usual.
    A Flat Pattern without a folder, and a feature without one, keep the old rule."""
    from fdcad.core.features.sheetmetal.common import folder_id

    out: set[str] = set()
    folded: set[str] = set()
    for feature in active:
        mine = folder_id(feature)
        if folded and (not mine or "" in folded or mine in folded):
            out.add(feature.id)
        elif feature.type == "flatten" and feature.params.get("flattened", False) is not True:
            folded.add(mine)
    return out


def _flat_only_result(feature: Feature, body: NamedShape | None) -> FeatureResult:
    return FeatureResult(
        body=body,
        issues=[
            Issue(
                FeatureState.WARNING,
                f"{feature.name} applies to the flat pattern only. Turn on Flatten to see it.",
                code="flat_only",
            )
        ],
    )


def _graph_driver(doc: Document, cancelled: Callable[[], bool]) -> Any:
    """The graph runner for this rebuild, or None when the part has no graphs."""
    if not doc.graphs:
        return None
    from fdcad.core.graph.drive import GraphDriver

    return GraphDriver(doc, cancelled)


def _run_graphs(
    driver: Any, feature: Feature, report: RebuildReport, variables: dict[str, tuple[Kind, float]]
) -> tuple[dict[str, tuple[Kind, float]], bool]:
    """Run the graphs positioned above ``feature`` and apply what they drive. True with
    the variables when the part's values may have changed."""
    drove = False
    for graph in driver.due(feature):
        new = driver.run(graph, report.results, variables)
        report.graphs[graph.id] = driver.results[graph.id]
        if new is not None:
            variables = new
        if new is not None or driver.params:
            refresh_values(driver.doc, variables)
            driver.apply_params()
            drove = True
    return variables, drove


class SavedNumbers:
    """The part as its file keeps it, for one rebuild (IDEAS 49, DECISIONS D2626).

    A part file keeps numbers to twelve significant digits. Building from the full
    numbers in memory let a session and the same part opened from its file differ
    where a kernel result hangs on the last digits (D1049, D1052, D1053). Each
    feature is built from its saved data read back, the same copy the cache key is
    made from, and ``BuildContext.document`` is the part made of such copies, so a
    feature that reads another (a pattern's seeds, a derived sketch) gets saved
    numbers too. The document itself keeps its numbers.

    A typed value that the equations solve worked out from its text in this rebuild
    (``solved``, its cell keys) keeps its full value: the file keeps the text, and
    opening the file works the value out again the same way. Rounding it would only
    lose digits, and an angle such as 360 degrees would come out just over a turn.

    The saved data of each feature is made once and also serves the cache key; the
    copy of the part is made only when a feature has to build, and made again after
    a graph or a measured value changes values further down.
    """

    def __init__(self, doc: Document, solved: Iterable[str] = ()) -> None:
        self.doc = doc
        self.solved = set(solved)
        self._data: dict[str, Any] = {}
        self._copy: Document | None = None
        self._features: dict[str, Feature] = {}

    def data(self, feature: Feature) -> Any:
        """``feature`` as the file writes it. Shared: callers must not change it."""
        found = self._data.get(feature.id)
        if found is None:
            found = self._data[feature.id] = to_json_data_feature(feature)
        return found

    def document(self) -> Document:
        """A shallow copy of the part whose features are their saved data read back."""
        if self._copy is None:
            import copy

            work = copy.copy(self.doc)
            work.features = [self._saved_copy(f) for f in self.doc.features]
            self._copy, self._features = work, {f.id: f for f in work.features}
        return self._copy

    def _saved_copy(self, feature: Feature) -> Feature:
        """``feature`` read back from its saved data, or ``feature`` itself when the file
        cannot keep it as it stands (D2670).

        The copy of the part holds every feature, also those that never build in this
        rebuild (suppressed, below the rollback bar). A value the file cannot write, such
        as nan in one of those, made every rebuild of the part raise. A feature that
        does build still stops at its own cache key, as before D2626.
        """
        from fdcad.core.io.fdef import feature_from_json_data

        try:
            return self._solved_values(feature, feature_from_json_data(self.data(feature)))
        except (ValueError, TypeError):  # FileFormatError is a ValueError
            return feature

    def _solved_values(self, feature: Feature, saved: Feature) -> Feature:
        """``saved`` with the full values of the typed values solved from their text."""
        for name, value in feature.params.items():
            kept = saved.params.get(name)
            if (
                isinstance(value, Param)
                and isinstance(kept, Param)
                and f"param:{feature.id}:{name}" in self.solved
            ):
                saved.params[name] = Param(kept.expr, value.value)
        dims = feature.data.get("dimensions") if feature.type == "sketch" else None
        copies = saved.data.get("dimensions")
        if isinstance(dims, list) and isinstance(copies, list) and len(dims) == len(copies):
            out = []
            for dim, raw in zip(dims, copies, strict=True):
                param = dim.get("param") if isinstance(dim, dict) else None
                stored = raw.get("param") if isinstance(raw, dict) else None
                if (
                    isinstance(param, Param)
                    and isinstance(stored, dict)
                    and f"dim:{feature.id}:{dim.get('id')}" in self.solved
                ):
                    # A new entry: the saved data is shared with the cache key.
                    raw = {**raw, "param": {**stored, "value": param.value}}
                out.append(raw)
            saved.data["dimensions"] = out
        return saved

    def feature(self, fid: str) -> Feature:
        """The saved copy of feature ``fid``, as found in ``document()``."""
        self.document()
        return self._features[fid]

    def changed(self, solved: Iterable[str] = ()) -> None:
        """The part's values changed during the rebuild: make the copies again.

        ``solved`` adds the cells a new solve worked out (D2673): a formula that fails
        on the 0 a measured value has before the first rebuild of a part just opened is
        solved after the measure, and keeps its full value as a later rebuild does."""
        self.solved.update(solved)
        self._data.clear()
        self._copy, self._features = None, {}


def _store_measured(doc: Document, feature: Feature, result: FeatureResult) -> bool:
    """Keep the values ``feature`` measured (TR57). True when one changed."""
    from fdcad.core.equations.engine import MEASURED_VALUES

    names = MEASURED_VALUES.get(feature.type, ())
    if not names or result.state is FeatureState.ERROR:
        return False
    old = doc.measured.get(feature.id, {})
    new = {}
    for name in names:
        value = result.extras.get(name)
        # nan or inf is never kept: formulas would pass it on, or not, by chance (D2671).
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if math.isfinite(value):
            new[name] = float(value)
    if not new or new == old:
        return False
    doc.measured[feature.id] = new
    return True


def _resolve_after_measure(
    doc: Document, report: RebuildReport
) -> tuple[dict[str, tuple[Kind, float]], dict[str, Issue], list[str]]:
    """Solve the part again so features further down use a value just measured.

    Features below take their values from this solve; those above were built already
    and keep theirs, so a formula never feeds back into the feature it measures. Also
    gives the cells the solve worked out (D2673).
    """
    from fdcad.core.equations.engine import solve

    solution = solve(doc)
    try:
        variables = document_variables(doc, solution)
    except ExpressionError as exc:
        variables = dict(solution.namespace)
        report.variable_error = str(exc)
    refresh_values(doc, solution=solution)
    return variables, _equation_errors(doc, solution.errors), list(solution.values)


def _measured_order_errors(doc: Document) -> dict[str, str]:
    """Formulas that use a measured value of their own feature or of one further down
    the tree: that value is not known yet when they build (TR57)."""
    from fdcad.core.equations.engine import MEASURED_VALUES, cells
    from fdcad.core.units.expressions import references

    position = {f.id: i for i, f in enumerate(doc.features)}
    owners: dict[str, Feature] = {}
    for feature in doc.features:
        for name in MEASURED_VALUES.get(feature.type, ()):
            owners[f"{name}@{feature.name}"] = feature
            owners[f"{name}@{feature.id}"] = feature
    if not owners:
        return {}
    out: dict[str, str] = {}
    for cell in cells(doc):
        if cell.fid is None or cell.fid not in position:
            continue
        for used in references(cell.expr):
            owner = owners.get(used)
            if owner is not None and position[owner.id] >= position[cell.fid]:
                out[cell.key] = (
                    f'Uses "{used}", which is measured when {owner.name} builds. '
                    f"Move this feature below {owner.name} or type a value."
                )
                break
    return out


def _equation_errors(doc: Document, errors: dict[str, str]) -> dict[str, Issue]:
    """One error per feature whose value or suppression formula cannot be solved (D390)."""
    errors = {**errors, **_measured_order_errors(doc)}
    out: dict[str, Issue] = {}
    for key, message in errors.items():
        parts = key.split(":")
        if parts[0] not in ("param", "dim", "suppress") or len(parts) < 2:
            continue
        fid = parts[1]
        if fid in out:
            continue
        try:
            name = doc.feature(fid).name
        except KeyError:
            continue
        what = parts[2] if len(parts) > 2 else "suppression"
        out[fid] = Issue(
            FeatureState.ERROR,
            f"{name}: the formula of {what} cannot be solved. {message}",
            code="equation",
        )
    return out


def to_json_data_feature(feature: Feature) -> Any:
    """Canonical JSON data of one feature, as saved in the file."""
    return feature_to_json_data(feature)


_MISSING_REFERENCE = re.compile(r"missing reference (f\d+)/")


def _suppressed_reference(message: str, ctx: BuildContext) -> str | None:
    """A clearer message when a missing face, edge or vertex was made by a suppressed
    feature: unsuppress it, rather than reselect (D431)."""
    match = _MISSING_REFERENCE.search(message)
    if match is None:
        return None
    try:
        feature = ctx.document.feature(match.group(1))
    except KeyError:
        return None
    return ctx.missing_message(feature.id) if feature.suppressed else None


def _sheet_result_types() -> frozenset[str]:
    from fdcad.core.features.sheetmetal.common import SHEET_TYPES

    return frozenset((*SHEET_TYPES, "stamp", "sheet_tab"))


_SHEET_RESULT_TYPES = _sheet_result_types()


def _build(feature: Feature, ftype: FeatureType | None, ctx: BuildContext) -> FeatureResult:
    if ftype is None:
        return FeatureResult(
            body=ctx.body,
            issues=[
                Issue(
                    FeatureState.ERROR,
                    f"{feature.name} is a '{feature.type}' feature, which this version of "
                    "FDCAD cannot build. Update FDCAD.",
                )
            ],
        )
    try:
        ftype.validate(feature)
        result = ftype.execute(feature, ctx)
        if feature.type in _SHEET_RESULT_TYPES:  # TR281 (D2312): several sheet bodies
            from fdcad.core.features.sheetmetal.common import with_other_bodies

            result = with_other_bodies(feature, ctx, result)  # type: ignore[assignment]
        return result
    except FeatureError as exc:
        message = _suppressed_reference(str(exc), ctx) or str(exc)
        cause = lost_cause(ctx, exc.highlight)
        if cause and cause not in message:
            message = f"{message} {cause}"
        return FeatureResult(
            body=ctx.body, issues=[Issue(FeatureState.ERROR, message, exc.fixes, exc.highlight)]
        )
    except Exception as exc:  # kernel or unexpected failure: never crash the app
        return FeatureResult(
            body=ctx.body,
            issues=[
                Issue(
                    FeatureState.ERROR,
                    f"{feature.name} failed in the geometry kernel ({type(exc).__name__}). "
                    "Change its values slightly or rebuild.",
                )
            ],
        )


def _under_defined(
    feature: Feature, doc: Document, results: dict[str, FeatureResult]
) -> str | None:
    """Why a feature may not use its sketch while Use Only Fully Defined Sketches is on,
    or None (TR36 item 6). Only the sketch a feature is built from counts."""
    from fdcad.core.sketch.solver import SketchStatus

    if feature.type == "sketch":
        return None
    ref = feature.refs.get("sketch")
    sid = ref.get("feature") if isinstance(ref, dict) else None
    result = results.get(sid) if isinstance(sid, str) else None
    output = result.sketch if result is not None else None
    if output is None or output.solve.status is not SketchStatus.UNDER:
        return None
    name = doc.feature(str(sid)).name
    return (
        f"{feature.name} uses {name}, which is not fully defined. Use Fully Define Sketch "
        f"on {name}, or turn off Use Only Fully Defined Sketches in the preferences."
    )


#: Where the part's own measures are kept in ``Document.measured`` (TR82).
PART_KEY = "__part__"


def _store_part_measures(doc: Document, body: NamedShape | None) -> None:
    """The finished part's volume (mm3), surface area (mm2) and, with a material, mass
    (g), for property formulas (``"mass@Part"``)."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.materials import part_material
    from fdcad.core.named_items import measure

    measure(doc, body)  # named faces and edges (TR152, D2105)
    if body is None:
        doc.measured.pop(PART_KEY, None)
        return
    vprops, sprops = GProp_GProps(), GProp_GProps()
    try:
        BRepGProp.VolumeProperties_s(body.shape, vprops)
        BRepGProp.SurfaceProperties_s(body.shape, sprops)
    except Exception:  # a damaged body: leave the values out
        doc.measured.pop(PART_KEY, None)
        return
    volume, area = abs(vprops.Mass()), sprops.Mass()
    values = {"volume": volume, "area": area}
    material = part_material(doc)
    if material is not None:
        values["mass"] = volume * material.density / 1000.0
    doc.measured[PART_KEY] = values
