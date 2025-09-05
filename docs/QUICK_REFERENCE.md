# Quick Reference: New Display Features

## Display Modes Summary

| Mode | Flag | Description | Use Case |
|------|------|-------------|----------|
| **Default** | (none) | Unique call chains, flat list | Quick analysis, clean output |
| **Tree** | `--tree`, `-t` | Unique call chains, tree view | Visualizing call hierarchy |
| **Verbose** | `--verbose`, `-v` | All paths including duplicates | Comprehensive analysis |

## Command Quick Reference

### Function Call Analysis
```bash
# Unique callers (default)
lock-trace callers function_name

# Tree view of callers
lock-trace callers function_name --tree

# All caller paths (including duplicates)
lock-trace callers function_name --verbose

# Same options work for callees
lock-trace callees function_name [--tree|--verbose]
```

### Lock Analysis Commands

#### Lock Protection Check
```bash
# Check lock protection (unique paths)
lock-trace lock-check my_func lock_var

# Tree view with protection status
lock-trace lock-check my_func lock_var --tree

# All paths including duplicates
lock-trace lock-check my_func lock_var --verbose
```

#### Lock Context Analysis
```bash
# Analyze lock context (unique paths)
lock-trace lock-context my_func

# Tree view of lock context
lock-trace lock-context my_func --tree

# All paths with lock details
lock-trace lock-context my_func --verbose

# Track specific locks only
lock-trace lock-context my_func spin,rcu
```

#### Find Unprotected Calls
```bash
# Find unprotected calls (unique paths)
lock-trace unprotected my_func lock_var

# Tree view of unprotected calls
lock-trace --tree unprotected my_func lock_var

# All unprotected paths
lock-trace --verbose unprotected my_func lock_var
```

## Output Format Comparison

### Default Mode
```
Unique call chains to function 'schedule':
==================================================
  - init_task → kernel_thread → schedule
  - kthreadd → kthread_create → schedule
  - worker_thread → process_one_work → schedule

Unique call chains found: 3
```

### Tree Mode (`--tree`)
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

### Verbose Mode (`--verbose`)
```
All call paths to function 'schedule':
==================================================
  1: init_task → kernel_thread → schedule
  2: init_task → kernel_thread → schedule
  3: kthreadd → kthread_create → schedule
  4: worker_thread → process_one_work → schedule
  5: worker_thread → process_one_work → schedule

Total paths found: 5
```

## Migration Guide

### Before (old behavior)
```bash
# Old commands showed all paths including duplicates
lock-trace callers schedule        # Showed duplicates
lock-trace lock-context my_func    # Showed duplicates
lock-trace lock-check my_func lock # Showed duplicates
```

### After (new behavior)
```bash
# Default now shows unique paths (cleaner)
lock-trace callers schedule                # Unique paths (NEW DEFAULT)
lock-trace lock-context my_func            # Unique paths (NEW DEFAULT)
lock-trace lock-check my_func lock         # Unique paths (NEW DEFAULT)

# Use --verbose for old behavior
lock-trace callers schedule --verbose      # Same as old default
lock-trace lock-context my_func --verbose  # Same as old default
lock-trace lock-check my_func lock --verbose # Same as old default

# New tree visualization
lock-trace callers schedule --tree         # NEW FEATURE
lock-trace lock-context my_func --tree     # NEW FEATURE
lock-trace lock-check my_func lock --tree  # NEW FEATURE
```

## Best Practices

### When to Use Each Mode

1. **Default mode**: 
   - Daily analysis and debugging
   - When you want clean, deduplicated output
   - For scripting and automation

2. **Tree mode (`--tree`)**:
   - Understanding call flow structure
   - Visualizing complex call hierarchies
   - Documentation and presentations

3. **Verbose mode (`--verbose`)**:
   - Comprehensive auditing
   - When you need to see every possible path
   - Debugging path analysis issues

### Performance Considerations

- **Fastest**: Default mode (minimal processing)
- **Medium**: Tree mode (builds tree structure)
- **Slowest**: Verbose mode (shows all paths)

### Combining with Other Options

```bash
# Depth limit with tree view
lock-trace callers schedule --tree --max-depth 5

# Custom database with verbose output
lock-trace -d /kernel lock-context my_func --verbose

# Multiple locks with tree visualization
lock-trace --tree lock-context my_func spin,mutex
```