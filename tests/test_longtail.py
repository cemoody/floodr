"""Tests for longtail cancellation feature."""

import time

import pytest

from floodr import Client, Request


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_longtail_basic():
    """Test basic longtail cancellation."""
    # Create a client with longtail settings
    # Cancel after 80% of requests complete and wait 0.5 seconds
    client = Client(longtail_percentile=0.8, longtail_wait=0.5)

    # Create requests with different delays
    # Using more reliable endpoints
    requests = [
        Request(url="https://httpbin.org/get"),  # Fast
        Request(url="https://httpbin.org/get"),  # Fast
        Request(url="https://httpbin.org/get"),  # Fast
        Request(url="https://httpbin.org/get"),  # Fast
        Request(url="https://httpbin.org/delay/5"),  # Slow (will be cancelled)
    ]

    start_time = time.time()
    responses = await client.request(requests)
    elapsed = time.time() - start_time

    # Should complete faster than waiting for all requests (5+ seconds)
    # Allow generous buffer for network latency
    assert elapsed < 4.5, f"Request took too long: {elapsed}s"

    # Check responses
    assert len(responses) == 5

    # Count successful responses (should be at least 3, ideally 4)
    successful_count = sum(1 for r in responses if r.ok)
    assert (
        successful_count >= 3
    ), f"Expected at least 3 successful, got {successful_count}"

    # Last request or any slow one should be cancelled
    cancelled_count = sum(
        1 for r in responses if r.error and "cancelled" in r.error.lower()
    )
    assert cancelled_count >= 1, "Expected at least one cancelled request"


@pytest.mark.asyncio
async def test_longtail_validation():
    """Test validation of longtail parameters."""
    # Should require both parameters
    with pytest.raises(
        ValueError,
        match="Both longtail_percentile and longtail_wait must be set together",
    ):
        Client(longtail_percentile=0.8)

    with pytest.raises(
        ValueError,
        match="Both longtail_percentile and longtail_wait must be set together",
    ):
        Client(longtail_wait=1.0)

    # Should validate percentile range
    with pytest.raises(
        ValueError, match="longtail_percentile must be between 0.0 and 1.0"
    ):
        Client(longtail_percentile=1.5, longtail_wait=1.0)

    with pytest.raises(
        ValueError, match="longtail_percentile must be between 0.0 and 1.0"
    ):
        Client(longtail_percentile=-0.1, longtail_wait=1.0)


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_longtail_request_ids():
    """Test that request IDs are preserved in responses."""
    client = Client(longtail_percentile=0.5, longtail_wait=0.1)

    # Create requests - they will have auto-generated UUIDs
    requests = [
        Request(url="https://httpbin.org/delay/0"),
        Request(url="https://httpbin.org/delay/0"),
        Request(url="https://httpbin.org/delay/3"),
        Request(url="https://httpbin.org/delay/3"),
    ]

    # Store original request IDs
    original_ids = [r.request_id for r in requests]

    responses = await client.request(requests)

    # Extract request IDs from responses
    response_ids = [r.request_id for r in responses]

    # All responses should have IDs
    assert all(id is not None for id in response_ids)
    assert len(response_ids) == len(requests)

    # Check that successful responses have original IDs
    for i, resp in enumerate(responses):
        if resp.ok:
            # Successful responses should have original ID
            assert resp.request_id == original_ids[i]
        else:
            # Cancelled responses should still have an ID
            assert resp.request_id is not None


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_longtail_with_module_function():
    """Test longtail with module-level request function."""
    from floodr import request

    requests = [
        Request(url="https://httpbin.org/get"),  # Fast endpoint
        Request(url="https://httpbin.org/get"),  # Fast endpoint
        Request(url="https://httpbin.org/delay/3"),  # Slower, but not as extreme
    ]

    start_time = time.time()
    responses = await request(
        requests,
        longtail_percentile=0.67,  # Cancel after 2/3 complete (need >0.666 to get 2 out of 3)
        longtail_wait=0.5,
    )
    elapsed = time.time() - start_time

    # Should complete quickly (faster than waiting for 3s delay)
    assert elapsed < 3.5, f"Expected < 3.5s, got {elapsed}s"
    assert len(responses) == 3

    # At least 2 should succeed (67% of 3 = 2.01, rounds to 2)
    success_count = sum(1 for r in responses if r.ok)
    assert success_count >= 2


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_longtail_all_fast():
    """Test longtail when all requests complete quickly."""
    client = Client(longtail_percentile=0.8, longtail_wait=2.0)

    # All fast requests
    requests = [Request(url="https://httpbin.org/get") for _ in range(5)]

    responses = await client.request(requests)

    # All should succeed
    assert len(responses) == 5
    assert all(r.ok for r in responses)
    assert all(r.error is None for r in responses)


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=1)
async def test_longtail_with_concurrency():
    """Test longtail with custom concurrency limit."""
    client = Client(longtail_percentile=0.5, longtail_wait=0.5)

    requests = [Request(url="https://httpbin.org/delay/1") for _ in range(10)]

    start_time = time.time()
    responses = await client.request(requests, max_concurrent=2)
    elapsed = time.time() - start_time

    # With concurrency=2 and 1-second delays:
    # Should complete faster than all 10 requests (which would take ~5s with concurrency=2)
    # But allow generous buffer for network conditions
    assert 2.0 <= elapsed <= 8.0, f"Expected 3-6s, got {elapsed}s"

    # Check some were cancelled
    cancelled_count = sum(
        1 for r in responses if r.error and "cancelled" in r.error.lower()
    )
    assert cancelled_count >= 3, f"Expected at least 3 cancelled, got {cancelled_count}"

    # And some succeeded
    success_count = sum(1 for r in responses if r.ok)
    assert success_count >= 4, f"Expected at least 4 successful, got {success_count}"
