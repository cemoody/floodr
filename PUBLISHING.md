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

## Cutting a New Release

This project uses GitHub Actions for automated releases. Follow these steps to create a new release:

### Prerequisites

1. Ensure PyPI Trusted Publishing is configured:
   - Go to https://pypi.org/manage/account/publishing/
   - Add a publisher with:
     - PyPI Project Name: `floodr`
     - Owner: `cemoody`
     - Repository name: `floodr`
     - Workflow name: `release.yml`
     - Environment: (leave blank)

### Release Process

1. **Update version numbers** in both files:
   - `pyproject.toml`: Update the `version` field
   - `Cargo.toml`: Update the `version` field
   
   ```bash
   # Example: updating to version 0.2.0
   sed -i '' 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml
   sed -i '' 's/version = "0.1.0"/version = "0.2.0"/' Cargo.toml
   ```

2. **Update CHANGELOG.md** with release notes:
   ```markdown
   ## [0.2.0] - 2024-01-08
   ### Added
   - New features...
   ### Changed
   - Breaking changes...
   ### Fixed
   - Bug fixes...
   ```

3. **Commit and push changes**:
   ```bash
   git add pyproject.toml Cargo.toml CHANGELOG.md
   git commit -m "Bump version to 0.2.0"
   git push origin main
   ```

4. **Create and push a git tag**:
   ```bash
   git tag -a v0.2.0 -m "Release version 0.2.0: Brief description"
   git push origin v0.2.0
   ```

5. **Create a GitHub Release**:
   - Go to https://github.com/cemoody/floodr/releases/new
   - Select the tag you just created (e.g., `v0.2.0`)
   - Set release title: `v0.2.0`
   - Copy release notes from CHANGELOG.md
   - ✅ Check "Set as the latest release"
   - Click "Publish release"

### What Happens Next

The GitHub Actions workflow will automatically:
1. Build wheels for Linux, macOS, and Windows
2. Build the source distribution (sdist)
3. Upload all artifacts to PyPI using Trusted Publishing
4. Attach built wheels to the GitHub Release

### Monitoring the Release

- Watch the workflow progress: https://github.com/cemoody/floodr/actions
- Once complete, verify the release:
  - PyPI: https://pypi.org/project/floodr/
  - Test installation: `pip install --upgrade floodr`

### Troubleshooting

If the release fails:
1. Check the GitHub Actions logs for errors
2. Ensure PyPI Trusted Publishing is properly configured
3. Verify version numbers don't conflict with existing releases
4. For manual release (emergency only), use the local build process above

### Version Numbering

Follow semantic versioning (https://semver.org/):
- MAJOR version (1.0.0): Incompatible API changes
- MINOR version (0.2.0): Add functionality (backwards-compatible)
- PATCH version (0.1.1): Bug fixes (backwards-compatible) 