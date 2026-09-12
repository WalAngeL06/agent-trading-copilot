"""Official v2 SDK lifecycle for the pinned, credential-free public ATK process."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from time import monotonic_ns
from types import MappingProxyType
from collections.abc import Mapping

from .okx_mcp import (
    McpMarketError, McpProvenance, OkxMcpMarketAdapter, sanitized_failure, validate_timeout,
)


MCP_SDK_VERSION = "2.2.0"
ATK_VERSION = "1.4.6"
ATK_PACKAGE = "@okx_ai/okx-trade-mcp"


@dataclass(frozen=True)
class AtkMcpLaunch:
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str]
    cwd: Path


def _installed_mcp():
    binary = shutil.which("okx-trade-mcp")
    candidates = []
    if binary:
        path = Path(binary).resolve()
        candidates.extend((path, path.parent / "node_modules/@okx_ai/okx-trade-mcp/dist/index.js",
                           path.parent.parent / "lib/node_modules/@okx_ai/okx-trade-mcp/dist/index.js"))
    if os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "npm/node_modules/@okx_ai/okx-trade-mcp/dist/index.js")
    return next((str(path) for path in candidates if path.is_file() and path.suffix == ".js"), None)


def _paths(node_path, server_path):
    node, server = node_path or shutil.which("node"), server_path or _installed_mcp()
    if not node or not server or not Path(node).is_file() or not Path(server).is_file():
        raise McpMarketError("ATK_NOT_INSTALLED")
    node, server = Path(node).resolve(), Path(server).resolve()
    if server.name != "index.js" or server.parent.name != "dist":
        raise McpMarketError("ATK_PACKAGE_MISMATCH")
    try:
        metadata = json.loads((server.parent.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise McpMarketError("ATK_PACKAGE_MISMATCH") from None
    if not isinstance(metadata, dict) or metadata.get("name") != ATK_PACKAGE:
        raise McpMarketError("ATK_PACKAGE_MISMATCH")
    if metadata.get("version") != ATK_VERSION:
        raise McpMarketError("ATK_VERSION_MISMATCH")
    return str(node), str(server)


def _sdk_client(launch: AtkMcpLaunch, timeout, errlog):
    # Lazy dependency: importing the domain adapter or running normal tests does
    # not require the SDK. Use the actual v2 API, not historical server examples.
    try:
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters, stdio_client
        sdk_version = version("mcp")
    except (ImportError, PackageNotFoundError):
        raise McpMarketError("MCP_SDK_UNAVAILABLE") from None
    if sdk_version != MCP_SDK_VERSION:
        raise McpMarketError("MCP_SDK_VERSION_MISMATCH")
    parameters = StdioServerParameters(command=launch.command, args=list(launch.args),
                                       env=dict(launch.env), cwd=launch.cwd)
    # The SDK safely inherits only OS essentials. Our overrides isolate all
    # home/app-data locations; arbitrary parent OKX/API/proxy variables stay out.
    transport = stdio_client(parameters, errlog=errlog)
    return Client(transport, read_timeout_seconds=timeout, cache=None)


@asynccontextmanager
async def open_atk_mcp(*, node_path=None, server_path=None, timeout=30, workdir=None):
    validate_timeout(timeout)
    start, started_ns = datetime.now(timezone.utc), monotonic_ns()
    stage = "initialize"
    try:
        node, server = _paths(node_path, server_path)
        workspace = Path(workdir or Path.cwd()).resolve()
        runs = workspace / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="atk-mcp-public-", dir=runs) as temporary:
            public_home = Path(temporary).resolve()
            if not public_home.is_relative_to(runs.resolve()):
                raise McpMarketError("PUBLIC_HOME_INVALID")
            env = MappingProxyType({
                "HOME": str(public_home), "USERPROFILE": str(public_home),
                "HOMEDRIVE": public_home.drive, "HOMEPATH": str(public_home)[len(public_home.drive):],
                "APPDATA": str(public_home), "LOCALAPPDATA": str(public_home),
                "OKX_SITE": "tr", "OKX_API_BASE_URL": "https://tr.okx.com",
                "OKX_DEMO": "false", "OKX_UPDATE_CHECK": "false",
                "OKX_TIMEOUT_MS": str(max(1, int(timeout*1000))),
            })
            launch = AtkMcpLaunch(node, (server, "--site", "tr", "--modules", "market",
                                         "--read-only", "--no-log"), env, public_home)
            with open(os.devnull, "w", encoding="utf-8") as errlog:
                async with AsyncExitStack() as stack:
                    # Enter and exit the SDK in the same task: its AnyIO cancel
                    # scopes must not be moved into asyncio.wait_for tasks.
                    async with asyncio.timeout(timeout):
                        session = await stack.enter_async_context(_sdk_client(launch, timeout, errlog))
                    if getattr(session.server_info, "version", None) != ATK_VERSION:
                        raise McpMarketError("ATK_VERSION_MISMATCH")
                    protocol = session.protocol_version
                    if not isinstance(protocol, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", protocol):
                        raise McpMarketError("MCP_PROTOCOL_ERROR")
                    adapter = OkxMcpMarketAdapter(session, timeout=timeout)
                    adapter.runtime_info = {"mcp_sdk_version": MCP_SDK_VERSION,
                                            "atk_version": ATK_VERSION, "protocol_version": protocol}
                    stage = "tools/list"
                    await adapter.discover()
                    stage = "runtime"
                    yield adapter
                    stage = "shutdown"
        # SDK disconnect and temporary-home cleanup complete before returning.
    except Exception as exc:
        error = sanitized_failure(exc)
        if error.provenance is None:
            error.provenance = McpProvenance(stage, None, None, start, datetime.now(timezone.utc),
                                            max(0, (monotonic_ns()-started_ns)//1_000_000), False,
                                            error.code, rpc_error_code=error.rpc_error_code)
        raise error from None
