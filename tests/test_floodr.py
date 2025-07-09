"""Tests for floodr library."""

import asyncio
import functools
from typing import Any, Callable, TypeVar

import pytest

from floodr import Client, request, warmup
from floodr.models import Request, Response

F = TypeVar("F", bound=Callable[..., Any])


def retry_flaky(max_attempts: int = 3, backoff_base: float = 1.0) -> Callable[[F], F]:
    """Decorator to retry flaky tests with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_base: Base time in seconds for exponential backoff (default: 1.0)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (AssertionError, Exception) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        # Calculate backoff time: 1s, 2s, 4s, etc.
                        backoff_time = backoff_base * (2**attempt)
                        print(
                            f"\nTest {func.__name__} failed (attempt {attempt + 1}/{max_attempts}), "
                            f"retrying in {backoff_time}s..."
                        )
                        await asyncio.sleep(backoff_time)
                    else:
                        print(
                            f"\nTest {func.__name__} failed after {max_attempts} attempts"
                        )

            # Re-raise the last exception if all attempts failed
            if last_exception:
                raise last_exception

        return wrapper  # type: ignore

    return decorator


@pytest.mark.asyncio
@retry_flaky(max_attempts=3, backoff_base=1.0)
async def test_single_request():
    """Test a single HTTP request."""
    req = Request(url="https://httpbin.org/get")
    responses = await request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200
    assert responses[0].ok


@pytest.mark.asyncio
@retry_flaky(max_attempts=3, backoff_base=1.0)
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
@retry_flaky(max_attempts=3, backoff_base=1.0)
async def test_post_request():
    """Test POST request with JSON data."""
    req = Request(url="https://httpbin.org/post", method="POST", json={"test": "data"})
    responses = await request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200


@pytest.mark.asyncio
@retry_flaky(max_attempts=3, backoff_base=1.0)
async def test_client():
    """Test using Client class."""
    client = Client()
    req = Request(url="https://httpbin.org/get")
    responses = await client.request([req])

    assert len(responses) == 1
    assert responses[0].status_code == 200


@pytest.mark.asyncio
@retry_flaky(max_attempts=3, backoff_base=1.0)
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
    assert resp.json_data() == {"result": "ok"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
