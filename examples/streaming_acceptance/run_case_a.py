#!/usr/bin/env python3
"""End-to-end Case A: exactly 1,000 filtered cells, deterministic resume."""

from __future__ import annotations

import argparse
import itertools
import json
import resource
import sys
import time
from pathlib import Path

from contract import (
    AcceptanceReport,
    cells_digest,
    gene_axis_digest,
    population_digest,
    safe_failure_kind,
    source_hosts_allowed,
    validate_row,
)
from preflight import inspect
from protocol import PublicTaraTools, product_index

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "plugins/tara/skills/tara/scripts"))


def _memory_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage if sys.platform == "darwin" else usage * 1024)


def run(config: dict) -> dict:
    from tara_data import connect

    report = AcceptanceReport("A")
    binding = inspect(config, "a")
    if binding["status"] != "green":
        raise ValueError("preflight_bindings_missing")
    expected_schema = set(config["expected_row_schema"])
    expected_condition = config["expected_condition"]
    sample_size, seed = config.get("sample_size", 1000), config.get("seed", 7)
    run_started = time.perf_counter()
    if sample_size != 1000:
        raise ValueError("case_a_requires_exactly_1000_cells")

    with connect(config["base_url"]) as tara:
        tools = PublicTaraTools(tara)
        tools.initialize()
        descriptors = product_index(tools.products())
        report.check(
            "mcp_products_advertised",
            {config["population_product"], config["gene_axis_product"]}
            <= set(descriptors),
        )
        population_product = descriptors.get(config["population_product"], {})
        gene_product = descriptors.get(config["gene_axis_product"], {})
        report.check(
            "population_product_revision",
            population_product.get("revision") == config["snapshot_version"]
            and population_product.get("dataset") == "Tahoe-100M"
            and population_product.get("layer") == "single_cell"
            and population_product.get("grain") == "cell",
        )
        report.check(
            "gene_axis_product_revision",
            gene_product.get("revision") == config["gene_axis_revision"]
            and gene_product.get("dataset") == "Tahoe-100M"
            and gene_product.get("grain") == "gene",
        )
        prepared = tools.prepare_sample(
            cell_line_id=config["cell_line_id"],
            drug_id=config["drug_id"],
            dataset_version=config["dataset_version"],
            snapshot_version=config["snapshot_version"],
            condition=expected_condition,
            sample_size=sample_size,
            seed=seed,
        )
        report.check("mcp_sample_ready", prepared.get("status") == "ready")
        source = tara.open(prepared["access_handle"])
        report.check("mcp_sample_handle", bool(prepared.get("access_handle")))
        metadata = source.metadata
        report.check(
            "approved_source_hosts",
            source_hosts_allowed(source, config["allowed_source_hosts"]),
        )
        report.check(
            "served_source_provenance",
            metadata.get("source_product") == config["population_product"]
            and metadata.get("revision")
            and metadata.get("dataset") == "Tahoe-100M"
            and metadata.get("layer") == "single_cell"
            and metadata.get("grain") == "cell"
            and metadata.get("format") == "parquet",
        )
        report.check("raw_counts", metadata.get("counts_space") == "raw")
        report.check(
            "dataset_version",
            metadata.get("dataset_version") == config["dataset_version"],
        )
        report.check(
            "snapshot_pinned",
            metadata.get("snapshot_version") == config["snapshot_version"],
        )
        report.check(
            "condition_pinned",
            metadata.get("condition", {}).get("condition_id")
            == expected_condition["condition_id"],
        )
        report.check("requested_seed", metadata.get("seed") == seed)
        report.check(
            "deterministic_sampling_algorithm",
            metadata.get("sampling_algorithm") == "sha256-priority-v1",
        )
        report.check("no_replacement", metadata.get("replacement") is False)
        report.check(
            "requested_cells", int(metadata.get("requested_cells", -1)) == 1000
        )
        report.check(
            "complete_population_size",
            int(metadata.get("available_cells", 0))
            >= max(1000, config["minimum_eligible_cells"]),
        )
        report.check(
            "exact_return_count", int(metadata.get("returned_cells", -1)) == 1000
        )
        report.check("sample_revision_present", bool(metadata.get("revision")))
        report.check(
            "gene_axis_revision",
            metadata.get("gene_axis_revision") == config["gene_axis_revision"],
        )
        axis_prepared = tools.prepare_product(
            config["gene_axis_product"], config["gene_axis_revision"]
        )
        axis_source = tara.open(axis_prepared["access_handle"])
        report.check(
            "approved_gene_axis_host",
            source_hosts_allowed(axis_source, config["allowed_source_hosts"]),
        )
        report.check(
            "gene_axis_source_binding",
            axis_source.metadata.get("product") == config["gene_axis_product"]
            and axis_source.metadata.get("revision") == config["gene_axis_revision"],
        )
        token_rows = list(axis_source.hf())
        axis_source.close()
        gene_tokens = [row["token_id"] for row in token_rows]
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
        if metadata.get("gene_count") is not None and int(
            metadata["gene_count"]
        ) != len(gene_tokens):
            raise ValueError("gene_axis_count_mismatch")

        decode_started = time.perf_counter()
        dataset = source.hf()
        iterator = iter(dataset)
        first = list(itertools.islice(iterator, config.get("batch_size", 16)))
        first_batch_seconds = time.perf_counter() - decode_started
        checkpoint = dataset.state_dict()
        resumed = source.hf()
        resumed.load_state_dict(checkpoint)
        tail = list(resumed)
        rows = first + tail
        decode_finished = time.perf_counter()
        source.close()

        ids = [row["cell_id"] for row in rows]
        unique = len(ids) == len(set(ids))
        report.check("unique_cells", unique)
        report.check("exact_rows", len(rows) == 1000)
        expected_encoding = metadata.get("expression_encoding")
        if expected_encoding != config["expected_count_encoding"]:
            raise ValueError("count_encoding_mismatch")
        nonzero, raw_sum = 0, 0
        for row in rows:
            n, total = validate_row(
                row,
                gene_tokens=set(gene_tokens),
                encoding=expected_encoding,
                expected={
                    **expected_condition,
                    "timepoint_provenance": config["expected_timepoint_provenance"],
                },
                expected_smiles=config["expected_smiles"],
                expected_schema=expected_schema,
                control=False,
            )
            nonzero += n
            raw_sum += total
        report.check(
            "exact_row_schema", all(set(row) == expected_schema for row in rows)
        )

        repeated_prepared = tools.prepare_sample(
            cell_line_id=config["cell_line_id"],
            drug_id=config["drug_id"],
            dataset_version=config["dataset_version"],
            snapshot_version=config["snapshot_version"],
            condition=expected_condition,
            sample_size=1000,
            seed=seed,
        )
        report.check("replay_sample_ready", repeated_prepared.get("status") == "ready")
        repeat = tara.open(repeated_prepared["access_handle"])
        replay_rows = list(repeat.hf())
        replay_ids = [row["cell_id"] for row in replay_rows]
        replay_revision = repeat.metadata.get("revision")
        repeat.close()
        replay_digest = population_digest(replay_ids)
        sample_hash = population_digest(ids)
        report.check("seed_replay", sample_hash == replay_digest)
        replay_count_hash = cells_digest(replay_rows)
        report.check("seed_count_replay", cells_digest(rows) == replay_count_hash)
        report.check(
            "same_sample_revision_replay",
            replay_revision == metadata.get("revision"),
        )
        report.check("native_resume", len(tail) == 1000 - len(first) and unique)
        elapsed = max(decode_finished - decode_started, 1e-9)
        report.metrics.update(
            {
                "release": config["dataset_version"],
                "snapshot_revision": metadata.get("snapshot_version"),
                "sample_revision": metadata.get("revision"),
                "eligible_cells": int(metadata.get("available_cells", 0)),
                "returned_cells": len(rows),
                "seed": seed,
                "sample_digest_sha256": sample_hash,
                "sample_count_digest_sha256": cells_digest(rows),
                "gene_axis_revision": config["gene_axis_revision"],
                "gene_axis_size": len(gene_tokens),
                "gene_axis_sha256": gene_axis_digest(gene_tokens),
                "nonzero_count_entries": nonzero,
                "logical_decoded_bytes": 16 * nonzero,
                "raw_count_sum": raw_sum,
                "time_to_first_batch_seconds": first_batch_seconds,
                "time_to_first_batch_from_run_start_seconds": first_batch_seconds
                + (decode_started - run_started),
                "source_and_axis_preparation_seconds": decode_started - run_started,
                "decoded_cells_per_second": len(rows) / elapsed,
                "decoded_nonzeros_per_second": nonzero / elapsed,
                "decoded_mib_per_second": (16 * nonzero / (1024 * 1024)) / elapsed,
                "peak_rss_bytes": _memory_bytes(),
            }
        )
    return report.as_dict()


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
            "case": "A",
            "mode": "offline_guard",
            "status": "red",
            "reason": "live execution requires --execute-live and coordinator-supplied approval bindings",
            "preflight": inspect(config, "a"),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    try:
        result = run(config)
    except Exception as exc:  # noqa: BLE001 - emit a sanitized red acceptance result
        # Do not print exceptions: transport/client errors can contain URLs or handles.
        result = AcceptanceReport("A")
        result.check("execution", False, safe_failure_kind(exc))
        result = result.as_dict()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())
