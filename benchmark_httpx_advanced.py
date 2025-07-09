#!/usr/bin/env python3
"""Advanced httpx optimizations benchmark."""

import asyncio
import time

import httpx
import uvloop  # Install with: pip install uvloop

from floodr import request, warmup
from floodr.models import Request


async def benchmark_httpx_basic(
    client: httpx.AsyncClient, url: str, num_requests: int
) -> float:
    """Basic httpx implementation."""
    start = time.time()
    tasks = [client.get(url) for _ in range(num_requests)]
    responses = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(f"httpx (basic): {num_requests} requests in {elapsed:.3f}s ({success} OK)")
    return elapsed


async def benchmark_httpx_semaphore(
    client: httpx.AsyncClient, url: str, num_requests: int, max_concurrent: int = 100
) -> float:
    """Httpx with semaphore for concurrency control."""
    start = time.time()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch():
        async with semaphore:
            return await client.get(url)

    tasks = [fetch() for _ in range(num_requests)]
    responses = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(
        f"httpx (semaphore): {num_requests} requests in {elapsed:.3f}s ({success} OK)"
    )
    return elapsed


async def benchmark_httpx_batched(
    client: httpx.AsyncClient, url: str, num_requests: int, batch_size: int = 50
) -> float:
    """Httpx with batched requests."""
    start = time.time()
    responses = []

    for i in range(0, num_requests, batch_size):
        batch = [client.get(url) for _ in range(min(batch_size, num_requests - i))]
        batch_responses = await asyncio.gather(*batch)
        responses.extend(batch_responses)

    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(f"httpx (batched): {num_requests} requests in {elapsed:.3f}s ({success} OK)")
    return elapsed


async def benchmark_httpx_queue(
    client: httpx.AsyncClient, url: str, num_requests: int, num_workers: int = 50
) -> float:
    """Httpx with worker pool pattern using queue."""
    start = time.time()
    queue = asyncio.Queue()
    responses = []

    # Fill queue with request indices
    for i in range(num_requests):
        await queue.put(i)

    async def worker():
        while True:
            try:
                await queue.get()
                response = await client.get(url)
                responses.append(response)
                queue.task_done()
            except asyncio.CancelledError:
                break

    # Start workers
    workers = [asyncio.create_task(worker()) for _ in range(num_workers)]

    # Wait for all requests to complete
    await queue.join()

    # Cancel workers
    for w in workers:
        w.cancel()

    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(f"httpx (queue): {num_requests} requests in {elapsed:.3f}s ({success} OK)")
    return elapsed


async def benchmark_floodr(url: str, num_requests: int) -> float:
    """Benchmark floodr."""
    start = time.time()
    requests = [Request(url=url) for _ in range(num_requests)]
    responses = await request(requests)
    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(f"floodr: {num_requests} requests in {elapsed:.3f}s ({success} OK)")
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
    requests = [Request(url=url) for _ in range(num_requests)]
    responses = await request(requests)
    elapsed = time.time() - start
    success = sum(1 for r in responses if r.status_code == 200)
    print(f"floodr (warmed): {num_requests} requests in {elapsed:.3f}s ({success} OK)")
    return elapsed


def create_optimized_client(http2: bool = False) -> httpx.AsyncClient:
    """Create an optimized httpx client."""
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_keepalive_connections=100, max_connections=200, keepalive_expiry=30.0
        ),
        http2=http2,
        timeout=httpx.Timeout(30.0, connect=5.0),
        # Disable some features that might add overhead
        follow_redirects=False,
        headers={"Accept-Encoding": "gzip, deflate, br"},
    )


async def main():
    """Run comprehensive benchmarks."""
    url = "https://jsonplaceholder.typicode.com/posts/1"
    request_counts = [100, 500, 1000]

    print(f"Benchmarking against: {url}")
    print(f"Event loop: {type(asyncio.get_event_loop()).__name__}\n")

    # Warmup
    print("Warming up...")
    await warmup(url)
    async with create_optimized_client() as client:
        await client.get(url)
    print()

    results = {}

    for count in request_counts:
        print(f"\n{'='*50}")
        print(f"Testing with {count} requests")
        print("=" * 50)

        results[count] = {}

        # Test basic httpx
        async with httpx.AsyncClient() as client:
            results[count]["basic"] = await benchmark_httpx_basic(client, url, count)
        await asyncio.sleep(0.5)

        # Test with optimized client
        async with create_optimized_client() as client:
            results[count]["optimized"] = await benchmark_httpx_semaphore(
                client, url, count, max_concurrent=100
            )
        await asyncio.sleep(0.5)

        # Test with HTTP/2
        async with create_optimized_client(http2=True) as client:
            print("httpx (HTTP/2): ", end="")
            results[count]["http2"] = await benchmark_httpx_semaphore(
                client, url, count, max_concurrent=100
            )
        await asyncio.sleep(0.5)

        # Test batched approach
        async with create_optimized_client() as client:
            results[count]["batched"] = await benchmark_httpx_batched(
                client, url, count, batch_size=50
            )
        await asyncio.sleep(0.5)

        # Test queue approach
        async with create_optimized_client() as client:
            results[count]["queue"] = await benchmark_httpx_queue(
                client, url, count, num_workers=50
            )
        await asyncio.sleep(0.5)

        # Test floodr
        results[count]["floodr"] = await benchmark_floodr(url, count)
        await asyncio.sleep(0.5)

        # Test floodr with prewarming
        warmup_connections = min(
            count // 2, 100
        )  # Use half the requests or 100, whichever is smaller
        results[count]["floodr_warmed"] = await benchmark_floodr_prewarmed(
            url, count, warmup_connections
        )

        # Print comparisons
        print(f"\nPerformance comparison for {count} requests:")
        floodr_time = results[count]["floodr"]
        floodr_warmed_time = results[count]["floodr_warmed"]

        # Compare against regular floodr
        print("\nCompared to floodr (cold start):")
        for method, time_taken in results[count].items():
            if method not in ["floodr", "floodr_warmed"]:
                speedup = time_taken / floodr_time
                improvement = results[count]["basic"] / time_taken
                print(
                    f"  {method}: {speedup:.2f}x slower than floodr, "
                    f"{improvement:.2f}x faster than basic httpx"
                )

        # Compare against warmed floodr
        print("\nCompared to floodr (prewarmed):")
        for method, time_taken in results[count].items():
            if method not in ["floodr", "floodr_warmed"]:
                speedup = time_taken / floodr_warmed_time
                print(f"  {method}: {speedup:.2f}x slower than warmed floodr")

        # Show improvement from warming
        warmed_improvement = floodr_time / floodr_warmed_time
        print(
            f"\nFloodr warmup improvement: {warmed_improvement:.2f}x faster with prewarming"
        )


async def main_with_uvloop():
    """Run benchmarks with uvloop for better performance."""
    print("Running with uvloop event loop for better performance...\n")
    await main()


if __name__ == "__main__":
    try:
        # Try to use uvloop for better performance
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(main_with_uvloop())
    except ImportError:
        print("uvloop not installed, using default event loop")
        print("Install uvloop for better performance: pip install uvloop\n")
        asyncio.run(main())
