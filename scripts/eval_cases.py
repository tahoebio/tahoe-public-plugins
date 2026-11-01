"""Write the plugin eval cases from the public prompt pack.

The human-readable sources under ``evals/tara/`` stay where they are. This
module renders the runner layout into an explicit directory, which must not
sit inside ``plugins/``. Cases that still need an independent expected value
are tagged ``blocked`` and are not part of the ``release`` tag. Pending and
cancellation prompts are not rendered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import common  # noqa: E402
from scripts.eval_pack import refuse_plugins_output, scoped_mcp_tool  # noqa: E402

HUMAN_PACK = Path("evals") / "tara"
PENDING_CASES = frozenset({"EB20", "EB21"})
HARD_FAIL_PATTERN = (
    r"\bc_\d+\b|proves target engagement|proves on-target potency|"
    r"treated the missing value as zero|vehicle was subtracted again"
)
_INDEPENDENT = re.compile(
    r"independent|oracle|compare the released double exactly", re.IGNORECASE
)
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_ANALYSIS_AFTER_GUIDE = frozenset(
    {
        "resolve_genes",
        "search_conditions",
        "list_cell_lines",
        "get_drug_info",
        "search_gene_sets",
        "get_expression_slice",
        "get_pathway_scores",
        "get_phenotype_scores",
        "get_differential_expression",
        "get_embedding_distance",
        "get_perturbation_markers",
        "run_sql",
        "send_feedback",
    }
)


@dataclass(frozen=True)
class Need:
    tool: str
    match: str | None = None


@dataclass(frozen=True)
class CaseSpec:
    name: str
    title: str
    prompt: str
    tags: tuple[str, ...]
    source: str
    needs: tuple[Need, ...]
    forbid: tuple[str, ...]
    order: tuple[tuple[str, str], ...]
    criteria: tuple[str, ...]
    blocked_reason: str | None = None
    skill: bool = True
    #: JavaScript-style regex that must match the mocked-call dump.
    route_pattern: str | None = None


def _fill(prompt: str) -> str:
    """Replace brace placeholders with a discover-don't-invent instruction."""

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).replace("_", " ")
        return (
            f"the {label} discovered from the public release "
            "(do not invent an identifier)"
        )

    return _PLACEHOLDER.sub(replace, prompt)


def _dataset_match() -> str:
    return r'"dataset"\s*:\s*"emerald-bay"'


def _tahoe() -> list[CaseSpec]:
    """S1–S8, E1–E5 and set A. Blocked rows still carry graders."""
    process = r'"process"\s*:'
    return [
        CaseSpec(
            name="s1-mapk-trametinib",
            title="S1 MAPK inhibitor readout",
            prompt=(
                "In Tahoe-100M, does Trametinib suppress MAPK pathway activity? "
                "Report per cell line."
            ),
            tags=("blocked",),
            source="evals/tara/signatures.md (S1)",
            blocked_reason=(
                "Needs an independent expected value for whether Trametinib "
                "lowers the score in most lines."
            ),
            needs=(
                Need("list_releases"),
                Need("get_validated_signatures", r"MAPK"),
                Need("search_conditions", r"Trametinib"),
                Need("get_pathway_scores", process),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The scored set is PROGENY_MAPK_A and no other MAPK set is called the validated readout.",
                "Rows used for the claim name score_source and validation_status.",
                "The per-line direction is not treated as already known; NULL scores are missing.",
            ),
        ),
        CaseSpec(
            name="s2-apoptosis",
            title="S2 apoptosis has no validated readout",
            prompt=(
                "In Tahoe-100M, how does Trametinib change apoptosis pathway "
                "activity in A549?"
            ),
            tags=("release",),
            source="evals/tara/signatures.md (S2)",
            needs=(
                Need("list_releases"),
                Need("search_conditions", r"Trametinib"),
                Need("get_pathway_scores", r'"process"\s*:\s*"Apoptosis"'),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The answer states that apoptosis has no validated readout.",
                "No other process readout is substituted and called validated.",
                "A set scored only by gene_sets is labelled exploratory.",
            ),
        ),
        CaseSpec(
            name="s3-kras-not-readout",
            title="S3 HALLMARK_KRAS_SIGNALING is not the readout",
            prompt=(
                "Is HALLMARK_KRAS_SIGNALING a good readout of KRAS pathway "
                "activity for drug effects in Tahoe-100M?"
            ),
            tags=("release",),
            source="evals/tara/signatures.md (S3)",
            needs=(
                Need("list_releases"),
                Need("get_validated_signatures", r"HALLMARK_KRAS_SIGNALING"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The set is described as tested and not the readout (passed_not_readout).",
                "PROGENY_MAPK_A is named as the validated readout to prefer.",
                "Any score for HALLMARK_KRAS_SIGNALING is labelled exploratory.",
                "The two sets' score sizes are not compared.",
            ),
        ),
        CaseSpec(
            name="s4-atf4-inversion",
            title="S4 ATF4 score direction",
            prompt=(
                "In Tahoe-100M, does Bortezomib activate the integrated stress "
                "response (ATF4) relative to vehicle?"
            ),
            tags=("blocked",),
            source="evals/tara/signatures.md (S4)",
            blocked_reason=(
                "Needs an independent expected value for Bortezomib's own "
                "per-line or median sign."
            ),
            needs=(
                Need("list_releases"),
                Need("get_validated_signatures", r"ATF4"),
                Need("search_conditions", r"Bortezomib"),
                Need("get_pathway_scores", r'"process"\s*:\s*"ATF4"'),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The scored set is the ATF4 readout and the inversion note is stated.",
                "The direction class is complex, not a simple expected sign.",
                "The conclusion is in process terms after applying the inversion.",
            ),
        ),
        CaseSpec(
            name="s5-yap-statins",
            title="S5 DepMap-only YAP readout",
            prompt=(
                "In Tahoe-100M, does Pitavastatin suppress YAP signaling more "
                "than Pravastatin?"
            ),
            tags=("blocked",),
            source="evals/tara/signatures.md (S5)",
            blocked_reason=(
                "Needs an independent expected value for which statin lowers "
                "the readout more."
            ),
            needs=(
                Need("list_releases"),
                Need("get_validated_signatures", r"YAP"),
                Need("get_pathway_scores", process),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The scored set is the YAP readout and the DepMap-only caveat is stated.",
                "The comparison does not claim target engagement or greater on-target potency.",
                "Scores are not residualised by the answer.",
            ),
        ),
        CaseSpec(
            name="s6-expression-control",
            title="S6 expression question is unaffected",
            prompt=(
                "In Tahoe-100M, how does Trametinib at 5 µM change DUSP6 "
                "expression versus vehicle in A549?"
            ),
            tags=("release",),
            source="evals/tara/signatures.md (S6)",
            needs=(
                Need("list_releases"),
                Need("resolve_genes", r"DUSP6"),
                Need("search_conditions", r"Trametinib"),
            ),
            forbid=("run_sql", "get_validated_signatures", "get_pathway_scores"),
            route_pattern=r"get_expression_slice|get_differential_expression",
            order=(),
            criteria=(
                "The answer does not use validation language.",
                "The contrast is descriptive and names its measurement.",
                "No p-value is invented.",
            ),
        ),
        CaseSpec(
            name="s7-emerald-mtorc1",
            title="S7 Emerald Bay mTORC1",
            prompt=(
                "In Emerald Bay, how does mTORC1 signalling respond for a treated "
                "profile and cell line you discover from the public release? "
                "Do not invent identifiers."
            ),
            tags=("blocked",),
            source="evals/tara/signatures.md (S7)",
            blocked_reason=(
                "Needs independent confirmation that the mTORC1 readout is in "
                "the differential vocabulary, and the score for the chosen profile."
            ),
            needs=(
                Need("list_releases"),
                Need("get_guide", _dataset_match()),
                Need("search_gene_sets", r"MTORC1"),
                Need("get_pathway_scores", r'"process"\s*:\s*"mTORC1"'),
            ),
            forbid=("run_sql",),
            order=(("get_guide", "get_pathway_scores"),),
            criteria=(
                "The answer uses the mTORC1 readout and calls the scores Emerald gold differentials.",
                "Tahoe-100M is not queried as a fallback.",
                "The scope caveat says the readout was not validated on Emerald Bay data.",
            ),
        ),
        CaseSpec(
            name="s8-emerald-kras-absent",
            title="S8 Emerald Bay custom KRAS readout",
            prompt=(
                "In Emerald Bay, what does the KRAS pathway readout show for a "
                "profile and cell line you discover from the public release? "
                "Do not invent identifiers."
            ),
            tags=("blocked",),
            source="evals/tara/signatures.md (S8)",
            blocked_reason=(
                "Needs independent confirmation that the custom readout name "
                "is absent from the Emerald Bay vocabulary."
            ),
            needs=(
                Need("list_releases"),
                Need("get_pathway_scores", r'"process"\s*:\s*"KRAS"'),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "KRAS resolves to its validated readout and missing Emerald rows are not a score.",
                "No other set is substituted and called validated.",
                "The missing value is not reported as zero and Tahoe-100M is not a fallback.",
            ),
        ),
        CaseSpec(
            name="e1-trametinib-expression",
            title="E1 Trametinib expression versus vehicle",
            prompt=(
                "In Tahoe-100M, how does Trametinib at 5 µM change DUSP6, ETV4, "
                "ETV5 and SPRY4 expression versus vehicle across the panel? "
                "Report per cell line."
            ),
            tags=("release",),
            source="evals/tara/E1.md",
            needs=(
                Need("list_releases"),
                Need("resolve_genes", r"DUSP6"),
                Need("search_conditions", r"Trametinib"),
            ),
            forbid=("run_sql",),
            route_pattern=r"get_expression_slice|get_differential_expression",
            order=(),
            criteria=(
                "The contrast is descriptive, from matched controls, and names its measurement.",
                "The exact Trametinib label is used. No p-value is invented.",
                "A per-line table includes the cell counts the route returns.",
            ),
        ),
        CaseSpec(
            name="e2-palbociclib",
            title="E2 Palbociclib coverage and annotation",
            prompt=(
                "Is Palbociclib in Tahoe-100M? At which doses? What are its "
                "annotated targets and approval status, and which panel lines "
                "carry a CDKN2A driver annotation?"
            ),
            tags=("release",),
            source="evals/tara/E2.md",
            needs=(
                Need("search_conditions", r"albociclib"),
                Need("get_drug_info"),
                Need("list_cell_lines"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The exact treatment label from the tools is used verbatim.",
                "Targets, mechanism and approval come from the annotation tool.",
                "Lines are reported with a public id and a name, and the count is stated.",
            ),
        ),
        CaseSpec(
            name="e3-bortezomib-survival",
            title="E3 Bortezomib survival near zero",
            prompt=(
                "Does Bortezomib at 5 µM kill the panel? The survival scores "
                "look close to zero — does that mean no effect?"
            ),
            tags=("release",),
            source="evals/tara/E3.md",
            needs=(
                Need("list_releases"),
                Need("get_guide", r"phenotype-readouts"),
                Need("search_conditions"),
                Need("get_phenotype_scores", r"Bortezomib"),
            ),
            forbid=("run_sql",),
            order=(("get_guide", "get_phenotype_scores"),),
            criteria=(
                "Survival near zero is not reported as no effect.",
                "Arrest and Augur are used as the cross-check.",
                "The significance family is stated, and Augur is not given a test it does not have.",
            ),
        ),
        CaseSpec(
            name="e4-statin-cholesterol",
            title="E4 two statins on cholesterol homeostasis",
            prompt=(
                "Compare Pitavastatin and Pravastatin at 5 µM on "
                "cholesterol-homeostasis signalling: HMGCR, LDLR, INSIG1, "
                "HMGCS1 expression and the HALLMARK cholesterol homeostasis "
                "gene set, across lines."
            ),
            tags=("release",),
            source="evals/tara/E4.md",
            needs=(
                Need("search_conditions", r"Pitavastatin"),
                Need("resolve_genes"),
                Need("get_differential_expression", r"Pitavastatin"),
                Need("search_gene_sets", r"CHOLESTEROL"),
                Need("get_pathway_scores", r"HALLMARK_CHOLESTEROL_HOMEOSTASIS"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "Both salt-form labels are used verbatim.",
                "Pathway scores are not vehicle-subtracted again and are not given a p-value.",
                "A NULL adjusted p-value is untested, not no effect.",
                "Greater on-target potency is not claimed as proven.",
            ),
        ),
        CaseSpec(
            name="e5-skin-embedding",
            title="E5 skin-derived lines in embedding space",
            prompt=(
                "Among the four skin-derived lines, which is moved most by "
                "Trametinib at 0.5 µM in embedding space, do the BRAF-driven "
                "lines separate from the others, and which genes mark the response?"
            ),
            tags=("release",),
            source="evals/tara/E5.md",
            needs=(
                Need("list_cell_lines", r"Skin"),
                Need("search_conditions"),
                Need("get_embedding_distance", r"Trametinib"),
                Need("get_perturbation_markers", r"Trametinib"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "Distances are compared within line. Direction is not read from a distance.",
                "The claim states how many lines were compared. Marker importance is not called a fold change.",
                "The BRAF question is descriptive.",
            ),
        ),
        CaseSpec(
            name="a1-mek-raf-list",
            title="A1 MEK and RAF inhibitors",
            prompt=(
                "Using tahoe tools, return the list of MEKi and RAFi in "
                "Tahoe-100M (excluding multi-TKi), after collapsing different "
                "salt forms."
            ),
            tags=("release",),
            source="evals/tara/set-A.md (A1)",
            needs=(
                Need("get_drug_info", r"MEK inhibitor"),
                Need("search_conditions"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The list comes from the annotation and condition tools, not from memory.",
                "Salt forms are collapsed only for this question, and labels are the ones the tools returned.",
            ),
        ),
        CaseSpec(
            name="a2-binimetinib-kras",
            title="A2 binimetinib and KRAS signalling",
            prompt=(
                "Using tahoe tools, does binimetinib up-reg or down-reg the "
                "KRAS signaling signature in Tahoe-100M? Consider the median "
                "effect across cell lines. Options: upregulate, downregulate, "
                "complex pattern, can't be determined"
            ),
            tags=("release",),
            source="evals/tara/set-A.md (A2)",
            needs=(
                Need("search_gene_sets", r"KRAS"),
                Need("search_conditions"),
                Need("get_pathway_scores", r"HALLMARK_KRAS_SIGNALING"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The answer chooses one of the stated options from the served scores.",
                "The gene set scored is the one the prompt names, labelled as the tools label it.",
            ),
        ),
        CaseSpec(
            name="a3-interferon-moa",
            title="A3 interferon response by mechanism",
            prompt=(
                "Using tahoe tools, which drug MOA induces the largest "
                "interferon alpha/beta response up-regulation in Tahoe-100M, "
                "at the highest dose? Consider the median effect across cell lines."
            ),
            tags=("release",),
            source="evals/tara/set-A.md (A3)",
            needs=(
                Need("search_gene_sets", r"INTERFERON"),
                Need("get_drug_info"),
                Need("get_pathway_scores"),
            ),
            forbid=(),
            order=(),
            criteria=(
                "The mechanism label comes from the annotation tool.",
                "The comparison uses the highest dose and a median across lines, not a significant-count headline.",
            ),
        ),
        CaseSpec(
            name="a4-dna-damage-count",
            title="A4 DNA damage annotation count",
            prompt=(
                "Using tahoe tools, how many agents induce DNA damage or "
                "inhibit DNA synthesis/repair in Tahoe-100M? Options: 0, 1-20, "
                "21-50, 51-70, 71-90, 91-100, cannot be determined. Do not "
                "collapse different salt forms."
            ),
            tags=("release",),
            source="evals/tara/set-A.md (A4)",
            needs=(Need("run_sql"),),
            forbid=(),
            order=(),
            criteria=(
                "The count is an annotation count from the guarded SQL tool, not a guess.",
                "Salt forms are not collapsed. The answer is one of the stated bins.",
            ),
        ),
        CaseSpec(
            name="a5-yap-mechanism",
            title="A5 statin YAP mechanism question",
            prompt=(
                "Using tahoe tools, in Tahoe-100M, we observe that Pitavastatin "
                "(Calcium) has a larger effect than Pravastatin (sodium) in "
                "downregulating the active YAP signature. Is this effect more "
                "likely mediated by (a) a larger on-target effect, or (b) a "
                "different mechanism, including off-target, or (c) cannot be "
                "determined? Answer based on what we know about the drug "
                "mechanism, and specifically the pharmacological differences "
                "between the two drugs."
            ),
            tags=("release",),
            source="evals/tara/set-A.md (A5)",
            needs=(
                Need("get_drug_info"),
                Need("search_gene_sets", r"YAP"),
                Need("get_pathway_scores"),
            ),
            forbid=("run_sql",),
            order=(),
            criteria=(
                "The answer does not treat the observation as proof of target engagement.",
                "Pharmacological differences come from the annotation tool.",
            ),
        ),
    ]


def _emerald_blocked(case: dict) -> str | None:
    if case["id"] == "EB15":
        return "Needs the older-server compatibility fixture. A current-release replay is not that server."
    if case["id"] == "EB16":
        return "Needs an account on which the dataset is not visible."
    if case["id"] == "EB17":
        return "Needs the incomplete-capability fixtures."
    if case["id"] == "EB23":
        return "Needs separate approval before any feedback is submitted."
    text = " ".join(item["assertion"] for item in case["hard_criteria"])
    if _INDEPENDENT.search(text):
        return "Needs an independent expected value from the public release."
    return None


def _emerald_needs(case: dict) -> tuple[Need, ...]:
    needs: list[Need] = []
    for tool in case["expected_tools"]:
        match = None
        if tool not in {"health", "list_releases", "cancel_execution", "send_feedback"}:
            match = _dataset_match()
        needs.append(Need(tool, match))
    return tuple(needs)


def _emerald_forbid(case: dict) -> tuple[str, ...]:
    expected = set(case["expected_tools"])
    forbidden = ["cancel_execution"]
    for tool in (
        "run_sql",
        "get_differential_expression",
        "get_embedding_distance",
        "get_perturbation_markers",
        "send_feedback",
    ):
        if tool not in expected:
            forbidden.append(tool)
    return tuple(forbidden)


def _emerald_order(case: dict) -> tuple[tuple[str, str], ...]:
    tools = list(case["expected_tools"])
    if "get_guide" not in tools:
        return ()
    after = tools[tools.index("get_guide") + 1 :]
    for tool in after:
        if tool in _ANALYSIS_AFTER_GUIDE:
            return (("get_guide", tool),)
    return ()


def _emerald() -> list[CaseSpec]:
    pack = json.loads((common.REPO_ROOT / HUMAN_PACK / "emerald-cases.json").read_text(encoding="utf-8"))
    specs = []
    for case in pack["cases"]:
        if case["id"] in PENDING_CASES:
            continue
        reason = _emerald_blocked(case)
        number = case["id"].lower()
        specs.append(
            CaseSpec(
                name=number,
                title=f"{case['id']} {case['title']}",
                prompt=_fill(case["prompt"]),
                tags=("blocked",) if reason else ("release",),
                source=f"evals/tara/emerald-cases.json ({case['id']})",
                blocked_reason=reason,
                needs=_emerald_needs(case),
                forbid=_emerald_forbid(case),
                order=_emerald_order(case),
                criteria=tuple(item["assertion"] for item in case["hard_criteria"]),
            )
        )
    return specs


def _probe() -> CaseSpec:
    return CaseSpec(
        name="live-probe",
        title="Live remote probe",
        prompt=(
            "Call the service health tool and the release-list tool, then say "
            "whether they answered. If sign-in is required and you cannot "
            "complete it, say that sign-in failed and stop. Do not invent a "
            "dataset, a count, or a scientific result."
        ),
        tags=("probe",),
        source="evals/tara/README.md (live probe)",
        needs=(Need("health"), Need("list_releases")),
        forbid=("run_sql",),
        order=(),
        criteria=(
            "The answer reports either that the tools answered or that sign-in failed.",
            "No measurement, dataset, or count is invented.",
        ),
        skill=False,
    )


def all_specs() -> list[CaseSpec]:
    return [*_tahoe(), *_emerald(), _probe()]


def _quote(pattern: str) -> str:
    if "'" in pattern:
        raise common.RepoError("grader pattern cannot contain a single quote")
    return "'" + pattern + "'"


def _scoped_route(pattern: str) -> str:
    """Rewrite short MCP tool names in a route regex to the scoped form."""
    names = sorted(set(re.findall(r"[a-z][a-z0-9_]+", pattern)), key=len, reverse=True)
    scoped = pattern
    for name in names:
        scoped = scoped.replace(name, scoped_mcp_tool(name))
    return scoped


def _route_call_pattern(pattern: str) -> str:
    """A trace regex that matches a call to one of the route's tools, not a tool listing."""
    return '"name":"(?:' + _scoped_route(pattern) + ')"'


def _tool_grader(need: Need, *, minimum: int, maximum: int | None) -> str:
    lines = ["---", "type: tool_used", f"tool: {scoped_mcp_tool(need.tool)}", "arm: with-only"]
    if need.match is not None:
        lines.append(f"input_match: {_quote(need.match)}")
    if minimum != 1:
        lines.append(f"min: {minimum}")
    if maximum is not None:
        lines.append(f"max: {maximum}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _rubric(spec: CaseSpec) -> str:
    criteria = "\n".join(f"- {line}" for line in spec.criteria)
    emerald = ""
    if spec.name.startswith("eb") or spec.name.startswith("s7") or spec.name.startswith("s8"):
        emerald = (
            "\nFor an Emerald Bay answer, also FAIL on a silent fallback to "
            "Tahoe-100M, a cross-dataset join, time zero treated as a drug "
            "effect, an unavailable score reported as zero, or a missing "
            "source attribution.\n"
        )
    return (
        "---\n"
        "type: llm\n"
        "---\n"
        "\n"
        "PASS if every case criterion holds and no hard-fail class applies.\n"
        "FAIL if any hard-fail class applies or a case criterion fails.\n"
        "\n"
        "Hard-fail classes from the public rubric:\n"
        "- Wrong effect direction — the claim runs opposite to the data.\n"
        "- Wrong or unstated control — the comparison arm is missing or mismatched.\n"
        "- Re-subtracting a served contrast — a vehicle or baseline value is\n"
        "  subtracted from a value the release already publishes as a contrast.\n"
        "- Mechanism from annotation alone — mechanism claimed from an annotation,\n"
        "  an enrichment or a similarity, without a measurement.\n"
        '- NULL treated as "no effect" or zero — an untested or unmeasured value\n'
        "  read as evidence of absence.\n"
        "- Wrong label silently substituted — a drug or cell-line label guessed\n"
        "  or normalised instead of confirmed.\n"
        "- A non-public dataset invented or sought — a screen, panel or table\n"
        "  outside the served release is used or looked for.\n"
        "- A dataset identity contract violated — report the public id or cell\n"
        "  name, not an opaque line code.\n"
        '- A "significant count" as the headline — a count of significant items\n'
        "  presented as the result instead of an effect size.\n"
        "- A tool-less guess where a tool exists — the answer is given without\n"
        "  the retrieval the prompt requires.\n"
        f"{emerald}\n"
        "Case criteria:\n"
        f"{criteria}\n"
    )


def _yaml_str(value: str) -> str:
    """A JSON string is a valid YAML double-quoted scalar. Plain scalars break
    on text such as ``Source: x``, which the eval runner refuses to load."""
    return json.dumps(value, ensure_ascii=False)


def _prompt(spec: CaseSpec) -> str:
    outcome = spec.blocked_reason or spec.title
    tags = ", ".join(_yaml_str(tag) for tag in spec.tags)
    description = f"{spec.title}. Source: {spec.source}."
    return (
        "---\n"
        f"name: {_yaml_str(spec.name)}\n"
        f"description: {_yaml_str(description)}\n"
        f"tags: [{tags}]\n"
        "runs: 1\n"
        "max_turns: 16\n"
        "timeout_seconds: 600\n"
        "allowed_tools: [Read, Glob, Grep, Skill]\n"
        f"expected_outcome: {_yaml_str(outcome)}\n"
        "---\n"
        "\n"
        f"{spec.prompt}\n"
    )


def render_case(spec: CaseSpec) -> dict[str, str]:
    """Relative path -> text for one case directory."""
    files: dict[str, str] = {f"{spec.name}/prompt.md": _prompt(spec)}
    graders: dict[str, str] = {}
    if spec.skill:
        graders["skill.md"] = _tool_grader(
            Need("Skill", r'"skill"\s*:\s*"(?:[\w-]+:)?tara"'),
            minimum=1,
            maximum=None,
        )
    counts: dict[str, int] = {}
    for need in spec.needs:
        counts[need.tool] = counts.get(need.tool, 0) + 1
    seen: dict[str, int] = {}
    for need in spec.needs:
        seen[need.tool] = seen.get(need.tool, 0) + 1
        suffix = "" if counts[need.tool] == 1 else f"-{seen[need.tool]}"
        graders[f"use-{need.tool}{suffix}.md"] = _tool_grader(need, minimum=1, maximum=None)
    for tool in spec.forbid:
        graders[f"forbid-{tool}.md"] = _tool_grader(Need(tool), minimum=0, maximum=0)
    for before, after in spec.order:
        graders[f"order-{before}-before-{after}.md"] = (
            "---\n"
            "type: tool_order\n"
            f"before: {scoped_mcp_tool(before)}\n"
            f"after: {scoped_mcp_tool(after)}\n"
            "arm: with-only\n"
            "---\n"
        )
    if spec.route_pattern:
        # The proxy is a real server to the runner, so there are no mock calls to
        # grade. The trace's first line lists every tool name; only a tool call
        # carries the name as an unescaped ``"name":"…"`` field.
        graders["route.md"] = (
            "---\n"
            "type: regex\n"
            f"pattern: {_quote(_route_call_pattern(spec.route_pattern))}\n"
            "target: trace\n"
            "arm: with-only\n"
            "---\n"
        )
    graders["hard-fail-phrases.md"] = (
        "---\n"
        "type: regex\n"
        f"pattern: {_quote(HARD_FAIL_PATTERN)}\n"
        "match: not_contains\n"
        "target: last_message\n"
        "---\n"
    )
    graders["rubric.md"] = _rubric(spec)
    for name, text in graders.items():
        files[f"{spec.name}/graders/{name}"] = text
    return files


def _readme(specs: list[CaseSpec]) -> str:
    blocked = [spec for spec in specs if "blocked" in spec.tags]
    rows = "\n".join(
        f"| `{spec.name}` | {spec.blocked_reason} |" for spec in blocked
    )
    return f"""# Plugin eval cases

Rendered eval cases. The human-readable prompts and the rubric stay in
`evals/tara/`. This directory is generated into a temporary plugin copy; it
is not part of the installed plugin.

Cases tagged `release` are the replay suite. Cases tagged `blocked` still have
graders, but they need an independent expected value or a fixture this replay
does not have. A blocked case is never a pass: `scripts/check_evals.py` refuses
a record that counts one as a pass. Cases tagged `probe` are the live
connectivity check and are not part of the replay.

Pending and cancellation prompts stay in the human pack only. They are not
cases here.

## Blocked cases

| Case | Why it is not a pass |
|---|---|
{rows}

## Replay

Record a live run against the staging service, then replay that recording.
Both wrappers copy the plugin to a temporary directory, render these cases
there, and point the copy at a local proxy. They pass `--tag release`, so
blocked cases and the live probe are not in the run.

```sh
EVAL_UPSTREAM_URL='https://…' EVAL_TOKEN_FILE=/path/to/token.json \
  scripts/eval_record.sh RUN_DIR
scripts/eval_replay.sh RUN_DIR/eval-recording RUN_DIR
```

`eval_record.sh` runs the cases live against the service through the proxy.
It saves `RUN_DIR/eval-recording/responses.json`, the live results, and
`eval-record.json`, the record the release report reads. `eval_replay.sh`
replays the recording with no network and writes the `eval-replay-*` files and
`eval-replay-misses.jsonl`. Agents vary their arguments between runs, so a
replay can miss calls; an unrecorded call is a tool error, not an invented
answer. Use replay for plugin-only changes, not as the release gate.

`scripts/check_evals.py RUN_DIR/eval-record.json` prints each case as
pass, fail, or blocked, with the grader reasons. It exits non-zero on a
partial run or on a blocked case counted as a pass.

## Live probe

One case, `live-probe`, is for a plugin copy pointed at the staging endpoint
the operator supplies. The repository manifest is not retargeted. The command
is:

```sh
EVAL_PROBE_MCP_URL='https://…' scripts/eval_probe.sh
```

That runs `--mocks off` and `--allow-tools "mcp__plugin_tara_tahoe-public__*"`
against the copy.

Outcome: not run. The eval runner was not invoked for this change, so there
is no connect result, no auth result, and no runner version.

Decision: a live profile is not added. Replay stays the release path until a
probe records either a connection or an auth failure.
"""


def render_suite() -> dict[str, str]:
    specs = all_specs()
    files = {"README.md": _readme(specs)}
    for spec in specs:
        for rel, text in render_case(spec).items():
            files[rel] = text
    return files


def write_suite(destination: Path) -> Path:
    """Write the suite into ``destination``. Refuses a path inside ``plugins/``."""
    destination = Path(destination)
    refuse_plugins_output(destination)
    for rel, text in render_suite().items():
        path = destination / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination",
        type=Path,
        help="directory to write. Must not be inside plugins/",
    )
    args = parser.parse_args(argv)
    try:
        path = write_suite(args.destination)
    except common.RepoError as exc:
        print(f"eval cases refused: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
