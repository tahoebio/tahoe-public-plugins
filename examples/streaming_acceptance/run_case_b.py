#!/usr/bin/env python3
"""End-to-end Case B: random raw-count control/treated STATE-style pairs."""

from __future__ import annotations

import argparse
import json
import resource
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from contract import (
    AcceptanceReport,
    gene_axis_digest,
    payload_types_valid,
    safe_failure_kind,
    source_hosts_allowed,
)
from preflight import inspect
from protocol import PublicTaraTools, product_ids

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "plugins/tara/skills/tara/scripts"))


def _memory_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage if sys.platform == "darwin" else usage * 1024)


def run(config: dict) -> dict:
    from tara_data import connect
    from tara_state_loader import StatePairs, build_index

    report = AcceptanceReport("B")
    binding = inspect(config, "b")
    if binding["status"] != "green":
        raise ValueError("preflight_bindings_missing")
    size = config.get("sample_size", 1000)
    seed = config.get("seed", 7)
    expected_schema = set(config["expected_row_schema"])
    if size != 1000:
        raise ValueError("case_b_requires_1000_treated_cells")
    if not {
        "cell_id",
        "cell_line_id",
        "drug_id",
        "drug",
        "sample",
        "plate",
        "dose",
        "dose_unit",
        "timepoint",
        "timepoint_unit",
        "is_control",
        "canonical_smiles",
        "genes",
        "expressions",
    }.issubset(expected_schema):
        raise ValueError("expected_schema_missing_required_fields")

    run_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="tara-streaming-acceptance-") as tmp:
        workdir = Path(tmp)
        workdir.chmod(0o700)
        with connect(config["base_url"]) as tara:
            tools = PublicTaraTools(tara)
            tools.initialize()
            available_products = product_ids(tools.products())
            report.check(
                "mcp_products_advertised",
                {
                    config["treated_product"],
                    config["control_product"],
                    config["gene_axis_product"],
                }
                <= available_products,
            )
            common = {
                "dataset_version": config["dataset_version"],
                "snapshot_version": config["snapshot_version"],
                "sample_size": size,
            }
            treated_prepared = tools.prepare_sample(
                cell_line_id=config["cell_line_id"],
                drug_id=config["drug_id"],
                condition=config["expected_treated_condition"],
                seed=seed,
                **common,
            )
            control_prepared = tools.prepare_sample(
                cell_line_id=config["cell_line_id"],
                drug_id=config["control_drug_id"],
                condition=config["expected_control_condition"],
                seed=seed ^ 0x5A17,
                **common,
            )
            report.check(
                "mcp_sample_ready",
                treated_prepared.get("status") == "ready"
                and control_prepared.get("status") == "ready",
            )
            treated = tara.open(treated_prepared["access_handle"])
            control = tara.open(control_prepared["access_handle"])
            report.check(
                "mcp_sample_handles",
                bool(treated_prepared.get("access_handle"))
                and bool(control_prepared.get("access_handle")),
            )
            if isinstance(treated, dict) or isinstance(control, dict):
                raise TypeError("served_population_not_prepared")
            available = {}
            population_revisions = {}
            source_reservations = {}
            decoded_reservations = {}
            for label, source, expected in (
                ("treated", treated, config["expected_treated_condition"]),
                ("control", control, config["expected_control_condition"]),
            ):
                meta = source.metadata
                if not source_hosts_allowed(source, config["allowed_source_hosts"]):
                    raise ValueError(f"{label}_source_host_not_approved")
                if meta.get("counts_space") != "raw":
                    raise ValueError(f"{label}_not_raw_counts")
                if meta.get("dataset_version") != config["dataset_version"]:
                    raise ValueError(f"{label}_dataset_version_mismatch")
                if meta.get("snapshot_version") != config["snapshot_version"]:
                    raise ValueError(f"{label}_snapshot_mismatch")
                if (
                    meta.get("condition", {}).get("condition_id")
                    != config[f"{label}_condition_id"]
                ):
                    raise ValueError(f"{label}_condition_id_mismatch")
                if meta.get("population_product") != config[f"{label}_product"]:
                    raise ValueError(f"{label}_product_mismatch")
                if meta.get("replacement") is not False:
                    raise ValueError(f"{label}_sample_status_or_replacement_mismatch")
                if meta.get("sampling_algorithm") != "sha256-priority-v1":
                    raise ValueError(f"{label}_sampling_algorithm_mismatch")
                if not meta.get("revision"):
                    raise ValueError(f"{label}_sample_revision_missing")
                if meta.get("expression_encoding") != config["expected_count_encoding"]:
                    raise ValueError(f"{label}_count_encoding_mismatch")
                if meta.get("gene_axis_revision") != config["gene_axis_revision"]:
                    raise ValueError(f"{label}_gene_axis_revision_mismatch")
                if meta.get("source_kind") != "tahoe_backed_served":
                    raise ValueError(f"{label}_source_provenance_mismatch")
                for key, value in expected.items():
                    if meta.get("condition", {}).get(key) != value:
                        raise ValueError(f"{label}_condition_metadata_mismatch:{key}")
                if (
                    int(meta.get("available_cells", 0))
                    < config["minimum_eligible_cells"]
                ):
                    raise ValueError(f"{label}_population_too_small")
                if meta.get("population_complete") is not True:
                    raise ValueError(f"{label}_population_incomplete")
                if int(meta.get("returned_cells", -1)) != size:
                    raise ValueError(f"{label}_incomplete_sample")
                if int(meta.get("requested_cells", -1)) != size:
                    raise ValueError(f"{label}_requested_count_mismatch")
                if not meta.get("population_revision"):
                    raise ValueError(f"{label}_population_revision_missing")
                expected_seed = seed if label == "treated" else seed ^ 0x5A17
                if int(meta.get("seed", -1)) != expected_seed:
                    raise ValueError(f"{label}_sampling_seed_mismatch")
                available[label] = int(meta["available_cells"])
                population_revisions[label] = meta["population_revision"]
                source_reservations[label] = int(meta.get("reserved_source_bytes", 0))
                decoded_reservations[label] = int(meta.get("reserved_decoded_bytes", 0))
                if (
                    not 0
                    < source_reservations[label]
                    <= config["expected_source_bytes"]
                ):
                    raise ValueError(f"{label}_source_reservation_exceeded")
                if (
                    not 0
                    < decoded_reservations[label]
                    <= config["expected_decoded_bytes"]
                ):
                    raise ValueError(f"{label}_decoded_reservation_exceeded")

            axis_source = tara.prepare(
                config["gene_axis_product"], revision=config["gene_axis_revision"]
            )
            if not source_hosts_allowed(axis_source, config["allowed_source_hosts"]):
                raise ValueError("gene_axis_host_not_approved")
            gene_tokens = [row["token_id"] for row in axis_source.hf()]
            axis_reserved_bytes = int(
                axis_source.metadata.get("reserved_source_bytes", 0)
            )
            axis_decoded_bytes = int(
                axis_source.metadata.get("reserved_decoded_bytes", 0)
            )
            axis_source.close()
            if (
                not gene_tokens
                or len(gene_tokens) != len(set(gene_tokens))
                or any(type(token) is not int for token in gene_tokens)
            ):
                raise ValueError("invalid_gene_axis_product")
            report.check(
                "exact_gene_count", len(gene_tokens) == config["expected_gene_count"]
            )
            report.check(
                "exact_gene_axis_digest",
                gene_axis_digest(gene_tokens) == config["expected_gene_axis_sha256"],
            )

            index_path = workdir / "state-pools.sqlite"
            index_metadata = build_index(
                index_path,
                [
                    (treated, config["expected_count_encoding"]),
                    (control, config["expected_count_encoding"]),
                ],
                gene_tokens=gene_tokens,
                gene_axis_revision=config["gene_axis_revision"],
                pool_scope="two explicitly pinned complete prepared samples; treated and matched control",
                max_bytes=config["max_decoded_bytes"],
                max_cells=2 * size + 100,
            )
            with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as index_conn:
                index_conn.execute("PRAGMA query_only=ON")
                expected_payload_schema = (
                    expected_schema - {"genes", "expressions"}
                ) | {"indices", "values"}
                exact_schema = True
                for payload_text, is_control in index_conn.execute(
                    "SELECT payload,is_control FROM cells"
                ):
                    payload = json.loads(payload_text)
                    exact_schema &= set(payload) == expected_payload_schema
                    exact_schema &= payload_types_valid(
                        payload, control=bool(is_control)
                    )
                    declared = (
                        config["expected_control_condition"]
                        if is_control
                        else config["expected_treated_condition"]
                    )
                    exact_schema &= all(
                        payload.get(key) == value
                        for key, value in declared.items()
                        if key in payload
                    )
                    exact_schema &= (
                        (payload.get("canonical_smiles") is None)
                        if is_control
                        else (
                            payload.get("canonical_smiles") == config["expected_smiles"]
                        )
                    )
                report.check("exact_source_row_schema_and_metadata", exact_schema)
                if not exact_schema:
                    raise ValueError("source_row_schema_or_metadata_mismatch")
                expected_sample_ids = {
                    "treated": [
                        r[0]
                        for r in index_conn.execute(
                            "SELECT id FROM cells WHERE is_control=0 ORDER BY id"
                        )
                    ],
                    "control": [
                        r[0]
                        for r in index_conn.execute(
                            "SELECT id FROM cells WHERE is_control=1 ORDER BY id"
                        )
                    ],
                }
            replay_sources = (
                ("treated", config["drug_id"], config["treated_condition_id"], seed),
                (
                    "control",
                    config["control_drug_id"],
                    config["control_condition_id"],
                    seed ^ 0x5A17,
                ),
            )
            sample_replay_ok = True
            replay_source_bytes = 0
            replay_decoded_bytes = 0
            for label, drug_id, condition_id, sample_seed in replay_sources:
                replay_prepared = tools.prepare_sample(
                    cell_line_id=config["cell_line_id"],
                    drug_id=drug_id,
                    dataset_version=config["dataset_version"],
                    snapshot_version=config["snapshot_version"],
                    sample_size=size,
                    seed=sample_seed,
                    condition=(
                        config["expected_treated_condition"]
                        if label == "treated"
                        else config["expected_control_condition"]
                    ),
                )
                sample_replay_ok &= replay_prepared.get("status") == "ready"
                replay = tara.open(replay_prepared["access_handle"])
                if isinstance(replay, dict):
                    sample_replay_ok = False
                    continue
                replay_ids = [row["cell_id"] for row in replay.hf(columns=["cell_id"])]
                replay_source_bytes += int(
                    replay.metadata.get("reserved_source_bytes", 0)
                )
                replay_decoded_bytes += int(
                    replay.metadata.get("reserved_decoded_bytes", 0)
                )
                sample_replay_ok &= (
                    replay.metadata.get("population_revision")
                    == population_revisions[label]
                    and sorted(replay_ids) == expected_sample_ids[label]
                )
                replay.close()
            report.check("sample_seed_replay", sample_replay_ok)
            total_source_bytes = (
                sum(source_reservations.values())
                + replay_source_bytes
                + axis_reserved_bytes
            )
            total_decoded_bytes = (
                sum(decoded_reservations.values())
                + replay_decoded_bytes
                + axis_decoded_bytes
            )
            report.check(
                "aggregate_source_budget",
                0
                < total_source_bytes
                <= min(config["expected_source_bytes"], config["max_source_bytes"]),
            )
            report.check(
                "aggregate_decoded_budget",
                0
                < total_decoded_bytes
                <= min(config["expected_decoded_bytes"], config["max_decoded_bytes"]),
            )
            treated.close()
            control.close()

        source_ready = time.perf_counter()
        pairs = StatePairs(
            index_path, seed=config.get("state_seed", 42), target_mode="treated_only"
        )
        iterator = iter(
            pairs.loader(
                batch_size=config.get("batch_size", 16), plate_homogeneous=True
            )
        )
        dataloader_started = time.perf_counter()
        first_batch = next(iterator)
        first_batch_seconds = time.perf_counter() - dataloader_started
        first_ids = list(first_batch["treated_cell_id"])
        first_pairing = list(
            zip(
                first_batch["treated_cell_id"],
                first_batch["control_cell_id"],
                strict=True,
            )
        )
        first_checks = _validate_batch(first_batch, config, len(gene_tokens))
        with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as index_conn:
            index_conn.execute("PRAGMA query_only=ON")
            first_checks.update(_validate_batch_against_index(first_batch, index_conn))
        if not all(
            value for key, value in first_checks.items() if key != "nonzero_entries"
        ):
            raise ValueError("first_batch_validation_failed")
        for checkpoint in first_batch["checkpoints"]:
            pairs.acknowledge(checkpoint)
        checkpoint = pairs.state_dict()

        remaining = []
        remaining_pairing = []
        decoded_nonzeros = first_checks["nonzero_entries"]
        for batch in iterator:
            validation = _validate_batch(batch, config, len(gene_tokens))
            with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as index_conn:
                index_conn.execute("PRAGMA query_only=ON")
                validation.update(_validate_batch_against_index(batch, index_conn))
            if not all(
                value for key, value in validation.items() if key != "nonzero_entries"
            ):
                raise ValueError("batch_validation_failed")
            decoded_nonzeros += validation["nonzero_entries"]
            remaining.extend(batch["treated_cell_id"])
            remaining_pairing.extend(
                zip(batch["treated_cell_id"], batch["control_cell_id"], strict=True)
            )
            for acknowledged in batch["checkpoints"]:
                pairs.acknowledge(acknowledged)
        dataloader_finished = time.perf_counter()
        resumed = StatePairs(
            index_path, seed=config.get("state_seed", 42), target_mode="treated_only"
        )
        resumed.load_state_dict(checkpoint)
        resumed_ids = []
        resumed_pairing = []
        resume_counts_match = True
        for batch in resumed.loader(batch_size=config.get("batch_size", 16)):
            resumed_ids.extend(batch["treated_cell_id"])
            resumed_pairing.extend(
                zip(batch["treated_cell_id"], batch["control_cell_id"], strict=True)
            )
            with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as index_conn:
                index_conn.execute("PRAGMA query_only=ON")
                resume_counts_match &= all(
                    _validate_batch_against_index(batch, index_conn).values()
                )
        report.check(
            "acknowledged_resume",
            len(resumed_ids) == len(remaining) and resumed_pairing == remaining_pairing,
        )
        report.check("resume_no_replay", not (set(resumed_ids) & set(first_ids)))
        report.check("resume_count_parity", resume_counts_match)

        all_ids = first_ids + remaining
        report.check(
            "unique_treated_targets", len(all_ids) == len(set(all_ids)) == size
        )
        report.check("sentence_length_one", first_checks["sentence_length_one"])
        report.check(
            "same_plate_line_timepoint", first_checks["same_plate_line_timepoint"]
        )
        report.check(
            "no_missing_control_skips", first_checks["no_missing_control_skips"]
        )
        report.check(
            "control_group_matches_exactly",
            first_checks["control_group_matches_exactly"],
        )
        report.check("raw_sparse_counts", first_checks["raw_sparse_counts"])
        report.check(
            "source_count_vector_parity", first_checks["source_count_vector_parity"]
        )
        report.check("exact_treated_smiles", first_checks["exact_treated_smiles"])
        report.check("null_control_smiles", first_checks["null_control_smiles"])
        report.check("served_source_provenance", True)
        report.check(
            "source_reservations",
            all(
                value <= config["expected_source_bytes"]
                for value in source_reservations.values()
            ),
        )
        report.check(
            "decoded_reservations",
            all(
                value <= config["expected_decoded_bytes"]
                for value in decoded_reservations.values()
            ),
        )
        complete_pairs = first_pairing + remaining_pairing
        replay_pairs = [
            (batch["treated_cell_id"][i], batch["control_cell_id"][i])
            for batch in StatePairs(
                index_path,
                seed=config.get("state_seed", 42),
                target_mode="treated_only",
            ).loader(batch_size=config.get("batch_size", 16), plate_homogeneous=True)
            for i in range(len(batch["treated_cell_id"]))
        ]
        report.check("seeded_pairing_replay", replay_pairs == complete_pairs)

        sharded_ids = []
        sharded_counts_match = True
        for rank in range(2):
            shard = StatePairs(
                index_path,
                seed=config.get("state_seed", 42),
                rank=rank,
                world_size=2,
                workers_per_rank=2,
                target_mode="treated_only",
            )
            for batch in shard.loader(
                batch_size=config.get("batch_size", 16),
                plate_homogeneous=True,
                num_workers=2,
            ):
                sharded_ids.extend(batch["treated_cell_id"])
                sharded_counts_match &= all(
                    value
                    for key, value in _validate_batch(
                        batch, config, len(gene_tokens)
                    ).items()
                    if key != "nonzero_entries"
                )
                with sqlite3.connect(
                    f"file:{index_path}?mode=ro", uri=True
                ) as index_conn:
                    index_conn.execute("PRAGMA query_only=ON")
                    sharded_counts_match &= all(
                        _validate_batch_against_index(batch, index_conn).values()
                    )
        report.check(
            "two_rank_two_worker_sharding",
            len(sharded_ids) == size
            and len(set(sharded_ids)) == size
            and set(sharded_ids) == set(all_ids),
        )
        report.check("sharded_count_parity", sharded_counts_match)
        elapsed = max(dataloader_finished - dataloader_started, 1e-9)
        report.metrics.update(
            {
                "release": config["dataset_version"],
                "snapshot_revision": config["snapshot_version"],
                "gene_axis_revision": config["gene_axis_revision"],
                "gene_axis_size": len(gene_tokens),
                "gene_axis_sha256": gene_axis_digest(gene_tokens),
                "treated_eligible_cells": available["treated"],
                "control_eligible_cells": available["control"],
                "treated_population_revision": population_revisions["treated"],
                "control_population_revision": population_revisions["control"],
                "source_reservations_bytes": source_reservations,
                "decoded_reservations_bytes": decoded_reservations,
                "aggregate_source_reservation_bytes": total_source_bytes,
                "aggregate_decoded_reservation_bytes": total_decoded_bytes,
                "treated_cells": len(all_ids),
                "paired_batches": (len(all_ids) + config.get("batch_size", 16) - 1)
                // config.get("batch_size", 16),
                "state_seed": config.get("state_seed", 42),
                "state_index_cells": index_metadata["cell_count"],
                "state_index_bytes": index_path.stat().st_size,
                "time_to_first_batch_seconds": first_batch_seconds,
                "time_to_first_batch_from_run_start_seconds": first_batch_seconds
                + (dataloader_started - run_started),
                "source_preparation_seconds": source_ready - run_started,
                "decoded_cells_per_second": len(all_ids) / elapsed,
                "decoded_nonzeros": decoded_nonzeros,
                "decoded_nonzeros_per_second": decoded_nonzeros / elapsed,
                "decoded_mib_per_second": (16 * decoded_nonzeros / (1024 * 1024))
                / elapsed,
                "peak_rss_bytes": _memory_bytes(),
            }
        )
    return report.as_dict()


def _validate_batch(batch: dict, config: dict, gene_count: int) -> dict:
    treated = batch["treated_counts"].coalesce()
    control = batch["control_counts"].coalesce()
    rows = len(batch["treated_cell_id"])
    expected = config["expected_treated_condition"]
    plate = batch["plate"]
    lines = batch["cell_line_id"]
    timepoints = batch["timepoint"]
    time_units = batch["timepoint_unit"]
    return {
        "sentence_length_one": (
            treated.shape == control.shape == (rows, 1, gene_count)
            and batch.get("cell_sentence_len") == 1
            and batch.get("counts_space") == "raw"
        ),
        "same_plate_line_timepoint": (
            all(value == expected["plate"] for value in plate)
            and len(set(lines)) == 1
            and all(value == expected["timepoint"] for value in timepoints)
            and all(value == expected["timepoint_unit"] for value in time_units)
            and all(value == expected["cell_line_id"] for value in lines)
            and all(value == expected["drug"] for value in batch["drug"])
            and all(value == expected["drug_id"] for value in batch["drug_id"])
            and all(value == expected["dose"] for value in batch["dose"])
            and all(value == expected["dose_unit"] for value in batch["dose_unit"])
            and all(value == expected["sample"] for value in batch["sample"])
        ),
        "raw_sparse_counts": (
            treated.is_sparse
            and control.is_sparse
            and all(
                float(value).is_integer() and value >= 0
                for value in treated.values().tolist()
            )
            and all(
                float(value).is_integer() and value >= 0
                for value in control.values().tolist()
            )
        ),
        "exact_treated_smiles": all(
            value == config["expected_smiles"] for value in batch["drug_smiles"]
        ),
        "null_control_smiles": all(value is None for value in batch["control_smiles"]),
        "nonzero_entries": int(treated.values().numel() + control.values().numel()),
        "no_missing_control_skips": batch.get("skipped_missing_controls") == 0,
    }


def _validate_batch_against_index(batch: dict, conn: sqlite3.Connection) -> dict:
    def row(cell_id):
        result = conn.execute(
            "SELECT payload FROM cells WHERE id=?", (cell_id,)
        ).fetchone()
        if result is None:
            raise ValueError("paired_cell_missing_from_index")
        return json.loads(result[0])

    def sparse_at(tensor, batch_index):
        coalesced = tensor.coalesce()
        indices = coalesced.indices()
        values = coalesced.values()
        return {
            int(indices[2, i]): float(values[i])
            for i in range(values.numel())
            if int(indices[0, i]) == batch_index
        }

    group_matches = True
    counts_match = True
    for i, (treated_id, control_id) in enumerate(
        zip(batch["treated_cell_id"], batch["control_cell_id"], strict=True)
    ):
        treated, control = row(treated_id), row(control_id)
        group = ("plate", "cell_line_id", "timepoint", "timepoint_unit")
        group_matches &= all(treated.get(key) == control.get(key) for key in group)
        group_matches &= (
            treated.get("is_control") is False and control.get("is_control") is True
        )
        treated_expected = dict(zip(treated["indices"], treated["values"], strict=True))
        control_expected = dict(zip(control["indices"], control["values"], strict=True))
        counts_match &= sparse_at(batch["treated_counts"], i) == treated_expected
        counts_match &= sparse_at(batch["control_counts"], i) == control_expected
    return {
        "control_group_matches_exactly": group_matches,
        "source_count_vector_parity": counts_match,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="connect using public OAuth and run the approved live acceptance case",
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not args.execute_live:
        result = {
            "case": "B",
            "mode": "offline_guard",
            "status": "red",
            "reason": "live execution requires --execute-live and coordinator-supplied approval bindings",
            "preflight": inspect(config, "b"),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    try:
        result = run(config)
    except Exception as exc:  # noqa: BLE001 - emit a sanitized red acceptance result
        # Do not print exceptions: transport/client errors can contain URLs or handles.
        report = AcceptanceReport("B")
        report.check("execution", False, safe_failure_kind(exc))
        result = report.as_dict()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())
