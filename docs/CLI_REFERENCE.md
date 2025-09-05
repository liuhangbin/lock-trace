# CLI Reference

Complete command-line interface reference for lock-trace tool.

## Global Options

Available for all commands:

- `--database-path`, `-d`: Path to cscope database directory (default: current directory)
- `--cscope-file`, `-f`: Path to cscope.out file (default: cscope.out in database directory)
- `--source-dir`, `-s`: Path to source code directory (default: same as database directory)
- `--max-depth`, `-m`: Maximum depth for call tracing (default: 10)
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates
- `--exclude-functions`, `-e`: Comma-separated list of functions to exclude from call paths
- `--exclude-directories`, `-E`: Comma-separated list of directories to exclude from call paths

## Display Modes

All analysis commands support three display modes:

### Default Mode (no flags)
- Shows unique call chains in flat list format
- Removes duplicate paths for cleaner output
- Uses arrow notation (→) for call paths
- Best for quick analysis and piping to other tools

### Tree Mode (`--tree`, `-t`)
- Shows unique call chains in tree structure
- Better visualization of call hierarchies
- Uses tree characters (├──, └──) for formatting
- Best for understanding call flow structure

### Verbose Mode (`--verbose`, `-v`)
- Shows all paths including duplicates
- Original behavior (before deduplication)
- Numbered output with full path details
- Best for comprehensive analysis

## Commands

### callers

Trace caller paths to a function.

**Syntax:**
```
lock-trace callers [OPTIONS] FUNCTION
```

**Arguments:**
- `FUNCTION`: Function to trace callers for

**Options:**
- `--max-depth INTEGER`: Override global max depth
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates

**Examples:**
```bash
# Default: unique call chains
lock-trace callers schedule

# Tree view
lock-trace --tree callers schedule

# Show all paths including duplicates
lock-trace --verbose callers schedule

# Limit depth
lock-trace --max-depth 5 callers schedule

# Exclude debug and helper functions
lock-trace --exclude-functions debug_print,trace_func callers schedule

# Combine options
lock-trace --tree --exclude-functions helper_func,debug_func callers schedule
```

### callees

Trace callee paths from a function.

**Syntax:**
```
lock-trace callees [OPTIONS] FUNCTION
```

**Arguments:**
- `FUNCTION`: Function to trace callees from

**Options:**
- `--max-depth INTEGER`: Override global max depth
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates

**Examples:**
```bash
# Default: unique call chains
lock-trace callees kmalloc

# Tree view
lock-trace --tree callees kmalloc

# Show all paths
lock-trace --verbose callees kmalloc

# Exclude memory debugging functions
lock-trace --exclude-functions kmemleak_alloc,debug_check callees kmalloc
```

### lock-check

Check if function is called with lock protection.

**Syntax:**
```
lock-trace lock-check [OPTIONS] FUNCTION LOCK
```

**Arguments:**
- `FUNCTION`: Function to check
- `LOCK`: Lock variable name to check for

**Options:**
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates

**Examples:**
```bash
# Default: unique call chains
lock-trace lock-check my_function spin

# Tree view with protection status
lock-trace --tree lock-check my_function spin

# Show all paths
lock-trace --verbose lock-check my_function rcu

# Exclude test and debug code paths
lock-trace --exclude-functions test_func,debug_helper lock-check my_function mutex
```

**Output:**
- Summary line showing protection ratio
- Per-path status: ✓ PROTECTED or ✗ UNPROTECTED
- In tree mode: protection status shown inline

### lock-context

Analyze lock context for function calls.

**Syntax:**
```
lock-trace lock-context [OPTIONS] FUNCTION [LOCKS]
```

**Arguments:**
- `FUNCTION`: Function to analyze
- `LOCKS`: Optional comma-separated list of specific locks to track

**Options:**
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates

**Examples:**
```bash
# Analyze all locks
lock-trace lock-context my_function

# Track specific locks only
lock-trace lock-context my_function spin,mutex

# Track single lock
lock-trace lock-context my_function rtnl

# Tree view (analyze all locks)
lock-trace --tree lock-context my_function

# Tree view with specific locks
lock-trace --tree lock-context my_function spin

# Show all paths
lock-trace --verbose lock-context my_function rcu

# Exclude initialization and cleanup code
lock-trace --exclude-functions init_func,cleanup_func lock-context my_function
```

**Output:**
- Call paths with held locks information
- Lock operations performed in each function
- In tree mode: separate tree display and lock details

### unprotected

Find unprotected calls to a function.

**Syntax:**
```
lock-trace unprotected [OPTIONS] FUNCTION REQUIRED_LOCKS
```

**Arguments:**
- `FUNCTION`: Function that requires protection
- `REQUIRED_LOCKS`: Comma-separated list of required locks

**Options:**
- `--tree`, `-t`: Display results as tree structure with unique call chains
- `--verbose`, `-v`: Show all paths including duplicates

**Examples:**
```bash
# Find unprotected calls
lock-trace unprotected my_function spin

# Multiple required locks
lock-trace unprotected my_function spin,mutex

# Tree view
lock-trace --tree unprotected my_function rcu

# Show all paths
lock-trace --verbose unprotected my_function spin,rtnl

# Exclude error handling paths
lock-trace --exclude-functions error_handler,panic unprotected my_function mutex
```

**Output:**
- Success message if all paths are protected
- List of unprotected paths with missing locks
- Currently held locks for each path

### stats

Get statistics for a function.

**Syntax:**
```
lock-trace stats FUNCTION
```

**Arguments:**
- `FUNCTION`: Function to analyze

**Examples:**
```bash
lock-trace stats my_function
```

**Output:**
- Caller/callee counts (total and unique)
- Call path statistics
- Lock protection summary
- Lock names encountered

## Configuration Examples

### Project Structure Variations

```bash
# Standard layout: everything in current directory
lock-trace callers schedule

# Separate database and source directories
lock-trace -d /build/db -s /src/linux callers schedule

# Custom cscope.out location
lock-trace -f /data/kernel.out -s /src/linux callers schedule

# Complex project setup
lock-trace -d /build -f /build/cscope.out -s /src/kernel callers schedule
```

### Combining Options

```bash
# Tree view with depth limit
lock-trace --tree --max-depth 3 callers schedule

# Verbose mode with custom database
lock-trace -d /kernel/build --verbose lock-context my_func

# Multiple locks with tree view
lock-trace --tree lock-context my_func spin,rtnl

# Exclude functions with custom database
lock-trace -d /build --exclude-functions debug_func,trace_func callers schedule

# Complex example: exclude functions, tree view, depth limit
lock-trace --tree --max-depth 5 --exclude-functions init_func,exit_func,debug_print lock-context critical_func

# Exclude multiple function types
lock-trace --exclude-functions test_,debug_,trace_,print_ --verbose unprotected my_func main_lock
```

## Function Filtering

The `--exclude-functions` option allows you to filter out unwanted call paths from analysis results. This is particularly useful for:

### Common Use Cases

- **Debug Code**: Exclude debugging and tracing functions that clutter analysis results
- **Test Code**: Filter out test functions when analyzing production code paths
- **Initialization**: Skip initialization and cleanup routines
- **Error Handling**: Exclude error handling paths for normal flow analysis

### Filtering Behavior

- **Exact Match**: Function names must match exactly (case-sensitive)
- **Path Exclusion**: If any function in a call path matches the exclude list, the entire path is filtered out
- **All Commands**: Works with all analysis commands (callers, callees, lock-check, etc.)

### Filtering Examples

```bash
# Exclude single function
lock-trace --exclude-functions debug_print callers my_function

# Exclude multiple functions (comma-separated)
lock-trace --exclude-functions debug_print,trace_func,test_helper callers my_function

# Common debugging patterns
lock-trace --exclude-functions printk,pr_debug,pr_info callers kernel_function

# Exclude initialization code
lock-trace --exclude-functions __init,__exit,probe,remove callees driver_function

# Exclude error handling
lock-trace --exclude-functions panic,BUG,WARN_ON unprotected critical_func main_lock

# Exclude directories (using short parameter)
lock-trace -E drivers callers my_function

# Exclude multiple directories
lock-trace -E drivers,fs,mm callers my_function

# Combine function and directory exclusions
lock-trace -e debug_print,trace_func -E drivers,fs callers my_function
```

## Lock Filtering and Matching

The lock-context analysis commands support flexible lock filtering that allows you to specify generic lock types as filters while displaying actual detected lock names.

### Supported Lock Filters

**Generic Filters** → **Matches Real Lock Names:**

| Filter | Matches | Example Real Names |
|--------|---------|-------------------|
| `rcu` | All RCU locks | `rcu_read_lock`, `rcu_read_unlock` |
| `rcu_lock` | All RCU locks | `rcu_read_lock`, `rcu_read_unlock` |
| `spin` | All spinlocks | `spin_lock_bh`, `spin_unlock_bh`, `spin_lock_irq` |
| `spin_lock` | All spinlocks | `spin_lock_bh`, `spin_unlock_bh`, `spin_lock_irq` |
| `mutex` | All mutexes | `mutex_lock`, `mutex_unlock`, `mutex_trylock` |
| `mutex_lock` | All mutexes | `mutex_lock`, `mutex_unlock`, `mutex_trylock` |
| `rtnl` | All RTNL locks | `rtnl_lock`, `rtnl_unlock`, `rtnl_net_lock` |
| `rtnl_lock` | All RTNL locks | `rtnl_lock`, `rtnl_unlock`, `rtnl_net_lock` |
| `netdev` | All netdev locks | `netdev_lock_ops`, `netdev_unlock_ops` |
| `netdev_lock` | All netdev locks | `netdev_lock_ops`, `netdev_unlock_ops` |

### Lock Filtering Examples

```bash
# Filter by spinlocks (displays real names like "spin_lock_bh")
lock-trace lock-context my_function spin

# Filter by RCU locks (displays real names like "rcu_read_lock")
lock-trace lock-context my_function rcu

# Filter by multiple lock types
lock-trace lock-context my_function spin,rcu,mutex

# Use specific lock function names (exact match)
lock-trace lock-context my_function rcu_read_lock,spin_lock_bh

# Check protection with generic filter
lock-trace lock-check my_function spin

# Find unprotected calls with multiple lock types
lock-trace unprotected my_function spin,rtnl
```

### Filter vs Display Behavior

**Important**: Lock filters are used for matching, but the output always shows the actual detected lock names:

```bash
# Input: generic filter
lock-trace lock-context my_function spin

# Output: actual lock names
Held locks: spin_lock_bh
Lock operations:
  acquire spin_lock_bh (spinlock) in caller_function
```

This design provides the convenience of simple filtering while maintaining accuracy by showing real lock names from the code.

## Output Formatting

### Call Path Notation

- **Arrow notation (→)**: Used in default and verbose modes
- **Tree notation**: Uses ├──, └──, and │ characters
- **Function names**: Displayed as-is from cscope
- **Protection status**: ✓ PROTECTED / ✗ UNPROTECTED

### Status Messages

- **Success**: Green checkmark (✓) or success message
- **Warning**: Unprotected paths highlighted
- **Error**: Clear error messages with context
- **Information**: Summary lines and counts

## Exit Codes

- `0`: Success
- `1`: General error (invalid arguments, function not found, etc.)
- `2`: Cscope database error
- `3`: File system error

## Performance Tips

1. **Use depth limits** (`--max-depth`) for large codebases
2. **Default mode** is fastest (no tree building overhead)
3. **Verbose mode** is slowest (shows all paths)
4. **Tree mode** has moderate overhead (tree building)
5. **Specific lock tracking** is faster than analyzing all locks

## Integration Examples

### Shell Scripting

```bash
# Check if function exists
if lock-trace stats my_function >/dev/null 2>&1; then
    echo "Function exists"
fi

# Count callers
callers=$(lock-trace callers my_function | grep -c "→")
echo "Function has $callers callers"

# Find unprotected functions
lock-trace unprotected critical_function main_lock || {
    echo "Critical function has unprotected calls!"
    exit 1
}
```

### CI/CD Integration

```bash
# Ensure critical functions are protected
critical_functions="alloc_memory free_memory update_state"
for func in $critical_functions; do
    if ! lock-trace unprotected "$func" main_lock; then
        echo "ERROR: $func has unprotected calls"
        exit 1
    fi
done
```
