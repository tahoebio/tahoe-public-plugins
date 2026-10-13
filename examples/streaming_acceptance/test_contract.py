from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from contract import (
    decode_sparse_row,
    gene_axis_digest,
    payload_types_valid,
    safe_failure_kind,
    source_hosts_allowed,
    validate_row,
)
from preflight import inspect
from protocol import PublicTaraTools


class _FakeResponse:
    def __init__(self, payload, *, status=200, session=None):
        self.status_code = status
        self.headers = {"content-type": "application/json"}
        if session:
            self.headers["mcp-session-id"] = session
        self.content = json.dumps(payload).encode()


class _FakeHTTP:
    def __init__(self):
        self.calls = []

    async def post(self, path, *, json, headers):
        self.calls.append((path, json, headers))
        message = json
        if message.get("method") == "initialize":
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"protocolVersion": "2025-06-18"},
                },
                session="session-test",
            )
        if message.get("method") == "notifications/initialized":
            return _FakeResponse({}, status=202)
        name = message["params"]["name"]
        value = (
            {"ok": True, "products": [{"product": "cells"}]}
            if name == "list_dataset_products"
            else {
                "ok": True,
                "access_handle": "opaque-test-handle",
                "condition": {"condition_id": "condition-1"},
            }
        )
        return _FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {"structuredContent": value, "content": []},
            }
        )


class _FakeConnection:
    def __init__(self):
        self._http = _FakeHTTP()

    @staticmethod
    def _run(coroutine):
        return asyncio.run(coroutine)


class ContractTests(unittest.TestCase):
    def test_gene_axis_digest_hashes_ordered_token_json(self):
        self.assertEqual(
            gene_axis_digest([3, 4, 9]),
            "ecd40fbc71d6fe48e5b426b5f7b9a16587d95e37edde011b315d34b2e08ef6f4",
        )
        self.assertNotEqual(gene_axis_digest([3, 4, 9]), gene_axis_digest([4, 3, 9]))

    def test_prepared_parquet_hash_is_not_misused_as_semantic_gene_axis_digest(self):
        repo_root = Path(__file__).resolve().parents[2]
        config = json.loads(
            (repo_root / "examples/streaming_acceptance/config.tahoe-100m-v1.json")
            .read_text(encoding="utf-8")
        )
        parquet_hash = config["source_pins"]["file_sha256"]["gene-axis.parquet"]
        self.assertEqual(config["gene_axis_revision"], parquet_hash)
        self.assertEqual(config["expected_gene_axis_tokens_sha256"], "")
        self.assertNotIn("expected_gene_axis_sha256", config)
        result = inspect(config, "a")
        check_map = {check["name"]: check["ok"] for check in result["checks"]}
        self.assertTrue(check_map["no_embedded_credentials"])
        self.assertFalse(check_map["expected_gene_axis_tokens_sha256"])

    def test_documented_runners_resolve_plugin_imports_without_pythonpath(self):
        repo_root = Path(__file__).resolve().parents[2]
        probe = r"""
import importlib.util
import runpy
import sys
from pathlib import Path

runner, module, expected = sys.argv[1:]
sys.path.insert(0, str(Path(runner).resolve().parent))
runpy.run_path(runner, run_name="acceptance_import_probe")
spec = importlib.util.find_spec(module)
assert spec is not None and spec.origin == expected, (module, spec)
"""
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        scripts = repo_root / "plugins/tara/skills/tara/scripts"
        for case, module in (("a", "tara_data"), ("b", "tara_state_loader")):
            runner = f"examples/streaming_acceptance/run_case_{case}.py"
            expected = scripts / f"{module}.py"
            with self.subTest(runner=runner):
                subprocess.run(
                    [sys.executable, "-c", probe, runner, module, str(expected)],
                    cwd=repo_root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_raw_count_schema_and_gene_axis_are_exact(self):
        schema = {
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
        }
        row = {
            "cell_id": 1,
            "cell_line_id": "CL1",
            "drug_id": "pubchem:1",
            "drug": "Drug",
            "sample": "s1",
            "plate": "p1",
            "dose": 1.0,
            "dose_unit": "uM",
            "timepoint": 24,
            "timepoint_unit": "h",
            "is_control": False,
            "canonical_smiles": "C",
            "genes": [3, 4],
            "expressions": [0, 7],
        }
        self.assertEqual(
            validate_row(
                row,
                gene_tokens={3, 4},
                encoding="delta_sparse_counts_v1",
                expected={
                    "cell_line_id": "CL1",
                    "drug_id": "pubchem:1",
                    "drug": "Drug",
                    "sample": "s1",
                    "plate": "p1",
                },
                expected_smiles="C",
                expected_schema=schema,
                control=False,
            ),
            (2, 7),
        )

    def test_wrong_row_value_types_fail_closed(self):
        schema = {
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
        }
        row = {
            "cell_id": 1,
            "cell_line_id": "CL1",
            "drug_id": "pubchem:1",
            "drug": "Drug",
            "sample": "s1",
            "plate": "p1",
            "dose": True,
            "dose_unit": "uM",
            "timepoint": 24,
            "timepoint_unit": "h",
            "is_control": False,
            "canonical_smiles": "C",
            "genes": [3],
            "expressions": [1],
        }
        with self.assertRaisesRegex(ValueError, "invalid_schema_type:dose"):
            validate_row(
                row,
                gene_tokens={3},
                encoding="delta_sparse_counts_v1",
                expected={},
                expected_smiles="C",
                expected_schema=schema,
                control=False,
            )

    def test_sparse_hf_marker_is_removed_as_a_paired_entry(self):
        self.assertEqual(
            decode_sparse_row(
                {"genes": [1, 3], "expressions": [-2, 5]}, "hf_sparse_tokens_v1", {3}
            ),
            ([3], [5]),
        )

    def test_invalid_counts_and_schema_fail_closed(self):
        for values in ([1.5], [-1], [float("nan")]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                decode_sparse_row(
                    {"genes": [3], "expressions": values}, "delta_sparse_counts_v1", {3}
                )
        with self.assertRaisesRegex(ValueError, "required_raw_count_field_missing"):
            validate_row(
                {"genes": [], "expressions": []},
                gene_tokens=set(),
                encoding="delta_sparse_counts_v1",
                expected={},
                expected_smiles="C",
                expected_schema={"genes", "expressions"},
            )

    def test_preflight_identifies_missing_real_bindings_offline(self):
        report = inspect({}, "a")
        self.assertEqual(report["status"], "red")
        self.assertFalse(report["live_ready"])
        names = {check["name"] for check in report["checks"] if not check["ok"]}
        self.assertTrue(
            {
                "base_url",
                "authorized_base_url",
                "auth_mode",
                "identity_mode",
                "population_product",
                "expected_condition",
            }
            <= names
        )

    def test_preflight_rejects_credential_fields(self):
        report = inspect({"api_token": "must-not-be-used"}, "a")
        self.assertIn(
            "no_embedded_credentials",
            {check["name"] for check in report["checks"] if not check["ok"]},
        )

    def test_failure_report_uses_fixed_sanitized_class(self):
        self.assertEqual(
            safe_failure_kind(RuntimeError("HTTP 429 rate_limited")),
            "quota_rate_limited_wait_without_retry",
        )
        self.assertEqual(
            safe_failure_kind(RuntimeError("signed https://private.invalid/secret")),
            "unclassified_failure",
        )

    def test_mcp_initialize_tool_discovery_and_prepare_handle_flow(self):
        connection = _FakeConnection()
        tools = PublicTaraTools(connection)
        tools.initialize()
        self.assertEqual([p["product"] for p in tools.products()], ["cells"])
        prepared = tools.prepare_sample(
            cell_line_id="CVCL_1234",
            drug_id="pubchem:1",
            dataset_version="release-1",
            snapshot_version="snapshot-1",
            condition={"condition_id": "condition-1", "plate": "p1"},
            sample_size=1000,
            seed=5,
        )
        self.assertEqual(prepared["access_handle"], "opaque-test-handle")
        product = tools.prepare_product("genes", "axis-rev")
        self.assertEqual(product["access_handle"], "opaque-test-handle")
        self.assertEqual(connection._http.calls[0][0], "/mcp")
        self.assertEqual(connection._http.calls[0][1]["method"], "initialize")
        self.assertEqual(
            connection._http.calls[1][1]["method"], "notifications/initialized"
        )
        self.assertEqual(
            connection._http.calls[-1][2]["MCP-Session-Id"], "session-test"
        )
        self.assertEqual(
            connection._http.calls[-2][1]["params"]["name"], "prepare_cell_sample"
        )
        self.assertEqual(
            connection._http.calls[-1][1]["params"]["name"], "prepare_dataset"
        )
        self.assertEqual(
            connection._http.calls[-1][1]["params"]["arguments"],
            {"product": "genes", "revision": "axis-rev", "options": {}},
        )

    def test_source_host_allowlist_rejects_hugging_face(self):
        class Source:
            @staticmethod
            def parquet_files():
                return ["https://huggingface.co/path/to/data.parquet"]

        self.assertFalse(source_hosts_allowed(Source(), ["huggingface.co"]))
        self.assertFalse(source_hosts_allowed(Source(), ["tara.tahoebio.io"]))

    def test_payload_schema_types_are_exact(self):
        row = {
            "cell_id": 1,
            "cell_line_id": "CL1",
            "drug_id": "pubchem:1",
            "drug": "Drug",
            "sample": "s1",
            "plate": "p1",
            "dose": 1.0,
            "dose_unit": "uM",
            "timepoint": 24,
            "timepoint_unit": "h",
            "is_control": False,
            "canonical_smiles": "C",
            "indices": [0, 2],
            "values": [1.0, 0.0],
        }
        self.assertTrue(payload_types_valid(row, control=False))
        self.assertFalse(payload_types_valid({**row, "dose": True}, control=False))
        self.assertFalse(
            payload_types_valid({**row, "canonical_smiles": None}, control=False)
        )
        pinned = {
            **row,
            "BARCODE_SUB_LIB_ID": "barcode-1",
            "pubchem_cid": 9562059,
            "moa_fine": None,
            "gene_count": 2,
            "tscp_count": 7,
            "timepoint_provenance": "study protocol",
        }
        self.assertTrue(payload_types_valid(pinned, control=False))
        self.assertFalse(
            payload_types_valid({**pinned, "pubchem_cid": "9562059"}, control=False)
        )
        self.assertFalse(
            payload_types_valid({**pinned, "timepoint_provenance": 24}, control=False)
        )


if __name__ == "__main__":
    unittest.main()
