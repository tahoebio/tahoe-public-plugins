# Changelog

All notable changes to this repository are recorded here. This project adheres
to semantic versioning.

## 0.4.0 — unreleased

- Add explicit dataset selection and capability-gated Emerald Bay routing.
  Preserve Tahoe's 0.3.9 server floor and legacy calls; Emerald requires server
  0.4.0 or later plus advertised capabilities for the signed-in account.
- Route pseudobulk raw counts, CPM and natural-log log1p(CPM), released five-day
  growth response, differential VISION and bounded single-cell raw SQL.
  Preserve sample/line identity, missingness, controls and dataset-specific
  guides. Refuse unavailable or unsupported Emerald requests without fallback.
- Add structured worked calls, offline schema/capability checks and a separate
  Emerald host-evaluation pack. Real host/MCP acceptance remains required;
  preparation and offline checks do not establish live readiness.
- Record Emerald source CC BY 4.0 attribution separately from Tahoe CC0,
  repository licenses and runtime-guide terms. Endpoint and sign-in stay the same.
- State the two version floors separately (Tahoe-100M 0.3.9, Emerald Bay 0.4.0),
  mark time-zero growth and `contrast_kind` at row level for treatment rankings,
  and forbid a numeric Emerald/Tahoe cross-dataset comparison (no conversion is
  provided). The EB18 eval case now fails on a reported cross-dataset delta.

## 0.3.4 — unreleased

- Correct the public docs for the open Google sign-in: drop the private-preview
  and publication-blocker claims from the README, promise Google (not GitHub, not
  email self-sign-up) across the install docs, and quote the one-line install
  prompt verbatim in `docs/install.md`.
- Give the Codex **terminal commands first** in the README and `docs/install.md`,
  and make the agent install prompt **install-then-stop**: an agent can neither
  connect the server nor sign the user in (MCP sign-in is the client's job, and a
  plugin install writes outside the agent's sandbox), so the prompt installs,
  approves the permission prompt, and stops — it no longer says "connect to
  Tara" or asks the agent to sign in or open a browser. The prompt is identical
  to the server landing page's `ASK_AGENT_PROMPT`.
- Name the private vulnerability-reporting route in `SECURITY.md` (GitHub private
  vulnerability reporting, with `tara@tahoebio.ai` as the fallback) and drop the
  unnamed-contact stub.
- Describe the repository's public state in `docs/releasing.md`, the README and
  the branch-sweep workflow: keep the leak-sweep gate, drop the "publication is
  blocked" and "pre-publication" framing.
- Document the restart step — tools load at session start — and the Codex
  `codex mcp login tahoe-public` sign-in, and note that a `tahoe-public`
  connection from before 2026-10-14 must be removed and re-added.
- Add the existing Tahoe brand mark as Tara's Codex listing logo and composer
  icon, and include it in release archives.
- Pin the approved logo's SHA-256 digest for working-tree, archive and history
  validation. Unknown or modified binary content still fails the residue scan.

## 0.3.3 — unreleased

Plugin ↔ server compatibility.

- Both manifests declare the minimum public server version the plugin is frozen
  against (`extensions["com.tahoebio"]["minServerVersion"]`, `0.3.9`), and the
  validator keeps it semver and identical across the two hosts.
- The skill's step 1 reads the served `server_version`, compares the three
  numbers numerically (0.3.10 is newer than 0.3.9) and warns below the minimum
  instead of assuming the published expected values hold; when no usable version
  is returned it reports compatibility as unknown.
- `docs/compatibility.md` gains a plugin ↔ server version table.

Repository licensing.

- Added `LICENSE` (Apache-2.0) for the plugin code and `LICENSE-CC-BY-4.0`
  (CC BY 4.0) for the skill text and documentation, with a `NOTICE` recording
  the attribution and the path map; `README.md` and `docs/data-and-licensing.md`
  state which paths fall under which licence.
- Both plugin manifests declare `license: Apache-2.0`, and the validator keeps
  the field equal to the code licence in both hosts.
- The release archive now ships `LICENSE`, `LICENSE-CC-BY-4.0` and `NOTICE` at
  its root, so a recipient has the terms and the attribution without the
  repository. The vendored `schemas/**` are named as the upstream's own
  Apache-2.0 files, separate from this repository's grants.
- The Tahoe brand mark (`plugins/tara/assets/tahoe-logo.png`) is carved out of
  the Apache-2.0 map as not licensed (all rights reserved) in README, NOTICE and
  the licensing doc, and the catch-all row names `evals/**` and root Markdown.
- The decision: code Apache-2.0 (attribution and a patent grant); skill text
  and docs CC BY 4.0; the served Tahoe-100M data CC0-1.0.

## 0.3.2 — unreleased

- Decline out-of-scope parts of a question in one sentence and offer the nearest
  analysis the served data can answer; never name or hint at a route outside
  Tahoe's tools.
- Publish the correctness pack (E1–E5, set A) with expected values frozen per
  server version and the call recipe for each (`evals/tara/`), record the first
  Codex run, strict results included, in `docs/install-verification.md`, and
  record the rubric revisions in `evals/tara/rubric.md`.
- Unserved-embeddings rows now offer the matched-vehicle distance tool instead of
  pointing outside the tools.

## 0.3.1

- Route gene-set discovery, differential pathway scores, phenotype readouts and
  matched embedding distances alongside the existing tools; synchronize the
  17-tool contract and validation pin.
- Route scientific methodology, statistics and catalog definitions to the
  server-owned `get_guide` topics instead of mirroring detailed guidance.
- Distinguish bounded pseudobulk retrieval from aggregate SQL over per-cell data
  and make the 1,000-row / 40 KB output limits explicit.
- Use the audited scientific-analysis description for skill discovery, with the
  current public data scope documented in the skill body.
- Preserve released DE log2 fold changes and defer phenotype definitions to the
  server guide and result provenance.
- Clarify named-tool output versus approved SQL columns, source-version replay
  limits and request/runtime bounds versus scan cost.

## 0.3.0 — unreleased

Richer, honest plugin descriptions.

- The plugin description now says what the public tools do today: coverage of
  drugs, doses, cell lines and genes; drug annotations; expression and
  drug-versus-vehicle differential expression; perturbation markers; pathway
  scores; phenotype readouts; embedding distance from vehicle; guarded
  read-only SQL. It refers to "Tahoe's data" and names no dataset.
- The description also states four analyses the public tools support, in plain
  wording: comparing a compound's response with annotated mechanism classes,
  comparing drug responses between genotype- or lineage-defined groups of cell
  lines, correlating baseline expression or driver-gene status with drug
  response (exploratory), and ranking relative depletion and cell-cycle effects
  per cell line across three doses.
- The Codex `interface` block (display name, short and long description,
  developer, category, capabilities, website, brand colour, three default
  prompts) lives under `extensions.com.openai` in the portable `plugin.json`,
  where Codex reads it. No logo or icon is set until an approved asset exists.
- The Claude manifest carries the identical description.
- Keywords no longer name a dataset.
- A test keeps the manifest text free of dataset and internal names.

## 0.2.0 — unreleased

The `tara` skill.

- `plugins/tara/skills/tara/SKILL.md` ships a real skill: when to use it, the
  non-negotiable rules, the call order, the routing table (short form), the
  analysis contract in brief, the response contract, the error vocabulary and
  what the tools do not serve.
- Three Tier 3 references under `skills/tara/references/`:
  `analysis-guidelines.md` (methodology), `data-catalog.md` (what is served,
  expression grain, coverage traps, the citation) and `tool-routing.md` (the long
  routing table, one worked call per tool, the response contract).
- `skills/tara/references/sql-guidance.md` documents `run_sql`: the guard's
  rules (one read-only `SELECT`/`WITH`/`UNION`, approved tables only, a literal
  key filter on any large table, no cross joins, a capped outer `LIMIT`), and the
  approved tables with their grain, keys, joins, units, controls and pitfalls.
- The skill routes only to tools that are live on the public service; no
  not-yet-served tool is named.
- Both hosts discover `skills/` by convention, so no manifest declares a
  `skills` field; the portable manifest is unchanged in shape.
- Validation now checks the skill: frontmatter, tier byte budgets, links that
  resolve inside the skill directory, mention completeness against the tool
  contract, and a locator/path/cell-code shape check.
- The release archive now carries the skill files alongside the manifests.
- Install, tool-contract, data-and-licensing and README docs describe the skill.

## 0.1.0 — unreleased

Initial repository skeleton.

- Marketplace catalog (`tahoe-public`) with the `tara` plugin.
- Plugin manifest and a draft skill placeholder (science review pending).
- Public documentation stubs.
- Validation, residue scanning and packaging scripts.
- Offline test suite and CI workflow.

### Packaging, docs, CI and leak scans (R6)

- Remote MCP server shipped as `tahoe-public` (`streamable-http` at
  `https://tara.tahoebio.io/mcp`) with no embedded credentials.
- Install documented as a single Codex CLI command, plus the Codex "Run without
  daemon" note; Codex CLI is the only tested host.
- Clean-machine install verification prepared for a human tester.
- Validation now covers the MCP configuration; residue and secret scanning now
  also covers the built archive and the full git history.
- Packaging discards an archive that contains residue or secrets.
- Licence remains an explicit placeholder — no LICENSE file, no `license` field.

### Leak-guard hardening (review)

- Every scanner pattern is now assembled from fragments, so `scripts/common.py`
  contains no forbidden literal and is scanned like any other file — the
  path-based exclusion is gone from both the working-tree and history scans.
- The history parser handles commit bodies without a trailing newline (as
  GitHub squash commits produce), tracks hunk line numbers, and reads binary
  changes.
- Content that cannot be read as text is reported, not skipped, in the working
  tree, the archive and history; a binary member now fails the release build.
- Packaging refuses a symlinked path component, so a symlinked parent directory
  can no longer pull files in from outside the checkout.
- Validation fails when history cannot be read in full (no repository, or a
  shallow clone).

### Per-branch leak scan (CI)

- The history scan is now a function of the commit under test: `scan_history`
  scans the history reachable from `HEAD` by default, so one stale branch can no
  longer fail every unrelated branch and `main`. `--all-refs` (and
  `scan_history(all_refs=True)`) restores the whole-repository sweep as an
  explicit developer option.
- `scripts/sweep_branches.py` runs the same per-ref scan once for every remote
  branch **and every tag** (annotated and lightweight), and prints a report —
  branch/tag, tip, offending commit, author, pass/fail — exiting 0. It backs the
  pre-publication gate and runs on `workflow_dispatch` and a weekly schedule. It
  fails loudly when it cannot do its job: a fetch it cannot read, or no refs.
- An annotated tag message is scanned only when the ref under test IS that tag: a
  tag object is not a commit, so `git log` never reads it, and a sibling tag
  never changes another ref's verdict. CI names the tag ref on a tag push (HEAD
  is then the tag's target commit), and both workflows fetch tag objects. The
  sweep reports each tag separately and scans a lightweight tag's own commit
  ancestry, so a tag that is the sole ref to a dirty commit is caught.
- The history scan walks the ref's full ancestry with no path limit and diffs
  every merge against each parent (`--diff-merges=separate`), so a line added in
  a conflict resolution is scanned as an added line even after a later commit
  removes it; commit messages of every commit — empty commits and merge commits
  included — are scanned with the same patterns, and `--full-history` keeps a
  commit on a merged parent that a merge resolution reverted. Binary findings
  carry their commit, so the report names the author.
- CI triggers on pushes to every branch **and on tag pushes** (a tag can point
  outside every branch tip's ancestry), plus pull requests.

### Thin plugin (no guidance payload)

- The plugin now ships connection manifests only: the portable Codex pair
  (`plugin.json`, `mcp.json`), a native Claude manifest
  (`plugins/tara/.claude-plugin/plugin.json`) and two catalogs — the Codex
  catalog and an owner-bearing Claude catalog.
- The `skills/` payload is gone. Scientific guidance is served by the service at
  runtime and is not distributed as files here.
- Catalogs are no longer required to be byte-identical; each host's shape is
  validated, and the two must agree on identity and on the plugin directory
  they resolve.
- The release archive is an explicit allowlist of manifest files (dotfiles
  included), not a directory prefix.
- Install docs lead with the plugin marketplace path for Codex and Claude, with
  the one-prompt variant and a direct `mcp add` as an advanced fallback.
- Data is CC0; guidance is proprietary and served at runtime. The licence
  remains a placeholder pending S11.
