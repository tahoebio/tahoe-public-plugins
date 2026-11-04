# Tara

Tara gives Claude and Codex read-only access to Tahoe Bio's single-cell
perturbation data. It covers Tahoe-100M, and Emerald Bay where your account can
reach it. The plugin adds a skill that guides analysis and connects to Tahoe's
remote MCP server. With it you can look up drugs, cell lines and genes, read drug
annotations, and retrieve expression, differential expression, perturbation
markers, pathway scores and embedding distance from vehicle.

## Install and sign in

Follow the install guide at <https://tara.tahoebio.io/install.md>. You add the
`tahoebio/tahoe-public-plugins` marketplace, install the `tara` plugin, and
then sign in with Google in the browser your client opens. You need a Tahoe
account to sign in. Your account decides which datasets and releases you can
use.

## Example prompts

- Which MEK and RAF inhibitors are in Tahoe's data?
- Does binimetinib up- or down-regulate KRAS signaling in Tahoe's data?
- In Tahoe's data, is Pitavastatin's stronger YAP suppression than
  Pravastatin's driven by greater on-target activity?

## Data flow

The plugin itself runs no code on your machine. Your client sends each tool call
to the remote server at <https://tara.tahoebio.io/mcp>, which processes the tool
arguments and returns results. Read the privacy policy at
<https://tara.tahoebio.io/privacy> and the terms at
<https://tara.tahoebio.io/terms>.

## Limits

Tara is for research use only. It gives no clinical or medical advice. Every
tool is read-only: it can query the data but cannot change it.

## Support

Report problems at <https://github.com/tahoebio/tahoe-public-plugins/issues>
or email tara@tahoebio.ai.

## Licenses

The plugin code and manifests are Apache-2.0 (`LICENSE`). The skill text and
documentation are CC BY 4.0 (`LICENSE-CC-BY-4.0`). `NOTICE` maps each part to
its licence. Tahoe-100M data is CC0 1.0, and Emerald Bay source data is CC BY
4.0, which requires attribution. The Tahoe logo and the names "Tahoe" and
"Tara" are not licensed.
