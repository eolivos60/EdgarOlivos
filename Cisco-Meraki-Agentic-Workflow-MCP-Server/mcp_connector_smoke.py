"""MCP connector smoke checks for local and Cloudflare endpoints.

This script validates the same flow a remote client relies on:
1) initialize
2) tools/list
3) tools/call reload_credentials
4) tools/call get_organization_devices (using org discovered from get_organizations)

Usage:
    .venv/Scripts/python.exe mcp_connector_smoke.py
    .venv/Scripts/python.exe mcp_connector_smoke.py --public-url https://.../mcp
    .venv/Scripts/python.exe mcp_connector_smoke.py --skip-local
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv


DEFAULT_LOCAL_URL = "http://127.0.0.1:3000/mcp"
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_TIMEOUT = 15.0


def _status(ok: bool, label: str, detail: str = "") -> None:
    prefix = "PASS" if ok else "FAIL"
    line = f"[{prefix}] {label}"
    if detail:
        line += f" - {detail}"
    print(line)


def _extract_json_payload(text: str) -> Dict[str, Any]:
    # Supports JSON responses and SSE-style responses:
    # event: message\n data: { ...json... }
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty response")

    if stripped.startswith("{"):
        return json.loads(stripped)

    data_lines = []
    for line in stripped.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())

    if not data_lines:
        raise ValueError("no JSON payload found in response")

    return json.loads("\n".join(data_lines))


def _post_jsonrpc(
    client: httpx.Client,
    url: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str], int]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    response = client.post(url, headers=headers, json=payload)
    status_code = response.status_code

    response.raise_for_status()

    session_from_header = response.headers.get("mcp-session-id")
    data = _extract_json_payload(response.text)
    return data, session_from_header, status_code


def initialize(
    client: httpx.Client,
    url: str,
    auth_token: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str], int]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "connector-smoke", "version": "1.0"},
        },
    }
    return _post_jsonrpc(client, url, payload, auth_token=auth_token)


def tools_list(
    client: httpx.Client,
    url: str,
    session_id: Optional[str],
    auth_token: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str], int]:
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    return _post_jsonrpc(client, url, payload, session_id=session_id, auth_token=auth_token)


def tool_call(
    client: httpx.Client,
    url: str,
    session_id: Optional[str],
    name: str,
    arguments: Dict[str, Any],
    auth_token: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str], int]:
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    return _post_jsonrpc(client, url, payload, session_id=session_id, auth_token=auth_token)


def discover_public_url(repo_root: pathlib.Path) -> Optional[str]:
    url_file = repo_root / ".cloudflared.url"
    if not url_file.exists():
        return None

    base_url = url_file.read_text(encoding="utf-8").strip()
    if not base_url:
        return None

    if base_url.endswith(DEFAULT_MCP_PATH):
        return base_url

    return f"{base_url}{DEFAULT_MCP_PATH}"


def run_endpoint_smoke(url: str, label: str, timeout: float, auth_token: Optional[str]) -> bool:
    print(f"\n=== {label} ===")
    session_id = None

    with httpx.Client(timeout=timeout, verify=True, follow_redirects=True) as client:
        start = time.perf_counter()
        try:
            init_data, init_session, init_status = initialize(client, url, auth_token=auth_token)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            session_id = init_session
            ok = "result" in init_data
            _status(ok, "initialize", f"HTTP {init_status}, {elapsed_ms:.0f} ms")
            if not ok:
                return False
        except Exception as exc:  # noqa: BLE001
            _status(False, "initialize", str(exc))
            return False

        try:
            tools_data, list_session, list_status = tools_list(
                client,
                url,
                session_id,
                auth_token=auth_token,
            )
            session_id = list_session or session_id
            tools = tools_data.get("result", {}).get("tools", [])
            tool_names = [tool.get("name", "") for tool in tools if isinstance(tool, dict)]
            has_reload = "reload_credentials" in tool_names
            has_org_devices = "get_organization_devices" in tool_names
            _status(
                has_reload and has_org_devices,
                "tools/list",
                (
                    f"HTTP {list_status}, tools={len(tool_names)}, "
                    f"reload_credentials={'yes' if has_reload else 'no'}, "
                    f"get_organization_devices={'yes' if has_org_devices else 'no'}"
                ),
            )
            if not has_reload or not has_org_devices:
                return False
        except Exception as exc:  # noqa: BLE001
            _status(False, "tools/list", str(exc))
            return False

        try:
            call_data, _, call_status = tool_call(
                client,
                url,
                session_id=session_id,
                name="reload_credentials",
                arguments={},
                auth_token=auth_token,
            )
            call_result = call_data.get("result", {})
            content_items = call_result.get("content", []) if isinstance(call_result, dict) else []
            success = False
            if content_items and isinstance(content_items[0], dict):
                text = content_items[0].get("text", "")
                if isinstance(text, str) and "\"success\": true" in text.lower():
                    success = True

            if not success and "error" in call_data:
                _status(False, "tools/call reload_credentials", f"HTTP {call_status}, error returned")
                return False

            _status(success, "tools/call reload_credentials", f"HTTP {call_status}")
            if not success:
                return False
        except Exception as exc:  # noqa: BLE001
            _status(False, "tools/call reload_credentials", str(exc))
            return False

        try:
            orgs_data, orgs_session, orgs_status = tool_call(
                client,
                url,
                session_id=session_id,
                name="get_organizations",
                arguments={},
                auth_token=auth_token,
            )
            session_id = orgs_session or session_id
            org_result = orgs_data.get("result", {})
            org_content = org_result.get("content", []) if isinstance(org_result, dict) else []
            organizations = []
            if org_content and isinstance(org_content[0], dict):
                raw_text = org_content[0].get("text", "")
                if isinstance(raw_text, str) and raw_text.strip():
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, list):
                        organizations = parsed

            has_org = bool(organizations and isinstance(organizations[0], dict) and organizations[0].get("id"))
            _status(has_org, "tools/call get_organizations", f"HTTP {orgs_status}, orgs={len(organizations)}")
            if not has_org:
                return False

            org_id = str(organizations[0].get("id", "")).strip()
            devices_data, _, devices_status = tool_call(
                client,
                url,
                session_id=session_id,
                name="get_organization_devices",
                arguments={"organization_id": org_id, "per_page": 10},
                auth_token=auth_token,
            )
            devices_result = devices_data.get("result", {})
            devices_content = devices_result.get("content", []) if isinstance(devices_result, dict) else []
            devices_ok = False
            device_count = 0
            if devices_content and isinstance(devices_content[0], dict):
                raw_text = devices_content[0].get("text", "")
                if isinstance(raw_text, str) and raw_text.strip():
                    parsed = json.loads(raw_text)
                    devices_ok = isinstance(parsed, list)
                    if isinstance(parsed, list):
                        device_count = len(parsed)

            _status(devices_ok, "tools/call get_organization_devices", f"HTTP {devices_status}, devices={device_count}")
            return devices_ok
        except Exception as exc:  # noqa: BLE001
            _status(False, "tools/call get_organization_devices", str(exc))
            return False


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP connector smoke checks")
    parser.add_argument("--local-url", default=DEFAULT_LOCAL_URL)
    parser.add_argument("--public-url", default="")
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--skip-public", action="store_true")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--auth-token", default="")
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parent
    load_dotenv(dotenv_path=repo_root / ".env", override=False)
    public_url = args.public_url.strip() or discover_public_url(repo_root)
    auth_token = args.auth_token.strip() or (os.getenv("MCP_AUTH_TOKEN") or "").strip()

    overall_ok = True

    if not args.skip_local:
        overall_ok = run_endpoint_smoke(args.local_url, "Local MCP Smoke", args.timeout, auth_token) and overall_ok

    if not args.skip_public:
        if not public_url:
            _status(False, "public URL discovery", "no --public-url and no .cloudflared.url")
            overall_ok = False
        else:
            overall_ok = run_endpoint_smoke(public_url, "Public MCP Smoke", args.timeout, auth_token) and overall_ok
            print(f"\nPublic URL used: {public_url}")

    print("\nREADY" if overall_ok else "NOT READY")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
