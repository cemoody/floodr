#!/bin/bash
# Build script for floodr Python package

set -e

echo "Building floodr Python package..."

# Check if Rust is installed (required for building)
if ! command -v cargo &> /dev/null; then
    echo "Error: Rust is not installed. Please install from https://rustup.rs/"
    echo "Rust is required to build the Python extension module."
    exit 1
fi

# Check if maturin is installed
if ! command -v maturin &> /dev/null; then
    echo "Installing maturin..."
    pip install maturin
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf target/wheels dist build *.egg-info

# Build the wheel
echo "Building Python wheel..."
maturin build --release

# Display the built wheel
echo ""
echo "Build complete! Wheel file(s):"
ls -la target/wheels/

echo ""
echo "To install locally:"
echo "  pip install target/wheels/floodr-*.whl"
echo ""
echo "To upload to PyPI:"
echo "  pip install twine"
echo "  twine upload target/wheels/*" 