"""MCP configuration: one streamable-HTTP server for the public service.

The remote server is named ``tahoe-public``. ``tara`` names the plugin and a
different, internal service, so it must not appear as an MCP server name here.
"""

from jsonschema import Draft202012Validator

from scripts import common


def _config() -> dict:
    return common.load_json(common.REPO_ROOT / common.MCP_CONFIG_REL)


def test_mcp_config_exists_and_matches_official_schema():
    Draft202012Validator(common.load_schema("mcp")).validate(_config())


def test_mcp_config_declares_exactly_the_public_server():
    servers = _config()["mcpServers"]
    assert list(servers) == [common.MCP_SERVER_NAME]
    assert common.MCP_SERVER_NAME == "tahoe-public"
    assert "tara" not in servers


def test_mcp_server_is_streamable_http_at_the_public_endpoint():
    server = _config()["mcpServers"][common.MCP_SERVER_NAME]
    assert server["type"] == "streamable-http"
    assert server["url"] == common.MCP_ENDPOINT
    assert common.MCP_ENDPOINT == "https://tara.tahoebio.io/mcp"


def test_mcp_server_carries_no_credentials():
    server = _config()["mcpServers"][common.MCP_SERVER_NAME]
    assert "headers" not in server
    assert "env" not in server
