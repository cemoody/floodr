#!/bin/bash
# Run all tests including integration tests that require network access

set -e

echo "Running all Rust tests (including network tests)..."
cargo test -- --include-ignored

echo ""
echo "Running Python tests..."
pytest tests/ -v

echo ""
echo "All tests completed!" 