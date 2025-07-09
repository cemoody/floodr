#!/usr/bin/env python3
"""Basic usage examples for floodr library."""

import asyncio
import time

from floodr import Client, Request, request, warmup


async def simple_get_example():
    """Simple GET request example."""
    print("=== Simple GET Request ===")

    # Single request
    req = Request(url="https://httpbin.org/get")
    responses = await request([req])

    resp = responses[0]
    print(f"Status: {resp.status_code}")
    print(f"Response time: {resp.elapsed:.3f}s")
    print(f"Content preview: {resp.text[:100]}...")
    print()


async def parallel_requests_example():
    """Parallel requests example."""
    print("=== Parallel Requests ===")

    # Create multiple requests
    urls = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
    ]

    # Time sequential requests (for comparison)
    print("Sequential requests:")
    start = time.time()
    for url in urls:
        req = Request(url=url)
        await request([req])
    sequential_time = time.time() - start
    print(f"Time: {sequential_time:.3f}s")

    # Time parallel requests
    print("\nParallel requests with floodr:")
    start = time.time()
    requests_list = [Request(url=url) for url in urls]
    responses = await request(requests_list)
    parallel_time = time.time() - start

    print(f"Time: {parallel_time:.3f}s")
    print(f"Speedup: {sequential_time/parallel_time:.1f}x")
    print(f"All successful: {all(r.ok for r in responses)}")
    print()


async def post_with_json_example():
    """POST request with JSON data."""
    print("=== POST with JSON ===")

    req = Request(
        url="https://httpbin.org/post",
        method="POST",
        json={"name": "floodr", "type": "library", "fast": True},
        headers={"X-Custom-Header": "floodr-example"},
    )

    responses = await request([req])
    resp = responses[0]

    data = resp.json()
    print(f"Posted data: {data['json']}")
    print(f"Headers received: {data['headers']['X-Custom-Header']}")
    print()


async def error_handling_example():
    """Error handling example."""
    print("=== Error Handling ===")

    requests_list = [
        Request(url="https://httpbin.org/status/200"),  # Success
        Request(url="https://httpbin.org/status/404"),  # Not found
        Request(url="https://httpbin.org/status/500"),  # Server error
        Request(url="https://invalid-domain-12345.com", timeout=2.0),  # Network error
    ]

    responses = await request(requests_list)

    for i, resp in enumerate(responses):
        print(f"\nRequest {i+1}:")
        print(f"  URL: {requests_list[i].url}")
        print(f"  Status: {resp.status_code}")
        print(f"  OK: {resp.ok}")
        if resp.error:
            print(f"  Error: {resp.error}")

        # Alternative: use raise_for_status()
        try:
            resp.raise_for_status()
            print("  Success!")
        except Exception as e:
            print(f"  Exception: {e}")
    print()


async def client_reuse_example():
    """Client reuse for better performance."""
    print("=== Client Reuse ===")

    # Create a client for connection pooling
    client = Client(max_connections=100)

    # Make multiple batches of requests
    for batch in range(3):
        print(f"\nBatch {batch + 1}:")
        requests_list = [
            Request(url=f"https://httpbin.org/get?batch={batch}&id={i}")
            for i in range(10)
        ]

        start = time.time()
        responses = await client.request(requests_list)
        elapsed = time.time() - start

        success_count = sum(1 for r in responses if r.ok)
        print(f"  Completed {success_count}/{len(responses)} in {elapsed:.3f}s")
    print()


async def concurrency_control_example():
    """Control concurrency for large batches."""
    print("=== Concurrency Control ===")

    # Create a large batch of requests
    requests_list = [Request(url=f"https://httpbin.org/get?id={i}") for i in range(50)]

    # Default concurrency (automatic)
    print("Default concurrency:")
    start = time.time()
    responses = await request(requests_list)
    print(f"  Time: {time.time() - start:.3f}s")
    print(f"  Success: {sum(1 for r in responses if r.ok)}/{len(responses)}")

    # Limited concurrency
    print("\nLimited concurrency (max 10):")
    start = time.time()
    responses = await request(requests_list, max_concurrent=10)
    print(f"  Time: {time.time() - start:.3f}s")
    print(f"  Success: {sum(1 for r in responses if r.ok)}/{len(responses)}")
    print()


async def main():
    """Run all examples."""
    print("floodr Library Examples\n")

    # Warmup connection pool
    print("Warming up...")
    await warmup("https://httpbin.org")
    print()

    # Run examples
    await simple_get_example()
    await parallel_requests_example()
    await post_with_json_example()
    await error_handling_example()
    await client_reuse_example()
    await concurrency_control_example()

    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
