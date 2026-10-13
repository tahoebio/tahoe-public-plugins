"""Sparse raw-count STATE-style sentence-length-one loader for Tara products.

Index complete delivered pools before spawning workers; controls never depend
on worker-local row arrival order. This is not STATE's X_hvg preprocessing or
SMILES-to-pert_emb model adapter.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, IterableDataset, get_worker_info


def source_rows(source):
    """Read only Tara-authorized Parquet files, with no HF/Databricks dependency."""
    import fsspec
    import pyarrow as pa
    import pyarrow.parquet as pq

    for url in source.parquet_files():
        with fsspec.open(url, "rb", block_size=256 * 1024, cache_type="readahead") as file:
            parquet = pq.ParquetFile(file)
            # Arrow can coalesce all selected row groups into one read even when
            # iter_batches yields small batches. Select one group per read so a
            # bounded client batch cannot become a whole-population range request.
            for group in range(parquet.num_row_groups):
                for batch in parquet.iter_batches(
                    batch_size=128, row_groups=[group], use_threads=False
                ):
                    yield from pa.Table.from_batches([batch]).to_pylist()


def sparse_counts(row, encoding, axis):
    genes = list(row["genes"])
    values = list(row["expressions"])
    if len(genes) != len(values):
        raise ValueError("unaligned_sparse_counts")
    if encoding == "hf_sparse_tokens_v1":
        if not genes or type(genes[0]) is not int or genes[0] != 1 or values[0] != -2:
            raise ValueError("missing_schema_marker")
        genes, values = genes[1:], values[1:]
    elif encoding != "delta_sparse_counts_v1":
        raise ValueError("unknown_counts_encoding")
    if len(set(genes)) != len(genes) or any(type(g) is not int or g not in axis for g in genes):
        raise ValueError("gene_axis_mismatch")
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("invalid_raw_counts")
    order = np.argsort([axis[g] for g in genes])
    return [axis[genes[i]] for i in order], [float(values[i]) for i in order]


def build_index(
    path,
    sources,
    *,
    gene_tokens,
    gene_axis_revision,
    pool_scope,
    max_bytes=64 * 1024**2,
    max_cells=100000,
):
    """Materialize a bounded complete index of the supplied prepared pools on disk.

    `sources` is [(TaraSource, encoding), ...], held open by the caller. Pool
    scope explicitly names full populations or selected prepared control samples.
    No claim is made that a selected control sample contains every atlas control.
    """
    if not pool_scope or not gene_axis_revision:
        raise ValueError("declare_pool_and_axis")
    tokens = tuple(gene_tokens)
    if not tokens or len(tokens) != len(set(tokens)) or any(type(g) is not int for g in tokens):
        raise ValueError("invalid_gene_axis")
    axis = {g: i for i, g in enumerate(tokens)}
    destination = Path(path)
    if destination.exists():
        raise ValueError("index_destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(destination)
    conn.execute("PRAGMA cache_size=-2048")
    conn.execute(
        "CREATE TABLE cells(id INTEGER PRIMARY KEY,plate TEXT,line TEXT,timepoint REAL,time_unit TEXT,condition_key TEXT,is_control INTEGER,payload TEXT)"
    )
    conn.execute("CREATE TABLE metadata(value TEXT)")
    count = 0
    digest = hashlib.sha256()
    try:
        for source, encoding in sources:
            if source.metadata.get("counts_space") != "raw":
                raise ValueError("raw_counts_required")
            if source.metadata.get("gene_axis_revision") != gene_axis_revision:
                raise ValueError("gene_axis_mismatch")
            if source.metadata.get("expression_encoding") != encoding:
                raise ValueError("counts_encoding_mismatch")
            for row in source_rows(source):
                for key in [
                    "cell_id",
                    "plate",
                    "cell_line_id",
                    "drug",
                    "sample",
                    "dose",
                    "dose_unit",
                    "timepoint",
                    "timepoint_unit",
                    "is_control",
                    "canonical_smiles",
                ]:
                    if key not in row:
                        raise ValueError("required_state_metadata_missing")
                if type(row["is_control"]) is not bool or type(row["cell_id"]) is not int:
                    raise ValueError("invalid_cell_identity")
                if row["canonical_smiles"] is None:
                    if not row["is_control"]:
                        raise ValueError("missing_treated_smiles")
                elif not isinstance(row["canonical_smiles"], str) or not row["canonical_smiles"]:
                    raise ValueError("invalid_smiles")
                indices, values = sparse_counts(row, encoding, axis)
                if len(indices) > len(tokens):
                    raise ValueError("invalid_sparse_width")
                payload = {k: v for k, v in row.items() if k not in {"genes", "expressions"}}
                payload.update(indices=indices, values=values)
                text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                condition_key = json.dumps(
                    [
                        row["drug"],
                        row["sample"],
                        row["dose"],
                        row["dose_unit"],
                        row["timepoint"],
                        row["timepoint_unit"],
                    ]
                )
                conn.execute(
                    "INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)",
                    (
                        row["cell_id"],
                        row["plate"],
                        row["cell_line_id"],
                        row["timepoint"],
                        row["timepoint_unit"],
                        condition_key,
                        int(row["is_control"]),
                        text,
                    ),
                )
                digest.update(text.encode())
                count += 1
                if count > max_cells:
                    raise ValueError("cell_index_limit")
                if count % 128 == 0:
                    conn.commit()
                    if destination.stat().st_size > max_bytes:
                        raise ValueError("cell_index_byte_limit")
        metadata = {
            "revision": digest.hexdigest(),
            "gene_axis_revision": gene_axis_revision,
            "gene_tokens": tokens,
            "pool_scope": pool_scope,
            "cell_count": count,
            "counts_space": "raw",
        }
        conn.execute("INSERT INTO metadata VALUES(?)", (json.dumps(metadata),))
        conn.execute(
            "CREATE INDEX control_group ON cells(plate,line,timepoint,time_unit,is_control,id)"
        )
        conn.commit()
        if destination.stat().st_size > max_bytes:
            raise ValueError("cell_index_byte_limit")
        return metadata
    except Exception:
        conn.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        conn.close()


class StatePairs(IterableDataset):
    def __init__(
        self,
        index,
        *,
        seed=0,
        epoch=0,
        rank=0,
        world_size=1,
        workers_per_rank=1,
        target_mode="treated_only",
        missing_controls="error",
    ):
        if any(
            type(v) is not int or v < 0 for v in [seed, epoch, rank, world_size, workers_per_rank]
        ):
            raise ValueError("invalid_seed_epoch_or_sharding")
        if not 0 <= rank < world_size or workers_per_rank < 1:
            raise ValueError("invalid_sharding")
        if target_mode not in {"treated_only", "all"} or missing_controls not in {"error", "skip"}:
            raise ValueError("invalid_pairing_policy")
        self.index = str(Path(index).resolve())
        self.seed = seed
        self.epoch = epoch
        self.rank = rank
        self.world_size = world_size
        self.workers_per_rank = workers_per_rank
        self.target_mode = target_mode
        self.missing_controls = missing_controls
        self.offsets = {}
        with self.connection() as conn:
            self.metadata = json.loads(conn.execute("SELECT value FROM metadata").fetchone()[0])

    def connection(self):
        conn = sqlite3.connect("file:" + self.index + "?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA cache_size=-2048")
        conn.execute("PRAGMA temp_store=FILE")
        return conn

    @property
    def fingerprint(self):
        return hashlib.sha256(
            json.dumps(
                [
                    self.metadata["revision"],
                    self.metadata["gene_axis_revision"],
                    self.metadata["gene_tokens"],
                    self.metadata["pool_scope"],
                    self.seed,
                    self.epoch,
                    self.rank,
                    self.world_size,
                    self.workers_per_rank,
                    self.target_mode,
                    self.missing_controls,
                ]
            ).encode()
        ).hexdigest()

    def set_epoch(self, epoch):
        if type(epoch) is not int or epoch < 0:
            raise ValueError("invalid_epoch")
        self.epoch = epoch
        self.offsets = {}

    def state_dict(self):
        return {
            "fingerprint": self.fingerprint,
            "epoch": self.epoch,
            "offsets": self.offsets.copy(),
        }

    def load_state_dict(self, state):
        if state["fingerprint"] != self.fingerprint or state["epoch"] != self.epoch:
            raise ValueError("resume_layout_or_epoch_mismatch")
        self.offsets = {str(k): int(v) for k, v in state["offsets"].items()}

    def acknowledge(self, checkpoint):
        if checkpoint["fingerprint"] != self.fingerprint:
            raise ValueError("resume_identity_mismatch")
        slot = str(checkpoint["slot"])
        self.offsets[slot] = max(self.offsets.get(slot, 0), checkpoint["offset"])

    def __iter__(self):
        info = get_worker_info()
        workers = info.num_workers if info else 1
        worker = info.id if info else 0
        if workers != self.workers_per_rank:
            raise ValueError("worker_layout_mismatch")
        slot = self.rank * workers + worker
        slots = self.world_size * workers

        def priority(cell_id):
            return hashlib.sha256(
                f"state-pair-v1\n{self.metadata['revision']}\n{self.seed}\n{self.epoch}\n{cell_id}".encode()
            ).hexdigest()

        conn = self.connection()
        conn.create_function("priority", 1, priority)
        predicate = "WHERE is_control=0" if self.target_mode == "treated_only" else ""
        targets = conn.execute(
            f"SELECT id,plate,line,timepoint,time_unit,payload FROM cells {predicate} ORDER BY plate,line,condition_key,priority(id),id"
        )
        owned = 0
        try:
            for cell_id, plate, line, timepoint, time_unit, payload in targets:
                if int(priority(cell_id)[:16], 16) % slots != slot:
                    continue
                owned += 1
                if owned <= self.offsets.get(str(slot), 0):
                    continue
                checkpoint = {"fingerprint": self.fingerprint, "slot": slot, "offset": owned}
                group = (plate, line, timepoint, time_unit)
                size = conn.execute(
                    "SELECT count(*) FROM cells WHERE plate=? AND line=? AND timepoint=? AND time_unit=? AND is_control=1",
                    group,
                ).fetchone()[0]
                if not size:
                    if self.missing_controls == "error":
                        raise ValueError("no_exact_plate_line_timepoint_controls")
                    yield {
                        "skipped": True,
                        "reason": "missing_exact_controls",
                        "treated_cell_id": cell_id,
                        "plate": plate,
                        "cell_line_id": line,
                        "checkpoint": checkpoint,
                    }
                    continue
                draw = (
                    int(
                        hashlib.sha256(
                            (priority(cell_id) + "\nindependent-control").encode()
                        ).hexdigest(),
                        16,
                    )
                    % size
                )
                control = json.loads(
                    conn.execute(
                        "SELECT payload FROM cells WHERE plate=? AND line=? AND timepoint=? AND time_unit=? AND is_control=1 ORDER BY id LIMIT 1 OFFSET ?",
                        group + (draw,),
                    ).fetchone()[0]
                )
                target = json.loads(payload)
                yield {
                    "control": control,
                    "treated": target,
                    "cell_sentence_len": 1,
                    "counts_space": "raw",
                    "pairing": "independent_control_with_replacement",
                    "gene_axis_revision": self.metadata["gene_axis_revision"],
                    "gene_count": len(self.metadata["gene_tokens"]),
                    "control_pool_scope": self.metadata["pool_scope"],
                    "checkpoint": checkpoint,
                }
        finally:
            conn.close()

    def loader(self, *, batch_size=16, plate_homogeneous=True, num_workers=0):
        if batch_size < 1 or (num_workers or 1) != self.workers_per_rank:
            raise ValueError("worker_layout_mismatch")
        return DataLoader(
            StateBatches(self, batch_size, plate_homogeneous),
            batch_size=None,
            num_workers=num_workers,
            persistent_workers=False,
            **({"multiprocessing_context": "spawn"} if num_workers else {}),
        )


class StateBatches(IterableDataset):
    def __init__(self, pairs, batch_size, plate_homogeneous):
        self.pairs = pairs
        self.batch_size = batch_size
        self.plate_homogeneous = plate_homogeneous

    def __iter__(self):
        batch = []
        group = None
        for pair in self.pairs:
            row = pair.get("treated", pair)
            current = (
                row.get("plate"),
                row.get("cell_line_id"),
                row.get("drug"),
                row.get("sample"),
                row.get("dose"),
                row.get("dose_unit"),
                row.get("timepoint"),
                row.get("timepoint_unit"),
            )
            if batch and (
                len(batch) >= self.batch_size or (self.plate_homogeneous and current != group)
            ):
                yield collate(batch)
                batch = []
            group = current
            batch.append(pair)
        if batch:
            yield collate(batch)


def collate(pairs):
    valid = [p for p in pairs if not p.get("skipped")]
    result = {
        "checkpoints": [p["checkpoint"] for p in pairs],
        "skipped_missing_controls": len(pairs) - len(valid),
        "cell_sentence_len": 1,
        "counts_space": "raw",
        "pert_emb": None,
    }
    if not valid:
        return result
    width = valid[0]["gene_count"]
    for role in ["control", "treated"]:
        coordinates = []
        values = []
        for i, pair in enumerate(valid):
            row = pair[role]
            coordinates.extend((i, 0, g) for g in row["indices"])
            values.extend(row["values"])
        indices = (
            torch.tensor(coordinates, dtype=torch.int64).T
            if coordinates
            else torch.empty((3, 0), dtype=torch.int64)
        )
        result[role + "_counts"] = torch.sparse_coo_tensor(
            indices,
            torch.tensor(values, dtype=torch.float32),
            (len(valid), 1, width),
            check_invariants=True,
        ).coalesce()
        result[role + "_cell_id"] = [p[role]["cell_id"] for p in valid]
    for key in [
        "plate",
        "cell_line_id",
        "drug",
        "drug_id",
        "sample",
        "dose",
        "dose_unit",
        "timepoint",
        "timepoint_unit",
    ]:
        result[key] = [p["treated"][key] for p in valid]
    result["drug_smiles"] = [p["treated"]["canonical_smiles"] for p in valid]
    result["control_smiles"] = [p["control"]["canonical_smiles"] for p in valid]
    result["gene_axis_revision"] = valid[0]["gene_axis_revision"]
    result["control_pool_scope"] = valid[0]["control_pool_scope"]
    return result
