# Project Overview

Lock-trace is a static analysis tool for kernel function call stacks and lock contexts analysis.

## Project Type
- **Language**: Python
- **Package Manager**: uv
- **Version Control**: git
- **Target**: Command-line tool with binary distribution

## Key Features
- **Static Call Stack Analysis**: Print kernel function call stacks using cscope database
- **Lock Context Analysis**: Determine if functions are called within lock protection contexts
- **Function Filtering**: Exclude specific functions from call path analysis (debug, test, initialization code)
- **Cscope Integration**: Leverages cscope for source code analysis (`cscope -d -L -2` for callees, `cscope -d -L -3` for callers)
- **Multiple Lock Types**: Supports spinlock, mutex, rwlock, RCU, semaphore analysis
- **Multiple Display Modes**: Default (unique paths), tree view, verbose (all paths including duplicates)
- **Binary Compilation**: PyInstaller-based standalone executable generation
- **Flexible Configuration**: Custom cscope.out file and source directory paths

## Directory Structure

```
lock-trace/
├── lock_trace/              # Main package
│   ├── __init__.py         # Package initialization
│   ├── __main__.py         # Entry point for binary compilation
│   ├── cli.py              # Command-line interface
│   ├── cscope_interface.py # Cscope integration
│   ├── call_tracer.py      # Call stack tracing
│   └── lock_analyzer.py    # Lock context analysis
├── tests/                  # Test suite
│   ├── test_cscope_interface.py
│   ├── test_call_tracer.py
│   └── test_lock_analyzer.py
├── docs/                   # Documentation
├── Makefile               # Build system
├── pyproject.toml         # Project configuration
└── README.md              # Project documentation
```
