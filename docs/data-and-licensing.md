# Data and licensing

Licensing is decided. This page says what each part of the repository is and
where its licence comes from. The full licence texts are in `LICENSE`
(Apache-2.0) and `LICENSE-CC-BY-4.0` (CC BY 4.0), and `NOTICE` carries the
attribution and the path map.

## What each part is, and its licence

| Part | What it is | Licence (SPDX) |
|------|------------|----------------|
| Plugin code | Manifests, scripts, tests, CI, configuration, the eval pack and root Markdown | `Apache-2.0` |
| Skill text | `plugins/tara/skills/**` and its references | `CC-BY-4.0` |
| Documentation | `docs/**` | `CC-BY-4.0` |
| Tahoe-100M source data | The Tahoe-100M dataset | `CC0-1.0` |
| Emerald Bay source data | The EmeraldBay dataset | `CC-BY-4.0` |
| Service guidance | Server instructions, tool descriptions, any guide the service returns | Not licensed for redistribution |
| Gene-set names | Names from the source collections | The source collection's terms |
| Vendored schemas | `schemas/plugin.schema.json`, `schemas/mcp.schema.json` (from agent-plugins.org) | `Apache-2.0` (upstream; `schemas/provenance.json`) |
| Brand assets | `plugins/tara/assets/tahoe-logo.png` — the Tahoe brand mark | Not licensed (all rights reserved) |
| Trademarks | "Tahoe", "Tara" | Not licensed |

## Plugin code — Apache-2.0

The code, manifests, tooling, tests and CI are licensed under the Apache
License 2.0 (see `LICENSE`). That licence grants a patent licence as well as
copyright permissions, and requires the attribution in `NOTICE` to be kept.

## Skill text and documentation — CC BY 4.0

The `tara` skill (`plugins/tara/skills/**`) and the documentation (`docs/**`)
are licensed under Creative Commons Attribution 4.0 International (see
`LICENSE-CC-BY-4.0`). You may share and adapt them, including commercially,
provided you give appropriate credit to Tahoe Bio, link to the licence and
indicate if changes were made.

## Data — separate source licenses

The Tahoe-100M data is released under CC0 1.0: free to use, including
commercially, without conditions. The licence comes from the dataset card at
<https://huggingface.co/datasets/tahoebio/Tahoe-100M>, which declares `cc0-1.0`.
Neither dataset is stored in this repository.

Emerald Bay source data uses CC BY 4.0, as declared by the
[EmeraldBay dataset card](https://huggingface.co/datasets/tahoebio/EmeraldBay).
Give appropriate credit to Tahoe Bio, link the source and
[CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/), and identify
changes or transformations. For example, label CPM or log1p(CPM) derived from
raw pseudobulk counts as a transformation; do not describe those values as
DESeq2-normalized expression. Retain the source revision and dataset release
with an analysis so the attribution identifies the data used.

A suitable short attribution is: “Source: Tahoe Bio, EmeraldBay, CC BY 4.0.
CPM and natural-log log1p(CPM) derived from raw pseudobulk counts using each
complete profile total.” Link the source and license and add the actual pinned
revision when using this wording. Tahoe-100M's CC0 license does not apply to
Emerald Bay.

## Guidance — not licensed for redistribution

The service's guidance is not in this repository. It lives only on the service
and is delivered at runtime. It is not covered by either licence here and may
not be redistributed. Neither Tahoe-100M's CC0 license nor Emerald Bay's CC BY 4.0 license
grants redistribution rights to runtime guidance or the service. The plugin's
CC BY 4.0 documentation is a separate work; do not treat it as permission to
copy a guide returned by `get_guide`.

## Gene-set names

Gene-set names keep the terms of their source collections: MSigDB, GO,
Reactome, KEGG, WikiPathways, BioCarta and PID.

## Vendored schemas

`schemas/plugin.schema.json` and `schemas/mcp.schema.json` are vendored
verbatim from agent-plugins.org and are the upstream's own files, licensed
Apache-2.0 upstream — they are not covered by this repository's CC BY 4.0
grant. `schemas/provenance.json` records each source, its licence and its
checksum.

## Brand assets

`plugins/tara/assets/tahoe-logo.png` is the Tahoe brand mark, used for the
plugin's listing logo and composer icon. It ships in the release archive but is
not licensed for reuse: it is all rights reserved and is a trademark of Tahoe
Bio, and neither licence in this repository covers it. It is not swept into the
Apache-2.0 grant that covers Tahoe's code.

## Trademarks

"Tahoe" and "Tara" are trademarks. No licence in this repository grants any
right to use them.

## No warranty

The software and documentation are provided "as is", without warranty of any
kind, express or implied.
