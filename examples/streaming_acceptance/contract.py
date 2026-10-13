"""Small, testable acceptance checks shared by the executable examples."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from urllib.parse import urlsplit

RAW_ROW_FIELDS = {
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


def decode_sparse_row(
    row: dict, encoding: str, gene_tokens: set[int]
) -> tuple[list[int], list[int]]:
    genes = list(row.get("genes", ()))
    values = list(row.get("expressions", ()))
    if len(genes) != len(values):
        raise ValueError("gene_count_length_mismatch")
    if encoding == "hf_sparse_tokens_v1":
        if not genes or type(genes[0]) is not int or genes[0] != 1 or values[0] != -2:
            raise ValueError("hf_cls_marker_mismatch")
        genes, values = genes[1:], values[1:]
    elif encoding != "delta_sparse_counts_v1":
        raise ValueError("unknown_count_encoding")
    if any(type(gene) is not int or gene not in gene_tokens for gene in genes):
        raise ValueError("gene_axis_mismatch")
    if len(genes) != len(set(genes)):
        raise ValueError("duplicate_gene_in_sparse_row")
    decoded = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("raw_count_not_numeric")
        if (
            not math.isfinite(float(value))
            or value < 0
            or not float(value).is_integer()
        ):
            raise ValueError("raw_count_not_nonnegative_integer")
        decoded.append(int(value))
    return genes, decoded


def validate_row(
    row: dict,
    *,
    gene_tokens: set[int],
    encoding: str,
    expected: dict,
    expected_smiles: str,
    expected_schema: set[str],
    control: bool | None = None,
) -> int:
    actual_schema = set(row)
    if actual_schema != expected_schema:
        raise ValueError("row_schema_mismatch")
    if RAW_ROW_FIELDS - actual_schema:
        raise ValueError("required_raw_count_field_missing")
    if not optional_row_fields_valid(row):
        raise TypeError("invalid_optional_row_field_type")
    if type(row["cell_id"]) is not int:
        raise ValueError("invalid_cell_identity")
    for key in (
        "cell_line_id",
        "drug_id",
        "drug",
        "sample",
        "plate",
        "dose_unit",
        "timepoint_unit",
    ):
        if not isinstance(row[key], str) or not row[key]:
            raise ValueError(f"invalid_schema_type:{key}")
    for key in ("dose", "timepoint"):
        if (
            isinstance(row[key], bool)
            or not isinstance(row[key], (int, float))
            or not math.isfinite(float(row[key]))
        ):
            raise ValueError(f"invalid_schema_type:{key}")
    if type(row["is_control"]) is not bool:
        raise ValueError("invalid_schema_type:is_control")
    if not isinstance(row["genes"], (list, tuple)) or not isinstance(
        row["expressions"], (list, tuple)
    ):
        raise TypeError("invalid_schema_type:sparse_arrays")
    if any(type(gene) is not int for gene in row["genes"]):
        raise ValueError("invalid_schema_type:genes")
    for key in (
        "cell_line_id",
        "drug",
        "sample",
        "plate",
        "dose_unit",
        "timepoint_unit",
    ):
        if key in expected and key in row and row[key] != expected[key]:
            raise ValueError(f"condition_mismatch:{key}")
    for key in ("dose", "timepoint"):
        if (
            key in expected
            and key in row
            and (row[key] is None or float(row[key]) != float(expected[key]))
        ):
            raise ValueError(f"condition_mismatch:{key}")
    if control is not None and row["is_control"] is not control:
        raise ValueError("control_status_mismatch")
    smiles = row["canonical_smiles"]
    if control is True:
        if smiles is not None:
            raise ValueError("control_smiles_must_be_null")
    elif not isinstance(smiles, str) or not smiles or smiles != expected_smiles:
        raise ValueError("treated_smiles_mismatch")
    genes, counts = decode_sparse_row(row, encoding, gene_tokens)
    return len(genes), sum(counts)


def population_digest(ids) -> str:
    """Stable opaque digest used only to compare deterministic replay in memory."""
    canonical = json.dumps(sorted(map(str, ids)), separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def cells_digest(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda row: str(row["cell_id"]))
    canonical = json.dumps(
        ordered, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def gene_axis_digest(tokens: list[int]) -> str:
    """Hash ordered token IDs as a compact UTF-8 JSON integer array.

    This semantic digest is distinct from the SHA-256 of the source Parquet
    file, which verifies file integrity but says nothing about the ordered IDs
    returned by the prepared gene-axis product.
    """
    return hashlib.sha256(
        json.dumps(tokens, separators=(",", ":")).encode()
    ).hexdigest()


def payload_types_valid(row: dict, *, control: bool) -> bool:
    text_fields = (
        "cell_line_id",
        "drug_id",
        "drug",
        "sample",
        "plate",
        "dose_unit",
        "timepoint_unit",
    )
    if type(row.get("cell_id")) is not int or type(row.get("is_control")) is not bool:
        return False
    if not all(isinstance(row.get(key), str) and row[key] for key in text_fields):
        return False
    if not optional_row_fields_valid(row):
        return False
    for key in ("dose", "timepoint"):
        if isinstance(row.get(key), bool) or not isinstance(row.get(key), (int, float)):
            return False
        if not math.isfinite(float(row[key])):
            return False
    if control:
        if row.get("canonical_smiles") is not None:
            return False
    elif (
        not isinstance(row.get("canonical_smiles"), str) or not row["canonical_smiles"]
    ):
        return False
    if not isinstance(row.get("indices"), list) or any(
        type(gene) is not int for gene in row["indices"]
    ):
        return False
    if not isinstance(row.get("values"), list):
        return False
    if len(row["indices"]) != len(row["values"]):
        return False
    return all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and value >= 0
        and float(value).is_integer()
        for value in row["values"]
    )


def optional_row_fields_valid(row: dict) -> bool:
    if "BARCODE_SUB_LIB_ID" in row and not isinstance(row["BARCODE_SUB_LIB_ID"], str):
        return False
    if "timepoint_provenance" in row and (
        not isinstance(row["timepoint_provenance"], str)
        or not row["timepoint_provenance"]
    ):
        return False
    if (
        "moa_fine" in row
        and row["moa_fine"] is not None
        and not isinstance(row["moa_fine"], str)
    ):
        return False
    if "pubchem_cid" in row and (
        row["pubchem_cid"] is not None and type(row["pubchem_cid"]) is not int
    ):
        return False
    for key in ("gene_count", "tscp_count"):
        if key in row and (type(row[key]) is not int or row[key] < 0):
            return False
    return True


def safe_failure_kind(error: Exception) -> str:
    """Map client failures to a fixed label without echoing URLs or server text."""
    message = str(error)
    if any(
        code in message
        for code in ("sign_in_required", "not_invited", "permission_denied")
    ):
        return "permission_or_identity_denied"
    if "rate_limited" in message:
        return "quota_rate_limited_wait_without_retry"
    if any(code in message for code in ("service_paused", "service_unavailable")):
        return "service_unavailable"
    if any(
        code in message
        for code in ("release_mismatch", "source_changed", "source_condition_mismatch")
    ):
        return "source_or_release_mismatch"
    if any(
        code in message
        for code in (
            "sample_scan_budget_exceeded",
            "sample_decoded_work_exceeded",
            "sample_export_too_large",
            "sample_batch_too_large",
            "sample_cache_capacity",
        )
    ):
        return "source_or_decoded_quota_exceeded"
    if any(
        code in message
        for code in (
            "sampling_population_not_available",
            "sampling_population_incomplete",
            "dataset_not_allowed",
            "pinned_export_required",
        )
    ):
        return "source_binding_unavailable"
    if any(
        code in message
        for code in (
            "not_found",
            "bad_request",
            "condition_mismatch",
            "schema_mismatch",
        )
    ):
        return "binding_or_contract_mismatch"
    return "unclassified_failure"


def source_hosts_allowed(source, allowed_hosts: list[str]) -> bool:
    """Check signed file URL hosts without printing URLs or following them."""
    allowed = {host.lower() for host in allowed_hosts}
    urls = source.parquet_files()
    if not urls:
        return False
    for url in urls:
        parsed = urlsplit(url.replace("tara+", "", 1))
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or host not in allowed:
            return False
        if (
            host == "huggingface.co"
            or host == "hf.co"
            or host.endswith(".huggingface.co")
        ):
            return False
    return True


@dataclass
class AcceptanceReport:
    case: str
    checks: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def check(self, name: str, okay: bool, detail: str = "") -> None:
        self.checks.append(
            {"name": name, "status": "green" if okay else "red", "detail": detail}
        )

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(
            item["status"] == "green" for item in self.checks
        )

    def as_dict(self) -> dict:
        return {
            "case": self.case,
            "status": "green" if self.passed else "red",
            "checks": self.checks,
            "metrics": self.metrics,
            "classification": "end_to_end_acceptance"
            if self.passed
            else "not_accepted",
        }
