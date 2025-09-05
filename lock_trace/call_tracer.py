"""Call stack tracer for building function call chains."""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from .cscope_interface import CscopeInterface, FunctionCall


@dataclass
class CallPath:
    """Represents a path in the call stack."""

    functions: List[str]
    depth: int

    def __str__(self) -> str:
        return " -> ".join(self.functions)


@dataclass
class CallGraph:
    """Represents the call graph for analysis."""

    callers: Dict[str, List[FunctionCall]]  # function -> list of callers
    callees: Dict[str, List[FunctionCall]]  # function -> list of callees

    def __init__(self):
        self.callers = defaultdict(list)
        self.callees = defaultdict(list)


class CallTracer:
    """Traces function call stacks using cscope data."""

    def __init__(
        self,
        cscope: CscopeInterface,
        max_depth: int = 10,
        enable_callback_search: bool = True,
    ):
        """Initialize call tracer.

        Args:
            cscope: CscopeInterface instance
            max_depth: Maximum depth for call stack traversal
            enable_callback_search: Whether to enable enhanced callback function search
        """
        self.cscope = cscope
        self.max_depth = max_depth
        self.enable_callback_search = enable_callback_search
        self._call_graph = CallGraph()
        self._cached_functions: Set[str] = set()

    async def _should_exclude_path(
        self,
        path: List[str],
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> bool:
        """Check if a path should be excluded based on excluded functions and directories.

        Args:
            path: List of function names in the path
            exclude_functions: Set of function names to exclude
            exclude_directories: Set of directory names to exclude

        Returns:
            True if the path contains any excluded function or function from excluded directories
        """
        # Check function exclusions
        if exclude_functions and any(func in exclude_functions for func in path):
            return True

        # Check directory exclusions
        if exclude_directories:
            for func in path:
                # Try to find the function definition to get its file location
                func_def = await self.cscope.find_function_definition(func)
                if func_def and func_def.file:
                    # Check if any excluded directory is in the file path
                    for excluded_dir in exclude_directories:
                        if excluded_dir in func_def.file:
                            return True

        return False

    async def build_call_graph(self, root_functions: List[str]) -> CallGraph:
        """Build call graph starting from root functions.

        Args:
            root_functions: List of root functions to start analysis from

        Returns:
            CallGraph containing caller/callee relationships
        """
        visited = set()
        queue = deque(root_functions)

        while queue:
            function = queue.popleft()
            if function in visited:
                continue

            visited.add(function)

            # Get functions called by this function
            callees = await self.cscope.get_functions_called_by(function)
            self._call_graph.callees[function] = callees

            # Get functions calling this function
            callers = await self.cscope.get_functions_calling(function)
            self._call_graph.callers[function] = callers

            # Add new functions to queue for analysis
            for call in callees:
                if call.function not in visited:
                    queue.append(call.function)

            for call in callers:
                if call.function not in visited:
                    queue.append(call.function)

        return self._call_graph

    async def trace_callers(
        self,
        target_function: str,
        max_depth: Optional[int] = None,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[CallPath]:
        """Trace all caller paths to a target function.

        Args:
            target_function: Function to trace callers for
            max_depth: Maximum depth to trace (uses instance default if None)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of CallPath objects showing paths to target function
        """
        if max_depth is None:
            max_depth = self.max_depth

        paths = []
        visited = set()

        async def _trace_recursive(current_func: str, path: List[str], depth: int):
            if (max_depth is not None and depth > max_depth) or current_func in visited:
                return

            # Add current path if not excluded
            current_path = path + [current_func]
            reversed_path = list(reversed(current_path))
            if not await self._should_exclude_path(
                reversed_path, exclude_functions, exclude_directories
            ):
                paths.append(CallPath(functions=reversed_path, depth=depth))

            # Continue tracing callers
            visited.add(current_func)

            # Get callers using enhanced search if enabled
            if self.enable_callback_search:
                callers = await self.cscope.get_callback_callers(current_func)
            else:
                callers = await self.cscope.get_functions_calling(current_func)

            for caller in callers:
                await _trace_recursive(caller.function, current_path, depth + 1)

            visited.remove(current_func)

        await _trace_recursive(target_function, [], 0)
        return paths

    async def trace_callees(
        self,
        source_function: str,
        max_depth: Optional[int] = None,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[CallPath]:
        """Trace all callee paths from a source function.

        Args:
            source_function: Function to trace callees from
            max_depth: Maximum depth to trace (uses instance default if None)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of CallPath objects showing paths from source function
        """
        if max_depth is None:
            max_depth = self.max_depth

        paths = []
        visited = set()

        async def _trace_recursive(current_func: str, path: List[str], depth: int):
            if (max_depth is not None and depth > max_depth) or current_func in visited:
                return

            # Add current path if not excluded
            current_path = path + [current_func]
            if not await self._should_exclude_path(
                current_path, exclude_functions, exclude_directories
            ):
                paths.append(CallPath(functions=current_path, depth=depth))

            # Continue tracing callees
            visited.add(current_func)
            callees = await self.cscope.get_functions_called_by(current_func)

            for callee in callees:
                await _trace_recursive(callee.function, current_path, depth + 1)

            visited.remove(current_func)

        await _trace_recursive(source_function, [], 0)
        return paths

    async def find_call_paths(
        self, from_function: str, to_function: str, max_depth: Optional[int] = None
    ) -> List[CallPath]:
        """Find all call paths from one function to another.

        Args:
            from_function: Starting function
            to_function: Target function
            max_depth: Maximum depth to search

        Returns:
            List of CallPath objects showing paths from source to target
        """
        if max_depth is None:
            max_depth = self.max_depth

        paths = []

        async def _find_paths_recursive(
            current_func: str,
            target: str,
            path: List[str],
            depth: int,
            visited: Set[str],
        ):
            if max_depth is not None and depth > max_depth:
                return

            if current_func == target:
                paths.append(CallPath(functions=path + [current_func], depth=depth))
                return

            if current_func in visited:
                return

            visited.add(current_func)
            callees = await self.cscope.get_functions_called_by(current_func)

            for callee in callees:
                await _find_paths_recursive(
                    callee.function,
                    target,
                    path + [current_func],
                    depth + 1,
                    visited.copy(),
                )

        await _find_paths_recursive(from_function, to_function, [], 0, set())
        return paths

    async def get_function_depth_map(self, root_functions: List[str]) -> Dict[str, int]:
        """Get minimum depth of each function from root functions.

        Args:
            root_functions: List of root functions (depth 0)

        Returns:
            Dictionary mapping function names to their minimum depth
        """
        depth_map = {}
        queue = deque([(func, 0) for func in root_functions])

        while queue:
            function, depth = queue.popleft()

            if function in depth_map and depth_map[function] <= depth:
                continue

            depth_map[function] = depth

            # Add callees at next depth level
            callees = await self.cscope.get_functions_called_by(function)
            for callee in callees:
                queue.append((callee.function, depth + 1))

        return depth_map

    async def get_call_statistics(self, function: str) -> Dict[str, int]:
        """Get call statistics for a function.

        Args:
            function: Function to analyze

        Returns:
            Dictionary with call statistics
        """
        callers = await self.cscope.get_functions_calling(function)
        callees = await self.cscope.get_functions_called_by(function)

        return {
            "caller_count": len(callers),
            "callee_count": len(callees),
            "unique_callers": len({call.function for call in callers}),
            "unique_callees": len({call.function for call in callees}),
        }

    async def get_unique_call_chains(
        self,
        target_function: str,
        max_depth: Optional[int] = None,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[CallPath]:
        """Get unique, complete call chains to a target function.

        Removes duplicate paths and returns only the longest complete chains.

        Args:
            target_function: Function to trace callers for
            max_depth: Maximum depth to trace
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of unique CallPath objects representing complete call chains
        """
        all_paths = await self.trace_callers(
            target_function, max_depth, exclude_functions, exclude_directories
        )

        # Group paths by their string representation
        path_groups = {}
        for path in all_paths:
            path_str = " -> ".join(path.functions)
            if path_str not in path_groups or len(path.functions) > len(
                path_groups[path_str].functions
            ):
                path_groups[path_str] = path

        # Filter out paths that are subsets of longer paths
        unique_paths = []
        sorted_paths = sorted(
            path_groups.values(), key=lambda p: len(p.functions), reverse=True
        )

        for path in sorted_paths:
            path_functions = path.functions
            is_subset = False

            # Check if this path is a subset of any longer path already added
            for existing_path in unique_paths:
                existing_functions = existing_path.functions
                if len(path_functions) < len(existing_functions):
                    # Check if this path is a suffix of the existing path
                    if existing_functions[-len(path_functions) :] == path_functions:
                        is_subset = True
                        break

            if not is_subset:
                unique_paths.append(path)

        # Sort by depth and then by first function name for consistent output
        unique_paths.sort(
            key=lambda p: (len(p.functions), p.functions[0] if p.functions else "")
        )

        return unique_paths

    async def get_unique_callee_chains(
        self,
        source_function: str,
        max_depth: Optional[int] = None,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> List[CallPath]:
        """Get unique, complete callee chains from a source function.

        Removes duplicate paths and returns only the longest complete chains.

        Args:
            source_function: Function to trace callees from
            max_depth: Maximum depth to trace
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths

        Returns:
            List of unique CallPath objects representing complete callee chains
        """
        all_paths = await self.trace_callees(
            source_function, max_depth, exclude_functions, exclude_directories
        )

        # Group paths by their string representation
        path_groups = {}
        for path in all_paths:
            path_str = " -> ".join(path.functions)
            if path_str not in path_groups or len(path.functions) > len(
                path_groups[path_str].functions
            ):
                path_groups[path_str] = path

        # Filter out paths that are subsets of longer paths
        unique_paths = []
        sorted_paths = sorted(
            path_groups.values(), key=lambda p: len(p.functions), reverse=True
        )

        for path in sorted_paths:
            path_functions = path.functions
            is_subset = False

            # Check if this path is a subset of any longer path already added
            for existing_path in unique_paths:
                existing_functions = existing_path.functions
                if len(path_functions) < len(existing_functions):
                    # Check if this path is a prefix of the existing path
                    if existing_functions[: len(path_functions)] == path_functions:
                        is_subset = True
                        break

            if not is_subset:
                unique_paths.append(path)

        # Sort by depth and then by first function name for consistent output
        unique_paths.sort(
            key=lambda p: (len(p.functions), p.functions[0] if p.functions else "")
        )

        return unique_paths

    def build_call_tree(self, paths: List[CallPath]) -> Dict[str, Any]:
        """Build a tree structure from call paths.

        Args:
            paths: List of CallPath objects

        Returns:
            Dictionary representing the call tree structure
        """
        tree = {}

        for path in paths:
            current = tree

            # Traverse/build the tree for this path
            for i, function in enumerate(path.functions):
                if function not in current:
                    current[function] = {
                        "_children": {},
                        "_is_leaf": i == len(path.functions) - 1,
                        "_depth": i,
                    }

                # Update leaf status - a node is a leaf only if it has no children
                if i < len(path.functions) - 1:
                    current[function]["_is_leaf"] = False

                current = current[function]["_children"]

        return tree

    def format_tree(
        self,
        tree: Dict[str, Any],
        target_function: str,
        prefix: str = "",
        is_last: bool = True,
    ) -> List[str]:
        """Format tree structure as text with tree-like visual representation.

        Args:
            tree: Tree structure from build_call_tree
            target_function: The target function being traced
            prefix: Current line prefix for tree formatting
            is_last: Whether this is the last node at current level

        Returns:
            List of formatted strings representing the tree
        """
        lines = []

        # Sort functions by name for consistent output
        functions = sorted(tree.keys())

        for i, function in enumerate(functions):
            node = tree[function]
            is_last_child = i == len(functions) - 1

            # Choose the appropriate tree characters
            if prefix == "":
                # Root level - no connector for first level
                connector = ""
                # For children of root nodes, use appropriate spacing
                new_prefix = "    "
            else:
                connector = "└── " if is_last_child else "├── "
                new_prefix = prefix + ("    " if is_last_child else "│   ")

            # Format the function name (no special highlighting)
            function_display = function

            lines.append(f"{prefix}{connector}{function_display}")

            # Recursively format children
            children = node["_children"]
            if children:
                child_lines = self.format_tree(
                    children, target_function, new_prefix, is_last_child
                )
                lines.extend(child_lines)

        return lines
