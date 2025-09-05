"""Lock context analyzer for functions called within lock protection."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

from .call_tracer import CallPath, CallTracer
from .cscope_interface import CscopeInterface, FunctionCall


class LockType(Enum):
    """Types of locks that can be analyzed."""

    SPINLOCK = "spinlock"
    MUTEX = "mutex"
    RWLOCK = "rwlock"
    RCU = "rcu"
    SEMAPHORE = "semaphore"
    CUSTOM = "custom"


@dataclass
class LockOperation:
    """Represents a lock operation (acquire/release)."""

    lock_name: str
    lock_type: LockType
    operation: str  # "acquire" or "release"
    function: str
    file: str
    line: int
    context: str


@dataclass
class LockContext:
    """Represents lock context information for a function call."""

    function: str
    held_locks: Set[str]
    call_path: List[str]
    lock_operations: List[LockOperation]


class LockAnalyzer:
    """Analyzes lock contexts in function call paths."""

    # Common lock function patterns
    LOCK_PATTERNS = {
        LockType.SPINLOCK: {
            "acquire": [
                r"spin_lock\s*\(",
                r"spin_lock_irq\s*\(",
                r"spin_lock_irqsave\s*\(",
                r"spin_lock_bh\s*\(",
            ],
            "release": [
                r"spin_unlock\s*\(",
                r"spin_unlock_irq\s*\(",
                r"spin_unlock_irqrestore\s*\(",
                r"spin_unlock_bh\s*\(",
            ],
        },
        LockType.MUTEX: {
            "acquire": [
                r"mutex_lock\s*\(",
                r"mutex_lock_interruptible\s*\(",
                r"mutex_trylock\s*\(",
            ],
            "release": [
                r"mutex_unlock\s*\(",
            ],
        },
        LockType.RWLOCK: {
            "acquire": [
                r"(?<!rcu_)read_lock\s*\(",  # Negative lookbehind to avoid matching rcu_read_lock
                r"(?<!rcu_)write_lock\s*\(",
                r"(?<!rcu_)read_lock_irq\s*\(",
                r"(?<!rcu_)write_lock_irq\s*\(",
                r"(?<!rcu_)read_lock_bh\s*\(",
                r"(?<!rcu_)write_lock_bh\s*\(",
            ],
            "release": [
                r"(?<!rcu_)read_unlock\s*\(",  # Negative lookbehind to avoid matching rcu_read_unlock
                r"(?<!rcu_)write_unlock\s*\(",
                r"(?<!rcu_)read_unlock_irq\s*\(",
                r"(?<!rcu_)write_unlock_irq\s*\(",
                r"(?<!rcu_)read_unlock_bh\s*\(",
                r"(?<!rcu_)write_unlock_bh\s*\(",
            ],
        },
        LockType.RCU: {
            "acquire": [
                r"rcu_read_lock\s*\(",
                r"rcu_read_lock_bh\s*\(",
            ],
            "release": [
                r"rcu_read_unlock\s*\(",
                r"rcu_read_unlock_bh\s*\(",
            ],
        },
        LockType.CUSTOM: {
            "acquire": [
                r"rtnl_lock\s*\(",
                r"rtnl_trylock\s*\(",
                r"rtnl_net_lock\s*\(",
                r"rtnl_nets_lock\s*\(",
                r"netdev_lock_ops\s*\(",
                r"netlink_table_grab\s*\(",
                r"genl_lock\s*\(",
            ],
            "release": [
                r"rtnl_unlock\s*\(",
                r"rtnl_net_unlock\s*\(",
                r"rtnl_nets_unlock\s*\(",
                r"netdev_unlock_ops\s*\(",
                r"netlink_table_ungrab\s*\(",
                r"genl_unlock\s*\(",
            ],
        },
    }

    # Lock matching configuration - maps lock patterns to generic target names
    LOCK_MATCHING_CONFIG = {
        # For RCU locks: lock_name contains these patterns
        "rcu_patterns": {
            "lock_name_patterns": ["rcu_read_lock", "rcu_read_unlock"],
            "generic_targets": ["rcu", "rcu_lock"],
        },
        # For RTNL locks: lock_name contains these patterns
        "rtnl_patterns": {
            "lock_name_patterns": ["rtnl"],
            "generic_targets": ["rtnl", "rtnl_lock"],
        },
        # For netdev locks: lock_name contains these patterns
        "netdev_patterns": {
            "lock_name_patterns": ["netdev_"],
            "generic_targets": ["netdev", "netdev_lock"],
        },
        # For spinlocks: lock_name contains these patterns
        "spin_patterns": {
            "lock_name_patterns": ["spin_lock", "spin_unlock"],
            "generic_targets": ["spin", "spin_lock", "spinlock"],
        },
        # For mutexes: lock_name contains these patterns
        "mutex_patterns": {
            "lock_name_patterns": ["mutex_lock", "mutex_unlock"],
            "generic_targets": ["mutex", "mutex_lock"],
        },
    }

    def __init__(self, cscope: CscopeInterface, call_tracer: CallTracer):
        """Initialize lock analyzer.

        Args:
            cscope: CscopeInterface instance
            call_tracer: CallTracer instance
        """
        self.cscope = cscope
        self.call_tracer = call_tracer
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[LockType, Dict[str, List[re.Pattern]]]:
        """Compile regex patterns for better performance."""
        compiled = {}
        for lock_type, operations in self.LOCK_PATTERNS.items():
            compiled[lock_type] = {}
            for op_type, patterns in operations.items():
                compiled[lock_type][op_type] = [
                    re.compile(pattern) for pattern in patterns
                ]
        return compiled

    async def find_lock_operations(self, function: str) -> List[LockOperation]:
        """Find lock operations within a function.

        Args:
            function: Function name to analyze

        Returns:
            List of LockOperation objects found in the function
        """
        operations = []

        # Get function calls made by this function
        calls = await self.cscope.get_functions_called_by(function)

        for call in calls:
            lock_ops = self._identify_lock_operation(call, function)
            operations.extend(lock_ops)

        return operations

    def _identify_lock_operation(
        self, call: FunctionCall, caller_function: str
    ) -> List[LockOperation]:
        """Identify if a function call is a lock operation.

        Args:
            call: FunctionCall to analyze
            caller_function: Name of the function that makes this call

        Returns:
            List of LockOperation objects (empty if not a lock operation)
        """
        operations = []

        for lock_type, ops in self._compiled_patterns.items():
            for op_type, patterns in ops.items():
                for pattern in patterns:
                    if pattern.search(call.context) or pattern.search(call.function):
                        # Extract lock variable name from context
                        lock_name = self._extract_lock_name(call.context, call.function)
                        operations.append(
                            LockOperation(
                                lock_name=lock_name,
                                lock_type=lock_type,
                                operation=op_type,
                                function=caller_function,
                                file=call.file,
                                line=call.line,
                                context=call.context,
                            )
                        )
                        break

        return operations

    def _extract_lock_name(self, context: str, function_name: str) -> str:
        """Extract lock variable name from context.

        Args:
            context: Context string containing the lock call
            function_name: Name of the lock function

        Returns:
            Extracted lock variable name or function name if extraction fails
        """
        # For certain lock types, use the function name directly instead of extracting variables
        # This is needed for locks where the function name itself is the important identifier
        function_name_prefixes = ["rcu_read_", "rtnl", "netdev_", "netlink_", "genl"]

        if any(function_name.startswith(prefix) for prefix in function_name_prefixes):
            # Additional check for rtnl/netdev to ensure it's actually a lock function
            if function_name.startswith(("rtnl", "netdev_")):
                if "lock" in function_name or "unlock" in function_name:
                    return function_name
            else:
                return function_name

        # Try to extract variable name from function call
        # Look for patterns like "spin_lock(&variable)" or "mutex_lock(&variable)"
        match = re.search(r"\(&?([a-zA-Z_][a-zA-Z0-9_]*)\)", context)
        if match:
            return match.group(1)

        # Try to extract from function call arguments
        match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", context)
        if match and match.group(1) != function_name:
            return match.group(1)

        return function_name

    async def _filter_operations_before_call(
        self,
        caller_function: str,
        target_function: str,
        operations: List[LockOperation],
    ) -> List[LockOperation]:
        """Filter lock operations to only include those before the target function call.

        Args:
            caller_function: Function that calls the target
            target_function: Target function being called
            operations: All lock operations in the caller function

        Returns:
            List of lock operations that occur before the target function call
        """
        # Get the line number where the target function is called
        calls = await self.cscope.get_functions_called_by(caller_function)
        target_call_line = None

        for call in calls:
            if call.function == target_function:
                target_call_line = call.line
                break

        # If we can't find the call, return all operations (fallback to old behavior)
        if target_call_line is None:
            return operations

        # Filter operations to only include those before the target call
        filtered_operations = []
        for op in operations:
            if op.line < target_call_line:
                filtered_operations.append(op)

        return filtered_operations

    def _lock_matches_target(self, lock_name: str, target_locks: List[str]) -> bool:
        """Check if a lock name matches any of the target locks.

        Uses LOCK_MATCHING_CONFIG for pattern-based matching to reduce code duplication.
        Supports both exact matches and generic pattern matching.

        Args:
            lock_name: The detected lock name (e.g. "rcu_read_lock", "spin_lock_bh")
            target_locks: List of target lock names from user

        Returns:
            True if lock matches any target, False otherwise
        """
        # Exact match first (works for specific locks like "rcu_read_lock")
        if lock_name in target_locks:
            return True

        # Check against all configured lock patterns
        for pattern_config in self.LOCK_MATCHING_CONFIG.values():
            lock_name_patterns = pattern_config["lock_name_patterns"]
            generic_targets = pattern_config["generic_targets"]

            # Check if lock_name matches any of the patterns for this lock type
            lock_matches_pattern = any(
                pattern in lock_name.lower() for pattern in lock_name_patterns
            )

            if lock_matches_pattern:
                # Check if any target matches the generic targets for this lock type
                for target in target_locks:
                    if target.lower() in generic_targets:
                        return True

        return False

    def _get_display_lock_name(
        self, lock_name: str, target_locks: Optional[List[str]]
    ) -> str:
        """Get the display name for a lock, always returning the actual detected lock name.

        Args:
            lock_name: The detected lock name (e.g. "rcu_read_lock", "spin_lock_bh")
            target_locks: List of target lock names from user (used for filtering only)

        Returns:
            The actual detected lock name to display to the user
        """
        # Always return the actual detected lock name, not the filter name
        return lock_name

    async def analyze_lock_context(
        self,
        target_function: str,
        target_locks: Optional[List[str]] = None,
        unique_only: bool = True,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[LockContext]:
        """Analyze lock context for a target function.

        Args:
            target_function: Function to analyze lock context for
            target_locks: Specific locks to check for (all locks if None)
            unique_only: Whether to return only unique call chains (default: True)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of LockContext objects showing lock states in call paths
        """
        contexts = []

        # Get caller paths - unique or all based on parameter
        if unique_only:
            call_paths = await self.call_tracer.get_unique_call_chains(
                target_function,
                exclude_functions=exclude_functions,
                exclude_directories=exclude_directories,
            )
        else:
            call_paths = await self.call_tracer.trace_callers(
                target_function,
                exclude_functions=exclude_functions,
                exclude_directories=exclude_directories,
            )

        for path in call_paths:
            lock_context = await self._analyze_path_locks(path, target_locks)
            contexts.append(lock_context)

        return contexts

    async def _analyze_path_locks(
        self, call_path: CallPath, target_locks: Optional[List[str]] = None
    ) -> LockContext:
        """Analyze locks held along a specific call path.

        Args:
            call_path: CallPath to analyze
            target_locks: Specific locks to track

        Returns:
            LockContext with lock information for this path
        """
        held_locks = set()
        all_operations = []
        protected_by_locks = set()  # Track locks that provide protection along the path

        # Walk through the call path and track lock operations
        # Exclude the target function (last in path) from lock operations analysis
        path_functions = (
            call_path.functions[:-1] if len(call_path.functions) > 1 else []
        )

        for i, function in enumerate(path_functions):
            operations = await self.find_lock_operations(function)
            original_operations = operations.copy()  # Keep all operations for display

            # For the function that directly calls the target function,
            # we need to filter lock operations by call order for state tracking
            if i == len(path_functions) - 1:  # Function that calls the target
                target_function = call_path.functions[-1]
                operations = await self._filter_operations_before_call(
                    function, target_function, operations
                )

            # Track lock operations in this function for state management
            function_acquires = set()
            function_releases = set()

            # For display: always show all operations regardless of target_locks filter
            # The target_locks filter only affects the "Held locks" state, not the operations display
            operations_for_display = original_operations

            for op in operations:
                # Check if this operation matches target filter for state tracking
                matches_target = not target_locks or self._lock_matches_target(
                    op.lock_name, target_locks
                )

                if matches_target:
                    # Always use the actual detected lock name for display
                    display_name = op.lock_name

                    if op.operation == "acquire":
                        held_locks.add(display_name)
                        function_acquires.add(display_name)
                        protected_by_locks.add(display_name)
                    elif op.operation == "release":
                        held_locks.discard(display_name)
                        function_releases.add(display_name)

            # Add operations for display purposes - only from calling functions
            all_operations.extend(operations_for_display)

            # For functions that have complete lock sections (acquire + release),
            # still consider the target function as being protected
            for lock in function_acquires:
                if lock in function_releases:
                    # This function has a complete lock section
                    protected_by_locks.add(lock)

        # If we found protection evidence but no currently held locks,
        # use the protection evidence (only when not filtering by target_locks)
        if not held_locks and protected_by_locks and not target_locks:
            held_locks = protected_by_locks

        return LockContext(
            function=call_path.functions[-1] if call_path.functions else "",
            held_locks=held_locks,
            call_path=call_path.functions,
            lock_operations=all_operations,
        )

    async def check_lock_protection(
        self,
        function: str,
        lock_name: str,
        unique_only: bool = True,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> Dict[str, bool]:
        """Check if a function is called with specific lock protection.

        Args:
            function: Function to check
            lock_name: Name of the lock to check for
            unique_only: Whether to return only unique call chains (default: True)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            Dictionary with call paths and whether they have lock protection
        """
        results = {}
        contexts = await self.analyze_lock_context(
            function, [lock_name], unique_only, exclude_functions, exclude_directories
        )

        for context in contexts:
            path_str = " -> ".join(context.call_path)
            results[path_str] = lock_name in context.held_locks

        return results

    async def find_unprotected_calls(
        self,
        function: str,
        required_locks: List[str],
        unique_only: bool = True,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[LockContext]:
        """Find call paths where function is called without required lock protection.

        Args:
            function: Function that requires lock protection
            required_locks: List of locks that should be held
            unique_only: Whether to return only unique call chains (default: True)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of LockContext objects for unprotected call paths
        """
        unprotected = []
        contexts = await self.analyze_lock_context(
            function,
            required_locks,
            unique_only,
            exclude_functions,
            exclude_directories,
        )

        for context in contexts:
            # Check if any required lock is missing
            missing_locks = set(required_locks) - context.held_locks
            if missing_locks:
                unprotected.append(context)

        return unprotected

    async def get_lock_summary(self, function: str) -> Dict[str, any]:
        """Get a summary of lock usage for a function.

        Args:
            function: Function to analyze

        Returns:
            Dictionary with lock usage summary
        """
        contexts = await self.analyze_lock_context(function)

        all_locks = set()
        protected_paths = 0
        unprotected_paths = 0

        for context in contexts:
            all_locks.update(context.held_locks)
            if context.held_locks:
                protected_paths += 1
            else:
                unprotected_paths += 1

        return {
            "function": function,
            "total_call_paths": len(contexts),
            "protected_paths": protected_paths,
            "unprotected_paths": unprotected_paths,
            "locks_encountered": list(all_locks),
            "lock_count": len(all_locks),
        }
