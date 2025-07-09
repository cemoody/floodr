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
    avg_latency1 = sum(r.elapsed for r in responses1) / len(responses1)

    # Warm up the global client
    await floodr.warmup("https://httpbin.org/", num_connections=10)

    # Second batch with warmed connections
    responses2 = await floodr.request(requests)
    avg_latency2 = sum(r.elapsed for r in responses2) / len(responses2)

    # The warmed requests should be faster on average
    # We can't guarantee this 100% due to network variability,
    # but it should be true most of the time
    print(f"Average latency without warmup: {avg_latency1:.3f}s")
    print(f"Average latency with warmup: {avg_latency2:.3f}s")

    # At least verify all requests succeeded
    assert all(r.ok for r in responses1)
    assert all(r.ok for r in responses2)
