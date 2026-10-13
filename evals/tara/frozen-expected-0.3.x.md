# Frozen expected values — server 0.3.9–0.3.10, release `tahoe-100m/v1`

Frozen from one reference run per prompt on the live service (Codex, two models
that agreed unless noted). Re-freeze when `server_version` or `release` changes.
Direction and structure criteria in `rubric.md` are fixed; the numbers below are
the reference. Gene values are the released log2 fold change versus same-plate,
same-line vehicle; pathway scores are dimensionless and already vehicle-subtracted.

## E1 — Trametinib 5 µM, DUSP6 / ETV4 / ETV5 / SPRY4 (exact label `Trametinib`)

- 50 lines, plates 3 and 12; 396 of 400 plate-level estimates estimable, all negative.
- Median across lines of the mean of the two plates: DUSP6 −3.77, ETV4 −2.59,
  ETV5 −3.38, SPRY4 −3.92.
- Spot values (plate 3 / plate 12): A549 DUSP6 −4.03 / −3.40; C32 DUSP6 −5.54 / −5.32.

## E2 — Palbociclib

- Label `palbociclib` (lowercase); doses 0.05, 0.5, 5 µM; targets CDK4, CDK6;
  mechanism "CDK inhibitor"; human-approved yes.
- 22 of 50 lines carry a CDKN2A driver annotation: A-172, A-427, A498, A549,
  AsPC-1, C32, H4, HS-578T, Hs 766T, LOX-IMVI, MIA PaCa-2, NCI-H1573, NCI-H1792,
  NCI-H2122, NCI-H460, NCI-H661, PANC-1, Panc 03.27, RPMI-7951, SW 1088,
  SW 1271, SW 900.

## E3 — Bortezomib 5 µM survival

- 50 lines on plate 3; survival score range −1.64 to +1.72; A549 −0.041 (n_cells_trt
  366, n_cells_ctrl 2138); A-427 −1.63; 17 of 50 lines significant and negative.

## E4 — Pitavastatin (Calcium) vs Pravastatin (sodium), 5 µM

- Pitavastatin on plate 9; pravastatin on plates 9 and 13. Shared plate 9, mean
  over lines, pitavastatin − pravastatin: HMGCR +0.018, LDLR +0.095, INSIG1
  +0.302, HMGCS1 +0.150, HALLMARK_CHOLESTEROL_HOMEOSTASIS +0.0195.
- Pitavastatin mean over lines (all plates): HMGCR +0.419 (49 lines), LDLR
  +0.225, INSIG1 +0.205, HMGCS1 +0.488; HALLMARK +0.0134 (48 lines).
- Pitavastatin / pravastatin, COLO 205: HMGCR +1.39 / +0.31, HMGCS1 +1.72 / +0.15,
  HALLMARK +0.139 / −0.012.

## E5 — Skin lines, Trametinib 0.5 µM, Tahoe-x1 cosine distance (plate 11 / plate 2)

- C32 0.0481 / 0.0937; LOX-IMVI 0.0182 / 0.0909; SK-MEL-2 0.0297 / 0.0612;
  RPMI-7951 0.0062 / 0.0330. C32 is largest on both plates and both metrics;
  BRAF-driven lines do not separate by magnitude. DUSP6 and EGR1 fall, NEAT1
  rises, in all four lines.

## Set A

- A1: Binimetinib, Cobimetinib, TAK-733, Trametinib (MEK); Dabrafenib, Encorafenib,
  Vemurafenib (RAF) — 7 compounds.
- A2: downregulate; HALLMARK_KRAS_SIGNALING median across 50 lines −0.0191.
- A3: MEK inhibitors rank first at 5 µM (value depends on gene set and aggregation;
  frozen as the ranking only).
- A4: 21–50 (27 agents labelled "DNA synthesis/repair inhibitor", salt forms separate).
- A5: (a), with the caveat that the data do not show target engagement; at 5 µM on
  plate 9 pitavastatin lowers the YAP signature more in 46 of 48 lines (−0.094 vs −0.025).
