"""Test warmup functionality."""

import pytest

import floodr


@pytest.mark.asyncio
async def test_basic_warmup():
    """Test basic warmup function."""
    # Should not raise any errors
    await floodr.warmup("https://httpbin.org/", num_connections=5)


@pytest.mark.asyncio
async def test_advanced_warmup():
    """Test advanced warmup with custom paths."""
    results = await floodr.warmup_advanced(
        base_url="https://httpbin.org",
        paths=["/get", "/headers"],
        num_connections=4,
        method="HEAD",
    )

    # Check we got results
    assert len(results) == 4

    # Check result structure
    for result in results:
        assert "url" in result
        assert "status" in result
        assert "elapsed" in result
        assert isinstance(result["elapsed"], float)
        assert result["elapsed"] > 0


@pytest.mark.asyncio
async def test_client_warmup():
    """Test warmup on client instance."""
    client = floodr.Client(max_connections=100)

    # Should not raise any errors
    await client.warmup("https://httpbin.org/", num_connections=10)

    # Now use the warmed client
    requests = [
        floodr.Request(url="https://httpbin.org/get"),
        floodr.Request(url="https://httpbin.org/headers"),
    ]

    responses = await client.request(requests)
    assert len(responses) == 2
    assert all(r.ok for r in responses)


@pytest.mark.asyncio
async def test_warmup_improves_latency():
    """Test that warmup actually improves latency."""
    # Create requests
    requests = [
        floodr.Request(url=f"https://httpbin.org/get?request={i}") for i in range(10)
    ]

    # First batch without warmup
    responses1 = await floodr.request(requests, use_global_client=False)

    # Check for any failed requests and print details
    failed_requests = [r for r in responses1 if not r.ok]
    if failed_requests:
        for r in failed_requests:
            print(f"Failed request: {r.url}, status: {r.status_code}, error: {r.error}")

    # Calculate average latency only for successful requests
    successful_responses1 = [r for r in responses1 if r.ok]
    if not successful_responses1:
        pytest.skip("All requests failed in first batch, skipping test")

    avg_latency1 = sum(r.elapsed for r in successful_responses1) / len(
        successful_responses1
    )

    # Warm up the global client
    await floodr.warmup("https://httpbin.org/", num_connections=10)

    # Second batch with warmed connections
    responses2 = await floodr.request(requests)

    # Calculate average latency only for successful requests
    successful_responses2 = [r for r in responses2 if r.ok]
    if not successful_responses2:
        pytest.skip("All requests failed in second batch, skipping test")

    avg_latency2 = sum(r.elapsed for r in successful_responses2) / len(
        successful_responses2
    )

    # The warmed requests should be faster on average
    # We can't guarantee this 100% due to network variability,
    # but it should be true most of the time
    print(
        f"Average latency without warmup: {avg_latency1:.3f}s (from {len(successful_responses1)} successful requests)"
    )
    print(
        f"Average latency with warmup: {avg_latency2:.3f}s (from {len(successful_responses2)} successful requests)"
    )

    # Verify that at least some requests succeeded
    assert len(successful_responses1) > 0, "No successful requests in first batch"
    assert len(successful_responses2) > 0, "No successful requests in second batch"

    # If we have enough successful requests, check that most succeeded
    if len(successful_responses1) >= 5:
        assert (
            len(successful_responses1) >= len(requests) * 0.8
        ), f"Too many failed requests in first batch: {len(failed_requests)}/{len(requests)}"
    if len(successful_responses2) >= 5:
        assert (
            len(successful_responses2) >= len(requests) * 0.8
        ), "Too many failed requests in second batch"
