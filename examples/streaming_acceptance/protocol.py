"""Minimal authenticated MCP Streamable HTTP calls over Tara's OAuth client."""

from __future__ import annotations

import json


class PublicTaraTools:
    """Use the Tara connection's public OAuth session for real MCP tool calls."""

    def __init__(self, connection):
        self.connection = connection
        self.session_id = None
        self.protocol_version = "2025-06-18"
        self.sequence = 0

    async def _post(self, message: dict, *, reply: bool = True) -> dict | None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
            headers["MCP-Protocol-Version"] = self.protocol_version
        response = await self.connection._http.post(
            "/mcp", json=message, headers=headers
        )
        if response.status_code not in ({200} if reply else {200, 202, 204}):
            raise RuntimeError("mcp_http_refused")
        self.session_id = response.headers.get("mcp-session-id", self.session_id)
        if not reply:
            return None
        content_type = response.headers.get("content-type", "")
        raw = response.content.decode("utf-8", "replace")
        if "text/event-stream" in content_type:
            data = [
                line[5:].strip()
                for line in raw.splitlines()
                if line.startswith("data:")
            ]
            if not data:
                raise RuntimeError("mcp_empty_stream")
            return json.loads(data[-1])
        return json.loads(raw)

    def _request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        reply = self.connection._run(
            self._post(
                {
                    "jsonrpc": "2.0",
                    "id": self.sequence,
                    "method": method,
                    "params": params,
                }
            )
        )
        if not isinstance(reply, dict) or "error" in reply:
            raise RuntimeError("mcp_rpc_refused")
        return reply.get("result", {})

    def initialize(self) -> None:
        result = self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "tara-streaming-acceptance", "version": "1"},
            },
        )
        self.protocol_version = result.get("protocolVersion", self.protocol_version)
        self.connection._run(
            self._post(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}, reply=False
            )
        )

    def call(self, name: str, arguments: dict | None = None) -> dict:
        result = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        if result.get("isError"):
            raise RuntimeError("mcp_tool_refused")
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            value = structured
        else:
            value = None
            for item in result.get("content", []):
                if item.get("type") != "text":
                    continue
                try:
                    parsed = json.loads(item["text"])
                except (ValueError, KeyError):
                    continue
                if isinstance(parsed, dict):
                    value = parsed
                    break
        if not isinstance(value, dict):
            raise TypeError("mcp_tool_missing_structured_result")
        if value.get("ok") is False or value.get("status") in {
            "error",
            "not_found",
            "pending",
        }:
            raise RuntimeError("mcp_tool_application_refused")
        return value

    def products(self) -> list[dict]:
        response = self.call("list_dataset_products")
        products = response.get("products")
        if not isinstance(products, list):
            raise TypeError("mcp_product_list_missing")
        return products

    def prepare_sample(
        self,
        *,
        cell_line_id: str,
        drug_id: str,
        dataset_version: str,
        snapshot_version: str,
        condition: dict,
        sample_size: int,
        seed: int,
    ) -> dict:
        arguments = {
            "cell_line_id": cell_line_id,
            "drug_id": drug_id,
            "dataset_version": dataset_version,
            "snapshot_version": snapshot_version,
            "condition_id": condition["condition_id"],
            "sample_size": sample_size,
            "seed": seed,
        }
        for key in ("dose", "dose_unit", "timepoint", "timepoint_unit", "plate"):
            if key in condition:
                arguments[key] = condition[key]
        response = self.call("prepare_cell_sample", arguments)
        sample = response.get("data", response)
        if not isinstance(sample, dict) or not sample.get("access_handle"):
            raise RuntimeError("mcp_prepare_handle_missing")
        return sample


def product_index(products: list[dict]) -> dict[str, dict]:
    return {
        str(item.get("id", item.get("product"))): item
        for item in products
        if isinstance(item, dict) and item.get("id", item.get("product")) is not None
    }
