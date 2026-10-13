# Stream or load Tahoe data with your existing Python reader

Streaming is available once the server advertises the data-access tools:
`list_dataset_products` — available once the server advertises it;
`prepare_dataset` — available once the server advertises it.
`prepare_cell_sample` — available once the server advertises it.
Until then, the examples below describe the new interface; the existing expression
slice and bounded SQL tools do not issue streaming sources.

The plugin bundles [tara_data.py](../scripts/tara_data.py), a connection helper.
Put its directory on your Python import path, or copy that file beside your notebook.
There is no Tara package to install. The connection uses FastMCP 4.1.0; if your Python
runtime does not already have it, install the bundled [requirements](../scripts/requirements.txt).
Keep your existing HF Datasets, Polars, PyTorch, Arrow or Mosaic libraries.

The helper uses the public sign-in flow and renews data access during a long job.
Public admission also depends on the service's launch policy; this draft does not
remove invitations or enable new access on the running endpoint.
Your notebook may need one browser sign-in if its host cannot bridge the plugin's
OAuth credentials. No Databricks account or cloud credentials are needed for the
metered Tara source. Keep the connection and source contexts open while reading.
Do not put native capability URLs in shared notebooks or logs; the helper supplies
them to readers directly, and they expire with their renewable access lease.

## Find the right product

```python
from tara_data import connect

with connect() as tara:
    products = tara.products()
    print(products)  # product ids, revisions, formats and row grain; no tokens
```

Choose ids actually returned by this service. The names below are example product
ids for registered releases, not a promise that every format is currently listed.
Record the returned revision, filters, gene axis and native checkpoint with your run.

| Product | Row grain | Use |
|---|---|---|
| Single-cell Parquet | One cell, paired sparse gene/count lists | HF streaming, lazy Polars, training |
| Single-cell Arrow condition | One cell, paired sparse gene/count lists | Future source-bound selected line + sample analysis |
| Pseudobulk Arrow condition | One gene × cell-line × sample | Future source-bound raw aggregated counts and normalized expression |
| Gene metadata Parquet | One gene | Stable token/Ensembl/symbol axis |
| Safe typed MDS | One cell/sample | Repeated training with native cache and resume |

Pseudobulk is not single-cell data. Published differential-expression results are
contrasts, not a raw pseudobulk-count download. Gene token ids are not matrix column
positions. In the declared HF sparse-token encoding, token 1 paired with count -2
is a CLS marker; exclude that pair from biological expression. Raw sparse-count
products can legitimately contain gene 1: use the product's declared encoding.
Missing stored gene entries mean zero. SQL-backed Arrow products are withheld until
their physical source reads have a verified bound; an estimated scan size is insufficient.

## HF Datasets: same training loop, a new source

Existing public HF path:

```python
from datasets import load_dataset

cells = load_dataset(
    "tahoebio/Tahoe-100M", "expression_data",
    revision="2dc57900b7981cfcf5e211527169a0b006546a95",
    split="train", streaming=True,
    columns=["genes", "expressions", "cell_line_id"],
)
first_batch = list(cells.take(128))
```

Tara path, retaining the actual HF streaming dataset:

```python
from tara_data import connect

with connect() as tara:
    with tara.prepare("tahoe100m-cells-parquet") as source:
        cells = source.hf(columns=["genes", "expressions", "cell_line_id"])
        first_batch = list(cells.take(128))
        # Existing .map(), .shuffle(seed=...), and native state_dict() still apply.
```

For a PyTorch training loop, pass `source.hf(...)` to your existing `DataLoader`.
Sparse arrays have variable lengths, so use your model's sparse collator rather than
the default collator for arbitrary gene/count arrays. Set the shuffle seed and pin
worker count/partitioning when comparing runs. Use the native HF state dictionary
(or StatefulDataLoader for worker-aware checkpoints); shuffle-buffer restoration has
HF's documented limitations. File sharding is deterministic:
`source.hf(rank=rank, world_size=world_size)` selects disjoint files in pinned order.

## Polars: project and filter before collecting

Existing public HF Parquet:

```python
import polars as pl

url = (
    "https://huggingface.co/datasets/tahoebio/Tahoe-100M/resolve/"
    "2dc57900b7981cfcf5e211527169a0b006546a95/"
    "data/train-00000-of-03388.parquet"
)
rows = pl.scan_parquet(url).select("cell_line_id", "sample").limit(128).collect()
```

Tara Parquet using the same lazy reader:

```python
import polars as pl
from tara_data import connect

with connect() as tara:
    with tara.prepare("tahoe100m-cells-parquet") as source:
        rows = (
            source.polars(names=["data/train-00000-of-03388.parquet"])
            .select("cell_line_id", "sample")
            .limit(128)
            .collect(engine="streaming")
        )
```

Both paths can prune columns and eligible row groups. A row filter does not guarantee
cheap reads when file statistics cannot exclude the unwanted rows. Selecting a
file does not select one biological condition. Use a registered complete condition
population or prepared cell sample when line/sample filtering must happen at the source.

## Ask for 1,000 complete cells

Resolve the public cell-line and drug ids using the coverage tools. Use the dataset
and snapshot versions reported by the products service, not an unpinned latest label.
The values here are variables obtained from those responses:

```python
from tara_data import connect

with connect() as tara:
    source = tara.sample_cells(
        cell_line_id=confirmed_cell_line_id, drug_id=confirmed_drug_id,
        dataset_version=dataset_version, snapshot_version=snapshot_version,
        sample_size=1000, seed=7,
    )
    if isinstance(source, dict):
        # Multiple dose/timepoint/plate choices, or a complete empty population.
        print(source)
    else:
        with source:
            print(source.metadata)  # requested/returned/available counts and condition
            cells = source.hf()     # complete sparse counts plus aligned cell metadata
            first_batch = list(cells.take(16))
            # Or source.polars().select(...).collect(engine="streaming").
```

When the response requests condition selection, choose one returned condition and
repeat with `condition_id=chosen_condition_id`. Dose, timepoint, sample and plate
are never silently pooled. A complete 800-cell population explicitly returns 800,
with status `fewer_than_requested`; an incomplete population is refused. Sampling
is deterministic without replacement. Rows retain raw counts and paired sparse
gene ids; there is no automatic normalization or gene truncation.

Preparation is a bounded read of an approved pinned population and its immutable
cell index. It refuses oversized sources before reading cell identities or counts,
and never falls back to a broad SQL scan. Reader startup and sample preparation
are separate costs. Full-atlas streaming needs separately registered bounded shards;
this sample endpoint does not promise every atlas condition is ready.

## Plate-matched control/treated batches

The plugin also bundles [tara_state_loader.py](../scripts/tara_state_loader.py).
Keep PyTorch, NumPy, PyArrow and fsspec in your usual reader environment. Prepare a
treated source and an explicit control source for each plate/line/timepoint, then
build the local index before spawning dataloader workers:

```python
from tara_state_loader import build_index, StatePairs

# Sources stay open during this bounded local indexing step.
build_index(
    "training-pool.sqlite", [(treated_source, treated_encoding),
                             (control_source, control_encoding)],
    gene_tokens=pinned_gene_tokens, gene_axis_revision=pinned_gene_axis_revision,
    pool_scope="declared prepared targets and control population",
)
pairs = StatePairs("training-pool.sqlite", seed=42, target_mode="treated_only")
for batch in pairs.loader(batch_size=16, plate_homogeneous=True):
    control = batch["control_counts"]  # sparse [B, 1, G]
    treated = batch["treated_counts"]  # sparse [B, 1, G]
    smiles = batch["drug_smiles"]      # aligned strings; control SMILES may be null
    process_batch(control, treated, smiles)
    for checkpoint in batch["checkpoints"]:
        pairs.acknowledge(checkpoint)  # save pairs.state_dict() after processing
```

Sentence length one means one complete treated cell and one independently sampled
control cell. Controls match plate, cell-line id and timepoint, and may be reused.
Missing exact controls fail by default; `missing_controls="skip"` reports explicit
skip counts. The control pool is the complete delivered declared pool; a selected
control sample does not become a census of all atlas controls. Set `rank`,
`world_size`, and `workers_per_rank` explicitly for disjoint treated examples;
resume requires the same layout, seed, epoch, pool and gene axis.

This loader returns raw sparse counts and SMILES. It does not reproduce STATE's
preprocessed dense HVG representation, encode SMILES into numeric `pert_emb`, or
launch training. Supply those model-specific steps explicitly. Preserve sample and
dose identity; identical drug SMILES can correspond to different doses.

## Filtered single-cell analysis: Arrow, Polars or sparse CSR

Confirm the public Cellosaurus id and exact sample with coverage tools. Only
conditions approved for the selected product are accepted. Use
`tara.conditions(product_id, cell_line=confirmed_cell_line)` to discover a bounded
page of accepted sample labels without querying expression.

```python
from tara_data import connect

# Set these from confirmed coverage and the product's accepted filters.
cell_line, sample = confirmed_cell_line, confirmed_sample
with connect() as tara:
    with tara.prepare(
        "tahoe100m-cells-arrow", cell_line=cell_line, sample=sample, batch_rows=128,
    ) as source:
        for frame in source.polars_batches():
            consume(frame)  # one bounded Arrow batch converted to Polars
            checkpoint = source.checkpoint  # persist only after processing
            break
```

`source.arrow_batches()` yields real Arrow RecordBatches. `source.csr_batches(gene_tokens)`
yields `(cell_batch, sparse_matrix)` using your pinned, unique gene-token axis and
removes the CLS pair. It never allocates a cells × all-genes dense atlas. A new
access lease can resume with `source.arrow_batches(cursor=saved_cursor)` for the same
account, revision and filters; `checkpoint['done']` means the stream finished.

`source.hf()` also adapts a condition Arrow stream to an HF IterableDataset for a
single reader. Use `num_workers=0` for this bridge. For distributed training, select
Parquet/MDS or partition distinct approved conditions; do not replay one condition
in every worker.

## Pseudobulk: preserve counts and replication

```python
from tara_data import connect

with connect() as tara:
    with tara.prepare(
        "tahoe100m-pseudobulk-arrow",
        cell_line=confirmed_cell_line, sample=confirmed_sample, batch_rows=128,
    ) as source:
        for frame in source.polars_batches():
            consume(frame.select("gene_name", "raw_counts", "cpm_log1p", "n_cells"))
```

These are gene × condition rows. Keep raw counts separate from normalized
`cpm_log1p`; preserve cell counts, plate and sample identity. Do not treat cells or
genes as independent biological replicates. Existing `get_expression_slice` is still
appropriate when a few genes and conditions answer your question.

## Mosaic Streaming: native sharding, cache and resume

A direct MDS workflow constructs `StreamingDataset(remote=your_source, local=your_cache)`.
Tara keeps that dataset and supplies a metered download adapter:

```python
from tara_data import connect

with connect() as tara:
    with tara.prepare("tahoe100m-cells-mds") as source:
        cells = source.mds(
            local="./cell-cache", cache_limit="256mb", predownload=128,
            shuffle=True, shuffle_seed=42, batch_size=32,
        )
        # Pass cells to your existing StreamingDataLoader or DataLoader.
        # Save/restore the native state_dict after processing a training batch.
```

Mosaic 0.13 needs the bundled HTTP download adapter; stock storage downloaders are
unchanged. Only typed safe products are accepted. The legacy public MDS product
uses pickle encodings and is not a supported substitute. Dataset preparation does
not publish or convert a new MDS product. Workers share their rank's renewable
source; distributed ranks open their own access. Keep native caches separated by
product/revision to avoid reusing a different release.

## Example prompts for the release demo

- "Keep my HF training code. Show how to read the first 128 Tahoe cells through Tara."
- "Give me a Polars lazy scan that loads just cell-line and sample metadata."
- "Stream raw single-cell counts for this confirmed line and sample into sparse CSR."
- "Load raw pseudobulk counts for a treatment and its matched vehicle, preserving plate and sample."
- "Show how to resume a seeded MDS training run with a bounded local cache."
- "Use the data-access handle from this chat in my existing Python reader."
- "Get 1,000 complete cells for this line and drug, with seed 7 and an explicit dose and plate."
- "Build plate-matched raw control/treated batches with aligned SMILES and sentence length one."

The chat can prepare an account-bound access handle. In Python, `tara.open(access_handle)`
redeems it after sign-in; its helper supplies data outside the model's context.
Data limits apply to the account across readers and renewals. Replays consume the
same budget. A short `take()` or client-side `limit()` does not authorize a full backend
scan, and a rate-limit response is a reason to stop, not to retry indefinitely.

These examples were checked with HF Datasets 4.8.4 and 5.1.0, Polars 2.0.0, PyArrow 26.0.0 and
Mosaic Streaming 0.13.0. The combined HF/Mosaic environment uses HF Hub 0.36.2 and
Transformers 4.57.6; newer HF Datasets releases may need a separate environment.
No speed advantage is claimed until representative source comparisons pass.
See the [HF streaming guide](https://huggingface.co/docs/datasets/stream).
