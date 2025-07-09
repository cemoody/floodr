"""
Example demonstrating connection pool warming for improved latency.

This shows how to pre-establish connections to a domain before making
the actual requests, which can significantly reduce latency.
"""

import asyncio
import time

import floodr


async def without_warmup():
    """Make requests without pre-warming the connection pool."""
    print("\n=== Without Warmup ===")

    # Create 50 requests to httpbin
    requests = [
        floodr.Request(
            url=f"https://httpbin.org/get?request={i}",
            method="GET",
        )
        for i in range(50)
    ]

    # Time the execution
    start = time.time()
    responses = await floodr.request(requests, max_concurrent=50)
    elapsed = time.time() - start

    # Check results
    successful = sum(1 for r in responses if r.status_code == 200)
    print(f"Completed {successful}/{len(requests)} requests in {elapsed:.2f}s")

    # Show first few response times
    print("First 5 response times:")
    for i, resp in enumerate(responses[:5]):
        print(f"  Request {i}: {resp.elapsed:.3f}s")

    return elapsed


async def with_warmup():
    """Make requests after pre-warming the connection pool."""
    print("\n=== With Warmup ===")

    # Warm up with 50 connections
    print("Warming up connection pool...")
    warmup_start = time.time()
    await floodr.warmup("https://httpbin.org/", num_connections=50)
    warmup_time = time.time() - warmup_start
    print(f"Warmup completed in {warmup_time:.2f}s")

    # Create the same 50 requests
    requests = [
        floodr.Request(
            url=f"https://httpbin.org/get?request={i}",
            method="GET",
        )
        for i in range(50)
    ]

    # Time the execution
    start = time.time()
    responses = await floodr.request(requests, max_concurrent=50)
    elapsed = time.time() - start

    # Check results
    successful = sum(1 for r in responses if r.status_code == 200)
    print(f"Completed {successful}/{len(requests)} requests in {elapsed:.2f}s")

    # Show first few response times
    print("First 5 response times:")
    for i, resp in enumerate(responses[:5]):
        print(f"  Request {i}: {resp.elapsed:.3f}s")

    return elapsed, warmup_time


async def advanced_warmup_example():
    """Demonstrate advanced warmup with specific paths."""
    print("\n=== Advanced Warmup ===")

    # Warm up with specific API endpoints
    print("Warming up with specific paths...")
    results = await floodr.warmup_advanced(
        base_url="https://httpbin.org",
        paths=["/get", "/post", "/headers", "/status/200"],
        num_connections=20,
        method="HEAD",
    )

    # Show warmup results
    print(f"Warmed up {len(results)} connections:")
    for result in results[:5]:  # Show first 5
        status = result.get("status", 0)
        elapsed = result.get("elapsed", 0)
        url = result.get("url", "")
        print(f"  {url}: {status} in {elapsed:.3f}s")


async def main():
    """Run all examples."""
    print("Connection Pool Warming Example")
    print("===============================")

    # Run without warmup
    time_without_warmup = await without_warmup()

    # Wait a bit to let connections close
    await asyncio.sleep(2)

    # Run with warmup
    time_with_warmup, warmup_time = await with_warmup()

    # Compare results
    print("\n=== Comparison ===")
    print(f"Without warmup: {time_without_warmup:.2f}s")
    print(f"With warmup: {time_with_warmup:.2f}s (+ {warmup_time:.2f}s warmup)")
    print(f"Total with warmup: {time_with_warmup + warmup_time:.2f}s")

    improvement = (time_without_warmup - time_with_warmup) / time_without_warmup * 100
    print(f"Request time improvement: {improvement:.1f}%")

    # Advanced warmup example
    await advanced_warmup_example()


if __name__ == "__main__":
    asyncio.run(main())
