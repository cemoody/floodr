#!/usr/bin/env python3
"""Simple benchmark comparing httpx and floodr performance."""

import asyncio
import os
import sys
import time

import httpx

# Add parent directory to path to import floodr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from floodr import request, warmup
from floodr.models import Request


async def benchmark_httpx(url: str, num_requests: int) -> float:
    """Benchmark httpx with async requests."""
    start = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for _ in range(num_requests)]
        responses = await asyncio.gather(*tasks)

    # Verify all successful
    success_count = sum(1 for r in responses if r.status_code == 200)

    elapsed = time.time() - start
    print(
        f"httpx: {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def benchmark_floodr(url: str, num_requests: int) -> float:
    """Benchmark floodr with parallel requests."""
    # Warmup the client
    await warmup(url)

    start = time.time()

    # Create requests
    requests = [Request(url=url) for _ in range(num_requests)]

    # Execute all requests in parallel
    responses = await request(requests)

    # Verify all successful
    success_count = sum(1 for r in responses if r.ok)

    elapsed = time.time() - start
    print(
        f"floodr: {num_requests} requests in {elapsed:.3f}s ({success_count} successful)"
    )
    return elapsed


async def main():
    """Run benchmarks."""
    url = "https://jsonplaceholder.typicode.com/posts/1"
    test_counts = [256, 512, 1024]

    print(f"Benchmarking against: {url}")
    print("-" * 60)

    for count in test_counts:
        print(f"\n{count} requests:")

        # Run httpx benchmark
        httpx_time = await benchmark_httpx(url, count)

        # Run floodr benchmark
        floodr_time = await benchmark_floodr(url, count)

        # Calculate speedup
        speedup = httpx_time / floodr_time
        print(f"Speedup: {speedup:.2f}x")

    print("\nBenchmark complete!")


if __name__ == "__main__":
    asyncio.run(main())
