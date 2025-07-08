# Installing floodr

floodr is a Python library with a Rust extension that needs to be compiled.

## Prerequisites

1. **Python 3.9+**
2. **Rust toolchain** (install from https://rustup.rs/)
3. **maturin** for building Python extensions

## Installation Steps

### 1. Install Rust (if not already installed)
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### 2. Install maturin
```bash
pip install maturin
```

### 3. Build and install floodr in development mode
```bash
# From the project root directory
maturin develop --release
```

This will:
- Compile the Rust code
- Build the Python extension
- Install it in your current Python environment

### 4. Verify installation
```python
import floodr
print(floodr.__version__)
```

## Usage Example

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

## Building for Production

To build a wheel for distribution:
```bash
maturin build --release
```

The wheel will be in `target/wheels/` and can be installed with:
```bash
pip install target/wheels/floodr-*.whl
``` 