# Warehouse portability — what changes, and what doesn't

Sigma sits on your warehouse, so a workbook spec has two layers with very
different portability:

| Layer | Portable across warehouses? |
|---|---|
| Element kinds, layout XML, `style`, controls, actions, overlays, agents, plugins, theme | **Yes.** Identical everywhere. |
| Sigma formulas (`Sum`, `SumIf`, `MaxIf`, `Lookup`, `Rollup`, `DateTrunc`, `Switch`) | **Yes.** Sigma compiles these to your warehouse's dialect. |
| **Custom SQL** in a `source: {kind: "sql", statement}` | **No.** Passed through to the warehouse verbatim. |
| **`CallText` / warehouse AI functions** | **No.** Names a warehouse-specific function. |
| Input-table write-back | Yes, but the connection must be write-enabled. |

Almost everything in this toolkit is in the portable layer. The exceptions are
listed below, with translations.

---

## The two places this repo assumes Snowflake

### 1. Seed SQL in the runnable examples

`sigma-input-table-app/examples/build_demand_planning_lite.py` and
`sigma-cohort-builder-app/examples/build_cohort_builder_reference.py` generate
synthetic rows so they run with no warehouse tables. That generator SQL is
Snowflake-flavoured. The *workbook* those scripts build is fully portable — only
the seed query needs a rewrite.

| Snowflake (as written) | Databricks SQL |
|---|---|
| `SELECT SEQ4() i FROM TABLE(GENERATOR(ROWCOUNT => 2000))` | `SELECT id AS i FROM RANGE(2000)` |
| `GET(ARRAY_CONSTRUCT('a','b','c'), MOD(i,3))::string` | `element_at(array('a','b','c'), CAST(MOD(i,3) AS INT) + 1)` — **1-indexed, hence the `+ 1`** |
| `i::string`, `x::int` | `CAST(i AS STRING)`, `CAST(x AS INT)` (`::` also works on recent DBSQL) |
| `DATEADD('month', n, DATE_TRUNC('month', CURRENT_DATE()))` | `ADD_MONTHS(DATE_TRUNC('MONTH', CURRENT_DATE()), n)` |
| `LPAD(i::string, 5, '0')` | `LPAD(CAST(i AS STRING), 5, '0')` |
| `'CUST-' \|\| x` | `CONCAT('CUST-', x)` (`\|\|` also works) |

`MOD()`, `ROUND()`, `SIN()`, `CASE WHEN` and `WITH` behave the same on both.

For literal helper tables, both dialects accept:

```sql
SELECT * FROM (VALUES ('a', 1), ('b', 2)) AS t(label, n)
```

which is usually simpler than a row generator anyway.

**A Snowflake-only trap that does not apply to Databricks:** on Snowflake,
`GET(ARRAY_CONSTRUCT(...), i)` returns a VARIANT, and an uncast VARIANT breaks
any downstream `Sum`/`Avg`/pivot with `Expected number; received variant` —
which surfaces as a generic "Invalid Argument" on every dependent KPI. Hence the
`::string` / `::int` casts throughout the examples. Databricks' `element_at`
returns a properly typed value, so this class of bug disappears. Still cast
explicitly — a linked input-table column inherits its source column's type, and
input-table column types are **pinned at create** (changing one needs a fresh
POST, not a PUT).

### 2. The live AI narrative

`command-center-recipes.md` §6 shows an AI insight band using:

```
CallText("SNOWFLAKE.CORTEX.COMPLETE", "<model>", <prompt-expression>)
```

`CallText` is Sigma's generic escape hatch for calling a **warehouse** function
that returns text. The first argument is the function name in *your* warehouse,
so on Databricks you point it at Databricks' own AI SQL functions (their
`ai_query` against a model-serving endpoint, or the built-in `ai_*` text
functions) rather than `SNOWFLAKE.CORTEX.COMPLETE`.

**Check the exact function name, argument order and return type in Databricks'
current SQL reference before wiring it up** — this has not been verified against
Databricks from this repo, and a wrong signature fails at query time, not at
POST. Everything else about the pattern transfers unchanged: build the prompt as
a Sigma string expression concatenating live figures with `&`, wrap the result in
`Replace(..., '"', "")`, and feed it per-segment movement rather than three
portfolio totals.

If AI functions aren't enabled on the connection, the band degrades cleanly —
drop the element and the page still works. Don't let it block the build.

**The trap that costs more than the porting does: the MODEL name, on a
warehouse where the function name is already correct.** Cortex model
availability is per-region and per-account — a model that exists in Snowflake's
documentation is not necessarily provisioned on *your* connection. Ask for one
that isn't and the band renders **`N/A`**. No error, no warning, a 200 on the
POST, and a page that looks finished until someone reads the empty insight
strip. It is indistinguishable from "the AI feature isn't enabled", so the usual
reaction is to abandon the element when the fix was one string.

Two consequences worth building around:

- **Verify the model before you wire it into a `{{...}}` body.** Run
  `SELECT SNOWFLAKE.CORTEX.COMPLETE('<model>', 'say hi')` against the connection
  first. One query settles it; guessing costs a full build-and-export cycle to
  find out, and then leaves you unsure whether the model or the prompt was wrong.
- **Prefer a widely-provisioned open model** (the Llama family is a safe default
  on most accounts) over the newest proprietary one. Newer and larger models are
  exactly the ones most likely to be missing from a given region — the model
  most likely to render `N/A` is the one you most want to use.

The same shape applies on other warehouses: whatever endpoint or model
identifier the AI function takes, a wrong-but-well-formed one usually fails at
query time as empty output rather than as an error you can see.

---

## Input tables and write-back on Databricks

Write-back works, with two operational notes:

- **The connection must be write-enabled.** `GET /v2/connections?limit=100`
  reports `writeAccess` per connection. Put input tables on a write-capable
  connection.
- **Keep the whole workbook on one connection where you can.** Joins cannot span
  two connections (`All join sources must share one connection`). If an input
  table has to join a custom-SQL helper table, that helper must live on the same
  connection — which means writing it in that warehouse's dialect.
- **An expired Databricks access token presents as a data problem, not an auth
  problem.** Input tables silently fail to load with a warehouse error. If
  write-back "just stopped working," check the token before you debug the spec.
  `workbook-spec-api.md` has a longer account of losing time to exactly this.
- **Input-table connection is pinned at create.** A PUT that changes it returns
  `Cannot change the connection of an existing input table` — moving them means
  re-POSTing a fresh workbook.

---

## Practical porting checklist

1. Point the spec at your connection ID. Nothing else in the layout changes.
2. Replace the example seed SQL with your real tables, or rewrite it per the
   table above.
3. Swap `SNOWFLAKE.CORTEX.COMPLETE` for your warehouse's AI function, or drop
   the insight band.
4. Confirm your input-table connection reports `writeAccess: true`.
5. `create` (not `verify`) to validate, then export a PNG and look at it.
