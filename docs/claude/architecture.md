# Architecture and Patterns

## Project Architecture

Lock-trace follows a modular layered architecture with clear separation of concerns:

```
CLI Layer (cli.py)
    ↓
Analysis Layer (lock_analyzer.py, call_tracer.py)
    ↓
Data Access Layer (cscope_interface.py)
    ↓
External Tool (cscope)
```

## Design Patterns

### Strategy Pattern
- Different lock types (spinlock, mutex, rwlock, RCU) handled through configurable patterns
- Lock operation detection using compiled regex patterns

### Command Pattern
- CLI subcommands encapsulate specific analysis operations
- Each command has distinct responsibility and parameters

### Factory Pattern
- CscopeInterface creates FunctionCall objects from raw cscope output
- CallTracer generates CallPath objects for different traversal types

### Observer Pattern
- CallTracer tracks visited functions during graph traversal
- Lock context analysis observes call paths for lock state changes

## Key Components

### Core Modules

#### **cscope_interface.py**
- **Purpose**: Interface to cscope tool for source code analysis
- **Key Functions**:
  - `get_functions_called_by()`: Uses `cscope -d -L -2 func`
  - `get_functions_calling()`: Uses `cscope -d -L -3 func`
  - `find_function_definition()`: Locates function definitions
- **Data Structures**: `FunctionCall` dataclass for call information

#### **call_tracer.py**
- **Purpose**: Graph traversal and call path analysis
- **Key Functions**:
  - `trace_callers()`: Find all paths leading to a function (supports function exclusion)
  - `trace_callees()`: Find all paths from a function (supports function exclusion)
  - `get_unique_call_chains()`: Remove duplicate call chains from caller analysis (supports function exclusion)
  - `get_unique_callee_chains()`: Remove duplicate call chains from callee analysis (supports function exclusion)
  - `build_call_tree()`: Build tree structure from call paths
  - `format_tree()`: Format tree for display
  - `find_call_paths()`: Specific source-to-target path finding
  - `_should_exclude_path()`: Check if call path contains excluded functions
- **Data Structures**: `CallPath`, `CallGraph` for representing call relationships

#### **lock_analyzer.py**
- **Purpose**: Lock context analysis and protection verification
- **Key Functions**:
  - `analyze_lock_context()`: Determine locks held in call paths (supports unique/all modes and function exclusion)
  - `find_unprotected_calls()`: Identify missing lock protection (supports unique/all modes and function exclusion)
  - `check_lock_protection()`: Verify specific lock requirements (supports unique/all modes and function exclusion)
  - `find_lock_operations()`: Identify lock operations within functions
  - `get_lock_summary()`: Generate lock usage statistics
- **Data Structures**: `LockOperation`, `LockContext` for lock state tracking

#### **cli.py**
- **Purpose**: Command-line interface and user interaction
- **Subcommands**:
  - `callers`: Show functions calling a target (supports tree/verbose modes)
  - `callees`: Show functions called by a source (supports tree/verbose modes)
  - `lock-check`: Check lock protection for a function (supports tree/verbose modes)
  - `lock-context`: Analyze lock context for functions (supports tree/verbose modes)
  - `unprotected`: Find unprotected calls to a function (supports tree/verbose modes)
  - `stats`: Generate function call and lock statistics
- **Display Modes**:
  - Default: Unique call chains in flat list format
  - Tree (`--tree`): Unique call chains in tree structure
  - Verbose (`--verbose`): All paths including duplicates
- **Global Options**:
  - `--exclude-functions`: Filter out specified functions from all call paths
  - `--max-depth`: Limit traversal depth
  - `--database-path`, `--cscope-file`, `--source-dir`: Configure cscope integration

### Data Flow

1. **Input Processing**: CLI parses arguments, validates cscope database, determines display mode, and processes exclude functions list
2. **Cscope Query**: CscopeInterface executes cscope commands and parses output
3. **Graph Construction**: CallTracer builds call relationships from cscope data
4. **Path Analysis**: CallTracer performs graph traversal to find call paths
5. **Function Filtering**: CallTracer applies exclude_functions filtering to remove unwanted paths
6. **Path Deduplication**: CallTracer applies unique filtering (unless verbose mode)
7. **Lock Analysis**: LockAnalyzer examines filtered paths for lock operations and contexts
8. **Display Formatting**: CLI applies tree formatting or flat list based on display mode
9. **Output Generation**: CLI formats and displays results to user

### Dependencies

#### **External Dependencies**
- **cscope**: Source code analysis tool (runtime dependency)
- **pyinstaller**: Binary compilation (development dependency)

#### **Python Dependencies**
- **Standard Library**: `argparse`, `pathlib`, `subprocess`, `re`, `collections`
- **Testing**: `pytest`, `pytest-cov`, `pytest-mock`
- **Code Quality**: `ruff`, `black`

## Development Principles

### **Modularity**
- Each module has single responsibility
- Clear interfaces between components
- Minimal coupling between layers

### **Testability**
- Comprehensive unit tests with mocking
- Separate business logic from I/O operations
- Test coverage requirements (>50%)

### **Error Handling**
- Graceful degradation when cscope queries fail
- Informative error messages for user issues
- Timeout handling for long-running operations

### **Performance**
- Compiled regex patterns for lock detection
- Efficient graph traversal with cycle detection
- Configurable depth limits for analysis

### **Extensibility**
- Easy addition of new lock types through pattern configuration
- Pluggable analysis algorithms
- Flexible output formatting options
