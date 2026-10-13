# Tara streaming acceptance examples

These examples exercise the bundled public Tara client and the served data
access handles. They are separate from server implementation tests and make no
readiness claim until both examples pass against a Tahoe-backed served source
with public-user-equivalent access.

## Cases

| Case | User workflow | Required green checks |
|---|---|---|
| A | Request 1,000 cells for one exact cell-line and drug condition | A listed Tahoe-100M single-cell product and immutable snapshot are pinned; the sample reports its revision and complete eligible count; exactly 1,000 unique matching cells arrive with raw-count schema; seed replay returns the same sample; every gene/count pair is aligned, unique, nonnegative integer raw counts on the pinned gene axis; resume after a saved checkpoint has no gaps or duplicates. |
| B | Feed random control/treated cells to a sentence-length-one STATE-style loader, grouped by plate | Prepare the treated sample with `prepare_cell_sample` and each complete pinned control well with `prepare_dataset`; raw sparse counts reconstruct exactly from source rows; treated SMILES equal the pinned canonical SMILES and control SMILES are null; each treated cell pairs with one independently seeded control from the same plate, line, timepoint and units; deterministic seed, acknowledged resume, and two-rank/two-worker treatment sharding have no lost or duplicated targets. |

Both cases record source and gene-axis revisions, schema, eligible and returned
population sizes, row/nonzero totals, deterministic sample digests, time to
first batch, decoded throughput, and process peak RSS. The output report contains
aggregate evidence only; access handles, signed URLs, tokens, cell identifiers,
and row payloads are never written to the report.

The harness binds each input to a listed public product and revision. It checks
the sample response's `dataset_version`, `snapshot_version`, exact condition,
`revision`, `seed`, `sampling_algorithm`, `replacement`, requested/returned/
available cell counts, `counts_space`, `expression_encoding`, and
`gene_axis_revision`. Complete-population behavior is part of the bounded server
acceptance check: incomplete populations must be refused before sampling. The
client requires more than 1,000 eligible cells and verifies 1,000 unique
selected cell ids, so a 1,000-row replay cannot be reported as a larger
population. The exact row schema and ordered gene axis are pinned from the
authorized source binding and checked against every received row.

The source-pinned config keeps `source_pins.file_sha256["gene-axis.parquet"]`
as the byte-level integrity hash of the Parquet source, unchanged from the
export inventory, and mirrors it as `gene_axis_file_sha256` for the runner.
The preflight requires this file hash to equal the pinned `gene_axis_revision`.
The separately named `expected_gene_axis_tokens_sha256` is
the semantic SHA-256 of the ordered `token_id` integer array encoded as compact
UTF-8 JSON, matching `gene_axis_digest()`. The exporter selects
`ORDER BY token_id`, asserts 62,710 rows and the exact `range(3, 62713)`, and
writes those rows in order. That code provenance supports the semantic digest
bound in the config, but does not itself prove the restored served artifact's
contents. Before a live case can pass, the prepared gene-axis product must
report the pinned product revision/file SHA-256 and its returned ordered token
IDs must hash to `expected_gene_axis_tokens_sha256`. No live restoration was
tested here.

For each cell row, the schema must contain `cell_id` (integer), `cell_line_id`,
`drug_id`, `drug`, `sample`, `plate`, `dose_unit`, and `timepoint_unit`
(nonempty strings), `dose` and `timepoint` (finite numbers), `is_control`
(boolean), `canonical_smiles` (the exact pinned canonical SMILES for treated
cells and null for controls), plus `genes` and `expressions` (aligned sparse
arrays). Pinned exports may also include `BARCODE_SUB_LIB_ID`, `pubchem_cid`,
`moa_fine`, `gene_count`, `tscp_count`, and `timepoint_provenance`; the exact
column list is bound per source. Known optional column types are checked too.
Each gene token must be an integer on the exact ordered pinned axis;
tokens must be unique per row; each raw count must be finite, nonnegative, and
integral. Both column names and row value types are checked exactly, with no
extra or missing columns. The State batch is then compared against its source
rows for exact sparse count parity.

## Bounded serving checks

Before calling either case end-to-end accepted, run these bounded checks against
the serving implementation and the public Tahoe source: (1) a complete
condition with more than 1,000 eligible cells returns 1,000 unique IDs, and the
same seed plus unchanged sample `revision` reproduces those IDs and count rows;
(2) a changed seed selects a different deterministic subset; (3) an incomplete
or census-mismatched population is refused before the count reader is invoked;
(4) the returned sample metadata and each row match the pinned release,
snapshot, condition, count encoding, gene-axis revision, exact schema and
canonical drug SMILES; (5) the selected source URLs use only the approved Tahoe
hosts; and (6) an identity denial, quota response, service pause, or source
budget refusal is surfaced without retrying or changing grants/settings. Keep
the population fixture limited to the requested condition and enough cells to
prove it exceeds 1,000; do not export or copy the data to a new host.

The harness needs only the existing advertised product fields `id`, `dataset`,
`layer`, `revision`, `format`, and `grain`; sample fields `access_handle`,
`status`, `requested_cells`, `returned_cells`, `available_cells`, `seed`,
`sampling_algorithm`, `replacement`, `condition`, `dataset_version`,
`snapshot_version`, `gene_axis_revision`, `expression_encoding`,
`counts_space`, and `source_product`. Opened-source metadata includes `product`,
`revision`, `dataset`, `layer`, `grain`, and `format`.
The endpoint coordinator still needs to bind the exact ordered gene axis and
row schema from the approved source manifest, along with the canonical drug
SMILES and matched control condition. This harness does not request new byte
reservation fields or a new population-revision field. PR53's sample `product`
identifies its generated `sample-*` artifact, not the registered bank used to
select the cells. The sample response's `source_product` identifies that
registered source bank; Case A and the treated side of Case B assert it.

The 1,000 rows are a sample from the reported complete eligible population. A
repeated 1,000-row sample is not scale evidence. These examples do not claim
whole-atlas coverage, do not fall back to Hugging Face or Databricks, and do not
turn hosted HF fixtures or local Delta-export parity into served-source passes.

## Offline preflight

From the repository root:

```sh
python examples/streaming_acceptance/preflight.py --case all
```

The preflight is offline and reads no credential values. It prints a red/green
JSON checklist of missing endpoint, product, release, condition, population,
gene-axis semantic digest, SMILES, and quota bindings. It never initiates OAuth
or sends a request. The credential-free `config.tahoe-100m-v1.json` records the
currently verified source metadata, product conditions, control wells, row
schema, gene axis and source digests. It deliberately leaves the endpoint,
allowed hosts, quota policy, and live-test approval blank. The coordinator must
confirm the source pins against the staged deployment and fill those service
bindings before the preflight can turn green. For a different source, use
`config.example.json`. Do not add tokens or passwords to either file. The
runtime uses `tara_data.connect()` and its existing public OAuth flow. There is
no option for a generic endpoint bearer token.

## Run the live cases

Only run after the coordinator supplies an authorized endpoint/source binding
and live-test approval. Install the plugin's bundled reader requirements and
the existing cell/data libraries in an isolated Python environment. Then run:

```sh
python examples/streaming_acceptance/run_case_a.py --config /path/to/authorized-config.json --execute-live
python examples/streaming_acceptance/run_case_b.py --config /path/to/authorized-config.json --execute-live
```

The output is green only when every acceptance assertion passes. A permission,
quota, service-pause, schema, source-completeness or resume failure is red; the
runner closes opened handles and does not retry, broaden a filter, or select a
fallback source. `rate_limited` requires waiting for the caller's quota window.
`sign_in_required` and `not_invited` are permission/identity failures;
`rate_limited`, `sample_cache_capacity`, `sample_scan_budget_exceeded`, and
`sample_decoded_work_exceeded` are quota/capacity failures; `service_paused` and
`service_unavailable` are availability failures. No condition is repaired by
creating a grant, changing a quota or making an immediate retry.
The runner never changes grants, quota, service settings, or deployment state.

## Evidence classification

* Synthetic loopback, hosted HF-derived fixture, or cached replay: **component
  test**, not end-to-end acceptance.
* Local parity against a Delta export: **component test**, not end-to-end
  acceptance.
* A green Case A and Case B report from this runner, using the approved public
  endpoint, public OAuth identity, and Tahoe-backed source: **end-to-end
  acceptance** for these two pinned workflows only.

The examples do not authorize paid workload, endpoint changes, export/egress,
deployment, or permission changes.
