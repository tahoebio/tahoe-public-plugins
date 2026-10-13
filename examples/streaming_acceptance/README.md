# Tara streaming acceptance examples

These examples exercise the bundled public Tara client and the served data
access handles. They are separate from server implementation tests and make no
readiness claim until both examples pass against a Tahoe-backed served source
with public-user-equivalent access.

## Cases

| Case | User workflow | Required green checks |
|---|---|---|
| A | Request 1,000 cells for one exact cell-line and drug condition | The source reports a pinned release, source/population revision, complete eligible count, and raw-count schema; returns exactly 1,000 unique cells from that condition; seed replay returns the same sample; every gene/count pair is aligned, unique, nonnegative integer raw counts on the pinned gene axis; resume after a saved checkpoint has no gaps or duplicates. |
| B | Feed random control/treated cells to a sentence-length-one STATE-style loader, grouped by plate | Raw sparse counts reconstruct exactly from source rows; treated SMILES equal the pinned canonical SMILES and control SMILES are null; each treated cell pairs with one independently seeded control from the same plate, line, timepoint and units; deterministic seed, acknowledged resume, and two-rank/two-worker treatment sharding have no lost or duplicated targets. |

Both cases record source and gene-axis revisions, schema, eligible and returned
population sizes, row/nonzero totals, deterministic sample digests, time to
first batch, decoded throughput, and process peak RSS. The output report contains
aggregate evidence only; access handles, signed URLs, tokens, cell identifiers,
and row payloads are never written to the report.

The served sample metadata must bind `source_kind`, `population_product`,
`population_revision`, `population_complete`, the nested exact condition,
`dataset_version`, `snapshot_version`, sample `revision`, `seed`, requested,
returned and eligible cell counts, `counts_space`, `expression_encoding`,
`gene_axis_revision`, `reserved_source_bytes`, and `reserved_decoded_bytes`.
Case B also binds its separate treated and control products/conditions. The row
schema is supplied from the authorized product binding and checked against every
received row. The harness rejects missing provenance, incomplete censuses, an
unknown count encoding, changed axes, or reservations above the approved case
caps. These fields are intentionally required for a green report; a fixture or
local export cannot supply served-source provenance.

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
gene-axis, SMILES, and quota bindings. It never initiates OAuth or sends a
request. Supply the exact authorized endpoint and source bindings in the JSON
config described by `config.example.json`; bind `base_url` to
`authorized_base_url`, set `auth_mode` to `public_plugin_oauth`, set
`identity_mode` to `public_user_equivalent`, and provide the quota policy and
live-test approval reference. Do not add tokens or passwords to the file. The
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
