import asyncio
import sys
import time
from dataclasses import dataclass

import httpx

from app.models.enums import CheckStatus, MonitorType

_CHECK_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class CheckOutcome:
    status: CheckStatus
    response_time_ms: int | None
    error_message: str | None


async def perform_health_check(monitor_type: MonitorType, target: str) -> CheckOutcome:
    """Run a single health check for `target` based on `monitor_type`."""
    if monitor_type == MonitorType.HTTP:
        return await _check_http(target)
    if monitor_type == MonitorType.TCP:
        return await _check_tcp(target)
    return await _check_ping(target)


async def _check_http(target: str, timeout: float = _CHECK_TIMEOUT_SECONDS) -> CheckOutcome:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
            response = await http_client.get(target)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if response.status_code < 400:
            return CheckOutcome(CheckStatus.SUCCESS, elapsed_ms, None)
        return CheckOutcome(CheckStatus.FAILURE, elapsed_ms, f"HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckOutcome(CheckStatus.FAILURE, elapsed_ms, str(exc))


async def _check_tcp(target: str, timeout: float = _CHECK_TIMEOUT_SECONDS) -> CheckOutcome:
    host, _, port_str = target.rpartition(":")
    port = int(port_str)
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        writer.close()
        await writer.wait_closed()
        return CheckOutcome(CheckStatus.SUCCESS, elapsed_ms, None)
    except (TimeoutError, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckOutcome(CheckStatus.FAILURE, elapsed_ms, str(exc))


async def _check_ping(target: str, timeout: float = _CHECK_TIMEOUT_SECONDS) -> CheckOutcome:
    if sys.platform == "win32":
        args = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), target]
    else:
        args = ["ping", "-c", "1", "-W", str(int(timeout)), target]

    start = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=timeout + 2)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if process.returncode == 0:
            return CheckOutcome(CheckStatus.SUCCESS, elapsed_ms, None)
        return CheckOutcome(CheckStatus.FAILURE, elapsed_ms, f"ping exited with code {process.returncode}")
    except (TimeoutError, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckOutcome(CheckStatus.FAILURE, elapsed_ms, str(exc))
