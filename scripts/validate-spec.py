#!/usr/bin/env python3
"""Pre-POST static validation for a Sigma workbook spec.

The Sigma POST/PUT endpoints accept structurally broken specs and silently
rewrite the layout — most notably, per-page `pages[].layout` fields are
discarded, and container children stack into a 1/13-wide single column when
not nested inside their container tag in the layout XML.

Handles BOTH schema generations:

  * current  — `{name, document: {pages: [{id,name}], elements: [...], layout}}`
               with `<Container>` / `<Element>` layout tags
  * legacy   — `{pages: [{id, elements: [...]}], layout}` with
               `<GridContainer>` / `<LayoutElement>` tags

and warns when it sees the legacy layout tags, which are a masked 400 on the
current API rather than a clear error.

Run before every POST/PUT:

    python3 scripts/validate-spec.py workbooks/<name>/spec.json

Exits 0 on success, non-zero on any issue (one issue per line on stderr).
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET


# The check list is built in main(); this is documentation only.
#   no-per-page-layout · elements-placed-in-layout · containers-have-children
#   legacy-layout-tags · column-format-kind · control-id-unique · element-shape
#   overlapping-siblings
# plus three advisory passes — `completeness`, `auto-rows-fixed-container` and
# `period-scoping` — which warn but never fail.

# Layout tag vocabulary. The current API renamed these; the old names are
# accepted by this linter so legacy specs still lint, but flagged.
CONTAINER_TAGS = ("Container", "GridContainer")
ELEMENT_TAGS = ("Element", "LayoutElement")
# <TabbedContainer> places its element too — without it here, every persona-tab
# build reports its tabbed container as "not placed in the layout" (a false
# positive that fired on a known-good 172-element workbook).
PLACED_TAGS = CONTAINER_TAGS + ELEMENT_TAGS + ("TabbedContainer",)
LEGACY_TAGS = ("GridContainer", "LayoutElement")


def _doc(spec: dict) -> dict:
    """The spec body, whether or not it is wrapped in `document`."""
    return spec.get("document") or spec


def _layout(spec: dict) -> str:
    d = _doc(spec)
    return d.get("layout") or spec.get("layout") or ""


def _elements(spec: dict):
    """Yield (locator, element) for both the flat and the per-page shapes."""
    d = _doc(spec)
    flat = d.get("elements")
    if isinstance(flat, list):
        for i, el in enumerate(flat):
            yield f"elements[{i}]", el
        return
    for pi, page in enumerate(d.get("pages", []) or []):
        for ei, el in enumerate(page.get("elements", []) or []):
            yield f"pages[{pi}].elements[{ei}]", el


def issues_per_page_layout(spec: dict) -> list[str]:
    issues = []
    for i, p in enumerate(_doc(spec).get("pages", []) or []):
        if p.get("layout"):
            issues.append(
                f"pages[{i}] ({p.get('id')}): has a per-page `layout` field. "
                "Sigma silently discards it — move to the top-level `layout` "
                "string with all <Page> elements as siblings."
            )
    return issues


def _parse_layout(layout: str) -> ET.Element | None:
    if not layout:
        return None
    # Multi-page layout is multiple <Page> siblings under one <?xml ... ?> decl —
    # not a valid single-root XML doc. Wrap to parse.
    cleaned = re.sub(r"<\?xml[^?]*\?>", "", layout).strip()
    wrapped = f"<root>{cleaned}</root>"
    try:
        return ET.fromstring(wrapped)
    except ET.ParseError as e:
        sys.stderr.write(f"validate-spec: layout XML failed to parse: {e}\n")
        return None


def issues_elements_placed(spec: dict, root: ET.Element | None) -> list[str]:
    if root is None:
        return ["no top-level `layout` field — workbook will have an auto-generated layout"]
    placed_ids = {
        el.get("elementId") for el in root.iter() if el.tag in PLACED_TAGS
    }
    issues = []
    for loc, el in _elements(spec):
        eid = el.get("id")
        if eid and eid not in placed_ids:
            issues.append(
                f"{loc} ({eid}, kind={el.get('kind')}): not placed in the layout "
                "XML — the current API rejects this outright; older versions "
                "rendered it at the page bottom or not at all."
            )
    return issues


def issues_containers_have_children(spec: dict, root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    container_ids = [
        el.get("id") for _, el in _elements(spec) if el.get("kind") == "container"
    ]
    by_id = {
        el.get("elementId"): el
        for el in root.iter()
        if el.tag in CONTAINER_TAGS
    }
    issues = []
    for cid in container_ids:
        gc = by_id.get(cid)
        if gc is None:
            issues.append(
                f"container element `{cid}`: no matching <Container> in layout XML."
            )
        elif len(list(gc)) == 0:
            issues.append(
                f"container element `{cid}`: <Container> has no nested children. "
                "Children must be nested INSIDE the container tag, not flat siblings."
            )
    return issues


def issues_legacy_layout_tags(spec: dict, root: ET.Element | None) -> list[str]:
    """<GridContainer>/<LayoutElement> were renamed to <Container>/<Element>.

    The current API returns a MASKED 400 ("An error has occurred, incident-id=…")
    for the old tags rather than naming them, so this is worth catching here.
    """
    if root is None:
        return []
    found = sorted({el.tag for el in root.iter() if el.tag in LEGACY_TAGS})
    if not found:
        return []
    rename = {"GridContainer": "Container", "LayoutElement": "Element"}
    return [
        "layout XML uses the legacy tag <%s> — rename to <%s>. The current API "
        "rejects the old tags with a masked 400 that does not name them."
        % (t, rename[t]) for t in found
    ]


def issues_column_format(spec: dict) -> list[str]:
    """`format` needs a `kind` — a bare/legacy shape returns a misleading error."""
    issues = []
    for loc, el in _elements(spec):
        for ci, col in enumerate(el.get("columns", []) or []):
            fmt = col.get("format")
            if isinstance(fmt, dict) and "kind" not in fmt:
                issues.append(
                    f"{loc}.columns[{ci}] ({col.get('id')}): `format` is missing "
                    "`kind` — Sigma rejects with 'Missing \"kind\" field'. Use "
                    "e.g. {\"kind\": \"number\", \"formatString\": \"$,.0f\"}."
                )
    return issues


def issues_element_shape(spec: dict) -> list[str]:
    """Shape mistakes the API rejects, or (worse) accepts and silently drops.

    Every one of these was paid for once on a live build; none of them is
    visible in a diff of the generated spec.
    """
    issues = []
    for loc, el in _elements(spec):
        eid, kind = el.get("id"), el.get("kind")
        style = el.get("style") or {}

        if isinstance(style, dict) and "backgroundImage" in style:
            issues.append(
                f"{loc} ({eid}): `backgroundImage` is inside `style`. It is a "
                "TOP-LEVEL element field — inside `style` it is silently dropped "
                "and the element renders with no background art. Use "
                '{"backgroundImage": {"source": {"kind": "url", "url": …}, '
                '"style": {"fit": "cover"}}}.'
            )

        pad = style.get("padding") if isinstance(style, dict) else None
        if pad is not None and pad != "none":
            issues.append(
                f"{loc} ({eid}): style.padding={pad!r}. Only \"none\" is accepted "
                "— default padding is implied by omitting the field."
            )

        if pad == "none" and isinstance(style, dict) and (
            "borderWidth" in style or "borderColor" in style
        ):
            issues.append(
                f"{loc} ({eid}): style.padding=\"none\" together with "
                "borderWidth/borderColor. The API rejects this outright: "
                "\"border fields require default padding\". Drop the padding, "
                "not the border — a bordered card wants the default padding "
                "anyway."
            )

        if kind == "text":
            body = el.get("body")
            if isinstance(body, str):
                for line in body.splitlines():
                    if re.match(r"\s*#{4,}\s", line):
                        issues.append(
                            f"{loc} ({eid}): text body uses a level-4+ markdown "
                            "heading. Only #, ## and ### are supported — deeper "
                            "levels are a hard 400. Use ### or bold text in a "
                            "coloured <span>."
                        )
                        break

        if kind == "image" and "url" in el and "source" not in el:
            issues.append(
                f"{loc} ({eid}): image has a bare `url`. It needs the source "
                'envelope: {"source": {"kind": "url", "url": …}} — a bare url '
                'fails as `Invalid kind: "image"`.'
            )

        for ci, col in enumerate(el.get("columns", []) or []):
            name = col.get("name")
            if isinstance(name, str) and "/" in name:
                issues.append(
                    f"{loc}.columns[{ci}] ({col.get('id')}): column name "
                    f"{name!r} contains '/'. Inside a [Bracket Reference] a slash "
                    "is the SOURCE qualifier, so any formula referencing this "
                    "column resolves it as source/column and fails with Unknown "
                    "column, cascading as 'Reference to errored column'."
                )
            if kind == "input-table" and col.get("hidden"):
                issues.append(
                    f"{loc}.columns[{ci}] ({col.get('id')}): `hidden: true` on an "
                    "input-table column DROPS the column rather than hiding it. "
                    "Anything referencing it will report 'Reference to errored "
                    "column'. Inline the formula or leave the column visible."
                )

        for fi, cf in enumerate(el.get("conditionalFormats", []) or []):
            if "columnId" in cf or "format" in cf:
                issues.append(
                    f"{loc}.conditionalFormats[{fi}]: wrong envelope. Use "
                    '{"type": "single", "columnIds": [...], "condition": ..., '
                    '"value": ..., "style": {...}} — not `columnId`/`format`.'
                )

        for ai, act in enumerate(el.get("actions", []) or []):
            for ei, eff in enumerate(act.get("effects", []) or []):
                name = eff.get("effect")
                where = f"{loc}.actions[{ai}].effects[{ei}]"
                if name == "open-overlay" and "overlayId" not in eff:
                    issues.append(
                        f"{where}: open-overlay takes `overlayId`, not `overlay`/`target`."
                    )
                if name == "close-overlay" and len(eff) > 1:
                    issues.append(
                        f"{where}: close-overlay takes no argument beyond `effect`."
                    )
                if name == "open-url" and "openTarget" not in eff:
                    issues.append(
                        f"{where}: open-url REQUIRES `openTarget` "
                        '("_self" | "_blank" | "_parent"). Omitting it is '
                        'rejected as `Invalid kind: "button"`, which names the '
                        "element rather than the missing field."
                    )

        x_axis = el.get("xAxis")
        if isinstance(x_axis, dict) and isinstance(x_axis.get("sort"), list):
            issues.append(
                f"{loc} ({eid}): xAxis.sort is a LIST. On an axis it is a single "
                'object — {"direction": "descending", "by": "<columnId>"}. '
                "(`groupings[].sort` IS a list, which is what makes this easy to "
                "get backwards.)"
            )

        if kind == "combo-chart":
            y = el.get("yAxis")
            # Current schema: {"columnIds": [...]}. Legacy specs (and UI
            # round-trips) carry a bare list here, so normalise before reading.
            series_list = y.get("columnIds", []) if isinstance(y, dict) else (y or [])
            for si, series in enumerate(series_list or []):
                if si == 0:
                    continue
                if isinstance(series, dict) and series.get("type") == "bar":
                    issues.append(
                        f"{loc} ({eid}): yAxis.columnIds[{si}] asks for "
                        'type "bar". On a combo chart ONLY series[0] can be a '
                        "bar — every later series is rewritten to `line` on "
                        "write, with a 200 and no warning. For grouped bars use "
                        "a `bar-chart` with a category column instead."
                    )
    return issues


def issues_completeness(spec: dict) -> list[str]:
    """Advisory only: flag a command center that stopped at 'charts on a page'.

    Not a correctness check — it never fails the build. It exists because the
    most common defect in a generated dashboard is not a broken element, it is a
    missing interaction layer, and nothing else in the pipeline notices.
    See reference/command-center-recipes.md §0.
    """
    kinds = {el.get("kind") for _loc, el in _elements(spec)}
    n = sum(1 for _ in _elements(spec))
    missing = []
    if "navigation" not in kinds:
        missing.append("a `navigation` element in the masthead (§12)")
    if "tabbed-container" not in kinds:
        missing.append("persona tabs — Executive vs Field Operations (§14)")
    if "progress" not in kinds:
        missing.append("a per-entity card grid with progress rings (§15)")
    if not (_doc(spec).get("overlays") or []):
        missing.append("drill-through overlays — modal and/or drawer (§17)")
    if not _doc(spec).get("agents"):
        missing.append("an in-workbook agent (§10)")
    if not missing:
        return []
    return [
        "%d elements. Missing: %s. A finished command center is ~170 elements; a "
        "build that stops at the chart layer lands near 50. This is advisory — "
        "see reference/command-center-recipes.md §0." % (n, "; ".join(missing))
    ]


# Element kinds that show a POINT-IN-TIME number rather than a series over time.
# A time-series chart legitimately spans every month in the base table; a KPI
# card, a scorecard row or a choropleth does not.
_SNAPSHOT_KINDS = ("kpi-chart", "table", "pivot-table", "region-map", "progress")
# Bare aggregates that DOUBLE when they span two periods. The `*If` variants are
# deliberately excluded: an author writing SumIf/MaxIf is already conditioning the
# aggregate. Min/Max are excluded on purpose too — over a period-invariant column
# (a plan target, a rate) they return the same answer across 12 months or 24, so
# flagging them is pure noise.
_BARE_AGG = re.compile(r"\b(?:Sum|Avg|Count|CountDistinct)\s*\(")
# A column reference to the time dimension. An element broken out BY time is a
# series and legitimately spans both periods — a trend chart, or a pivot with
# quarters across the top.
_TIME_DIM = re.compile(r"/(?:Period|Quarter|Month|Week|Day|Date)\s*\]")


def issues_period_scoping(spec: dict) -> list[str]:
    """Advisory: a snapshot measure that forgot to scope to the current period.

    The canonical base table (examples/base-table-snowflake.sql) holds TWO
    periods — 24 months split by a `Period Name` column into "Current Period"
    and "Prior Period". Every comparative KPI depends on that split.

    The trap: `Sum([Book/RMR]) / 12` reads like "trailing twelve months" and is
    not. It sums all 24 months and divides by 12, so it returns roughly DOUBLE.
    It renders as a perfectly plausible number, which is why it survives review
    — the tell is that the scorecard stops reconciling with the KPI band, and
    nobody adds up the column. Caught on a real build only by exporting a PNG
    and summing the rows by hand.

    Correct form:  SumIf([Book/RMR], [Book/Period Name] = "Current Period") / 12

    The one false-positive class worth knowing: if a date-range control filters
    the source table, the control does the scoping and a bare `Sum(...)` is
    correct. Judge it on the DEFAULT state, though — a control with no value
    selected filters nothing, so the view an audience sees on first load still
    spans both periods.

    Advisory only — a single-period base table has no `Period Name` column, and
    this never fires there.
    """
    has_period_split = any(
        isinstance(col, dict)
        and (col.get("name") or "").strip().lower() == "period name"
        for _loc, el in _elements(spec)
        for col in (el.get("columns", []) or [])
    )
    if not has_period_split:
        return []

    issues = []
    for loc, el in _elements(spec):
        if el.get("kind") not in _SNAPSHOT_KINDS:
            continue
        cols = el.get("columns", []) or []
        # Broken out by time somewhere in the element -> it is a series, not a
        # snapshot. Exempt it.
        if any(
            isinstance(c, dict) and _TIME_DIM.search(c.get("formula") or "")
            for c in cols
        ):
            continue
        for ci, col in enumerate(cols):
            if not isinstance(col, dict):
                continue
            f = col.get("formula")
            if not isinstance(f, str) or "Period Name" in f:
                continue
            if _BARE_AGG.search(f):
                issues.append(
                    "%s.columns[%d] (%s) on a %s: %s"
                    % (loc, ci, col.get("id"), el.get("kind"), f[:90])
                )

    if not issues:
        return []
    # One explanation, then the locations. Emitting the full rationale per hit
    # buried a 200-element workbook under a dozen identical paragraphs, which
    # trains people to scroll past the advisory entirely.
    shown, extra = issues[:6], len(issues) - 6
    return [
        "%d aggregate(s) have no `Period Name` predicate. The base table holds "
        "BOTH periods, so these span 24 months, not 12 — wrap in "
        'SumIf(..., [<src>/Period Name] = "Current Period"). Ignore where a '
        "date-range control scopes the source instead, but judge that on the "
        "DEFAULT state: an unset control filters nothing.\n%s"
        % (
            len(issues),
            "\n".join(
                ["    " + m for m in shown]
                + (["    … and %d more" % extra] if extra > 0 else [])
            ),
        )
    ]


def is_legacy_getback(spec: dict, root: ET.Element | None) -> bool:
    """Is this a GET-back of a UI-built workbook rather than a create payload?

    `GET /v2/workbooks/{id}/spec` returns the pre-August-2026 nested shape —
    `pages[].elements[...]` with `<LayoutElement>` tags. Linting one produces a
    finding for essentially every element, which reads as "this tool is broken"
    unless you know the shape is simply older. The repo's own bundled examples
    are all GET-backs, so this fires on the first thing most people try.
    """
    nested = "document" not in spec and any(
        isinstance(p, dict) and p.get("elements")
        for p in (spec.get("pages") or [])
    )
    legacy_tags = root is not None and any(
        el.tag in LEGACY_TAGS for el in root.iter()
    )
    return nested or legacy_tags


def _span(val):
    """Parse a `gridColumn`/`gridRow` value like "3 / 9" into (start, end)."""
    if not val:
        return None
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)\s*$", val)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return (a, b) if b > a else None


def issues_overlapping_siblings(_spec: dict, root: ET.Element | None) -> list[str]:
    """Two siblings occupying the same grid cells.

    Invisible in the spec, obvious in a screenshot: the later element paints over
    the earlier one, or the renderer reflows both. Caught this on a five-row
    alert card where the meta line and the body both claimed rows 3-6 and the
    meta rendered ABOVE the body.
    """
    if root is None:
        return []
    issues = []
    for parent in root.iter():
        kids = [k for k in parent if k.tag in PLACED_TAGS and k.get("elementId")]
        rects = []
        for k in kids:
            col, row = _span(k.get("gridColumn")), _span(k.get("gridRow"))
            if col and row:
                rects.append((k.get("elementId"), col, row))
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                (a, ac, ar), (b, bc, br) = rects[i], rects[j]
                if ac[0] < bc[1] and bc[0] < ac[1] and ar[0] < br[1] and br[0] < ar[1]:
                    issues.append(
                        f"`{a}` and `{b}` overlap inside <{parent.tag} "
                        f"{parent.get('elementId') or parent.get('id')}>: "
                        f"columns {ac[0]}-{ac[1]} vs {bc[0]}-{bc[1]}, "
                        f"rows {ar[0]}-{ar[1]} vs {br[0]}-{br[1]}."
                    )
    return issues


def issues_auto_rows_in_fixed_container(spec: dict, root: ET.Element | None) -> list[str]:
    """A container with gridTemplateRows="auto" whose own height is fixed.

    The leftover height is dumped into the first auto row — you get a tall white
    gap under the section heading, and the children can come back out of order.
    Give any wrapper that holds a card grid or a list an explicit
    `repeat(N, 1fr)` matching its row span.
    """
    if root is None:
        return []
    issues = []
    for parent in root.iter():
        for k in parent:
            if k.tag not in CONTAINER_TAGS:
                continue
            rows = _span(k.get("gridRow"))
            if not rows:
                continue
            span = rows[1] - rows[0]
            kids = len([c for c in k if c.tag in PLACED_TAGS])
            if k.get("gridTemplateRows") == "auto" and span >= 12 and kids >= 4:
                issues.append(
                    f"container `{k.get('elementId')}` spans {span} rows with "
                    f'{kids} children and gridTemplateRows="auto". A fixed-height '
                    "container with auto rows dumps the leftover height into the "
                    "first row (a white gap under the heading) and can reorder "
                    f'children. Use gridTemplateRows="repeat({span}, 1fr)".'
                )
    return issues


def issues_control_id_unique(spec: dict) -> list[str]:
    seen: dict[str, str] = {}
    issues = []
    for _loc, el in _elements(spec):
            if el.get("kind") != "control":
                continue
            cid = el.get("controlId")
            if not cid:
                continue
            if cid in seen:
                issues.append(
                    f"controlId `{cid}` duplicated on elements {seen[cid]} and {el.get('id')}. "
                    "controlId is workbook-wide unique."
                )
            else:
                seen[cid] = el.get("id")
    return issues


def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate-spec.py <spec.json>\n")
        sys.exit(2)
    with open(sys.argv[1]) as f:
        spec = json.load(f)

    root = _parse_layout(_layout(spec))

    checks = [
        ("no-per-page-layout",          lambda: issues_per_page_layout(spec)),
        ("elements-placed-in-layout",   lambda: issues_elements_placed(spec, root)),
        ("containers-have-children",    lambda: issues_containers_have_children(spec, root)),
        ("legacy-layout-tags",          lambda: issues_legacy_layout_tags(spec, root)),
        ("column-format-kind",          lambda: issues_column_format(spec)),
        ("control-id-unique",           lambda: issues_control_id_unique(spec)),
        ("element-shape",               lambda: issues_element_shape(spec)),
        ("overlapping-siblings",        lambda: issues_overlapping_siblings(spec, root)),
    ]

    if is_legacy_getback(spec, root):
        sys.stderr.write(
            "[note] This looks like a GET-back of a UI-built workbook (nested "
            "`pages[].elements` and/or legacy <LayoutElement>/<GridContainer> "
            "tags), not a create payload.\n"
            "       Expect a finding for nearly every element: the linter is "
            "correctly identifying the pre-August-2026 schema, not a defect in "
            "the spec.\n"
            "       Read these for style, then author your own in the current "
            "shape — see reference/schema-2026-08-breaking-changes.md.\n\n"
        )

    all_issues: list[tuple[str, str]] = []
    for tag, fn in checks:
        for msg in fn():
            all_issues.append((tag, msg))

    # Advisory — heuristics, so they warn and never fail. The first catches the
    # defect nothing else does: a structurally perfect, half-finished dashboard.
    for msg in issues_completeness(spec):
        sys.stderr.write(f"[completeness] {msg}\n")
    for msg in issues_auto_rows_in_fixed_container(spec, root):
        sys.stderr.write(f"[auto-rows-fixed-container] {msg}\n")
    for msg in issues_period_scoping(spec):
        sys.stderr.write(f"[period-scoping] {msg}\n")

    if not all_issues:
        print(f"validate-spec: {sys.argv[1]} — all {len(checks)} checks passed")
        sys.exit(0)

    for tag, msg in all_issues:
        sys.stderr.write(f"[{tag}] {msg}\n")
    sys.stderr.write(f"\nvalidate-spec: {len(all_issues)} issue(s) found in {sys.argv[1]}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
