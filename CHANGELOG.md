# Changelog

All notable changes to this repository are recorded here. This project adheres
to semantic versioning.

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
