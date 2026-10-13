# Frozen expected values

Each value below can be reproduced with the prompt in its file and the call
recipe given here, against the public tools. Re-freeze when `server_version`,
`release` or `guide_version` changes; direction and structure criteria live in
the prompt files and do not change with a re-freeze.

## Provenance

| Field | Value |
|---|---|
| `server_version` | 0.3.9 and 0.3.10 (the service was upgraded during the window; each reference run recorded its own version, and the two models' runs of E1, E5 and A5 straddle the upgrade and agree) |
| `release` | `tahoe-100m/v1` |
| `guide_version` | `c89b154d8b61059b778d673574d34e98259e527632b68c040c92cf10139fa3b2` |
| Frozen | 2026-10-12 and 2026-10-13, one reference run per prompt on each of two models; numbers agree between models unless noted |

Gene values are the released log2 fold change versus same-plate, same-line
vehicle. Pathway scores are dimensionless and already vehicle-subtracted. Cell
lines are identified by the Cellosaurus id and name returned by the tools.

## E1-DE

Prompt: [E1.md](E1.md). Route: `resolve_genes(["DUSP6","ETV4","ETV5","SPRY4"])`;
`get_differential_expression(drug="Trametinib", dose=5, genes=[the four])`,
repeated with `cell_lines` in batches of ten lines when the response is truncated.

- 50 lines on plates 3 and 12: 400 gene/line/plate rows, 396 estimable, all negative.
- Aggregation: per line, the mean of the two plates' log2 fold changes (one plate
  where the other has no estimate); then the median across the 50 lines.
- Result: DUSP6 −3.77, ETV4 −2.59, ETV5 −3.38, SPRY4 −3.92.
- Spot values (plate 3 / plate 12): A549 DUSP6 −4.03 / −3.40; C32 DUSP6 −5.54 / −5.32.

The expression-slice route of E1 has no frozen values (no recorded run followed it).

## E2

Prompt: [E2.md](E2.md). Route: `search_conditions(query="albociclib")`,
`get_drug_info(query="Palbociclib")`, `list_cell_lines()` filtered on the CDKN2A
driver annotation.

- Label `palbociclib` (lowercase); doses 0.05, 0.5 and 5 µM; targets CDK4, CDK6;
  mechanism "CDK inhibitor"; human-approved yes.
- 22 of 50 lines carry a CDKN2A driver annotation: A-172, A-427, A498, A549,
  AsPC-1, C32, H4, HS-578T, Hs 766T, LOX-IMVI, MIA PaCa-2, NCI-H1573, NCI-H1792,
  NCI-H2122, NCI-H460, NCI-H661, PANC-1, Panc 03.27, RPMI-7951, SW 1088, SW 1271,
  SW 900. (Cellosaurus ids are returned by `list_cell_lines`.)

## E3

Prompt: [E3.md](E3.md). Route: `get_phenotype_scores(drug=["Bortezomib"],
phenotypes=["survival"], dose=5)`; add the arrest and Augur phenotypes for the
cross-check.

- 50 lines on plate 3; survival score from −1.64 (−1.63975) to +1.72 (+1.71547).
- A549 −0.041 (`n_cells_trt` 366, `n_cells_ctrl` 2138); A-427 −1.63.
- Significance: 17 rows are negative with the tool's `significant` flag true
  (family: the `p_adj_fdr` column).

## E4

Prompt: [E4.md](E4.md). Route: `get_differential_expression(drug=["Pitavastatin (Calcium)",
"Pravastatin (sodium)"], dose=5, genes=[one gene per call])` and
`get_pathway_scores(drug=[both], dose=5, gene_sets=["HALLMARK_CHOLESTEROL_HOMEOSTASIS"])`.

- Pitavastatin is on plate 9; pravastatin is on plates 9 and 13. The shared-plate
  comparison uses plate 9 only.
- Shared plate 9, mean over lines of pitavastatin minus pravastatin: HMGCR +0.018,
  LDLR +0.095, INSIG1 +0.302, HMGCS1 +0.150, HALLMARK_CHOLESTEROL_HOMEOSTASIS +0.0195.
- Pitavastatin mean over lines, all its plates: HMGCR +0.419 (49 lines), LDLR
  +0.225, INSIG1 +0.205, HMGCS1 +0.488 (50 lines); HALLMARK +0.0134 (48 lines).
- COLO 205, pitavastatin / pravastatin: HMGCR +1.39 / +0.31, HMGCS1 +1.72 / +0.15,
  HALLMARK +0.139 / −0.012.

## E5

Prompt: [E5.md](E5.md). Route: `get_embedding_distance(drug="Trametinib",
cell_lines=["C32","LOX-IMVI","RPMI-7951","SK-MEL-2"], dose=0.5)`.

| Line | Driver | Cosine, plate 11 / plate 2 |
|---|---|---|
| C32 | BRAF V600E | 0.0481 / 0.0937 |
| LOX-IMVI | BRAF V600E | 0.0182 / 0.0909 |
| SK-MEL-2 | NRAS Q61R | 0.0297 / 0.0612 |
| RPMI-7951 | BRAF V600E | 0.0062 / 0.0330 |

C32 is largest on both plates and both metrics; the three BRAF-driven lines span
the largest and smallest distances, so they do not separate by magnitude. With
`get_differential_expression` on the same four lines at 0.5 µM, DUSP6 and EGR1
decrease and NEAT1 increases in all four.

## Set A

Prompts: [set-A.md](set-A.md).

- **A1.** `get_drug_info(moa="MEK inhibitor")` and `(moa="RAF inhibitor")`, salts and the
  solvate collapsed, multi-kinase inhibitors excluded: Binimetinib, Cobimetinib,
  TAK-733, Trametinib; Dabrafenib, Encorafenib, Vemurafenib (7 compounds).
- **A2.** `get_pathway_scores(drug="Binimetinib", gene_sets=["HALLMARK_KRAS_SIGNALING"],
  limit=1000)`; per line, the median across doses and plates; then the median across the
  50 lines: −0.0191. Answer: downregulate.
- **A3.** Differential pathway scores at 5 µM for `REACTOME_INTERFERON_ALPHA_BETA_SIGNALING`
  (guarded `run_sql` over the differential pathway score table, or `get_pathway_scores`),
  mechanism from `get_drug_info`. MEK inhibitors rank first. The value depends on the
  aggregation (median of drug medians: +0.0239; mean of drugs within a MOA then median
  across lines: +0.0085); `HALLMARK_INTERFERON_ALPHA_RESPONSE` also ranks MEK inhibitors first.
  Only the ranking is frozen.
- **A4.** Count of distinct drug labels whose `moa-fine` annotation is "DNA synthesis/repair
  inhibitor", salt forms counted separately: 27. Answer bucket: 21–50.
- **A5.** `get_pathway_scores(gene_sets=["CORDENONSI_YAP_CONSERVED_SIGNATURE"], drug=["Pitavastatin (Calcium)",
  "Pravastatin (sodium)"], dose=5)`: on plate 9, pitavastatin lowers the signature more than
  pravastatin in 46 of 48 lines (mean −0.094 versus −0.025). Answer: (a), stated with the
  caveat that the scores are transcriptional and do not show target engagement.
