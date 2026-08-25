-- The ONE BASE TABLE — the most important decision in a command-center build.
--
-- Every control filters everything ONLY because every element sources from this
-- one table. A control can only filter a table that holds the dimension, and
-- adding a control does not create a join. If a map click must filter the bars,
-- this table needs the state column.
--
-- The columns below are the contract the rest of the pattern assumes:
--   Product / State / Period            -> the filterable dimensions
--   Period Name                         -> "Current Period" | "Prior Period"
--   Revenue / Cost / Net Revenue / ...  -> the measures
--   Quarter / Month                     -> pre-computed grains for the grain control
--
-- `Period Name` is what makes comparative KPIs possible without a second query:
--   current  = SumIf([Revenue], [Period Name] = "Current Period")
--   prior    = SumIf([Revenue], [Period Name] = "Prior Period")
-- See reference/command-center-recipes.md §1.
--
-- This is SNOWFLAKE dialect. See base-table-databricks.sql for the same shape
-- in Databricks SQL, and reference/warehouse-portability.md for the mapping.
--
-- Everything is generated from one `product` constant block so the arithmetic
-- reconciles BY CONSTRUCTION: if the KPI band and the ranked table both read
-- from here they cannot disagree, which is the first thing an analyst checks.
-- Swap the two CTEs for your real tables when you have them.

WITH product AS (
    SELECT 'Line A' AS product, 1 AS product_order, 96 AS volume_base,
           0.972 AS yield_rate, 0.348 AS cost_rate, 0.46 AS fee_monthly,
           0.091 AS risk_rate, 0.214 AS opex_ratio, 0.086 AS annual_growth,
           1.038 AS goal_pct
    UNION ALL SELECT 'Line B', 2, 31, 0.966, 0.392, 0.28, 0.112, 0.228, 0.186, 1.061
    UNION ALL SELECT 'Line C', 3, 19, 0.964, 0.406, 0.16, 0.124, 0.236, 0.142, 0.981
    UNION ALL SELECT 'Line D', 4, 13, 0.958, 0.438, 0.21, 0.108, 0.244, 0.118, 0.942
    UNION ALL SELECT 'Line E', 5, 11, 0.970, 0.326, 0.11, 0.131, 0.218, 0.164, 1.014
    UNION ALL SELECT 'Line F', 6,  6, 0.944, 0.472, 0.34, 0.226, 0.262, 0.208, 0.908
),
states AS (
    SELECT 'TX' AS state, 0.142 AS state_share
    UNION ALL SELECT 'FL', 0.098  UNION ALL SELECT 'GA', 0.081
    UNION ALL SELECT 'CA', 0.069  UNION ALL SELECT 'NC', 0.062
    UNION ALL SELECT 'SC', 0.058  UNION ALL SELECT 'TN', 0.049
    UNION ALL SELECT 'OH', 0.045  UNION ALL SELECT 'PA', 0.041
    UNION ALL SELECT 'IL', 0.038  UNION ALL SELECT 'AZ', 0.034
    UNION ALL SELECT 'AL', 0.031  UNION ALL SELECT 'VA', 0.029
    UNION ALL SELECT 'MO', 0.026  UNION ALL SELECT 'IN', 0.024
),
months AS (
    -- 24 complete months: index 0-11 = prior period, 12-23 = current period.
    SELECT DATEADD('month', SEQ4() - 23, DATE_TRUNC('month', CURRENT_DATE())) AS period_month,
           SEQ4() AS month_index
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
grid AS (
    SELECT
        p.*,
        s.state,
        s.state_share,
        m.period_month,
        m.month_index,
        -- a deterministic per-state tilt so each state has its own story and the
        -- map has something to show. HASH keeps it stable across runs.
        (MOD(ABS(HASH(s.state || p.product)), 21) - 10) / 100.0 AS state_tilt,
        -- mild seasonality so the sparklines and trend chart aren't straight lines
        1 + 0.06 * SIN((m.month_index + p.product_order) * 3.14159265 / 6) AS seasonal
    FROM product p
    CROSS JOIN states s
    CROSS JOIN months m
),
calc AS (
    SELECT
        product,
        product_order,
        state,
        period_month,
        month_index,
        goal_pct,
        CASE WHEN month_index >= 12 THEN 'Current Period' ELSE 'Prior Period' END AS period_name,
        volume_base
          * state_share
          * (1 + state_tilt)
          * POWER(1 + annual_growth / 12, month_index)
          * seasonal                                            AS volume,
        yield_rate, cost_rate, fee_monthly, risk_rate, opex_ratio
    FROM grid
)
SELECT
    CAST(product          AS VARCHAR)      AS "Product",
    CAST(product_order    AS NUMBER)       AS "Product Order",
    CAST(state            AS VARCHAR)      AS "State",
    CAST(period_month     AS DATE)         AS "Period",
    CAST(period_name      AS VARCHAR)      AS "Period Name",
    -- pre-computed grains: DateTrunc(Lower([Grain]), ...) is an Invalid Query in
    -- Sigma, so a grain control must hold a literal date part. See
    -- reference/command-center-recipes.md §8.
    CAST(DATE_TRUNC('quarter', period_month) AS DATE) AS "Quarter",
    CAST(DATE_TRUNC('month',   period_month) AS DATE) AS "Month",
    CAST(volume                         AS NUMBER(18,4)) AS "Volume",
    CAST(volume * yield_rate            AS NUMBER(18,4)) AS "Revenue",
    CAST(volume * cost_rate             AS NUMBER(18,4)) AS "Cost",
    CAST(fee_monthly                    AS NUMBER(18,4)) AS "Ancillary",
    -- NOTE: this column is a SPREAD (revenue - cost + ancillary), i.e. a gross
    -- margin. If your business's headline number is revenue, do NOT label this
    -- "Revenue" on a card — name it for what it computes. This mislabelling has
    -- been shipped more than once.
    CAST(volume * yield_rate - volume * cost_rate + fee_monthly
                                        AS NUMBER(18,4)) AS "Net Revenue",
    CAST(volume * risk_rate             AS NUMBER(18,4)) AS "Provision",
    CAST(volume * yield_rate * opex_ratio AS NUMBER(18,4)) AS "Opex",
    CAST(volume * yield_rate - volume * cost_rate + fee_monthly
         - volume * risk_rate - volume * yield_rate * opex_ratio
                                        AS NUMBER(18,4)) AS "Contribution Profit",
    CAST(risk_rate                      AS NUMBER(9,4))  AS "Risk Rate",
    CAST(cost_rate * 100                AS NUMBER(9,4))  AS "Cost Pct",
    CAST(goal_pct                       AS NUMBER(9,4))  AS "Goal Pct"
FROM calc
