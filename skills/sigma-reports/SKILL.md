---
name: sigma-reports
description: Build pixel-perfect, paginated Sigma reports as code via POST /v2/reports/spec — statements, invoices, LP reports, regulatory documents, anything destined for PDF. Use when the deliverable is a fixed-layout printed page rather than a responsive dashboard. For dashboards use sigma-workbook-conventions instead. Covers the report envelope, absolute positioning, header/footer panels, the element kinds reports actually accept, the silent text-clipping class of bugs, and the PDF export polling loop.
---

# Sigma reports as code

A **report** is a separate document kind from a workbook: fixed page size,
absolute pixel positioning, repeating header/footer panels, and PDF as the
output. Use it when the deliverable is a printed page — a customer statement, an
invoice, an LP report, a regulatory filing — not a dashboard someone filters.

If the output is interactive, you want `sigma-workbook-conventions`. Reports have
no controls, no containers, no actions, no agents.

---

## 0. Check the endpoint is enabled before you plan anything

**Reports-as-code is a gated beta.** `POST /v2/reports/spec` and
`PUT /v2/reports/{id}/spec` are not available on every org, and a non-enrolled
org will fail at the endpoint rather than at the payload. Confirm access first:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $SIGMA_API_TOKEN" \
  "$SIGMA_BASE_URL/v2/reports/<any-existing-report-id>/spec"
```

A 200 means you're enrolled. A 403 or 404 means the spec endpoints aren't on for
this org — talk to your Sigma contact before designing around them. The regular
report endpoints (`create`, `get`, `list`, `copy`, `export`) are generally
available; only the **`/spec`** ones are gated.

Also worth knowing: many orgs already have auto-created `"(Report)"` companions
of existing workbooks. `GET`-ing one of those is the fastest way to see real
element shapes for your own org, and is more reliable than any documentation —
including this file.

---

## 1. The envelope

```json
{
  "name": "Acme — Service Statement (August 2026)",
  "folderId": "<folderId>",
  "document": {
    "schemaVersion": 1,
    "kind": "report",
    "elements": [ "...flat list of ALL elements across all pages..." ],
    "pages": [ {"id": "p1", "name": "Statement"},
               {"id": "p2", "name": "Activity"},
               {"id": "pdata", "name": "Data", "visibility": "hidden"} ],
    "panels": [ "...header/footer, see §3..." ],
    "config": { "margin": 30, "pageHeight": 1056, "pageWidth": 816 },
    "settings": { "theme": { "overrides": { "...": "..." } } },
    "layout": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<Page id=\"p1\">..."
  }
}
```

Same flat-`elements` + `pages` + `layout`-XML shape as the current workbook
schema. `config` is report-specific: `pageWidth: 816` and `pageHeight: 1056` are
US Letter at 96dpi; `margin` is a print-safety border around the whole page.

Verified against a live 3-page report: 36 elements, 3 pages, 2 panels, 2,805
characters of layout XML.

---

## 2. Positioning is absolute, in pixels

No grid, no rows and columns. Every element is placed by `x`/`y`/`width`/`height`
inside its `<Page>`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Page id="p1">
  <Element elementId="p1-donut"  x="30"  y="4"   width="178" height="178"/>
  <Element elementId="p1-l-bal"  x="220" y="4"   width="190" height="22"/>
  <Element elementId="p1-k-bal"  x="220" y="22"  width="190" height="40"/>
  <Element elementId="p1-rule1"  x="30"  y="330" width="756" height="1"/>
</Page>
```

`x + width` must stay inside `pageWidth - margin`. With the values above that
ceiling is 786, which is why a full-width rule is `x=30 width=756`.

**Never place a column at a literal `margin + <number>`.** Compute offsets from a
list of column widths plus a fixed gap, and assert the row fits:

```python
H_COL_W, H_GAP, x = [230, 200, 180, 146], 12, MARGIN
cols = []
for w in H_COL_W:
    cols.append((x, w)); x += w + H_GAP
assert x - H_GAP <= PAGE_W - MARGIN, "header row overflows the page"
```

Magic-number offsets drift out of sync the moment a width changes. A real
statement shipped for a while with its last header column overlapping its
neighbour by 5px and overflowing the right margin by 34px — which reads as
"looks cramped on the right" in a render, never as an API error.

The report UI's own **Page Layout → Margins** field is a different thing: a
print-safety border around the finished page. It cannot move, resize or
de-overlap an absolutely positioned element. If columns overlap, the bug is in
your `x`/`width` maths.

---

## 3. Header and footer panels

Global furniture repeats across pages via `panels`, not by duplicating elements:

```json
"panels": [
  { "id": "global-header", "type": "header", "title": "Statement header",
    "config": { "height": 104, "backgroundColor": "" },
    "pages": ["p1", "p2"] },
  { "id": "global-footer", "type": "footer", "title": "Statement footer",
    "config": { "height": 62, "backgroundColor": "" },
    "pages": ["p1", "p2"] }
]
```

Elements belonging to a panel are placed in the layout under a `<Panel>` block
rather than a `<Page>`. `pages` lists which pages the panel appears on, so a
cover page can opt out.

---

## 4. Element kinds reports accept

Verified present in a working report: `text`, `image`, `table`, `kpi-chart`,
`bar-chart`, `donut-chart`, `divider`.

**No containers.** There is no container element and no page background-colour
mechanism. For a coloured band, use an `image` element whose source is a
data-URI SVG of a solid rect.

`image.style.fit` is `contain | cover | scale-down`. `fit: "fill"` is rejected
with the misleading `Invalid kind: "image"`.

### Styled text goes in the body, not in fields

A report `text` element has only `id`, `kind`, `body`. Element-level `color`,
`fontSize`, `fontWeight` and `align` are silently dropped on round-trip. Style it
with an inline span inside the body:

```json
{ "id": "p1-l-bal", "kind": "text",
  "body": "<span style=\"font-size: 11px; color: #5B6B7F\">Total Charges</span>" }
```

Markdown in `body` renders, including links — `[**Title**](https://…)` gives a
bold hyperlink coloured by `settings.theme.overrides.colors.highlight`. Two
trailing spaces before `\n` is a hard break, which is how you get one clickable
item per line inside a single element; a bare `\n` collapses the lines.

**A `text` body must be non-empty.** An empty string is accepted by POST and then
crashes the viewer with a generic "Invalid document" and no field pointer.

---

## 5. The silent failure mode: clipping

Reports have their own version of "renders as nothing" — and it is **clipping**,
because every box is a fixed height:

- **A table clips its last rows** if the height is too short, with no error and no
  scrollbar. A 7-row table needed 252px, not 210px. Budget roughly **36px per row
  plus ~22px of header**, and add height when you add rows.
- **Body text clips at BOTH top and bottom** if the box is too short. Default body
  type wraps at roughly **86 characters per 720px of width** with a **~22px line
  height**, so `ceil(chars / 86) * 22 + padding`. Strip markdown URLs before
  counting. A 5-line paragraph in a 4-line box loses its last line silently — this
  bit twice on one build, once on a warning paragraph and once on a footer.
- **An `H1` needs more box height than its font size** or the glyphs clip and the
  next element overlaps.

The fix for all three is the same: render the PDF and look at it. There is no API
error for any of them.

### The one that looks like clipping and isn't: silent pagination

**An element that "doesn't render" has usually been pushed onto page 2.** A
statement whose content ended at `y=856` — comfortably inside
`pageHeight − header − footer` = 890 — silently paginated, and its closing
paragraph vanished from page 1. Two things made this cost an hour:

- `qlmanage` renders **only page 1**, so the second page is invisible in the
  usual check and the element looks like it failed.
- The overflow threshold is **lower than the arithmetic suggests**. Empirically
  content had to end by **~700px** on an 816×1056 page with a 104px header and a
  62px footer, not 890.

Diagnose it in one line before touching heights — the text is either in the PDF
or it isn't:

```python
from pypdf import PdfReader
r = PdfReader("out.pdf")
print(len(r.pages))                              # 2 when you expected 1 = your answer
print("my paragraph" in r.pages[0].extract_text())
```

Then assert the ceiling in the generator so it fails at build time, not in a
render: `assert y <= 700, f"page 1 content will paginate: {y}"`.

---

## 6. Aggregates over a column you didn't design for

A report that totals a column will total **every** row in it. A line whose value
is legitimately negative in one design (a redemption, a credit) poisons the total
in another. On one build a "dispatches avoided" line entered as `-142` turned a
411-event tally into a nonsensical 127 in the footer total. If a table has a
total row, every value in that column has to belong in a sum.

---

## 7. PDF export — the fastest verification loop

No browser, no auth dance:

```bash
# 1. kick off the render — format.layout is REQUIRED
curl -s -X POST "$SIGMA_BASE_URL/v2/reports/<reportId>/export" \
  -H "Authorization: Bearer $SIGMA_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"format":{"type":"pdf","layout":"portrait"}}'
# -> {"queryId": "..."}

# 2. poll. HTTP 204 means STILL RENDERING. 200 + bytes means done.
curl -s -o out.pdf -w '%{http_code}\n' \
  -H "Authorization: Bearer $SIGMA_API_TOKEN" \
  "$SIGMA_BASE_URL/v2/query/<queryId>/download"
```

Omitting `format.layout` errors. Treating 204 as failure is the usual mistake —
it means keep polling.

To actually look at the pages on macOS, where there's no `pdftoppm`: split the PDF
one page per file with `pypdf`, then `qlmanage -t -s 1500 -o . page.pdf`.
`qlmanage` only renders page 1 of a multi-page PDF correctly, hence the split.

To verify links, harvest each page's `/Annots → /A → /URI` with `pypdf` and curl
them. That is exactly what a reader can click, so it catches both dead URLs and
links that silently failed to render as links.

---

## 8. Share links are slug-based

`https://app.sigmacomputing.com/<org>/report/<reportId>` **404s in a browser** —
the reportId is an API-only identifier. The shareable URL is a name slug plus a
short id, returned as the `url` field from `GET /v2/reports/{id}/spec`. Always
read it back rather than constructing it. A `|` in the name becomes `-or-`, and
the link changes if the document is renamed.

---

## 9. Smaller verified traps

- **A report table's summary bar has no verified shape.** Every table in a
  known-good report carries `tableComponents: {summaryBar: "hidden"}`, and
  adding a `summary: [...]` array is rejected as `Invalid kind: "table"`. Put
  the total in its own labelled `kpi-chart` next to the table — it also lands
  where the eye expects a total, which the summary bar does not.
- **Budget ~33px per row, not 30.** At 30px the last rows clip a few pixels off
  the bottom — visible in a render, silent everywhere else.
- **A section heading needs more gap than its own height.** An 18px heading with
  a 16px gap is overlapped by the card beneath it.
- **`verticalAlign: "top"` on a text element is rejected at POST**, masked as
  `Invalid kind: "text"`. Use `"middle"`. Relatedly, `style.padding` gives an
  honest error: `must be 'none' or omitted`.
- **A column `format: {kind: "datetime", formatString: "MMM d"}` renders the
  format string literally** — "MMM d" in every cell. Format dates to a display
  string in SQL instead.
- **A dark logo on a light header needs its own recolour.** A helper that falls
  back to a white-recoloured asset hands you an invisible logo and no error. See
  the recolour rule in `../sigma-workbook-styling/SKILL.md`.
- **Park helper tables somewhere, not nowhere.** Source tables that feed elements
  but shouldn't be seen can go on a `visibility: "hidden"` page, or in a 10×5 box
  in a corner. They do have to be placed.
- **The POST validator is looser than the viewer.** An invalid document can return
  `200 success: true`, store fine, and then throw a generic `Error: Invalid
  document` in the viewer with no field-level detail. Diffing what you sent
  against the `GET`-back reveals what was silently stripped, which is usually the
  fastest way to narrow it down.
- **One org logged a constant, unrelated `Invalid document` console error on every
  report page load**, valid documents included. Don't treat console noise as
  signal — the real signals are a visible error banner in the canvas, or zero
  rendered content in the DOM. SVG data-URIs and warehouse queries also take a few
  seconds; wait and re-check before concluding anything is broken.

### One contradiction, flagged rather than resolved

An earlier build concluded that `kpi-chart.style` in a report accepts only
`{padding: "none"}`, and that adding `backgroundColor` broke the viewer. A later
working report carries `style: {padding: "none", backgroundColor: "#ffffff"}` on
its KPI elements and renders and exports correctly. Either the earlier diagnosis
was wrong or the behaviour changed. **Treat `backgroundColor` on a report
`kpi-chart` as probably fine but verify on your org**, and if a report stores with
a 200 and then won't render, that field is a reasonable first thing to strip.

---

## 10. Workflow

1. Confirm the `/spec` endpoints are enabled for your org (§0).
2. `GET` an existing report in your org and read its real shapes.
3. Author the spec. Compute every `x` from a width list, never a magic number.
4. `POST` to create. A 200 is necessary, not sufficient.
5. Export the PDF, split it, and **look at every page**. Clipping is invisible in
   the spec and obvious in a render.
6. Read the `url` field back for the shareable link.
