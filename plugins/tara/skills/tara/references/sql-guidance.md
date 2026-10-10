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
  or `information_schema`, no file path or volume source. Cell-level embeddings
  and the centred absolute pathway-score run are not served.
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
- Two drug labels carry a trailing space: match `drug IN ('Erdafitinib',
  'Erdafitinib ')`, not `=` alone.
- Quote hyphenated column names with backticks (`` `moa-fine` ``,
  `` `tahoe-x1-3b` ``).
- Several annotation columns are `; `-separated lists (for example the driver
  genes in `cell_line_metadata`): test membership with
  `array_contains(split(Driver_Gene_Symbol, '; '), 'KRAS')`, not `=`.
- `cell_line` in the large tables is the service's internal code; join
  `cell_line_metadata` on `cell_id` to return Cellosaurus ids and names. Never
  put the internal code in a deliverable.
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

## The approved tables

Grain, keys and the columns to filter on. Tables marked **LARGE** need a
selective `WHERE` in the `SELECT` that reads them.

| Table | Grain | Keys |
|---|---|---|
| `pseudobulk_expression` **LARGE** | one gene × sample aggregate (dense) | `gene_name`, `drug`, `cell_line`, `sample_id`, `plate` |
| `deseq2_results` **LARGE** | one gene in one tested contrast | `drug`, `cell_line`, `gene_name`, `gene_id`, `plate` |
| `single_cell_expression` **LARGE** | one stored nonzero (cell, gene) | `cell_line`, `sample`, `cell_joinid`, `gene_joinid` |
| `obs` **LARGE** | one cell | `cell_line`, `drug`, `sample`, `sublibrary` |
| `augur_feature_results` **LARGE** | one gene's classifier feature in one model | `drug`, `cell_line`, `gene`, `plate` |
| `vision_scores_pseudobulk_differential` **LARGE** | one treated pseudobulk sample × gene set | `drug`, `cell_line`, `gene_set`, `plate` |
| `phenotype_scores` | one drug × line × dose × plate × phenotype | `drug`, `cell_line`, `dose`, `plate`, `phenotype` |
| `gene_metadata` | one gene | `gene_name`, `ensembl_id`, `gene_joinid` |
| `cell_line_metadata` | one cell line | `cell_id`, `cell_line_id_cellosaurus`, `cell_name` |
| `drug_metadata` | one drug label | `drug` |
| `augur_summary_results` | one Augur AUC per drug × line × plate | `drug`, `cell_line`, `plate` |
| `gini_heterogeneity` | one heterogeneity row per condition × resolution | `perturbation`, `cell_line`, `plate` |
| `survival_log_odds_ratio` | one survival log-odds row per plate × line × drug | `drug`, `cell_line`, `plate` |
| `cell_cycle_arrest_results` | one arrest score per plate × line × drug × analysis | `drug`, `cell_line`, `plate`, `analysis_type` |
| `survival_effect_size_odds_ratio`, `survival_significance_neg_log10p`, `cell_cycle_effect_size_matrix`, `cell_cycle_significance_matrix` | wide matrices: one row per drug × concentration, one column per cell line | `drug__concentration`, `analysis_type` |
| the Tahoe-x1 embedding-centroid table | one drug × line × plate centroid, mean embedding + cell count | `cell_line`, `plate` |

The centred absolute pathway-score run is refused by the guard; only the
differential pathway scores are served.

## Notes per table

- **`pseudobulk_expression`** — `cpm_log1p = ln(1 + 1e6 * raw_counts /
  total_counts)`; use `raw_counts` for count models. The vehicle is `dose = 0`
  (not a name match). `n_cells` is the aggregate size, not a replicate count.
  `cell_line` is the internal code.
- **`deseq2_results`** — `dose` is a **string** (`'0.05'`, `'0.5'`, `'5.0'`);
  `padj` and `pvalue` are optimistic (three synthetic pseudoreplicates), and a
  NULL `padj` means the gene was untested, never "no effect". Two external-id
  columns are placeholders in this export — use the crosswalk. Not the public
  `tahoe-de-rhaister` statistics, which use a different method.
- **`single_cell_expression`** — clustered by (cell_line, sample): put both
  predicates here, then join `obs` on `cell_joinid = soma_joinid` and
  `gene_metadata` on `gene_joinid`. Never scan one gene across all cells; use
  `pseudobulk_expression` for that. An absent row means zero only inside the
  verified measured axes.
- **`obs`** — per-cell QC (`gene_count`, `tscp_count`, `pcnt_mito`), cell-cycle
  scores and `phase`. `soma_joinid` matches `single_cell_expression.cell_joinid`.
  Always filter on `drug` or `cell_line`.
- **`phenotype_scores`** — the primary condition-level table. `phenotype` is
  `survival`, `g1_arrest`, `s_arrest`, `g2m_arrest`, `gini` or `augur`, and it
  selects the meaning of `score`, `p_value`, `p_adj_fdr` and `significant` (NULL
  for gini and augur — absent is not "not significant"). Here `cell_line` is the
  Cellosaurus id. `dose` is a float in uM. No vehicle rows. Filter `phenotype`
  first. Survival is a **relative** abundance log odds ratio: uniform killing
  reads near zero, so a score near zero is not "no effect".
- **`gene_metadata`** — `gene_name` is the Ensembl id where no symbol exists;
  `gene_joinid` matches `single_cell_expression.gene_joinid`.
- **`cell_line_metadata`** — the 50-line crosswalk (49 cancer lines plus one
  immortalized normal line). Join it for Cellosaurus ids and names.
- **`drug_metadata`** — verbatim released annotations: targets, a broad and a
  fine mechanism class, approval and trial status, SMILES, `pubchem_cid`. Salt
  forms are separate labels. `unclear` means the mechanism is not confidently
  assigned, not that the compound has no effect.
- **`augur_feature_results`** — mean classifier feature importance. Importance is
  not a fold change and carries no direction; take direction from
  `deseq2_results` or `pseudobulk_expression`. A gene absent here is not in that
  model.
- **`vision_scores_pseudobulk_differential`** — the score is the change in
  gene-set activity versus the matched vehicle mean. No statistics. It is already
  a contrast: use it as-is, never subtract a vehicle again. `conc` is in uM.
- **The embedding-centroid table** — a centroid is the mean of cells, not a cell
  and not a replicate. Compare distances within a line, plate-matched, and do not
  interpret a direction. A low cell count makes a centroid noisy.
- **The wide matrices** — one column per cell line (Cellosaurus ids), NULL where
  untested. Prefer `phenotype_scores` for survival, arrest, gini and augur.
