# SQL routing and response limits

Use a bounded tool first. Use `run_sql(statement, max_rows)` for a join,
aggregate or approved table those tools do not expose. For Tahoe, read
`get_guide(topic="querying-with-run-sql")` and
`get_guide(topic="table-reference")`. For Emerald, pass
`dataset="emerald-bay"` to both guide calls and every SQL call. Confirm the
selected entry in `list_releases()` advertises the tool and required aliases.

Only one read-only statement over approved aliases is permitted. Never use
cross-dataset joins, guessed table names, storage paths or external sources.
`max_rows` is 1 to 1,000 (default 200), and results are bounded to 40 KB.
Neither bound permits a full cell-matrix export, pagination around the ceiling,
or an unfiltered warehouse scan. Large tables require selective key filters;
read the selected guide for exact keys, columns, joins and allowed functions.

Tahoe's per-cell alias is `single_cell_expression`; Emerald's is
`expr_expression_cell`. Confirm availability and columns in the guide before
use. Keep aligned sparse arrays aligned. For Emerald joins, retain sample and
line keys, the measured-gene boundary, unavailable lattice rows and complete
profile totals. Do not turn missing profiles into zeros or normalize only the
requested genes. The bounded expression tool is preferable for CPM/log1p.

A Tahoe metadata aggregate, without the new dataset argument:

```json
{"tool":"run_sql","arguments":{"statement":"SELECT COUNT(*) AS n FROM drug_metadata","max_rows":100}}
```

An Emerald metadata aggregate, only after its capability check:

```json
{"tool":"run_sql","arguments":{"dataset":"emerald-bay","statement":"SELECT COUNT(*) AS n FROM phenotype_sample","max_rows":100}}
```

Use the returned manifest to retain normalized SQL, bound parameters where
present, SQL hash, dataset/release and server version. On `pending`, poll the
same tool with the same dataset, statement and effective arguments plus the
returned `result_handle`. Do not resubmit. On truncation, narrow or aggregate;
do not present a prefix as complete. Request-unit and runtime limits are not
dollar limits. See [tool-routing.md](tool-routing.md) for refusal handling.
