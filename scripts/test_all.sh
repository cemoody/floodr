#!/bin/bash
# Run all tests including integration tests that require network access

set -e

echo "Running all Rust tests (including network tests)..."
cargo test --all-features -- --include-ignored

echo -e "\nRunning Python tests..."
pytest -v -p no:syrupy

echo -e "\nAll tests completed!" 