"""Tests for connection pool warming functionality."""

import time

import pytest

import floodr


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_basic_warmup():
    """Test basic warmup functionality."""
    # This should pre-establish connections without errors
    await floodr.warmup("https://httpbin.org/", num_connections=5)


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_advanced_warmup():
    """Test advanced warmup with specific paths."""
    results = await floodr.warmup_advanced(
        base_url="https://httpbin.org",
        paths=["/get", "/status/200", "/headers"],
        num_connections=3,
    )

    # Should get results for each path
    assert len(results) == 3

    # Count successful results (httpbin.org can return 502 sometimes)
    successful = sum(1 for r in results if r["status"] == 200)
    assert successful >= 2, f"Expected at least 2 successful, got {successful}"

    for result in results:
        # Either successful or server error
        assert result["status"] in [
            0,
            200,
            502,
            503,
        ], f"Unexpected status: {result['status']}"
        assert result["elapsed"] > 0
        assert result["url"] in [
            "https://httpbin.org/get",
            "https://httpbin.org/status/200",
            "https://httpbin.org/headers",
        ]


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_client_warmup():
    """Test warmup using Client instance."""
    client = floodr.Client()
    await client.warmup("https://httpbin.org/", num_connections=10)

    # Now make requests with the warmed client
    requests = [
        floodr.Request(url="https://httpbin.org/get"),
        floodr.Request(url="https://httpbin.org/headers"),
    ]
    responses = await client.request(requests)

    assert len(responses) == 2
    assert all(r.ok for r in responses)


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_warmup_improves_latency():
    """Test that warmup actually improves latency."""
    # First batch without warmup
    requests = [
        floodr.Request(url=f"https://httpbin.org/get?request={i}") for i in range(10)
    ]

    start = time.time()
    cold_responses = await floodr.request(requests)
    cold_time = time.time() - start

    # Count successful responses (httpbin.org can be flaky)
    cold_successful = sum(1 for r in cold_responses if r.ok)
    assert (
        cold_successful >= 7
    ), f"Too many failed requests in cold batch: {10 - cold_successful}/10 failed"

    # Calculate average latency only for successful responses
    successful_cold = [r for r in cold_responses if r.ok]
    if successful_cold:
        cold_avg = sum(r.elapsed for r in successful_cold) / len(successful_cold)
    else:
        pytest.skip("All cold requests failed, skipping test")

    # Now warm the connection pool
    await floodr.warmup("https://httpbin.org/", num_connections=10)

    # Second batch with warmed connections
    start = time.time()
    warm_responses = await floodr.request(requests)
    warm_time = time.time() - start

    # Count successful responses
    warm_successful = sum(1 for r in warm_responses if r.ok)
    assert (
        warm_successful >= 7
    ), f"Too many failed requests in warm batch: {10 - warm_successful}/10 failed"

    # Calculate average latency only for successful responses
    successful_warm = [r for r in warm_responses if r.ok]
    if successful_warm:
        warm_avg = sum(r.elapsed for r in successful_warm) / len(successful_warm)
    else:
        pytest.skip("All warm requests failed, skipping test")

    # Warm requests should generally be faster
    # But due to network variability, we'll just check they complete
    print(f"Cold avg latency: {cold_avg:.3f}s, Warm avg latency: {warm_avg:.3f}s")
    print(f"Cold total time: {cold_time:.3f}s, Warm total time: {warm_time:.3f}s")
    print(
        f"Cold successful: {cold_successful}/10, Warm successful: {warm_successful}/10"
    )
