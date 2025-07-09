# Changelog

## [0.1.0] - Unreleased

### Added
- Initial release of floodr Python package
- Fast parallel HTTP requests powered by Rust
- Support for GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS methods
- Async/await support
- Type-safe API with Pydantic models
- Automatic concurrency management
- Connection pooling
- Comprehensive error handling
- Connection pool warming for reduced latency
  - `warmup()` function to pre-establish connections
  - `warmup_advanced()` for warming specific endpoints
  - Support for warming both global and client-specific pools 