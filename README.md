# floodr - Fast Parallel HTTP Requests for Python

[![PyPI version](https://badge.fury.io/py/floodr.svg)](https://badge.fury.io/py/floodr)
[![Python](https://img.shields.io/pypi/pyversions/floodr.svg)](https://pypi.org/project/floodr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/cemoody/floodr/actions/workflows/test.yml/badge.svg)](https://github.com/cemoody/floodr/actions/workflows/test.yml)

A high-performance Python library for parallel HTTP requests, built with Rust for speed and reliability. Perfect for bulk API requests, web scraping, and any scenario where you need to fetch multiple URLs concurrently.

## Features

- 🚀 **Fast**: Built with Rust for maximum performance
- 🔄 **Async**: Full async/await support with Python's asyncio
- 🎯 **Simple API**: Intuitive interface similar to requests/httpx
- 🏊 **Connection Pooling**: Automatic connection reuse for better performance
- 🎛️ **Configurable**: Control timeouts, concurrency limits, and more
- 🛡️ **Type Safe**: Full type hints and runtime validation
- 📦 **Zero Dependencies**: Minimal Python dependencies (just pydantic)

## Installation

### From PyPI

```bash
pip install floodr
```

### With uv

```bash
uv add floodr
```

### From source

```bash
# Clone the repository
git clone https://github.com/yourusername/floodr.git
cd floodr

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install maturin (build tool)
pip install maturin

# Build and install
maturin develop --release
```

## Requirements

- Python 3.9 or higher
- Rust toolchain (only for building from source)

## Quick Start

```python
import asyncio
import floodr

async def main():
    # Simple parallel GET requests
    urls = [
        "https://api.github.com/users/github",
        "https://api.github.com/users/torvalds",
        "https://api.github.com/users/rust-lang"
    ]
    
    responses = await floodr.get(urls)
    
    for url, resp in zip(urls, responses):
        data = resp.json()
        print(f"{data['name']} has {data['public_repos']} public repos")

asyncio.run(main())
```

## API Reference

The floodr library provides a modern API using Pydantic models for request/response handling:

```python
from floodr import Request, Response, request

# Create requests with Pydantic validation
requests = [
    Request(url="https://httpbin.org/get"),
    Request(
        url="https://httpbin.org/post",
        method="POST",
        json={"key": "value"},
        headers={"X-Custom": "header"}
    ),
    Request(
        url="https://httpbin.org/get",
        params={"search": "query", "page": "1"}
    ),
]

# Execute multiple requests in parallel
responses = await request(requests)

# Access response data
for resp in responses:
    print(f"Status: {resp.status_code}")
    print(f"Headers: {resp.headers}")
    print(f"Content: {resp.text}")
    if resp.ok:
        data = resp.json()  # Parse JSON response

# Use the client for connection reuse
from floodr import Client
client = Client(max_connections=2048)
responses = await client.request(requests)

# Control concurrency for large batches
responses = await request(requests, max_concurrent=100)
```

### Request Model

The `Request` model supports the following fields:
- `url` (required): The URL to request (validated as proper URL)
- `method`: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) - defaults to GET
- `headers`: Dictionary of HTTP headers
- `params`: URL query parameters (dict or dict with list values for multiple params)
- `json`: JSON body data (automatically serialized)
- `data`: Form data or raw body (string, bytes, or dict)
- `timeout`: Request timeout in seconds

### Response Model

The `Response` model provides:
- `status_code`: HTTP status code
- `headers`: Response headers as dict
- `content`: Raw response body as bytes
- `text`: Response body as string (property)
- `ok`: True if status is 2xx (property)
- `json()`: Parse response as JSON
- `elapsed`: Time taken for request in seconds
- `url`: Final URL after redirects
- `error`: Error message if request failed (network errors, timeouts, etc.)
- `raise_for_status()`: Raise exception for errors

### Error Handling

floodr provides comprehensive error handling without interrupting batch processing:

```python
from floodr import Request, request

requests = [
    Request(url="https://httpbin.org/status/200"),  # Success
    Request(url="https://httpbin.org/status/404"),  # HTTP error
    Request(url="https://httpbin.org/status/500"),  # Server error
    Request(url="https://invalid-domain.com", timeout=2.0),  # Network error
]

responses = await request(requests)

for req, resp in zip(requests, responses):
    if resp.error:
        # Network error (DNS, connection, timeout)
        print(f"Request failed: {resp.error}")
    elif not resp.ok:
        # HTTP error (4xx, 5xx)
        print(f"HTTP {resp.status_code} error for {resp.url}")
    else:
        # Success
        print(f"Success: {resp.status_code}")

# Or use raise_for_status() for exception-based handling
for resp in responses:
    try:
        resp.raise_for_status()
        # Process successful response
        data = resp.json()
    except Exception as e:
        print(f"Error: {e}")
```

#### Error Types

1. **Network Errors**: Connection failures, DNS resolution, timeouts
   - `status_code`: 0
   - `error`: Contains error message
   - `ok`: False

2. **HTTP Errors**: 4xx and 5xx responses
   - `status_code`: The actual HTTP status
   - `error`: None (valid HTTP response)
   - `ok`: False

3. **Validation Errors**: Invalid URLs, methods, or data
   - Raised immediately when creating Request objects
   - Standard Python exceptions (ValidationError)

### Concurrency Control

The `max_concurrent` parameter allows you to control the number of simultaneous requests:

- **None (default)**: Automatic concurrency based on batch size
  - For ≤100 requests: All requests run concurrently
  - For >100 requests: Limits to `batch_size / 10` (between 100-500)
- **Custom value**: Set a specific limit for concurrent requests

This is particularly useful for:
- Avoiding overwhelming target servers
- Managing memory usage for very large batches
- Complying with rate limits
- Optimizing performance based on network conditions

Example:
```python
# Fetch many URLs with controlled concurrency
requests = [Request(url=f"https://api.example.com/item/{i}") for i in range(1000)]

# Automatic concurrency (would use ~100 concurrent requests)
responses = await request(requests)

# Limited concurrency (gentler on the server)
responses = await request(requests, max_concurrent=50)

# Using client
client = Client()
responses = await client.request(requests, max_concurrent=20)
```

### Connection Pool Warming

When you know you'll be making many concurrent requests to a specific domain, you can pre-warm the connection pool to reduce latency:

```python
import floodr

# Pre-establish 100 connections to the domain
await floodr.warmup("https://api.example.com", num_connections=100)

# Now make your actual requests - they'll reuse the warmed connections
requests = [Request(url=f"https://api.example.com/item/{i}") for i in range(100)]
responses = await request(requests)  # Much lower latency!
```

#### Why Warm Connections?

When making HTTP requests, establishing new connections involves:
1. DNS resolution
2. TCP handshake
3. TLS negotiation (for HTTPS)

This can add 50-200ms per connection. By pre-warming the pool, subsequent requests can reuse existing connections, significantly reducing latency.

#### Advanced Warming

For more control, use `warmup_advanced`:

```python
# Warm specific endpoints with detailed results
results = await floodr.warmup_advanced(
    base_url="https://api.example.com",
    paths=["/health", "/api/v1/status", "/api/v1/users"],
    num_connections=50,
    method="HEAD"  # Use HEAD for minimal data transfer
)

# Check warmup results
for result in results:
    print(f"{result['url']}: {result['status']} in {result['elapsed']:.3f}s")
```

#### Using with Client

The `Client` class also supports warming:

```python
client = Client(max_connections=1000)

# Warm the client's connection pool
await client.warmup("https://api.example.com", num_connections=100)

# Use the warmed client
responses = await client.request(requests)
```

#### Best Practices

1. **Warm before bulk requests**: If you're about to make 100+ requests to a domain, warm with 10-20% of that number
2. **Use HEAD requests**: The default HEAD method minimizes data transfer during warming
3. **Consider server limits**: Don't warm more connections than the server can handle
4. **Reuse warmed pools**: The global client maintains connections for 5 minutes

## Performance

floodr is designed for high-performance parallel requests:

- **6-10x faster** than pure Python solutions like aiohttp for parallel requests
- **Automatic concurrency management** prevents overwhelming servers
- **Memory efficient** with streaming responses
- **Connection pooling** for reduced latency

### Benchmarks

| Concurrent Requests | aiohttp | httpx | floodr | Speedup |
|-------------------|---------|-------|------|---------|
| 100 | 1.2s | 1.1s | 0.3s | 4x |
| 500 | 5.8s | 5.2s | 0.8s | 7x |
| 1000 | 11.4s | 10.8s | 1.6s | 7x |

*Benchmark against httpbin.org, results may vary based on network conditions*

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/floodr.git
cd floodr
pip install -e ".[dev]"

# Run tests
pytest

# Run all tests including integration tests
./scripts/test_all.sh

# Format code
black floodr tests

# Lint
ruff check floodr tests
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Technical Details

floodr is a Python library with a Rust backend for maximum performance. It's not intended to be used as a standalone Rust crate, but rather as a Python package that leverages Rust's speed and safety.

## Acknowledgments

- Built with [PyO3](https://pyo3.rs/) and [maturin](https://github.com/PyO3/maturin)
- Powered by [tokio](https://tokio.rs/) and [reqwest](https://github.com/seanmonstar/reqwest)
- Inspired by [requests](https://github.com/psf/requests) and [httpx](https://github.com/encode/httpx) 