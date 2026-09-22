"""
Shared pytest configuration for the Meraki MCP Server test suite.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--mcp-url",
        default="http://127.0.0.1:3000/mcp",
        help="Base URL of the MCP HTTP endpoint (default: http://127.0.0.1:3000/mcp)",
    )
