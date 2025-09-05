# Python Specific Guidelines

## Version Requirements
- Minimum Python version: 3.8+
- Use pyproject.toml for project configuration
- Target compatibility across development and runtime environments

## Package Structure
- **Main Package**: `lock_trace/` contains all core modules
- **Entry Points**: CLI tool available as `lock-trace` command
- **Binary Entry**: `__main__.py` for PyInstaller standalone executables
- **Package Initialization**: `__init__.py` with version information
- **Modular Design**: Separate modules for distinct functionality

## Code Style and Quality
- **Formatting**: Use Black with 88-character line length
- **Linting**: Use Ruff for fast Python linting
- **Type Hints**: Use type annotations for all public APIs
- **Docstrings**: Google-style docstrings for all modules, classes, and functions
- **Import Organization**: Standard library → third-party → local imports

## Error Handling
- **Specific Exceptions**: Use `RuntimeError` for system-level issues
- **Context Information**: Include file paths, line numbers in error messages
- **Graceful Degradation**: Handle missing tools (cscope) with informative errors
- **Timeout Handling**: Manage subprocess timeouts appropriately

## Performance Considerations
- **Compiled Patterns**: Pre-compile regex patterns for lock detection
- **Graph Traversal**: Use efficient algorithms with cycle detection
- **Memory Management**: Use generators for large call graphs
- **Configurable Limits**: Depth limits to prevent infinite recursion

## Testing Strategy
- **Unit Tests**: Mock external dependencies (subprocess, file system)
- **Coverage**: Maintain >50% test coverage
- **Test Structure**: Mirror source structure in `tests/` directory
- **Fixtures**: Use pytest fixtures for common test setup

## Binary Distribution
- **PyInstaller**: Create standalone executables
- **Entry Point**: Use `__main__.py` for proper module importing
- **Dependencies**: Include hidden imports for runtime resolution
- **Path Handling**: Support both development and frozen environments

## External Tool Integration
- **Cscope Commands**: Use specific cscope flags (`-d -L -2`, `-d -L -3`)
- **Subprocess Management**: Handle timeouts and error conditions
- **File Path Resolution**: Support flexible cscope.out and source directory locations
- **Validation**: Verify tool availability before execution

## CLI Design Principles
- **Subcommands**: Organize functionality into logical subcommands
- **Configuration**: Support both CLI arguments and sensible defaults
- **Output Format**: Provide clear, parseable output for analysis results
- **Help Text**: Comprehensive help for all commands and options
