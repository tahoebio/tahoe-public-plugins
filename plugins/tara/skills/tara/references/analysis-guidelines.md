# Reading the server's scientific guidance

The scientific analysis and statistics guidance is maintained server-side and
served by `get_guide`. This plugin routes to it rather than distributing a copy.
Call `get_guide()` to discover the current `topics`; retain `guide_version`.

| Before | Read with `get_guide(topic=...)` |
|---|---|
| Planning an analysis | `establish-the-analysis-contract` |
| Selecting sources, controls and joins | `verify-semantics-and-coverage` |
| Choosing replication, intervals or multiple-testing methods | `statistical-discipline` |
| Comparing a measurement with a released contrast | `measurements-versus-treatment-contrasts`, plus the relevant scientific layer topic |
| Interpreting DE | `differential-expression` |
| Interpreting pathway scores | `pathway-scores` |
| Interpreting a phenotype | `phenotype-readouts` and the result's provenance |
| Preparing a report | `reporting-standards` |
| Recording an analysis | `reproducible-output` |

Guide topics and result provenance define the selected source's methodology.
A tool's name or an example call does not establish units, independent
replication, control design or score direction. If the guide does not resolve
an interpretation needed for the answer, state the uncertainty instead of
inventing a convention. Keep the server's detailed guidance in the analysis
session; do not redistribute it as part of the plugin.
