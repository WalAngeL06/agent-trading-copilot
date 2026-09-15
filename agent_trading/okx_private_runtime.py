"""Authenticated product-owned ATK child, separate from credential-free market runtime."""

import asyncio
from contextlib import AsyncExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import MappingProxyType
from collections.abc import Mapping

from .account_snapshots import PrivateSnapshotRead
from .okx_mcp import validate_timeout
from .okx_mcp_runtime import ATK_VERSION, _paths, _sdk_client
from .okx_private import OkxPrivateReadAdapter, PrivateReadError, failed_read
from .okx_private_config import PrivateConfig


_PRIVATE_LOG_SCOPE = ContextVar("okx_private_log_scope", default=False)
# Exact logger names inspected in pinned SDK 2.2.0's stdio/client dispatch path.
# Session historically uses the bare 'client' logger. HTTP/OAuth are unused.
_SDK_LOGGERS = ("client", "mcp.client.stdio", "mcp.client.client", "mcp.client.caching",
                "mcp.shared.dispatcher", "mcp.shared.direct_dispatcher",
                "mcp.shared.jsonrpc_dispatcher", "mcp.shared.tool_name_validation",
                "mcp.os.win32.utilities", "mcp.os.posix.utilities")


class _PrivateSdkFilter(logging.Filter):
    def filter(self, record):
        # Drop the whole record, including traceback, args and extra fields.
        # Task-local context also covers SDK transport tasks created by us.
        return not _PRIVATE_LOG_SCOPE.get()


@contextmanager
def _quiet_sdk_logs():
    guard = _PrivateSdkFilter()
    loggers = [logging.getLogger(name) for name in _SDK_LOGGERS]
    for logger in loggers:
        logger.addFilter(guard)
    token = _PRIVATE_LOG_SCOPE.set(True)
    try:
        yield
    finally:
        _PRIVATE_LOG_SCOPE.reset(token)
        for logger in loggers:
            logger.removeFilter(guard)


@dataclass(frozen=True)
class PrivateLaunch:
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str] = field(repr=False)
    cwd: Path


async def read_private_snapshots(config: PrivateConfig, *, node_path=None, server_path=None,
                                 timeout=30, workdir=None) -> PrivateSnapshotRead:
    """Terminal sanitized result after shutdown; missing auth never starts a process.

    Deliberately no server/CLI credential-store fallback, private audit payload,
    HTTP endpoint, strategy integration, OAuth refresh, or exchange write path.
    """
    try:
        try:
            validate_timeout(timeout)
        except ValueError:
            raise PrivateReadError("CONFIG_INVALID") from None
        if not isinstance(config, PrivateConfig):
            raise PrivateReadError("CONFIG_INVALID")
        if config.error_code:
            raise PrivateReadError(config.error_code)
        if not config.ready:
            return PrivateSnapshotRead("AUTH_MISSING", "AUTH_MISSING")
        node, server = _paths(node_path, server_path)
        workspace = Path(workdir or Path.cwd()).resolve()
        runs = workspace / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="atk-mcp-private-", dir=runs) as temporary:
            private_home = Path(temporary).resolve()
            env = MappingProxyType({
                "HOME": str(private_home), "USERPROFILE": str(private_home),
                "HOMEDRIVE": private_home.drive, "HOMEPATH": str(private_home)[len(private_home.drive):],
                "APPDATA": str(private_home), "LOCALAPPDATA": str(private_home),
                "OKX_SITE": "tr", "OKX_API_BASE_URL": "https://tr.okx.com",
                "OKX_DEMO": "false", "OKX_UPDATE_CHECK": "false",
                "OKX_TIMEOUT_MS": str(max(1, int(timeout*1000))),
                "OKX_API_KEY": config.api_key, "OKX_SECRET_KEY": config.secret_key,
                "OKX_PASSPHRASE": config.passphrase,
            })
            launch = PrivateLaunch(node, (server, "--site", "tr", "--modules", "account,earn",
                                          "--read-only", "--no-log"), env, private_home)
            # No raw SDK/provider stderr is retained. The toolkit's persistent
            # logs and update checks are disabled; secrets are never CLI args.
            with open(os.devnull, "w", encoding="utf-8") as errlog, _quiet_sdk_logs():
                async with AsyncExitStack() as stack:
                    async with asyncio.timeout(timeout):
                        client = await stack.enter_async_context(_sdk_client(launch, timeout, errlog))
                    if getattr(client.server_info, "version", None) != ATK_VERSION:
                        raise PrivateReadError("ATK_VERSION_MISMATCH")
                    protocol = client.protocol_version
                    if not isinstance(protocol, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", protocol):
                        raise PrivateReadError("MCP_PROTOCOL_ERROR")
                    adapter = OkxPrivateReadAdapter(client, timeout=timeout)
                    await adapter.discover()
                    result = await adapter.snapshot()
        return result
    except Exception as exc:
        return failed_read(exc)
