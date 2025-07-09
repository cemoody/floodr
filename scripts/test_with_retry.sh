#!/bin/bash
# Run tests with visible retry output

echo "Running tests with automatic retry on failures..."
echo "Tests marked with @pytest.mark.flaky will retry up to 3 times"
echo ""

# Run with verbose output to see retries
pytest -v --tb=short -o log_cli=true -o log_cli_level=INFO

echo ""
echo "To see retry behavior in action, run specific tests:"
echo "  pytest tests/test_longtail.py -v --tb=short"
echo ""
echo "Tests using httpbin.org may occasionally fail due to network issues."
echo "The retry mechanism will automatically retry these tests up to 3 times." 