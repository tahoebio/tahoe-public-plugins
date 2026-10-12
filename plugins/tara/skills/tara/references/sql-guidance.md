# Querying the served tables with SQL

`run_sql(statement, max_rows)` runs **one** read-only SQL query over the
approved tables. Use the bounded tools first (`search_conditions`,
`resolve_genes`, `get_expression_slice`, `get_guide`); reach for SQL when a
question needs a join, an aggregate or a table the bounded tools do not expose.
Tables are named by their bare name (the service resolves and qualifies it); the
served names are the ones `list_releases` reports. The dialect is Databricks SQL.

What runs is the **server-normalized** SQL: tables qualified, comments and hints
dropped, an outer `LIMIT` added. It is echoed in `manifest.sql` with its
`sql_sha256` — cite it to reproduce a result. `max_rows` is 1 to 1000 (default
200); your own `LIMIT` can only lower the cap. `truncated`, or
`complete = false`, means the row cap or the response size cut the result:
aggregate in SQL instead of paging. A slow query returns `pending`: call again
with the SAME statement and `result_handle`. A query running longer than about a
minute is cancelled. Each call costs three request units; a refused statement
costs none.

## What the guard refuses

The statement is parsed and refused with a fixed `error_type` that never echoes
your SQL:

- `not_read_only`, `multiple_statements`, `parse_failed` — one `SELECT` / `WITH`
  / `UNION` only. No writes, DDL, `SET`, `DESCRIBE`, `SHOW` or `EXPLAIN`, and no
  second statement.
- `table_not_allowed` — only the approved tables. No other catalog, no `system`
  or `information_schema`, no file path or volume source. The per-cell
  embedding table is not served.
- `function_not_allowed` — no file, network, AI, reflection, identity or
  generator functions (`read_files`, `http_request`, `ai_*`, `reflect`, `url_*`,
  `current_user`, `sequence`, `repeat`), no table-valued functions, no qualified
  function calls.
- `filter_required` — a **large** table needs, in the `WHERE` of the `SELECT`
  that reads it, a `key = literal` or `key IN (literals)` on one of its keys. A
  subquery, a range, `LIKE`, `IS NOT NULL`, `NOT`, a constant such as `1 = 1`,
  and an `OR` with an unfiltered branch do **not** count; a filter in an outer
  query does not unlock a CTE or a subquery below it. A function such as
  `trim(drug)` does not count as a key filter.
- `query_too_costly` — no cross, comma or natural join; every join needs an
  `a.col = b.col` predicate between two different, qualified tables (or `USING`);
  no `WITH RECURSIVE`; at most four tables.
- Also refused: Delta time travel (`VERSION AS OF`, `TIMESTAMP AS OF`), hidden
  columns (names starting with `_`), parameter markers, and a CTE named like an
  approved table (`WITH obs AS ...`).

## Habits that avoid trouble

- Filter `drug`, `cell_line` or a gene on the large table itself, and join the
  small tables after.
- Two drug labels carry a trailing space in the data tables (not in
  `drug_metadata`): filter with `drug IN ('Erdafitinib', 'Erdafitinib ')`, and
  join the metadata on `trim(t.drug) = m.drug`, or both drugs silently drop.
- Quote hyphenated column names with backticks (`` `moa-fine` ``,
  `` `tahoe-x1-3b` ``).
- Several annotation columns are `; `-separated lists (for example the driver
  genes in `cell_line_metadata`): test membership with
  `array_contains(split(Driver_Gene_Symbol, '; '), 'KRAS')`, not `=`.
- Unbounded aggregates such as `collect_list` over a large filtered table are
  cancelled at the time limit.

```sql
-- MEK / RAF inhibitors and what they target
SELECT drug, targets, `moa-fine` FROM drug_metadata
WHERE `moa-fine` LIKE '%MEK%' OR `moa-fine` LIKE '%RAF%' ORDER BY drug
```

```sql
-- Condition-level survival scores for one drug, with cell-line identity
SELECT p.cell_line, c.cell_name, p.dose, p.score, p.p_adj_fdr
FROM phenotype_scores p JOIN cell_line_metadata c ON p.cell_line = c.cell_line_id_cellosaurus
WHERE p.drug = 'Trametinib' AND p.phenotype = 'survival' ORDER BY p.score LIMIT 50
```

```sql
-- Top differentially expressed genes of one contrast
SELECT c.cell_name, d.gene_name, d.log2FoldChange, d.padj
FROM deseq2_results d JOIN cell_line_metadata c ON d.cell_line = c.cell_id
WHERE d.drug IN ('Trametinib', 'Trametinib ') AND d.dose = '5.0'
  AND d.gene_name IN ('TP53', 'MYC') ORDER BY d.padj LIMIT 20
```

## Table semantics

Which tables are served, their grain, keys, units, missing-value meaning and
measurement-versus-contrast status are **not restated here**: the server
generates them from its own schemas. Read `get_guide(topic="table-reference")`
before writing a query, and `get_guide(topic="querying-with-run-sql")` for the
server's own query notes. Table names come from `list_releases`.

Traps that hold across tables:

- A table named `*_differential` is already vehicle-subtracted: use it as-is and
  never subtract a vehicle again. Its absolute counterpart is not subtracted and
  carries the vehicle rows. A NULL there means no matched vehicle, not zero.
- `dose` is a string in some tables and a float in others; check the table's
  schema in the guide before filtering.
- A table's `gene` or `cell_line` column may be an internal index or code, not a
  symbol or a Cellosaurus id: resolve it through the metadata tables, and never
  put an internal code in a deliverable.
- Importance, centroid-distance and survival-style scores are not fold changes;
  take direction from an expression or differential table.
