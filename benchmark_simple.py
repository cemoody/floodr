#!/usr/bin/env python3
"""Simple benchmark comparing httpx and floodr performance."""

import asyncio
import time

import httpx

from floodr import request, warmup
from floodr.models import Request


async def benchmark_httpx(
    client: httpx.AsyncClient, url: str, num_requests: int
) -> float:
    """Benchmark httpx with async requests."""
    start = time.time()

    tasks = [client.get(url) for _ in range(num_requests)]
    responses = await asyncio.gather(*tasks)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    print(
        f"httpx:            {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def benchmark_httpx_optimized(
    client: httpx.AsyncClient,
    url: str,
    num_requests: int,
    max_concurrent: int = 100,
    is_http2: bool = False,
) -> float:
    """Benchmark httpx with optimized async requests using semaphore."""
    start = time.time()

    # Use a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
        async with semaphore:
            return await client.get(url)

    tasks = [fetch(client, url) for _ in range(num_requests)]
    responses = await asyncio.gather(*tasks)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    prefix = "httpx (HTTP/2)" if is_http2 else "httpx"
    print(
        f"{prefix}:{num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def benchmark_floodr(url: str, num_requests: int) -> float:
    """Benchmark floodr with parallel requests."""
    start = time.time()

    # Create request objects
    requests = [Request(url=url) for _ in range(num_requests)]

    # Execute all requests in parallel
    responses = await request(requests)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    print(
        f"floodr:           {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def benchmark_floodr_prewarmed(
    url: str, num_requests: int, warmup_connections: int = 50
) -> float:
    """Benchmark floodr with prewarmed connection pool."""
    # Extract domain from URL for warming
    from urllib.parse import urlparse

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Warm up the connection pool (not counted in timing)
    print(f"  (warming {warmup_connections} connections...)", end="", flush=True)
    warmup_start = time.time()
    await warmup(base_url, num_connections=warmup_connections)
    warmup_time = time.time() - warmup_start
    print(f" done in {warmup_time:.2f}s)")

    # Now run the actual benchmark
    start = time.time()

    # Create request objects
    requests = [Request(url=url) for _ in range(num_requests)]

    # Execute all requests in parallel (will use warmed connections)
    responses = await request(requests)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    print(
        f"floodr (warmed):  {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def main():
    """Run benchmarks for different request counts."""
    url = "https://jsonplaceholder.typicode.com/posts/1"
    request_counts = [64, 128, 256, 512]

    print(f"Benchmarking against: {url}\n")

    # Warmup
    print("Warming up...")
    await warmup(url)

    # Create different httpx clients with various optimizations

    # Basic client
    async with httpx.AsyncClient() as client:
        await client.get(url)

    # Optimized client with connection pooling and HTTP/2
    limits = httpx.Limits(
        max_keepalive_connections=100, max_connections=200, keepalive_expiry=30.0
    )

    # Client with HTTP/2 support (if server supports it)
    async with httpx.AsyncClient(
        limits=limits, http2=True, timeout=httpx.Timeout(30.0, connect=5.0)
    ) as optimized_client:
        await optimized_client.get(url)  # Warmup

    print()

    # Run benchmarks
    for count in request_counts:
        print(f"--- {count} requests ---")

        # Basic httpx
        async with httpx.AsyncClient() as client:
            httpx_time = await benchmark_httpx(client, url, count)

        await asyncio.sleep(0.5)

        # Optimized httpx with connection pooling
        async with httpx.AsyncClient(limits=limits) as client:
            httpx_opt_time = await benchmark_httpx_optimized(
                client, url, count, max_concurrent=min(count, 100)
            )

        await asyncio.sleep(0.5)

        # Optimized httpx with HTTP/2
        async with httpx.AsyncClient(limits=limits, http2=True) as client:
            httpx_h2_time = await benchmark_httpx_optimized(
                client, url, count, max_concurrent=min(count, 100), is_http2=True
            )

        await asyncio.sleep(0.5)

        # Run floodr benchmark
        floodr_time = await benchmark_floodr(url, count)

        await asyncio.sleep(0.5)

        # Run floodr with prewarming
        warmup_connections = min(
            count // 2, 100
        )  # Use half the requests or 100, whichever is smaller
        floodr_warmed_time = await benchmark_floodr_prewarmed(
            url, count, warmup_connections
        )

        # Calculate speedups
        speedup_basic = httpx_time / floodr_time
        speedup_opt = httpx_opt_time / floodr_time
        speedup_h2 = httpx_h2_time / floodr_time

        # Speedups for warmed floodr
        speedup_basic_warmed = httpx_time / floodr_warmed_time
        speedup_opt_warmed = httpx_opt_time / floodr_warmed_time
        speedup_h2_warmed = httpx_h2_time / floodr_warmed_time
        warmed_improvement = floodr_time / floodr_warmed_time

        print(f"\nSpeedup vs basic httpx:     {speedup_basic:.2f}x")
        print(f"Speedup vs optimized httpx: {speedup_opt:.2f}x")
        print(f"Speedup vs httpx HTTP/2:    {speedup_h2:.2f}x")
        print("\nWith prewarming:")
        print(f"Speedup vs basic httpx:     {speedup_basic_warmed:.2f}x")
        print(f"Speedup vs optimized httpx: {speedup_opt_warmed:.2f}x")
        print(f"Speedup vs httpx HTTP/2:    {speedup_h2_warmed:.2f}x")
        print(f"Improvement over cold start: {warmed_improvement:.2f}x")
        print()


if __name__ == "__main__":
    asyncio.run(main())
