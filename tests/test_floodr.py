"""Tests for floodr library."""

import asyncio

import pytest

from floodr import Client, request, warmup
from floodr.models import Request, Response


@pytest.mark.asyncio
async def test_single_request():
    """Test a single HTTP request."""
    req = Request(url="https://httpbin.org/get")
    responses = await request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200
    assert responses[0].ok


@pytest.mark.asyncio
async def test_multiple_requests():
    """Test multiple parallel requests."""
    requests_list = [
        Request(url="https://httpbin.org/get?page=1"),
        Request(url="https://httpbin.org/get?page=2"),
        Request(url="https://httpbin.org/get?page=3"),
    ]
    responses = await request(requests_list)

    assert len(responses) == 3
    for resp in responses:
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_post_request():
    """Test POST request with JSON data."""
    req = Request(url="https://httpbin.org/post", method="POST", json={"test": "data"})
    responses = await request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200


@pytest.mark.asyncio
async def test_client():
    """Test using Client class."""
    client = Client()
    req = Request(url="https://httpbin.org/get")
    responses = await client.request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200


@pytest.mark.asyncio
async def test_warmup():
    """Test warmup function."""
    # Should not raise any errors
    await warmup("https://httpbin.org")


@pytest.mark.asyncio
async def test_error_handling():
    """Test handling of failed requests."""
    # This domain should not exist
    req = Request(url="https://invalid-domain-xyz-123.com", timeout=2.0)
    responses = await request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 0
    assert not responses[0].ok
    assert responses[0].error is not None


def test_response_model():
    """Test Response model functionality."""
    resp = Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"result": "ok"}',
        url="https://example.com",
        elapsed=1.0,
        error=None,
    )

    assert resp.ok
    assert resp.text == '{"result": "ok"}'
    assert resp.json() == {"result": "ok"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
