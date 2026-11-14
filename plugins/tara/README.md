# Tara

Explore how drugs change gene expression, pathways and cell states with
Tahoe Bio's single-cell perturbation data, directly in Claude and Codex.
Tara combines access to a remote MCP server with a skill for choosing
measurements, checking coverage and interpreting results.

Tahoe-100M provides drug annotations, expression, drug-versus-vehicle
differential expression, perturbation markers, pathway scores, relative
depletion, cell-cycle effects and embedding distance from vehicle. Its
validated signatures panel identifies a readout where one exists, with evidence
and caveats; it reports when no validated readout is available, and no other
set is substituted.
Emerald Bay provides expression, five-day in-vitro growth response and
differential VISION scores. Available datasets and tools depend on your account.
These measurements do not establish a drug's mechanism or patient benefit.

## Install and sign in

Follow <https://tara.tahoebio.io/install.md>. Install the `tara` plugin from
`tahoebio/tahoe-public-plugins`, then sign in with your email address or Google
in the browser your client opens. This creates or uses your Tahoe account.

In Claude Code, run
`claude plugin marketplace add tahoebio/tahoe-public-plugins`, then
`claude plugin install tara@tahoe-public`.

## Example prompts

- Which MEK and RAF inhibitors are in Tahoe's data?
- Does binimetinib up- or down-regulate KRAS signaling in Tahoe's data?
- In Tahoe's data, is Pitavastatin's stronger YAP suppression than
  Pravastatin's driven by greater on-target activity?

## Data flow and limits

The plugin runs no local code. Your client sends tool arguments to
<https://tara.tahoebio.io/mcp>. The service logs tool arguments, including SQL,
and usage metadata as described in the [privacy policy](https://tara.tahoebio.io/privacy).
Do not include credentials, patient information or confidential material in calls.

Dataset queries are read-only. The cancellation tool stops your pending query;
the feedback tool sends text to Tahoe only when you ask. Neither changes the
scientific datasets. Results have row and size limits; incomplete results must
be narrowed or reported as incomplete.

Tara is for research use only, not clinical or treatment advice.
Read the [terms](https://tara.tahoebio.io/terms).

## Support and licences

Report problems at <https://github.com/tahoebio/tahoe-public-plugins/issues>
or email tara@tahoebio.ai.

Code and manifests are Apache-2.0; skill text and documentation are CC BY 4.0.
The included [Apache licence](LICENSE), [CC BY licence](LICENSE-CC-BY-4.0.txt)
and [licence notice](NOTICE.md) give the details. Tahoe-100M data is
CC0; Emerald Bay source data is CC BY 4.0 and requires attribution.
The Tahoe logo and the names "Tahoe" and "Tara" are not licensed.
