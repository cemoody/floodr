"""
preq - Fast parallel HTTP requests for Python, powered by Rust

A high-performance HTTP client library that executes multiple requests in parallel,
similar to requests/httpx but optimized for bulk operations.
"""

import asyncio
import json as json_module
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

from .models import Request, Response
from .preq import ParallelClient

# Import the Rust extension
from .preq import Request as _RustRequest
from .preq import Response as _RustResponse
from .preq import execute as _rust_execute
from .preq import warmup as _rust_warmup

__version__ = "0.1.0"
__all__ = [
    "Client",
    "Request",
    "Response",
    "request",
    "warmup",
]


class Client:
    """Parallel HTTP client with connection pooling"""

    def __init__(
        self,
        max_connections: Optional[int] = None,
        timeout: float = 60.0,
        enable_compression: bool = False,
    ):
        """
        Initialize a parallel HTTP client.

        Args:
            max_connections: Maximum number of concurrent connections (None for dynamic sizing)
            timeout: Default timeout in seconds
            enable_compression: Enable gzip/brotli compression
        """
        self._client = ParallelClient(max_connections, timeout, enable_compression)
        self.timeout = timeout

    async def request(
        self, requests: List[Request], max_concurrent: Optional[int] = None
    ) -> List[Response]:
        """
        Execute multiple requests in parallel.

        Args:
            requests: List of Request objects to execute
            max_concurrent: Maximum concurrent requests (None for automatic based on batch size)

        Returns:
            List of Response objects in the same order as requests
        """
        rust_requests = [req.to_rust_request() for req in requests]

        # Convert to the old Request format expected by Rust
        old_format_requests = []
        for rust_req in rust_requests:
            # Handle params by adding to URL
            url = rust_req["url"]
            if "params" in rust_req and rust_req["params"]:
                params_str = urlencode(rust_req["params"], doseq=True)
                url = f"{url}?{params_str}"

            old_req = _RustRequest(
                url=url,
                method=rust_req["method"],
                headers=rust_req.get("headers"),
                json=(
                    json_module.dumps(rust_req["json"])
                    if rust_req.get("json") is not None
                    else None
                ),
                data=(
                    rust_req.get("body") if "body" in rust_req else rust_req.get("data")
                ),
                timeout=rust_req.get("timeout"),
            )
            old_format_requests.append(old_req)

        if (
            hasattr(self._client, "execute_with_concurrency")
            and max_concurrent is not None
        ):
            rust_responses = await self._client.execute_with_concurrency(
                old_format_requests, max_concurrent
            )
        else:
            rust_responses = await self._client.execute(old_format_requests)

        return [_convert_response(resp) for resp in rust_responses]

    async def warmup(self, url: str):
        """Warm up the connection pool by making a dummy request"""
        await self._client.warmup(url)


def _convert_response(rust_response: _RustResponse) -> Response:
    """Convert Rust response to Pydantic model"""
    return Response(
        status_code=rust_response.status_code,
        headers=rust_response.headers,
        content=bytes(rust_response.content),
        elapsed=rust_response.elapsed,
        url=rust_response.url,
        error=getattr(rust_response, "error", None),
    )


# Module-level convenience function
async def request(
    requests: List[Request],
    use_global_client: bool = True,
    max_concurrent: Optional[int] = None,
    **client_kwargs,
) -> List[Response]:
    """
    Execute multiple requests in parallel.

    Args:
        requests: List of Request objects
        use_global_client: Use a global client for better performance (default: True)
        max_concurrent: Maximum concurrent requests (None for automatic based on batch size)
        **client_kwargs: Arguments passed to Client constructor

    Returns:
        List of Response objects
    """
    rust_requests = []
    for req in requests:
        rust_req = req.to_rust_request()

        # Handle params by adding to URL
        url = rust_req["url"]
        if "params" in rust_req and rust_req["params"]:
            params_str = urlencode(rust_req["params"], doseq=True)
            url = f"{url}?{params_str}"

        old_req = _RustRequest(
            url=url,
            method=rust_req["method"],
            headers=rust_req.get("headers"),
            json=(
                json_module.dumps(rust_req["json"])
                if rust_req.get("json") is not None
                else None
            ),
            data=rust_req.get("body") if "body" in rust_req else rust_req.get("data"),
            timeout=rust_req.get("timeout"),
        )
        rust_requests.append(old_req)

    rust_responses = await _rust_execute(
        rust_requests,
        use_global_client=use_global_client,
        max_concurrent=max_concurrent,
        **client_kwargs,
    )
    return [_convert_response(resp) for resp in rust_responses]


async def warmup(url: str):
    """Warm up the global connection pool"""
    await _rust_warmup(url)
