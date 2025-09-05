# Lock-Trace

Static analysis tool for kernel function call stack analysis and lock context checking.

## Features

1. **Function Call Stack Tracing**: Static analysis of function call relationships with upward caller tracing
2. **Lock Context Analysis**: Check if function calls are protected by specified locks
3. **Cscope-based**: Fast querying using cscope database

## Requirements

- Python 3.8+
- cscope tool
- Pre-built cscope database

## Installation

### Option 1: Python Package Installation

```bash
# Install dependencies
uv sync

# Development installation
uv sync --group dev
```

### Option 2: Binary Compilation

Build a standalone binary executable:

```bash
# Install build dependencies
make install-dev

# Build binary executable
make binary

# Test the binary
./dist/lock-trace --help

# Install binary system-wide (optional)
make install-binary
```

### Build System

The project includes a comprehensive Makefile with the following targets:

```bash
# Development
make install        # Install dependencies
make install-dev    # Install development dependencies
make test          # Run tests
make lint          # Run code linting
make format        # Format code

# Binary compilation
make binary        # Build standalone binary
make binary-portable  # Build portable binary with dependencies
make binary-debug     # Build debug binary

# Installation
make install-binary   # Install binary to /usr/local/bin
make uninstall-binary # Remove installed binary

# Cleaning
make clean         # Clean build artifacts
make clean-all     # Clean all generated files

# Utilities
make help          # Show all available targets
make version       # Show version information
make check-deps    # Check system dependencies
```

## Usage

### 1. Prepare cscope database

Build cscope database in kernel source directory:

```bash
# Generate file list
find . -name "*.c" -o -name "*.h" > cscope.files

# Build database
cscope -b -q -k
```

### 2. Configuration Options

The tool supports flexible configuration for different project layouts:

- **Default**: cscope.out and source code in current directory
- **Custom database directory**: Use `-d /path/to/database`  
- **Custom cscope.out file**: Use `-f /path/to/cscope.out`
- **Custom source directory**: Use `-s /path/to/source`

Examples:
```bash
# Default: everything in current directory
lock-trace callers schedule

# Custom database directory
lock-trace -d /path/to/kernel callers schedule  

# Custom paths (useful for complex project structures)
lock-trace -f /data/cscope.out -s /code/linux callers schedule
```

### 3. Display Options

All analysis commands (`callers`, `callees`, `lock-check`, `lock-context`, `unprotected`) support three display modes:

- **Default (no flags)**: Shows unique call chains in flat list format, removing duplicate paths for cleaner output
- **Tree mode (`--tree`, `-t`)**: Shows unique call chains in tree structure format for better visualization
- **Verbose mode (`--verbose`, `-v`)**: Shows all paths including duplicates (original behavior)

These options can be combined with any command for consistent analysis across different tools.

### 4. Basic Commands

#### Trace function callers

```bash
# See who calls the schedule function (default: unique call chains)
lock-trace callers schedule --max-depth 5

# Show as tree structure
lock-trace callers schedule --tree

# Show all paths including duplicates
lock-trace callers schedule --verbose

# Specify cscope database path
lock-trace -d /path/to/kernel/source callers schedule

# Use custom cscope.out file and source directory
lock-trace -f /path/to/cscope.out -s /path/to/source callers schedule
```

#### Trace function callees

```bash
# See what functions kmalloc calls (default: unique call chains)
lock-trace callees kmalloc --max-depth 3

# Show as tree structure
lock-trace callees kmalloc --tree

# Show all paths including duplicates
lock-trace callees kmalloc --verbose
```

#### Check lock protection

```bash
# Check if my_function is called under spinlock protection (default: unique call chains)
lock-trace lock-check my_function spin

# Show as tree structure
lock-trace lock-check my_function rcu --tree

# Show all paths including duplicates
lock-trace lock-check my_function mutex --verbose
```

#### Analyze lock context

```bash
# Analyze lock context of my_function (default: unique call chains)
lock-trace lock-context my_function

# Track specific locks only
lock-trace lock-context my_function --locks spin,rcu

# Show as tree structure
lock-trace lock-context my_function --tree

# Show all paths including duplicates
lock-trace lock-context my_function --verbose
```

#### Find unprotected calls

```bash
# Find my_function calls without required lock protection (default: unique call chains)
lock-trace unprotected my_function --required-locks spin,mutex

# Show as tree structure
lock-trace unprotected my_function --required-locks rcu --tree

# Show all paths including duplicates
lock-trace unprotected my_function --required-locks spin,rtnl --verbose
```

#### Get function statistics

```bash
# Get function call statistics
lock-trace stats my_function
```

## Development

### Using Makefile

```bash
# Run tests
make test

# Code formatting
make format

# Build binary package
make binary

# Build Python package
make package

# Run all CI checks
make ci
```

### Manual commands

```bash
# Run tests
uv run pytest

# Code formatting
uv run black .
uv run ruff check .

# Build Python package
uv build
```

## Supported Lock Types

- **Spinlock**: `spin_lock()`, `spin_unlock()`, `spin_lock_irq()`, etc.
- **Mutex**: `mutex_lock()`, `mutex_unlock()`, etc.  
- **RW Lock**: `read_lock()`, `write_lock()`, `read_unlock()`, `write_unlock()`, etc.
- **RCU**: `rcu_read_lock()`, `rcu_read_unlock()`, etc.

## Example Output

### Call Stack Tracing

#### Default view (unique call chains)
```
Unique call chains to function 'schedule':
==================================================
  - init_task → kernel_thread → schedule
  - kthreadd → kthread_create → schedule  
  - worker_thread → process_one_work → schedule

Unique call chains found: 3
```

#### Tree view (`--tree`)
```
Call tree to function 'schedule':
==================================================
init_task
└── kernel_thread
    └── schedule
kthreadd
└── kthread_create
    └── schedule
worker_thread
└── process_one_work
    └── schedule

Unique call chains found: 3
```

#### Verbose view (`--verbose`)
```
All call paths to function 'schedule':
==================================================
  1: init_task → kernel_thread → schedule
  2: init_task → kernel_thread → schedule (duplicate)
  3: kthreadd → kthread_create → schedule
  4: worker_thread → process_one_work → schedule
  5: worker_thread → process_one_work → schedule (duplicate)

Total paths found: 5
```

### Lock Protection Check

#### Default view
```
Lock protection analysis for function 'my_function' with lock 'my_lock':
======================================================================
Summary: 2/3 paths have lock protection

✓ PROTECTED: caller1 → my_function
✗ UNPROTECTED: caller2 → my_function  
✓ PROTECTED: caller3 → lock_func → my_function
```

#### Tree view (`--tree`)
```
Lock protection analysis for function 'my_function' with lock 'my_lock':
======================================================================
Summary: 2/3 paths have lock protection

Protection status tree:
caller1
└── my_function [✓ PROTECTED]
caller2
└── my_function [✗ UNPROTECTED]
caller3
└── lock_func
    └── my_function [✓ PROTECTED]
```

### Lock Context Analysis

#### Default view
```
Lock context analysis for function 'my_function':
======================================================================
  1: caller1 → my_function
     Held locks: spin_lock_bh
     Lock operations:
       acquire spin_lock_bh (spinlock) in caller1

  2: caller2 → my_function
     Held locks: None

Call chains found: 2
```

#### Tree view (`--tree`)
```
Lock context analysis for function 'my_function':
======================================================================
Lock context tree:
caller1
└── my_function
caller2
└── my_function

Lock context details:
  1: Held locks: spin_lock_bh
  2: Held locks: None
```

## Architecture

```
lock_trace/
├── __init__.py
├── cscope_interface.py    # Cscope interface wrapper
├── call_tracer.py         # Call stack tracer
├── lock_analyzer.py       # Lock context analyzer
└── cli.py                 # Command-line interface
```

## License

GPLv3 License
