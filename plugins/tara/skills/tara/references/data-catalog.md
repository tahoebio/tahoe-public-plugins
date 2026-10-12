# The served Tahoe-100M dataset

What this server serves, and the traps to avoid. This is not an inventory:
confirm what a release contains with `list_releases`, `search_conditions`,
`list_cell_lines` and `resolve_genes`, and read `get_guide(...)` for the
server's own account of conditions and controls, genes, expression grain,
differential expression and table semantics (its topic list is in the response).
`list_releases()` names the release; every result carries it, so a figure can be
pinned. A newer release is a source change: re-establish coverage.

## What is served

One bounded, read-only slice of the public **Tahoe-100M** release, reached only
through this server's tools. There is no direct table or file access; the only
client-supplied query is one guarded, read-only `run_sql` statement over the
approved tables. Every tool is read-only and runs as the service's
own read identity, so the release is the same for every caller. Responses are
bounded to a fixed byte ceiling: a truncated response says so, and narrowing the
request is the only way to see more.

## Coverage traps

- Presence in a compound library is not coverage in the release. Confirm an arm
  exists with `search_conditions` before a question or request assumes it.
- Panel drug names appear as free base and as salt form. Count and ranking
  questions over drugs must dedupe to the parent or active moiety, or one drug
  counts twice and top-N rankings shift.
- Drug and cell-line labels are case-sensitive and may be lowercase or carry a
  salt suffix. Confirm the exact label with `search_conditions(query=...)` before
  a request assumes it, and use the label verbatim.
- The panel is cancer lines plus one immortalized normal line; exclude or note
  it before a pan-cancer claim. The same caution applies to genotype and lineage
  strata, where n can be thin.
- A substring match on the vehicle label also selects real treatments whose
  labels contain that substring as a salt. Match the vehicle as the exact label,
  not a substring.
- A missing row is not zero. Sparse omissions mean zero only inside the verified
  measured gene and condition axes; an unmeasured gene or an absent condition is
  unavailable, not zero.
- Coverage facts are release-specific, so re-check them when the release changes.

## Citation and provenance

Tahoe-100M is public: Zhang et al. (2025), "Tahoe-100M: A Giga-Scale Single-Cell
Perturbation Atlas for Context-Dependent Gene Function and Cellular Modeling",
bioRxiv [10.1101/2025.02.20.639398](https://doi.org/10.1101/2025.02.20.639398);
CC0 release on
[Hugging Face](https://huggingface.co/datasets/tahoebio/Tahoe-100M) and the
[Arc Virtual Cell Atlas](https://arcinstitute.org/tools/virtualcellatlas). Cite
the release when asked about provenance.

## What these tools do not serve

Only the public Tahoe-100M release is served -- one drug panel (379 treatments,
3 doses, vehicle `DMSO_TF`), one 50-line cell panel, 14 plates. There is no file
or table browsing; the only client-supplied query is a guarded `run_sql`
statement, and a table outside the approved set is refused. Not available, so do
not search for it here:
other Tahoe screens or unreleased datasets; clinical or adverse-event data;
proprietary external reference panels (dependency, viability or signature
databases) joined to this release; unreleased compound annotations beyond the
released drug metadata; per-cell embeddings (public in the Hugging Face release,
not through these tools); embedding vectors themselves (distances only); internal
cell-line codes (results carry Cellosaurus ids and names). If a
question needs one of these, say so and stop; do not substitute a different
population, measurement or dataset silently.
