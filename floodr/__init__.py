"""
floodr - Fast parallel HTTP requests for Python, powered by Rust

A high-performance HTTP client library that executes multiple requests in parallel,
similar to requests/httpx but optimized for bulk operations.
"""

import asyncio
import json as json_module
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlencode

from .models import Request, Response

if TYPE_CHECKING:
    # Type stubs for Rust extension
    class ParallelClient:
        def __init__(
            self,
            max_connections: Optional[int],
            timeout: float,
            enable_compression: bool,
        ) -> None: ...
        def execute(self, requests: list[Any]) -> list[Any]: ...
        def execute_with_concurrency(
            self, requests: list[Any], max_concurrent: int
        ) -> list[Any]: ...
        def warmup(self, url: str, num_connections: Optional[int] = None) -> None: ...

    class _RustRequest:
        def __init__(
            self,
            url: str,
            method: str,
            headers: Optional[dict[str, str]] = None,
            json: Optional[str] = None,
            data: Optional[bytes] = None,
            timeout: Optional[float] = None,
        ) -> None: ...

    class _RustResponse:
        status_code: int
        headers: dict[str, str]
        content: bytes
        elapsed: float
        url: str
        error: Optional[str]

    async def _rust_execute(
        requests: list[_RustRequest],
        use_global_client: bool = True,
        max_concurrent: Optional[int] = None,
        **kwargs: Any,
    ) -> list[_RustResponse]: ...
    async def _rust_warmup(
        url: str,
        num_connections: Optional[int] = None,
        enable_compression: Optional[bool] = None,
    ) -> None: ...
    async def _rust_warmup_advanced(
        base_url: str,
        paths: Optional[list[str]] = None,
        num_connections: Optional[int] = None,
        enable_compression: Optional[bool] = None,
        method: Optional[str] = None,
    ) -> list[dict[str, Any]]: ...

else:
    # Import the Rust extension
    # Create async wrappers for the sync functions
    import asyncio

    from .floodr import ParallelClient
    from .floodr import Request as _RustRequest
    from .floodr import Response as _RustResponse
    from .floodr import execute_sync as _rust_execute_sync
    from .floodr import warmup_advanced_sync as _rust_warmup_advanced_sync
    from .floodr import warmup_sync as _rust_warmup_sync

    async def _rust_execute(
        requests, use_global_client=True, max_concurrent=None, **kwargs
    ):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _rust_execute_sync(
                requests,
                use_global_client=use_global_client,
                max_concurrent=max_concurrent,
                **kwargs,
            ),
        )

    async def _rust_warmup(url, num_connections=None, enable_compression=None):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _rust_warmup_sync, url, num_connections, enable_compression
        )

    async def _rust_warmup_advanced(
        base_url, paths=None, num_connections=None, enable_compression=None, method=None
    ):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            _rust_warmup_advanced_sync,
            base_url,
            paths,
            num_connections,
            enable_compression,
            method,
        )


__version__ = "0.1.0"
__all__ = [
    "Client",
    "Request",
    "Response",
    "request",
    "warmup",
    "warmup_advanced",
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
        self, requests: list[Request], max_concurrent: Optional[int] = None
    ) -> list[Response]:
        """
        Execute multiple requests in parallel.

        Args:
            requests: List of Request objects to execute
            max_concurrent: Maximum concurrent requests (None for automatic based on batch size)

        Returns:
            List of Response objects in the same order as requests
        """
        rust_requests: list[dict[str, Any]] = [
            req.to_rust_request() for req in requests
        ]

        # Convert to the old Request format expected by Rust
        old_format_requests: list[_RustRequest] = []
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

        # Run the sync methods in an executor
        loop = asyncio.get_event_loop()
        if (
            hasattr(self._client, "execute_with_concurrency")
            and max_concurrent is not None
        ):
            rust_responses = await loop.run_in_executor(
                None,
                self._client.execute_with_concurrency,
                old_format_requests,
                max_concurrent,
            )
        else:
            rust_responses = await loop.run_in_executor(
                None, self._client.execute, old_format_requests
            )

        return [_convert_response(resp) for resp in rust_responses]

    async def warmup(self, url: str, num_connections: int = 10):
        """
        Warm up the connection pool by establishing multiple connections.

        Args:
            url: URL to warm up connections to
            num_connections: Number of connections to establish (default: 10)
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._client.warmup, url, num_connections)


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
    requests: list[Request],
    use_global_client: bool = True,
    max_concurrent: Optional[int] = None,
    **client_kwargs: Any,
) -> list[Response]:
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
    rust_requests: list[_RustRequest] = []
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


async def warmup(url: str, num_connections: int = 10, enable_compression: bool = False):
    """
    Warm up the global connection pool by establishing multiple connections.

    Args:
        url: URL to warm up connections to
        num_connections: Number of connections to pre-establish (default: 10)
        enable_compression: Whether to enable compression for the warmed connections

    This is useful when you know you'll be making many concurrent requests to
    a specific domain soon. Pre-warming the connection pool can significantly
    reduce latency for the actual requests.
    """
    await _rust_warmup(url, num_connections, enable_compression)


async def warmup_advanced(
    base_url: str,
    paths: Optional[list[str]] = None,
    num_connections: int = 10,
    enable_compression: bool = False,
    method: str = "HEAD",
) -> list[dict[str, Any]]:
    """
    Advanced warmup with custom paths and detailed results.

    Args:
        base_url: Base URL of the domain to warm up
        paths: List of paths to use for warming (default: ["/"])
        num_connections: Number of connections to establish
        enable_compression: Whether to enable compression
        method: HTTP method to use for warmup (default: "HEAD")

    Returns:
        List of dicts with warmup results for each connection:
        - url: The full URL that was warmed
        - status: HTTP status code (0 if failed)
        - elapsed: Time taken in seconds
        - error: Error message if failed (optional)

    Example:
        results = await warmup_advanced(
            "https://api.example.com",
            paths=["/health", "/api/v1/status"],
            num_connections=50
        )
    """
    return await _rust_warmup_advanced(
        base_url, paths, num_connections, enable_compression, method
    )
