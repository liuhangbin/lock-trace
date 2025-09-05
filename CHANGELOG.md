# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-09-09

### Added

- Static analysis tool for kernel function call stacks and lock contexts
- CLI commands: `callers`, `callees`, `lock-check`, `lock-context`, `unprotected`, `stats`
- Multiple display modes: default (unique paths), tree view, verbose (all paths)
- Function and directory filtering with `--exclude-functions` and `--exclude-directories`
- Lock analysis for spinlock, mutex, rwlock, RCU, semaphore, and custom locks
- Intelligent lock matching with generic filters (spin, rcu, mutex, etc.)
- Asynchronous operations for improved performance
- Callback function detection and analysis
- PyInstaller-based binary compilation
- Comprehensive test suite with >50% coverage
- GitHub Actions CI/CD workflows
- Support for Python 3.12+

### Dependencies

- Python 3.12+
- cscope (runtime dependency)
- aiofiles (async file operations)

### Notes

- Initial release of lock-trace
- Requires cscope database generated from source code
- Designed for Linux kernel analysis but extensible to other C codebases

[0.1.0]: https://github.com/yourusername/lock-trace/releases/tag/v0.1.0
