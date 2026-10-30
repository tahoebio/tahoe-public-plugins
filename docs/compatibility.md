# Compatibility

Only tested combinations are claimed. The install workflows target Codex CLI
and Claude Code; prepared instructions alone do not establish tested support.

## Hosts and requirements

- Codex CLI or Claude Code, with a Google account and browser for sign-in.
- No Databricks account or credentials are required.
- See `docs/install-verification.md` for recorded Tahoe runs, their failures and
  limitations. No fresh Emerald host run has been recorded yet.
- Other hosts, offline data access and alternate sign-in flows are not claimed.

## Plugin and server versions

Both manifests retain `extensions["com.tahoebio"]["minServerVersion"]` at
0.3.9 for existing Tahoe use. Compare versions numerically. A version check
alone never establishes a dataset's availability or numeric correctness.

| Plugin / route | Server requirement | Evidence / behavior |
|---|---|---|
| 0.3.4 Tahoe-100M | 0.3.9 or later | Legacy frozen record in `evals/tara/frozen-expected-0.3.x.md`. |
| 0.4.0 Tahoe-100M | 0.3.9 or later | Preserves legacy calls without a dataset argument; old numeric freezes apply only to their recorded versions. |
| 0.4.0 Emerald Bay | 0.4.0 or later plus advertised capabilities | Explicit dataset on every guide/data/SQL call; real host acceptance still required. |
| 0.5.0 Tahoe-100M and Emerald Bay | Unchanged from 0.4.0 | Legacy calls, including named `gene_sets` requests, are unchanged. |
| 0.5.0 validated signatures | 0.5.0 or later plus `validated_signatures` in discovery | The server default is off. Prepared and checked offline only; real host acceptance still required. |

For an Emerald request, require a successful, untruncated `list_releases`
response with the Emerald entry and requested capabilities. A legacy Tahoe-only
response, an unknown version, absent capabilities or an access refusal must
produce an unavailable/unverified result, never a Tahoe fallback. `health`
may recover a missing version, but cannot replace capability discovery.

An account allowed to validate Emerald can see it while another account still
sees only Tahoe. The plugin does not enable access, choose validator accounts or
change server configuration. Installing or merging this plugin does not make
Emerald public.

## Scientific and host verification

The historical Tahoe freezes were taken during the server 0.3.9 to 0.3.10
upgrade window. Revalidate when server, release or guide version changes; do
not reuse those values as Emerald expectations. Emerald expected values must
come from independent pinned source evidence, never the candidate response.

Offline checks validate schemas, shipped examples, guide topics, package
contents and residue. Fresh installed-plugin sessions on both hosts must still
verify selection, capability refusals, numerical semantics, provenance,
truncation and pending handles against the actual remote MCP. Record exact
plugin/server/host versions and guide versions. Blocked or skipped required
cases are incomplete, not passes. See [the Emerald eval pack](../evals/tara/emerald-README.md) and
[install checks](install-verification.md).
