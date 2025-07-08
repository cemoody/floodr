#!/usr/bin/env python3
"""Simple benchmark comparing httpx and preq performance."""

import asyncio
import time

import httpx

from preq import request, warmup
from preq.models import Request


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


async def benchmark_preq(url: str, num_requests: int) -> float:
    """Benchmark preq with parallel requests."""
    start = time.time()

    # Create request objects
    requests = [Request(url=url) for _ in range(num_requests)]

    # Execute all requests in parallel
    responses = await request(requests)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    print(
        f"preq:             {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
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

        # Run preq benchmark
        preq_time = await benchmark_preq(url, count)

        # Calculate speedups
        speedup_basic = httpx_time / preq_time
        speedup_opt = httpx_opt_time / preq_time
        speedup_h2 = httpx_h2_time / preq_time

        print(f"Speedup vs basic httpx:     {speedup_basic:.2f}x")
        print(f"Speedup vs optimized httpx: {speedup_opt:.2f}x")
        print(f"Speedup vs httpx HTTP/2:    {speedup_h2:.2f}x")
        print()


if __name__ == "__main__":
    asyncio.run(main())
