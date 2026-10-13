#!/usr/bin/env python3
"""Offline binding check; never reads credentials or contacts the service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REQUIRED = {
    "base_url": "authorized HTTPS service origin",
    "authorized_base_url": "coordinator-supplied endpoint binding; must equal base_url",
    "allowed_source_hosts": "exact coordinator-approved data-source host allowlist",
    "auth_mode": "must be the bundled public Tara OAuth flow",
    "identity_mode": "must be public-user-equivalent access",
    "quota_policy": "endpoint quota/rate-limit policy binding",
    "live_test_approval_ref": "explicit live-test approval reference before any live run",
    "dataset_version": "served dataset version",
    "snapshot_version": "immutable served snapshot version",
    "population_product": "served raw-count population product id used for Case A",
    "gene_axis_product": "served gene-axis product id",
    "gene_axis_revision": "immutable gene-axis revision",
    "expected_gene_count": "exact number of genes in the pinned axis",
    "expected_gene_axis_sha256": "SHA-256 of the ordered pinned gene-token axis",
    "expected_source_bytes": "authorized worst-case source reservation for this case",
    "expected_decoded_bytes": "authorized worst-case decoded-work reservation for this case",
    "cell_line_id": "exact cell-line id",
    "drug_id": "resolved drug id",
    "expected_drug": "exact served drug label",
    "expected_smiles": "canonical SMILES pinned from authorized drug metadata",
    "expected_count_encoding": "declared raw sparse-count encoding",
    "expected_row_schema": "exact schema columns from the served product manifest",
    "expected_condition": "exact Case A cell-line/drug/sample/dose/plate/timepoint filters",
    "condition_id": "exact pinned condition id for Case A",
    "treated_product": "served raw-count treated product id for Case B",
    "control_product": "served raw-count control product id for Case B",
    "treated_condition_id": "exact treated condition id for Case B",
    "control_condition_id": "exact matched control condition id for Case B",
    "control_drug_id": "resolved control drug id for Case B",
    "expected_treated_condition": "exact Case B treated source filter metadata",
    "expected_control_condition": "exact Case B control source filter metadata",
    "expected_plate": "plate required for control matching",
    "expected_timepoint_unit": "timepoint unit required for control matching",
}


def inspect(config: dict, case: str) -> dict:
    checks = []
    forbidden = {
        key
        for key in config
        if any(
            term in key.lower()
            for term in ("token", "password", "authorization", "credential", "secret")
        )
    }
    checks.append(
        {
            "name": "no_embedded_credentials",
            "ok": not forbidden,
            "requirement": "no token, password, authorization, credential, or secret fields in config",
        }
    )
    for key, description in REQUIRED.items():
        if case == "a" and key in {
            "treated_product",
            "control_product",
            "treated_condition_id",
            "control_condition_id",
            "expected_plate",
            "expected_timepoint_unit",
            "control_drug_id",
            "expected_treated_condition",
            "expected_control_condition",
        }:
            continue
        if case == "b" and key in {
            "expected_condition",
            "condition_id",
            "population_product",
        }:
            continue
        value = config.get(key)
        if key.startswith("expected_") and key.endswith("_condition"):
            okay = isinstance(value, dict) and bool(value)
        elif key == "expected_row_schema":
            okay = (
                isinstance(value, list)
                and bool(value)
                and all(isinstance(v, str) for v in value)
            )
        elif key == "expected_gene_axis_sha256":
            okay = (
                isinstance(value, str)
                and len(value) == 64
                and all(c in "0123456789abcdef" for c in value)
            )
        elif key == "allowed_source_hosts":
            okay = (
                isinstance(value, list)
                and bool(value)
                and all(isinstance(v, str) and v.strip() for v in value)
            )
        elif key in {
            "expected_gene_count",
            "expected_source_bytes",
            "expected_decoded_bytes",
        }:
            okay = type(value) is int and value > 0
        else:
            okay = isinstance(value, str) and bool(value.strip())
        checks.append({"name": key, "ok": okay, "requirement": description})

    origin = config.get("base_url")
    if origin:
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname is not None
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        checks.append(
            {
                "name": "base_url_shape",
                "ok": valid,
                "requirement": "HTTPS origin only; no credentials, path, query, or fragment",
            }
        )

    for key in (
        "sample_size",
        "minimum_eligible_cells",
        "batch_size",
        "max_decoded_bytes",
        "max_source_bytes",
    ):
        value = config.get(key)
        okay = type(value) is int and value > 0
        if key == "sample_size":
            okay = okay and value == 1000
        if key == "minimum_eligible_cells":
            okay = okay and value > config.get("sample_size", 1000)
        checks.append(
            {
                "name": key,
                "ok": okay,
                "requirement": "positive integer"
                + (" exactly 1000" if key == "sample_size" else ""),
            }
        )
    checks.append(
        {
            "name": "aggregate_source_budget",
            "ok": type(config.get("expected_source_bytes")) is int
            and type(config.get("max_source_bytes")) is int
            and 0 < config["expected_source_bytes"] <= config["max_source_bytes"],
            "requirement": "complete source reservation, including replay and gene axis, fits the approved byte cap",
        }
    )
    checks.append(
        {
            "name": "aggregate_decoded_budget",
            "ok": type(config.get("expected_decoded_bytes")) is int
            and type(config.get("max_decoded_bytes")) is int
            and 0 < config["expected_decoded_bytes"] <= config["max_decoded_bytes"],
            "requirement": "complete decoded-work reservation fits the approved byte cap",
        }
    )

    checks.append(
        {
            "name": "endpoint_binding",
            "ok": bool(config.get("base_url"))
            and config.get("base_url") == config.get("authorized_base_url"),
            "requirement": "base_url must exactly match the coordinator-supplied authorized_base_url",
        }
    )
    allowed_hosts = config.get("allowed_source_hosts", [])
    no_hf_fallback = isinstance(allowed_hosts, list) and not any(
        host.lower() in {"huggingface.co", "hf.co"}
        or host.lower().endswith(".huggingface.co")
        for host in allowed_hosts
        if isinstance(host, str)
    )
    checks.append(
        {
            "name": "no_hosted_hf_fallback",
            "ok": no_hf_fallback,
            "requirement": "data hosts are explicitly allowlisted and do not include Hugging Face",
        }
    )
    expected = (
        config.get("expected_condition")
        if case == "a"
        else config.get("expected_treated_condition")
    )
    if isinstance(expected, dict):
        checks.append(
            {
                "name": "condition_identity_binding",
                "ok": expected.get("cell_line_id") == config.get("cell_line_id")
                and expected.get("drug") == config.get("expected_drug")
                and expected.get("drug_id") == config.get("drug_id"),
                "requirement": "condition metadata agrees exactly with the requested cell-line and drug",
            }
        )
    if case == "b":
        treated = config.get("expected_treated_condition", {})
        control = config.get("expected_control_condition", {})
        checks.append(
            {
                "name": "plate_control_binding",
                "ok": bool(treated)
                and bool(control)
                and all(
                    treated.get(key) == control.get(key)
                    for key in ("cell_line_id", "plate", "timepoint", "timepoint_unit")
                )
                and treated.get("plate") == config.get("expected_plate")
                and treated.get("timepoint_unit")
                == config.get("expected_timepoint_unit")
                and treated.get("drug_id") == config.get("drug_id")
                and control.get("drug_id") == config.get("control_drug_id"),
                "requirement": "treated/control conditions share exact plate, line and timepoint; each uses its resolved drug id",
            }
        )
    checks.append(
        {
            "name": "authorized_source_kind",
            "ok": config.get("authorized_source_kind") == "tahoe_backed_served",
            "requirement": "source must be the coordinator-authorized Tahoe-backed served source",
        }
    )
    checks.append(
        {
            "name": "public_oauth",
            "ok": config.get("auth_mode") == "public_plugin_oauth",
            "requirement": "runtime uses bundled public Tara OAuth; no endpoint token/password accepted",
        }
    )
    checks.append(
        {
            "name": "public_user_equivalent_identity",
            "ok": config.get("identity_mode") == "public_user_equivalent",
            "requirement": "identity and effective access match a public user",
        }
    )
    checks.append(
        {
            "name": "no_live_request",
            "ok": True,
            "requirement": "offline preflight made no network request and read no credential values",
        }
    )
    missing = [check["name"] for check in checks if not check["ok"]]
    return {
        "case": case.upper(),
        "status": "green" if not missing else "red",
        "checks": checks,
        "missing": missing,
        "live_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("a", "b", "all"), default="all")
    parser.add_argument(
        "--config", type=Path, help="authorized, credential-free JSON bindings"
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config else {}
    cases = ("a", "b") if args.case == "all" else (args.case,)
    reports = [inspect(config, case) for case in cases]
    result = {
        "mode": "offline_preflight",
        "status": "green"
        if all(report["status"] == "green" for report in reports)
        else "red",
        "cases": reports,
        "binding_ready": all(report["status"] == "green" for report in reports),
        "live_ready": False,
        "note": "Green preflight only means bindings are complete; it is not an endpoint or data acceptance pass.",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "green" else 2


if __name__ == "__main__":
    raise SystemExit(main())
