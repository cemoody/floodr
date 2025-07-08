# Publishing to PyPI

This guide explains how to publish floodr to PyPI.

## Prerequisites

1. PyPI account (https://pypi.org/account/register/)
2. Test PyPI account (https://test.pypi.org/account/register/)
3. API tokens for both accounts
4. Rust toolchain installed
5. Python 3.9+ with pip

## Setup

1. Install required tools:
```bash
pip install twine maturin build
```

2. Configure PyPI credentials:

Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-<your-token-here>

[testpypi]
username = __token__
password = pypi-<your-test-token-here>
repository = https://test.pypi.org/legacy/
```

## Building

1. Update version in `pyproject.toml` and `Cargo.toml`
2. Update CHANGELOG.md
3. Build the package:

```bash
# Build wheels for current platform
./build.sh

# Or build for multiple platforms using cibuildwheel
pip install cibuildwheel
cibuildwheel --platform linux
```

## Testing

1. Test on Test PyPI first:
```bash
twine upload --repository testpypi target/wheels/*
```

2. Install from Test PyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ floodr
```

## Publishing

1. Tag the release:
```bash
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

2. Upload to PyPI:
```bash
twine upload target/wheels/*
```

## GitHub Actions

The repository includes GitHub Actions workflows that automatically:

1. Run tests on push/PR
2. Build and publish wheels when a release is created

To use automated publishing:

1. Go to repository Settings → Secrets → Actions
2. Add repository secret `PYPI_API_TOKEN` with your PyPI token
3. Create a new release on GitHub
4. The workflow will automatically build and publish

## Post-Release

1. Verify installation:
```bash
pip install floodr
python -c "import floodr; print(floodr.__version__)"
```

2. Update documentation if needed
3. Announce the release 