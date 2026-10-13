# Set A — five lookup and aggregation questions

Run each prompt as written, one fresh session each. Hard criteria for every prompt: the answer is retrieved with the tools (no tool-less guess), labels are confirmed rather than guessed, and the stated option or count is the one in the frozen values. Frozen values: [frozen-expected-0.3.x.md](frozen-expected-0.3.x.md#set-a).

## A1

> Using tahoe tools, return the list of MEKi and RAFi in Tahoe100M (excluding multi-TKi), after collapsing different salt forms.

Route: `get_drug_info(moa="MEK inhibitor")`, `get_drug_info(moa="RAF inhibitor")`, `search_conditions` to confirm treatment arms.

## A2

> Using tahoe tools, does binimetinib up-reg or down-reg the KRAS signaling signature in Tahoe100M? Consider the median effect across cell lines. Options: upregulate, downregulate, complex pattern, can't be determined

Route: `search_gene_sets(query="KRAS")`, `search_conditions`, `get_pathway_scores(drug="Binimetinib", gene_sets=["HALLMARK_KRAS_SIGNALING"])`.

## A3

> Using tahoe tools, which drug MOA induces the largest interferon alpha/beta response up-regulation in Tahoe100M, at the highest dose? Consider the median effect across cell lines.

Route: `search_gene_sets(query="INTERFERON")`, `get_pathway_scores` or guarded `run_sql` over the differential pathway scores at 5 µM, mechanism of action from `get_drug_info`.

## A4

> Using tahoe tools, how many agents induce DNA damage or inhibit DNA synthesis/repair in Tahoe100M? Options: 0, 1-20, 21-50, 51-70, 71-90, 91-100, cannot be determined. Do not collapse different salt forms.

Route: guarded `run_sql` over the drug annotation table, counting distinct drug labels by mechanism annotation.

## A5

> Using tahoe tools, in Tahoe100M, we observe that Pitavastatin (Calcium) has a larger effect than Pravastatin (sodium) in downregulating the active YAP signature. Is this effect more likely mediated by (a) a larger on-target effect, or (b) a different mechanism, including off-target, or (c) cannot be determined? Answer based on what we know about the drug mechanism, and specifically the pharmacological differences between the two drugs.

Route: `get_drug_info`, `search_gene_sets(query="YAP")`, `get_pathway_scores`. The answer states that the data do not show target engagement.
