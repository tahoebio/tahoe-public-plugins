from __future__ import annotations

import asyncio
import json
import unittest

from contract import (
    decode_sparse_row,
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
        self.assertEqual(connection._http.calls[0][0], "/mcp")
        self.assertEqual(connection._http.calls[0][1]["method"], "initialize")
        self.assertEqual(
            connection._http.calls[1][1]["method"], "notifications/initialized"
        )
        self.assertEqual(
            connection._http.calls[-1][2]["MCP-Session-Id"], "session-test"
        )
        self.assertEqual(
            connection._http.calls[-1][1]["params"]["name"], "prepare_cell_sample"
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


if __name__ == "__main__":
    unittest.main()
