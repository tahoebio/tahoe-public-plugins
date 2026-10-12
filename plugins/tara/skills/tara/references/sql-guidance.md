# SQL routing and response limits

Use a bounded tool first. Use `run_sql(statement, max_rows)` for a join,
aggregate or approved table those tools do not expose. Before writing SQL, read
`get_guide(topic="querying-with-run-sql")` for the guard's current rules and
`get_guide(topic="table-reference")` for current aliases, columns, keys and
scientific semantics. `list_releases()` identifies the served release.

Submit one read-only statement over approved tables. `max_rows` is 1 to 1,000
(default 200); a result is also bounded to 40 KB. For per-cell expression, use
SQL aggregates over the advertised `single_cell_expression` table. These
limits do not support a full cell-matrix export or pagination around the ceiling,
and do not cap the warehouse scan cost.

Use `manifest.sql` and `sql_sha256` to record the server-normalized statement.
If the response is `pending`, poll the same tool with the same statement and
`result_handle`; do not resubmit. If it is truncated, narrow the query or return
an aggregate summary instead. Request-unit costs and runtime bounds are defined
by the service; they are not dollar limits.

```sql
-- A small metadata aggregate
SELECT COUNT(*) AS n FROM drug_metadata
```

The server guide explains required key filters, joins, allowed functions and
refused statements. See [tool-routing.md](tool-routing.md) for the error
vocabulary. Read the scientific layer's guide and result provenance before
interpreting query output, including `differential-expression` for released
log2 fold changes and `phenotype-readouts` for phenotype-specific statistics.
