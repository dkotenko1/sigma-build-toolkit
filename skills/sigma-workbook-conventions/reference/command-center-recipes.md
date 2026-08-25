# Command-center recipes — the shapes a polished overview page needs

Verified element shapes for the pieces that make an executive command-center page
read as a designed product rather than a stack of charts. Each one below is
either absent from, or only named in passing by, the rest of this reference —
they are collected here because they are the parts that most often get built
wrong, or silently render empty.

All of these were verified against a live org by building and re-building real
workbooks, then exporting a PNG and looking at it. Where a field is a trap, the
trap is documented rather than the happy path.

**Start with the base table.** Every formula below references columns
(`Product`, `State`, `Period`, `Period Name`, `Revenue`, `Net Revenue`,
`Goal Pct`) that come from one shared source table. A runnable example of that
table — with the `Current Period` / `Prior Period` split the comparative KPIs
depend on — is in `../examples/base-table-snowflake.sql` (and
`base-table-databricks.sql`). Read that first, or §1's formulas will look like
they reference columns from nowhere.

**And get the export loop working before you build.** `scripts/export-png.sh
<workbookId> <pageId>` renders a page so you can look at it. Four of the
failures below are invisible in the spec and obvious in a screenshot.

**Lint before every POST, in this order:** `scripts/validate-openapi.py`
(per-element field shapes, checked offline against Sigma's published OpenAPI)
then `scripts/validate-spec.py` (layout, placement, and the behavioural traps a
schema cannot express). Shape errors are cheaper to fix and a spec that fails the
first will never reach the second. The reason to run them at all rather than
letting the API tell you: **the API stops at the first bad element** and masks it
as `Invalid kind: "<kind>"`, so debugging by POST costs one round trip per
mistake.

---

## 0. The completeness checklist — read this before you decide you are done

Every recipe below is optional in isolation and load-bearing in aggregate. A
build that uses §1–§10 and stops lands at roughly **50 elements** and reads as a
competent dashboard. A finished command center for a real customer is roughly
**170 elements**, and the difference is not more charts — it is the interaction
layer: persona tabs, card grids, an alert feed, drill-through overlays, and a
navigation bar. That gap has been shipped more than once because nothing in this
file said out loud what "done" contains.

Grade the build against this list before calling it finished. The right-hand
column is where the shape lives.

| Block | Done means | § |
|---|---|---|
| Masthead | logo + gradient + **`navigation` element** + a cross-document CTA | §12 |
| KPI band | **composite** card: current tile + prior tile + shared sparkline | §13 |
| AI narrative | icon + bordered band, fed row-level movement | §6 |
| Filter bar | period, dimension list, **date-grain**, **break-out-by** | §8 |
| Primary viz | map that cross-filters + **time-series** breakout (not one categorical bar) | §7, §18 |
| Persona tabs | Executive vs **Field Operations** in a `tabbed-container` | §14 |
| Card grid | per-entity cards: name, **`progress` ring**, tag, value, subline, drill button | §15 |
| Alert feed | severity-coloured operational cards bound to an alerts table | §16 |
| Drill-through | card → `set-control-value` → **modal**; row → **drawer** | §17 |
| Detail table | ranked, with vs-plan conditional bands | §3 |
| Agents | one per interactive surface, each with its own tools | §10 |
| Plumbing | source tables parked on a **hidden `Data` page**, not on the canvas | §12 |
| **Theme** | brand `highlight`, `categoricalScheme`, fonts and canvas set in `settings.theme.overrides` | §20 |

Two of these carry most of the perceived quality: the **persona tabs with a
Field Operations view** (§14–§16) and **drill-through** (§17). A dashboard
without them is a report; with them it is an application, and that is the
difference a customer notices in the first ten seconds.

---

## 1. The comparative KPI card

The single most load-bearing element on an overview page, and the one most often
degraded into two bare numbers side by side. What makes it read as a real KPI is
that the *current* KPI carries `comparisonColumn` plus `comparison` — that is
what renders the delta badge.

```json
{
  "id": "kpi-revenue",
  "kind": "kpi-chart",
  "source": { "elementId": "tbl-base", "kind": "table" },
  "columns": [
    { "id": "v-cur",  "formula": "SumIf([tbl-base/Revenue], [tbl-base/Period Name] = \"Current Period\")",
      "name": "Revenue ($M)", "format": { "kind": "number", "formatString": "$,.0f", "currencySymbol": "$" } },
    { "id": "v-prior", "formula": "SumIf([tbl-base/Revenue], [tbl-base/Period Name] = \"Prior Period\")",
      "name": "Prior TTM", "format": { "kind": "number", "formatString": "$,.0f", "currencySymbol": "$" } }
  ],
  "value": { "columnId": "v-cur", "color": "#FFFFFF", "fontSize": 26 },
  "comparisonColumn": { "columnId": "v-prior" },
  "comparison": { "display": "delta", "colorGood": "#CDEBB8", "colorBad": "#FFCFC7", "fontSize": 13 },
  "name": { "text": "Revenue ($M)", "color": "#FFFFFF", "fontSize": 12 },
  "layout": { "anchor": "middle" },
  "style": { "padding": "none", "backgroundColor": "#0B2740" }
}
```

Traps, all of them cost real debugging time:

- **`backgroundColor: "transparent"` is rejected** on `kpi-chart` and
  `line-chart`, and the rejection is masked as `Invalid kind: "kpi-chart"`.
  `"none"`, `"#00000000"`, `"rgba(0,0,0,0)"` and a theme ref all fail too.
- **Omitting `backgroundColor` renders OPAQUE WHITE, not see-through.** If the
  card sits on a gradient container, that hides the gradient behind a solid
  tile. Give the tile its own hex fill matching the gradient's end.
- Use the element's **own native `name`** for the title (it accepts `color` and
  `fontSize`), never a separate text tile or an SVG image of the title text.

> ### `Sum(x) / 12` is not "trailing twelve months"
>
> The most expensive arithmetic mistake against this base table, because it is
> invisible. The table holds **24 months** — both halves of the `Period Name`
> split — so a scorecard column written as
>
> ```
> Round(Sum([Book/Sites]) / 12, 0)          ❌ spans 24 months, ~2x too high
> Round(SumIf([Book/Sites], [Book/Period Name] = "Current Period") / 12, 0)   ✅
> ```
>
> returns roughly double. It renders as a completely plausible number. Nothing
> errors, nothing is empty, and the spec diff looks right.
>
> The tell is that **the detail table stops reconciling with the KPI band** — the
> KPI cards use `SumIf(..., "Current Period")` because they need the prior-period
> half for the delta badge, so they are correct by construction while everything
> else drifts. Nobody adds up a scorecard column by hand, which is how this ships.
>
> It bites every non-time-series element: ranked tables, choropleth values,
> `progress` ring numerators, drill-through overlays. Time-series charts are fine
> — spanning both periods is the whole point of a trend line. `validate-spec.py`
> flags the snapshot cases as `period-scoping`.
>
> Cheapest check: sum the detail table's column and compare it to the KPI card
> above it. They should match exactly.
>
> **The exception:** if a `date-range` control filters the base table, the
> control does the scoping and a bare `Sum(...)` is right. Judge that on the
> **default** state, though — a control with no value selected filters nothing,
> so the view your audience sees on first load still spans both periods. That is
> precisely when a demo gets screenshotted.

## 2. The card sparkline

A `line-chart` with axes and legend suppressed, drawn in white so it can sit on
the card's dark end.

```json
{
  "id": "sp-revenue",
  "kind": "line-chart",
  "source": { "elementId": "tbl-base", "kind": "table" },
  "columns": [
    { "id": "sp-x", "formula": "[tbl-base/Period]", "name": "Period" },
    { "id": "sp-y", "formula": "Sum([tbl-base/Revenue])", "name": "Trend" },
    { "id": "sp-c", "formula": "\"Trend\"", "name": "Series" }
  ],
  "xAxis": { "columnId": "sp-x", "format": { "labels": "hidden", "marks": "none" } },
  "yAxis": { "columnIds": ["sp-y"],
             "format": { "labels": "hidden", "marks": "none",
                         "scale": { "type": "linear", "zero": false, "hideZeroLine": true } } },
  "color": { "by": "category", "column": "sp-c", "scheme": ["#FFFFFF"] },
  "name": { "visibility": "hidden" },
  "legend": { "visibility": "hidden" },
  "style": { "padding": "none", "backgroundColor": "#0B2740" },
  "lineAreaStyle": { "interpolation": "monotone" }
}
```

**The trap:** a white line on a tile with no `backgroundColor` is a white line on
white — it renders as nothing, with a 200 response and no warning. `zero: false`
matters too; a sparkline anchored at zero flattens into a straight line.

## 3. `progress` — rings and bars

Undocumented elsewhere in this reference, and it fails silently in two different
ways.

```json
{
  "id": "ring-a",
  "kind": "progress",
  "source": { "elementId": "tbl-cards", "kind": "table" },
  "shape": "ring",
  "value": "MaxIf([tbl-cards/Goal Pct], [tbl-cards/Product] = \"Line A\")",
  "min": "0", "max": "1",
  "config": { "label": { "visibility": "hidden" } },
  "style": { "padding": "none" }
}
```

- **`progress` needs an explicit `source`.** It resolves without one while the
  element sits directly on a page; move it inside a `<Tab>` and the formula has
  nothing to bind to, and every ring renders empty.
- **`progress` has no `name`.** The caption is `config.label`, and that label is
  the *element name*, not the value — omit it and every ring prints "Progress
  ring". `label.visibility: "visible"` is not in the enum and comes back as
  `Invalid kind: "progress"`. Ship it hidden.
- **`config.fillColor` and `config.trackColor` are silently DROPPED** — they do
  not come back in the GET-back, and the ring paints in the theme's `highlight`
  color. An earlier version of this section showed them as if they worked, which
  is why so many otherwise-branded dashboards have Sigma-blue rings on them. The
  fix is the theme (§20), not the element.
- `shape` accepts `"ring"` and `"bar"`.

## 4. Row-scoped card grids (`MaxIf`)

Cards that each show one row of a small table are **hand-built containers**, not
a `repeated-container`. The repeated-container write schema exposes no `name`
field, so the repeater-qualified `{{[Repeater/Column]}}` reference its own docs
require cannot be written from code. Say so if asked — this surprises people.

The workaround is a row-scoped lookup per card:

```
MaxIf([tbl-cards/<Column>], [tbl-cards/Product] = "<this card's product>")
```

Inside a `text` element, wrap it in `{{ }}` with an optional format:

```
{{MaxIf([tbl-cards/Volume], [tbl-cards/Product] = "Line A") | ,.2f}}
```

Inline HTML inside a text body is limited to `<u> <sub> <sup> <span> <a>`.
`<b>` is **rejected**, so emphasis must be markdown outside the span.

## 5. Text elements that bind to data

**A `text` element has no `source` field.** Its fields are `body`, `id`, `kind`,
`overflow`, `verticalAlign`. A `{{formula}}` inside one resolves only against a
**sourced data element sharing its container**.

This is why an alert card or a stat tile carries a small KPI alongside the
prose — that KPI is not decoration, it is what gives the text something to bind
to. Drop it and every `{{...}}` in the card goes blank.

## 6. A live AI narrative (warehouse AI function)

> **Warehouse-specific.** The example below uses Snowflake Cortex. `CallText`
> calls a function in *your* warehouse, so on Databricks or BigQuery the
> function name changes — see `warehouse-portability.md`. Everything else
> about the pattern transfers unchanged.

An LLM-authored insight band, evaluated at view time against live data:

```
**AI INSIGHT** — {{Replace(CallText("SNOWFLAKE.CORTEX.COMPLETE", "<model>", <prompt-expression>), '"', "")}}
```

`<prompt-expression>` is a Sigma string expression, so concatenate the live
figures into it with `&`:

```
"You are an analyst covering <company> (<domain>). Write TWO sentences. "
"First: name the <segment noun> that moved most and quantify it. "
"Second: name the biggest risk with its number and what to do about it. "
"Data: revenue $" & Text(Round(SumIf([tbl/Revenue], [tbl/Period Name] = "Current Period"), 2)) & "M vs $"
  & Text(Round(SumIf([tbl/Revenue], [tbl/Period Name] = "Prior Period"), 2)) & "M prior."
```

**Probe the model name BEFORE you wire this up.** The `"<model>"` argument is
the single most likely thing to be wrong, and it fails in the worst possible
way: an unavailable model makes the whole `{{...}}` render as **`N/A`** — no
error, no model name, and a CSV export of a neighbouring element reports only
`Export failed … with errors`. It looks like your formula is broken when the
formula is fine.

**Model availability is per-account, not per-Sigma.** Which models a given
warehouse account has provisioned depends on its region and entitlements, so
there is no list worth hardcoding here — including the one in any example above.
Spend ninety seconds probing instead. POST a throwaway one-element workbook,
export it as CSV, read the answer, delete it:

```json
{"id": "probe", "kind": "table", "name": "Probe",
 "source": {"connectionId": "<conn>", "kind": "sql",
            "statement": "SELECT SNOWFLAKE.CORTEX.COMPLETE('<model>', 'Reply with the single word OK') AS M"},
 "columns": [{"id": "c0", "formula": "[Custom SQL/M]", "name": "M"}]}
```

`POST /v2/workbooks/{id}/export {"elementId": "probe", "format": {"type": "csv"}}`
then poll `GET /v2/query/{queryId}/download`. A provisioned model returns `OK`;
an unprovisioned one returns the `Export failed` blob. Probe every candidate in
one pass — one column per model in a single `SELECT` fails as a unit and tells
you nothing about which one was at fault, so give each model its own probe.

Lessons worth inheriting:

- **Feed it row-level movement, not three totals.** Given only totals it writes
  "revenue grew, watch margin" — true, useless, and already on screen above it.
  Given per-segment figures it can name the thing that actually moved.
- **Get the magnitude right in the prompt string.** Dividing a $-millions column
  by 1000 and labelling it "B" tells the model the business is 1000× its real
  size, and it will confidently write that number into the narrative.
- **Use your own domain nouns in the prompt.** If the underlying column is
  called `Members` but the business calls them sites, say so explicitly, or the
  narrative inherits the column name.
- Wrap in `Replace(..., '"', "")` — the model often returns a quoted string.
- Never build a `{{...}}` body with Python `str.format()`. `{{` is format's
  escape for a literal brace, so the markers collapse to `{...}` and Sigma
  stores the whole thing as escaped literal text. Use `%`-substitution.

## 7. A geographic overview that cross-filters

```json
{
  "id": "map-states",
  "kind": "region-map",
  "source": { "elementId": "tbl-base", "kind": "table" },
  "region": "usa-states",
  "columns": [
    { "id": "m-state", "formula": "[tbl-base/State]", "name": "State" },
    { "id": "m-val",   "formula": "Sum([tbl-base/Attainment])", "name": "% of plan" }
  ]
}
```

A working instance with full styling lives in
`../../sigma-workbook-styling/examples/marketing-control-center.json` — search
for `"kind": "region-map"`.

**The cross-filtering rule, which is the whole reason the map earns its space:**
clicking a state filters every other element **only because every element
sources from the same base table**. A control can only filter a table that has
the dimension. **Adding a control does not create a join.** If the map must
filter the bars, the base table needs the state column. An earlier iteration of
this pattern used five separate source tables and cross-filtering silently
stopped working.

## 8. One dynamic chart instead of four static ones

A `segmented` control holding a dimension name, resolved in the chart's own
formula, replaces a row of near-identical charts:

```
Switch([ColorBy], "State", [tbl/State], "Type", [tbl/Category], [tbl/Product])
```

Same trick for time grain, with one caveat: `DateTrunc(Lower([Grain]), ...)`
returns **Invalid Query**. `DateTrunc`'s first argument must be a date-part
literal or a control already holding one, so the control's values must be
literally `quarter` / `month` / `week`.

## 9. Page navigation and drill-through

`navigation` is a supported element kind. For drill-through, a `button` with a
navigate effect targets a page — note the target is **nested**
(`navigate → target → page`), which a top-level value scan will miss when you
are checking for dangling references after removing a page.

`open-overlay` opens a modal or drawer. Two things about overlays:

- `header.title` **must be present**. Omitting it renders "New Modal"; `""`
  crashes the overlay; `" "` gives a blank bar. The header cannot be hidden.
- Overlay child elements live in the flat `document.elements` list, with the
  layout keeping a `<Page id="myModal">` block that places them.

## 10. Agents (the in-workbook copilot)

```json
{
  "id": "agent-main",
  "name": "<Company> Copilot",
  "instructions": "<domain framing> The <segment noun>s are: <names>. <economics>. Cite <metrics>, and always name the <segment noun>. Be concise and quantitative.",
  "greeting": { "mode": "generated",
                "prompt": "Greet the user in one short line, then offer exactly three specific questions you can answer from this data. Name real segments and make one about whichever is behind plan." },
  "dataSources": [ { "kind": "table", "elementId": "tbl-base" } ],
  "tools": [
    { "toolId": "t-focus", "kind": "action", "name": "Focus a segment",
      "description": "Filter the page to one segment.",
      "steps": [ { "kind": "effect", "effect": "set-control-value",
                   "control": "SegmentFilter",
                   "value": { "type": "agent-input", "inputName": "The segment to focus on" } } ] }
  ]
}
```

- `greeting: {mode: "generated"}` beats hardcoded suggestion chips, which go
  stale the moment the data moves.
- An action tool's `agent-input` value **needs `inputName`** for `insert-rows`;
  a bare `{type: "agent-input"}` is rejected there.
- **Feed the agent your real segment names and domain vocabulary.** Agents read
  the source table's column names, so if a column is generically named the
  greeting will offer to trend it by that name. State the business meaning in
  `instructions` explicitly: "the column named X is actually Y — always use Y."
- The effect enum has twelve entries and **`call-api` is not one of them.**

## 12. The masthead: navigation, a cross-document CTA, and a hidden Data page

The header is not just a logo on a gradient. Three things make it read as an
application shell:

**A real `navigation` element**, not buttons pretending to be tabs:

```json
{"id": "nav-main", "kind": "navigation", "mode": "manual", "showIcons": false,
 "optionStyle": {"style": "pill", "orientation": "horizontal",
                 "textColor": "#c7e4f7", "selectedColor": "#ffffff"},
 "options": [{"label": "Command Center", "destination": {"type": "page", "pageId": "pg1"}},
             {"label": "RMR Planning",   "destination": {"type": "page", "pageId": "pg2"}}]}
```

`mode` is required (`Invalid kind: "navigation"` without it). Repeat the element
per page — one instance cannot be placed in two pages' layouts.

**A CTA that leaves the workbook.** `open-document` can target a **report**, so
the statement/invoice you built with `sigma-reports` is one click from the
dashboard:

```json
{"id": "btn-stmt", "kind": "button", "text": "Perimeter service statement ↗",
 "appearance": "filled",
 "actions": [{"id": "a-stmt", "trigger": "on-click",
              "effects": [{"effect": "open-document", "document": "<reportId>",
                           "documentType": "report", "openTarget": "_blank"}]}]}
```

**Park the plumbing on a hidden page.** Every element must be placed in the
layout, but a source table sitting at the bottom of the canvas is visible
clutter and invites the audience to read raw rows. Give the sources their own
page and hide it:

```json
"pages": [{"id": "pg1", "name": "Command Center"},
          {"id": "pgData", "name": "Data", "visibility": "hidden"}]
```

## 13. The composite KPI card (current + prior + sparkline)

§1 gives one tile with a delta badge. The version that reads as a designed
product is **three elements in one gradient container**: a dark current tile
carrying the delta, a saturated prior tile beside it, and a full-width sparkline
band beneath both.

```json
// container — gradient via the TOP-LEVEL backgroundImage field (see §13 trap)
{"id": "c-rev", "kind": "container", "spacing": "small",
 "style": {"padding": "none", "borderRadius": "round"},
 "backgroundImage": {"source": {"kind": "url", "url": "data:image/svg+xml;base64,…"},
                     "style": {"fit": "cover"}}}

// current — dark tile, owns the comparison badge
{"id": "kc-rev", "kind": "kpi-chart", "source": {"elementId": "tbl-base", "kind": "table"},
 "columns": [{"id": "vc-rev", "formula": "SumIf([Book/Net Revenue], [Book/Period Name] = \"Current Period\")",
              "name": "Field gross margin ($M)", "format": {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}},
             {"id": "vk-rev", "formula": "SumIf([Book/Net Revenue], [Book/Period Name] = \"Prior Period\")",
              "name": "Prior TTM", "format": {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}}],
 "value": {"columnId": "vc-rev", "color": "#ffffff", "fontSize": 26},
 "comparisonColumn": {"columnId": "vk-rev"},
 "comparison": {"display": "delta", "colorGood": "#cdebb8", "colorBad": "#ffcfc7", "fontSize": 13},
 "name": {"text": "Field gross margin ($M)", "color": "#ffffff", "fontSize": 12},
 "layout": {"anchor": "middle"},
 "style": {"padding": "none", "backgroundColor": "#231f20"}}

// prior — the brand-accent tile beside it, no comparison of its own
{"id": "kp-rev", "kind": "kpi-chart", "source": {"elementId": "tbl-base", "kind": "table"},
 "columns": [{"id": "vp-rev", "formula": "SumIf([Book/Net Revenue], [Book/Period Name] = \"Prior Period\")",
              "name": "Prior TTM", "format": {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}}],
 "value": {"columnId": "vp-rev", "color": "#ffffff", "fontSize": 22},
 "name": {"text": "Prior TTM", "color": "#ffffff", "fontSize": 13},
 "layout": {"anchor": "middle"},
 "style": {"padding": "none", "backgroundColor": "#ed1c24"}}
```

Layout, on a 12-column card grid with explicit fractional rows so every card in
the row is identical regardless of value length:

```xml
<Container elementId="c-rev" type="grid" gridColumn="1 / 7" gridRow="1 / 12"
           gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="repeat(12, 1fr)">
  <Element elementId="kc-rev" gridColumn="1 / 7"  gridRow="1 / 9"/>
  <Element elementId="kp-rev" gridColumn="7 / 13" gridRow="1 / 9"/>
  <Element elementId="sp-rev" gridColumn="1 / 13" gridRow="9 / 13"/>
</Container>
```

> **The trap that eats an hour: `backgroundImage` is a TOP-LEVEL element field,
> not a `style` property.** Put it inside `style` and it is silently dropped —
> the container renders plain white, and a white logo and white title text
> disappear into it with a 200 response. Same envelope shape as an image:
> `{"source": {"kind": "url", "url": …}, "style": {"fit": "cover"}}`.

## 14. Persona tabs — the Executive / Field Operations split

One dashboard serving two audiences is why a `tabbed-container` earns its place:
the exec tab answers *how is the book performing*, the operations tab answers
*what do I do this morning*. This is the single biggest visual/interaction gap
between a "charts on a page" build and a real one.

```json
{"id": "tc-persona", "kind": "tabbed-container",
 "tabs": [{"name": "Executive"}, {"name": "Field Operations"}],
 "tabBar": {"alignment": "start"}}
```

```xml
<TabbedContainer elementId="tc-persona" type="tabbed-container"
                 gridColumn="1 / 19" gridRow="25 / 73">
  <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="map-geo"  gridColumn="1 / 12"  gridRow="1 / 19"/>
    <Element elementId="bar-prod" gridColumn="12 / 25" gridRow="1 / 19"/>
    <Element elementId="tbl-rank" gridColumn="1 / 25"  gridRow="19 / 33"/>
  </Tab>
  <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <!-- the card grid (§15) and the alert feed (§16) live here -->
  </Tab>
</TabbedContainer>
```

**Size the container to the TALLER tab and fill the shorter one**, otherwise
whichever tab is shorter leaves a page-length white void below its content.

**You cannot screenshot the second tab.** `export-png.sh` renders the default
tab. To verify the other one, build a scratch copy with the two `<Tab>` blocks
and the `tabs` names swapped, export that, and delete it — that round trip is how
the white-gap and child-ordering bugs above were caught.

**Do the swap on a THROWAWAY workbook, not on the real one.** The obvious
version — PUT the swapped spec to the live workbook, export, PUT the real spec
back — leaves the deliverable in the swapped state for as long as the export
takes, and strands it there permanently if anything between the two PUTs fails.
`POST` a copy instead, export it, `DELETE /v2/files/{id}`; the real workbook is
never written to at all. Roughly:

```python
lay = spec["document"]["layout"]
m = re.search(r"(<TabbedContainer\b[^>]*>)(.*?)(</TabbedContainer>)", lay, re.S)
tabs = re.findall(r"<Tab\b.*?</Tab>", m.group(2), re.S)          # positional, no ids
spec["document"]["layout"] = lay[:m.start(2)] + tabs[1] + tabs[0] + lay[m.end(2):]
for e in spec["document"]["elements"]:                            # labels too, or the
    if e.get("kind") == "tabbed-container":                       # screenshot lies
        e["tabs"] = list(reversed(e["tabs"]))
```

Swap the `tabs` labels as well as the layout blocks. Miss that and the export
shows the right content under the wrong tab name, which is worse than not
checking.

**Overlays, unlike tabs, export directly.** `export-png.sh <workbookId>
modalCard` renders a modal or drawer page on its own — the overlay id is just a
page id as far as the exporter is concerned. Worth knowing before you build the
swap harness for something you could have screenshotted outright.

Tabs are positional — there is no id on a `<Tab>`, so the Nth `<Tab>` binds to
`tabs[N]`. A `select-tab` effect targets it by index:
`{"effect": "select-tab", "tabbedContainer": "tc-persona", "selectedTab": {"type": "tab", "index": 1}}`.

**`progress` rings and any element inside a `<Tab>` need an explicit `source`**
(§3) — a formula that resolved while the element sat directly on the page has
nothing to bind to once it moves into a tab, and every ring renders empty.

## 15. The per-entity card grid (the Field Operations centrepiece)

Six hand-built cards, one per entity, each a container holding five children.
Not a `repeated-container` — that kind cannot bind per-card values from code
(§4). Every value is a row-scoped `MaxIf` against a small cards table.

```json
{"id": "pcard-p1", "kind": "container", "spacing": "small",
 "style": {"backgroundColor": "#ffffff", "borderRadius": "round",
           "borderColor": "#dce4ee", "borderWidth": 1}}

{"id": "pc-name-p1", "kind": "text", "body": "### Line A",
 "verticalAlign": "middle"}

{"id": "pc-ring-p1", "kind": "progress", "shape": "ring", "mode": "percent",
 "source": {"elementId": "tbl-pc", "kind": "table"},
 "value": "MaxIf([Product Cards/Goal Pct], [Product Cards/Product] = \"Line A\")",
 "min": "0", "max": "1", "config": {"label": {"visibility": "hidden"}}}

{"id": "pc-bal-p1", "kind": "kpi-chart", "source": {"elementId": "tbl-pc", "kind": "table"},
 "columns": [{"id": "pcv-p1",
              "formula": "MaxIf([Product Cards/RMR], [Product Cards/Product] = \"Line A\")",
              "name": "Recurring revenue in service",
              "format": {"kind": "number", "formatString": "$,.0f", "suffix": "M", "currencySymbol": "$"}}],
 "value": {"columnId": "pcv-p1", "color": "#ed1c24", "fontSize": 24},
 "name": {"visibility": "hidden"}, "style": {"padding": "none"}}

{"id": "pc-sub-p1", "kind": "text", "verticalAlign": "end", "body":
 "<span style=\"color: #5B6B7F\">{{MaxIf([Product Cards/Rate Label], [Product Cards/Product] = \"Line A\")}}</span> **{{MaxIf([Product Cards/Rate Value], [Product Cards/Product] = \"Line A\")}}** <span style=\"color: #5B6B7F\">· {{MaxIf([Product Cards/Status], [Product Cards/Product] = \"Line A\")}}</span>"}

{"id": "pc-open-p1", "kind": "button", "text": "View detail →", "appearance": "text",
 "actions": [{"id": "a-pc-open-p1", "trigger": "on-click", "effects": [
   {"effect": "set-control-value", "control": "cardProduct",
    "value": {"type": "constant", "value": {"type": "text", "value": "Line A"}}},
   {"effect": "open-overlay", "overlayId": "modalCard"}]}]}
```

Notes that cost real time:

- The `kpi-chart` on the card is what gives the sibling `text` elements
  something to bind to (§5). Remove it and every `{{MaxIf(...)}}` in the card
  goes blank.
- **Generate the six cards in a loop** over the entity list, suffixing every id
  with the entity key. Hand-writing them guarantees drift between cards.
- Give every card the identical child skeleton and
  `gridTemplateRows="repeat(N, 1fr)"` — with `auto`, a card whose value string
  is longer lays out differently from its siblings inside an identical box.
- `progress` has **no `name`**; the caption is `config.label`, and it prints the
  element name, so ship it `hidden`.
- **The section wrapper needs explicit rows too.** A wrapper container holding
  the card grid with `gridTemplateRows="auto"` and a fixed outer height dumps
  all the leftover height into its first auto row — you get a tall white gap
  under the section heading, and the children can come back in the wrong order.
  Give any fixed-height wrapper `gridTemplateRows="repeat(N, 1fr)"` matching its
  own row span. `validate-spec.py` warns on this as `auto-rows-fixed-container`.

## 16. The alert feed

The operations tab's second half: one card per operational alert, colour-graded
by severity, bound to a tiny alerts table (`Alert Key`, `Severity`, `Title`,
`Body`, `Impact`, `Owner`, `Age`). It is the element that makes a dashboard feel
like it is *for* someone.

```json
{"id": "ncard-n1", "kind": "container",
 "style": {"backgroundColor": "#fcebeb", "borderRadius": "round",
           "borderColor": "#f09595", "borderWidth": 1}}
{"id": "nsev-n1", "kind": "text", "verticalAlign": "middle",
 "body": "<span style=\"color: #EF4444\">CRITICAL</span>"}
{"id": "ntitle-n1", "kind": "text", "verticalAlign": "middle",
 "body": "<span style=\"color: #EF4444\">**{{MaxIf([Notifications/Title], [Notifications/Alert Key] = \"a1\")}}**</span>"}
{"id": "nbody-n1", "kind": "text", "verticalAlign": "start",
 "body": "<span style=\"color: #501313\">{{MaxIf([Notifications/Body], [Notifications/Alert Key] = \"a1\")}}</span>"}
{"id": "nkpi-n1", "kind": "kpi-chart", "source": {"elementId": "tbl-notif", "kind": "table"},
 "columns": [{"id": "nkv-n1",
              "formula": "MaxIf([Notifications/Impact], [Notifications/Alert Key] = \"a1\")",
              "name": "bps over book attrition", "format": {"kind": "number", "formatString": ",.0f"}}],
 "value": {"columnId": "nkv-n1", "color": "#ef4444", "fontSize": 20},
 "name": {"text": "bps over book attrition", "color": "#791f1f", "fontSize": 10},
 "style": {"padding": "none"}}
```

**Check the child rows do not overlap.** In a five-row card it is easy to give
the body `gridRow="3 / 6"` and the meta line `gridRow="5 / 6"`; the overlap
renders the meta line ABOVE the body, and no API error mentions it.
`validate-spec.py` catches this as `overlapping-siblings`.

### Placement: a narrow right rail, not full-width bands

The shape above says what a card contains and nothing about how wide it should
be, and the default reading — one full-width band per alert, stacked under the
card grid — is the weaker of the two layouts. Put the feed in a **narrow rail
down the right-hand side, beside the card grid**, not below it:

```xml
<Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
  <Element   elementId="txt-ops1" gridColumn="1 / 17"  gridRow="1 / 3"/>
  <Element   elementId="txt-ops2" gridColumn="17 / 25" gridRow="1 / 3"/>
  <!-- card grid: two columns of cards, 1 / 17 -->
  <Container elementId="ncard-a1" gridColumn="17 / 25" gridRow="3 / 10"  … />
  <Container elementId="ncard-a2" gridColumn="17 / 25" gridRow="10 / 17" … />
  <Container elementId="ncard-a3" gridColumn="17 / 25" gridRow="17 / 24" … />
</Tab>
```

Why it reads better, in order of how much it matters:

- **One scan column.** Severity chips line up vertically, so the eye ranks three
  alerts in one pass. Spread across full-width bands they are three separate
  left-to-right reads.
- **The text wraps into a paragraph shape.** An alert body is 2–3 sentences; at
  full width it becomes one long line with a large empty right margin, and the
  card's height collapses to almost nothing. In a rail it fills its box.
- **It sits beside the card grid, not after it.** "Here is the book / here is
  what is wrong with it" is one screen instead of a scroll.

Inside the card, give it **seven rows** and split the bottom row rather than
letting the KPI span the full height:

```xml
<Container elementId="ncard-a1" type="grid" gridColumn="17 / 25" gridRow="3 / 10"
           gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(7, 1fr)">
  <Element elementId="nico-a1"   gridColumn="1 / 5"   gridRow="1 / 2"/>
  <Element elementId="nsev-a1"   gridColumn="5 / 25"  gridRow="1 / 2"/>
  <Element elementId="ntitle-a1" gridColumn="1 / 25"  gridRow="2 / 4"/>
  <Element elementId="nbody-a1"  gridColumn="1 / 25"  gridRow="4 / 6"/>
  <Element elementId="nkpi-a1"   gridColumn="1 / 13"  gridRow="6 / 8"/>
  <Element elementId="nmeta-a1"  gridColumn="13 / 25" gridRow="6 / 8"/>
</Container>
```

- **Separate the severity chip from the title.** One `text` holding
  `CRITICAL · **Title**` cannot wrap sensibly in a narrow column — the chip and
  the first words of the title end up on the same line and the title breaks
  mid-phrase. Two elements on two rows always wrap cleanly.
- **The impact KPI goes bottom-LEFT, with owner and age bottom-right.** A KPI
  spanning the card's full height centres its number against the body text and
  reads as a second headline competing with the title. Confined to the bottom
  half of a 12-column split it reads as a footnote, which is what it is. It is
  still load-bearing: it is the sourced element the `{{MaxIf(...)}}` in every
  sibling `text` binds against (§5).
- Give the KPI a `name` (the units — "sites past standard", "bps over book
  attrition") and keep `fontSize` around 20. The label is doing as much work as
  the number.

Drive the three severity palettes (critical / warning / info) from one dict in
the generator so the fills, borders and icon strokes stay in step. The leading
icon is a data-URI SVG (§ styling skill) whose `stroke` is the severity colour.

## 17. Drill-through: card → modal, row → drawer

The interaction that turns a dashboard into an app. Both overlays live in
`document.overlays` and both get their own `<Page id="...">` block in the layout.

```json
"overlays": [
  {"id": "modalCard", "type": "modal", "name": "Product Card",
   "modal": {"width": "large",
             "header": {"title": "Service line detail", "showCloseIcon": "shown"},
             "footer": {"primaryCta": {"visible": "hidden"},
                        "secondaryCta": {"visible": "hidden"}}}},
  {"id": "drawerProduct", "type": "drawer", "name": "Product Detail",
   "drawer": {"width": "medium", "position": "end", "showShadow": "shown",
              "header": {"title": "Service line detail", "showCloseIcon": "shown"}}}
]
```

The pattern is always **seed a control, then open the overlay**, and every
element inside the overlay filters on that control. From a card button it is a
constant (§15); from a table row it is the selected column:

```json
{"trigger": {"on": "on-select",
             "condition": {"type": "column", "column": "rk-prod", "condition": "IsNotNull"}},
 "effects": [{"effect": "set-control-value", "control": "cardProduct",
              "value": {"type": "column", "column": "rk-prod"}},
             {"effect": "open-overlay", "overlayId": "drawerProduct"}]}
```

**Seed the control with a starting value.** Until the first click the control is
empty, so every `MaxIf(…, [Control])` in the overlay resolves to `null` — and
that is exactly the state a `POST`-then-screenshot review sees, which reads as
"the drill-through is broken" when it is merely unclicked. A `text` control takes
a plain default and it round-trips:

```json
{"kind": "control", "id": "ctrl-cardvert", "controlId": "CardVertical",
 "name": "Card Vertical", "controlType": "text", "mode": "equals",
 "case": "insensitive", "includeNulls": "when-no-value-is-selected",
 "showOperators": false,
 "value": "<the first entity's name>"}
```

(The "controls have no code-representable default" rule is about `list` controls
specifically — see `schema-2026-08-breaking-changes.md` §11.) Park the control on
the hidden Data page; it needs to be placed in the layout like any element, and
it is plumbing, not UI.

Traps:

- The effect field is **`overlayId`**; `close-overlay` takes **no argument**.
- **Overlay-level `actions` cannot resolve any control** — put a real `button`
  element inside the overlay page instead of using the modal's footer CTAs, and
  hide both CTAs as above.
- `header.title` must be present and non-empty (§9).
- **Don't title the overlay with a data binding.** A `{{[T/Column]}}` heading
  inside a modal whose source is not yet filtered to one row renders the literal
  string **"Multiple values"** — which is exactly what an audience sees on the
  first click. Either title it statically, or bind through the same `MaxIf(...,
  [Control])` scoping every other element in the overlay uses.
- Give the overlay a way onward, not just closed: a
  `close-overlay` → `set-control-value` → `navigate` chain that lands the user
  on the modeler page already scoped to what they clicked.

## 18. Time-series breakout, not a categorical bar

A single categorical bar chart ("RMR by product") shows size and nothing else.
The chart that earns the space is the same measure **over time, split by the
break-out control**, so it shows size *and* direction and answers the grain
control at the same time:

```json
{"id": "bar-prod", "kind": "bar-chart", "source": {"elementId": "tbl-base", "kind": "table"},
 "columns": [
   {"id": "bp-cat", "name": "Series",
    "formula": "Switch([ColorBy], \"State\", [Book/State], \"Revenue type\", [Book/Balance Type], [Book/Product])"},
   {"id": "bp-x", "formula": "DateTrunc([Grain], [Book/Period])", "name": "Period"},
   {"id": "bp-y", "formula": "Sum([Book/Net Revenue])", "name": "Field gross margin ($M)",
    "format": {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}}],
 "xAxis": {"columnId": "bp-x"}, "yAxis": {"columnIds": ["bp-y"]},
 "color": {"by": "category", "column": "bp-cat"},
 "stacking": "stacked"}
```

`DateTrunc([Grain], …)` works **only** because the `Grain` segmented control
holds literal date-part strings (`quarter` / `month` / `week`) — see §8.
`DateTrunc(Lower([Grain]), …)` is an Invalid Query.

## 20. The workbook theme — the brand lever element `style` cannot reach

The single highest-leverage branding block, and the one most often skipped
because the rest of the page already looks branded. **Progress-ring fill,
control chips and pills, chart series colors, the page canvas and the type stack
are all theme-driven.** Set every element's `style` to your brand red and, with
no theme, the rings, the segmented controls and the stacked bar still render
Sigma default **blue**.

```json
"settings": {
  "theme": {
    "overrides": {
      "pageWidth": "large",
      "colors": {"text": "#231F20", "highlight": "#ED1C24", "success": "#1E7A4B",
                 "warning": "#D97706", "danger": "#EF4444", "darkMode": "hidden"},
      "colorOverrides": {"backgroundCanvas": "#F2F4F7", "canvasBackground": "#F2F4F7"},
      "categoricalScheme": ["#ED1C24", "#231F20", "#7A1015", "#D97706",
                            "#5B6B7F", "#1E7A4B", "#A9C6E8", "#F2C9CB"],
      "fonts": {"textFont": "Inter", "dataFont": "Inter"},
      "borderRadius": "round",
      "space": {"unit": "small", "showElementPadding": "shown"}
    }
  }
}
```

Verified round-tripping on a live org. Notes:

- **`highlight` is the one that matters most** — it drives `progress` rings,
  selected control chips, the tab underline and link color.
- **`categoricalScheme` is the only color lever a multi-measure chart has.**
  Element-level `categoricalScheme` is dropped (masked), so a stacked breakout
  with no `color.scheme` inherits this list *in category order* — which is
  alphabetical, so your brand's hero color may land on the smallest series.
  Where one specific color matters, use
  `color: {by: "category", column: <a constant-string column>, scheme: ["#hex"]}`.
- **`categoricalScheme[0]` interacts with white KPI sparklines.** If you set it
  to `#FFFFFF` for that reason, every first series elsewhere goes invisible —
  give the sparkline its own explicit `scheme: ["#FFFFFF"]` instead and keep
  slot 0 for the brand.
- Keep the base theme **light**. A dark theme renders input tables and dropdowns
  as white-on-white; apply dark only to the masthead and KPI cards, per element.
- `darkMode: "hidden"` stops a viewer's dark-mode toggle from inverting a
  carefully-built brand surface.

Two layout traps that look like theme problems and are not:

- **A `segmented` control narrower than about four grid columns degrades to a
  dropdown.** Same spec, different width, completely different affordance —
  the pill row is half the point of a breakout control, so give it the room.
- **Swapping `xAxis`/`yAxis` does not transpose a bar chart.** Putting the
  measure on `xAxis` and the dimension on `yAxis.columnIds` drops the grouping
  and renders one bar per *source row* — hundreds of hairlines with a NaN axis.
  Keep the dimension on `xAxis` and the measure on `yAxis`.

## 21. Before you trust any of this

`POST /v2/workbooks/spec/verify` skips SQL resolution, dangling element IDs,
duplicate IDs, layout placement and workspace feature flags. It has passed while
`create` failed on every one of those. **Always create or update to validate**,
then export a PNG and look at it. Four of the failure modes above are invisible
in the spec and obvious in a screenshot.
