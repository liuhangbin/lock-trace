"""Command-line interface for lock-trace."""

import argparse
import asyncio
import sys
from typing import Dict, List, Optional, Set

from .call_tracer import CallTracer
from .cscope_interface import CscopeInterface
from .lock_analyzer import LockAnalyzer


class LockTraceCLI:
    """Command-line interface for lock-trace tool."""

    def __init__(self):
        """Initialize CLI."""
        self.cscope = None
        self.tracer = None
        self.analyzer = None

    async def setup(
        self,
        database_path: str,
        max_depth: int = 1,
        cscope_file: Optional[str] = None,
        source_dir: Optional[str] = None,
        enable_callback_search: bool = True,
    ):
        """Setup the analysis tools.

        Args:
            database_path: Path to cscope database directory
            max_depth: Maximum depth for call tracing
            cscope_file: Path to cscope.out file
            source_dir: Path to source code directory
            enable_callback_search: Whether to enable enhanced callback function search
        """
        try:
            self.cscope = CscopeInterface(database_path, cscope_file, source_dir)
            await self.cscope._validate_database()
            self.tracer = CallTracer(self.cscope, max_depth, enable_callback_search)
            self.analyzer = LockAnalyzer(self.cscope, self.tracer)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    async def trace_callers(
        self,
        function: str,
        max_depth: Optional[int] = None,
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Trace and print caller paths for a function.

        Args:
            function: Function to trace callers for
            max_depth: Maximum depth to trace
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        await self._trace_function_paths(
            function,
            "callers",
            max_depth,
            tree,
            verbose,
            exclude_functions,
            exclude_directories,
        )

    async def _trace_function_paths(
        self,
        function: str,
        direction: str,
        max_depth: Optional[int] = None,
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Unified function to trace caller or callee paths.

        Args:
            function: Function to trace paths for
            direction: "callers" or "callees"
            max_depth: Maximum depth to trace
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        if not await self.cscope.function_exists(function):
            print(
                f"Error: Function '{function}' not found in cscope database",
                file=sys.stderr,
            )
            return

        # Determine direction-specific text and methods
        if direction == "callers":
            direction_text = "to"

            async def get_all_paths(func, depth):
                return await self.tracer.trace_callers(
                    func, depth, exclude_functions, exclude_directories
                )

            async def get_unique_paths(func, depth):
                return await self.tracer.get_unique_call_chains(
                    func, depth, exclude_functions, exclude_directories
                )

        else:  # callees
            direction_text = "from"

            async def get_all_paths(func, depth):
                return await self.tracer.trace_callees(
                    func, depth, exclude_functions, exclude_directories
                )

            async def get_unique_paths(func, depth):
                return await self.tracer.get_unique_callee_chains(
                    func, depth, exclude_functions, exclude_directories
                )

        if tree:
            # Use unique call chains for tree display
            paths = await get_unique_paths(function, max_depth)

            if not paths:
                print(f"No {direction} paths found.")
                return

            print(f"Call tree {direction_text} function '{function}':")
            print("=" * 50)

            # Build and format tree
            call_tree = self.tracer.build_call_tree(paths)
            tree_lines = self.tracer.format_tree(call_tree, function)

            for line in tree_lines:
                print(line)

            print(f"\nUnique call chains found: {len(paths)}")
        elif verbose:
            # Verbose: show all paths (original behavior)
            paths = await get_all_paths(function, max_depth)

            if not paths:
                print(f"No {direction} paths found.")
                return

            print(f"All call paths {direction_text} function '{function}':")
            print("=" * 50)

            for i, path in enumerate(paths, 1):
                print(f"{i:3d}: {path}")

            print(f"\nTotal paths found: {len(paths)}")
        else:
            # Default: flattened unique call chains
            paths = await get_unique_paths(function, max_depth)

            if not paths:
                print(f"No {direction} paths found.")
                return

            print(f"Unique call chains {direction_text} function '{function}':")
            print("=" * 50)

            for path in paths:
                chain_str = " → ".join(path.functions)
                print(f"  - {chain_str}")

            print(f"\nUnique call chains found: {len(paths)}")

    async def trace_callees(
        self,
        function: str,
        max_depth: Optional[int] = None,
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Trace and print callee paths from a function.

        Args:
            function: Function to trace callees from
            max_depth: Maximum depth to trace
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        await self._trace_function_paths(
            function,
            "callees",
            max_depth,
            tree,
            verbose,
            exclude_functions,
            exclude_directories,
        )

    async def check_lock_protection(
        self,
        function: str,
        lock_name: str,
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Check if function is called with lock protection.

        Args:
            function: Function to check
            lock_name: Lock to check for
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        if not await self.cscope.function_exists(function):
            print(
                f"Error: Function '{function}' not found in cscope database",
                file=sys.stderr,
            )
            return

        print(
            f"Lock protection analysis for function '{function}' with lock '{lock_name}':"
        )
        print("=" * 70)

        # Get results based on verbose flag (unique vs all paths)
        unique_only = not verbose
        results = await self.analyzer.check_lock_protection(
            function, lock_name, unique_only, exclude_functions, exclude_directories
        )

        if not results:
            print("No call paths found for analysis.")
            return

        protected_count = sum(1 for protected in results.values() if protected)
        total_count = len(results)

        print(f"Summary: {protected_count}/{total_count} paths have lock protection\n")

        if tree:
            # Display as tree structure with protection status
            self._display_protection_tree(function, lock_name, results)
        else:
            # Display as list
            for path, protected in results.items():
                status = "✓ PROTECTED" if protected else "✗ UNPROTECTED"
                print(f"{status}: {path}")

    async def analyze_lock_context(
        self,
        function: str,
        locks: Optional[List[str]] = None,
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Analyze lock context for a function.

        Args:
            function: Function to analyze
            locks: Specific locks to check for
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        if not await self.cscope.function_exists(function):
            print(
                f"Error: Function '{function}' not found in cscope database",
                file=sys.stderr,
            )
            return

        print(f"Lock context analysis for function '{function}':")
        if locks:
            print(f"Tracking locks: {', '.join(locks)}")
        print("=" * 70)

        # Get contexts based on verbose flag (unique vs all paths)
        unique_only = not verbose
        contexts = await self.analyzer.analyze_lock_context(
            function, locks, unique_only, exclude_functions, exclude_directories
        )

        if not contexts:
            print("No call paths found for analysis.")
            return

        if tree:
            # Display as tree structure with lock information
            self._display_lock_context_tree(function, contexts, locks)
        else:
            # Display as list
            for i, context in enumerate(contexts, 1):
                path_str = " → ".join(context.call_path)
                # When no specific locks are requested from CLI, always show "None"
                if locks is None:
                    held_locks = ["None"]
                else:
                    held_locks = (
                        list(context.held_locks) if context.held_locks else ["None"]
                    )

                print(f"{i:3d}: {path_str}")
                print(f"     Held locks: {', '.join(held_locks)}")

                if context.lock_operations:
                    print("     Lock operations:")
                    for op in context.lock_operations:
                        # Special display for different custom lock types
                        if op.lock_type.value == "custom":
                            if op.lock_name.lower().startswith("rtnl"):
                                lock_type_display = "rtnl"
                            elif op.lock_name.lower().startswith("netdev"):
                                lock_type_display = "netdev"
                            elif (
                                "netlink" in op.lock_name.lower()
                                or "genl" in op.lock_name.lower()
                            ):
                                lock_type_display = "netlink"
                            else:
                                lock_type_display = "custom"
                        else:
                            lock_type_display = op.lock_type.value
                        print(
                            f"       {op.operation} {op.lock_name} ({lock_type_display}) in {op.function}"
                        )
                print()

        print(f"\nCall chains found: {len(contexts)}")

    async def find_unprotected_calls(
        self,
        function: str,
        required_locks: List[str],
        tree: bool = False,
        verbose: bool = False,
        exclude_functions: Optional[Set[str]] = None,
        exclude_directories: Optional[Set[str]] = None,
    ) -> None:
        """Find unprotected calls to a function.

        Args:
            function: Function that requires protection
            required_locks: List of required locks
            tree: Whether to display results as a tree structure
            verbose: Whether to show all paths (including duplicates)
            exclude_functions: Set of function names to exclude from paths
            exclude_directories: Set of directory names to exclude from paths
        """
        if not await self.cscope.function_exists(function):
            print(
                f"Error: Function '{function}' not found in cscope database",
                file=sys.stderr,
            )
            return

        print(f"Unprotected calls to function '{function}':")
        print(f"Required locks: {', '.join(required_locks)}")
        print("=" * 70)

        # Get unprotected calls based on verbose flag (unique vs all paths)
        unique_only = not verbose
        unprotected = await self.analyzer.find_unprotected_calls(
            function,
            required_locks,
            unique_only,
            exclude_functions,
            exclude_directories,
        )

        if not unprotected:
            print("✓ All call paths are properly protected!")
            return

        print(f"Found {len(unprotected)} unprotected call paths:\n")

        if tree:
            # Display as tree structure with missing lock information
            self._display_unprotected_tree(function, unprotected, required_locks)
        else:
            # Display as list
            for i, context in enumerate(unprotected, 1):
                path_str = " → ".join(context.call_path)
                missing_locks = set(required_locks) - context.held_locks

                print(f"{i:3d}: {path_str}")
                print(f"     Missing locks: {', '.join(missing_locks)}")
                if context.held_locks:
                    print(f"     Held locks: {', '.join(context.held_locks)}")
                print()

    async def get_function_stats(self, function: str) -> None:
        """Get statistics for a function.

        Args:
            function: Function to analyze
        """
        if not await self.cscope.function_exists(function):
            print(
                f"Error: Function '{function}' not found in cscope database",
                file=sys.stderr,
            )
            return

        # Get call statistics
        call_stats = await self.tracer.get_call_statistics(function)

        # Get lock summary
        lock_summary = await self.analyzer.get_lock_summary(function)

        print(f"Statistics for function '{function}':")
        print("=" * 50)
        print(
            f"Callers: {call_stats['caller_count']} ({call_stats['unique_callers']} unique)"
        )
        print(
            f"Callees: {call_stats['callee_count']} ({call_stats['unique_callees']} unique)"
        )
        print(f"Call paths: {lock_summary['total_call_paths']}")
        print(f"Protected paths: {lock_summary['protected_paths']}")
        print(f"Unprotected paths: {lock_summary['unprotected_paths']}")
        print(f"Locks encountered: {lock_summary['lock_count']}")

        if lock_summary["locks_encountered"]:
            print(f"Lock names: {', '.join(lock_summary['locks_encountered'])}")

    def _display_protection_tree(
        self, function: str, lock_name: str, results: Dict[str, bool]
    ) -> None:
        """Display lock protection results as a tree structure.

        Args:
            function: Target function
            lock_name: Lock being checked
            results: Dictionary mapping call paths to protection status
        """
        # Convert results back to CallPath objects for tree building
        from .call_tracer import CallPath

        paths = []
        for path_str in results.keys():
            functions = path_str.split(" -> ")
            paths.append(CallPath(functions=functions, depth=len(functions) - 1))

        # Build and format tree
        call_tree = self.tracer.build_call_tree(paths)
        tree_lines = self.tracer.format_tree(call_tree, function)

        print("Protection status tree:")
        for line in tree_lines:
            # Add protection status to each function if it's the target
            if function in line:
                # Find matching path for this line
                for path_str, protected in results.items():
                    if path_str.endswith(function):
                        status = " [✓ PROTECTED]" if protected else " [✗ UNPROTECTED]"
                        line = line.replace(function, function + status)
                        break
            print(line)

    def _display_lock_context_tree(
        self, function: str, contexts: List, locks: Optional[List[str]] = None
    ) -> None:
        """Display lock context results as a tree structure.

        Args:
            function: Target function
            contexts: List of LockContext objects
            locks: List of specific locks requested (None if no specific locks)
        """
        from .call_tracer import CallPath

        paths = []
        for context in contexts:
            path = CallPath(
                functions=context.call_path, depth=len(context.call_path) - 1
            )
            paths.append(path)

        # Build and format tree
        call_tree = self.tracer.build_call_tree(paths)
        tree_lines = self.tracer.format_tree(call_tree, function)

        print("Lock context tree:")
        for line in tree_lines:
            print(line)

        # Show lock details for each unique path
        print("\nLock context details:")
        for i, context in enumerate(contexts, 1):
            # When no specific locks are requested from CLI, always show "None"
            if locks is None:
                held_locks = ["None"]
            else:
                held_locks = (
                    list(context.held_locks) if context.held_locks else ["None"]
                )
            print(f"{i:3d}: Held locks: {', '.join(held_locks)}")

    def _display_unprotected_tree(
        self, function: str, unprotected: List, required_locks: List[str]
    ) -> None:
        """Display unprotected calls as a tree structure.

        Args:
            function: Target function
            unprotected: List of unprotected LockContext objects
            required_locks: List of required locks
        """
        from .call_tracer import CallPath

        paths = []
        for context in unprotected:
            path = CallPath(
                functions=context.call_path, depth=len(context.call_path) - 1
            )
            paths.append(path)

        # Build and format tree
        call_tree = self.tracer.build_call_tree(paths)
        tree_lines = self.tracer.format_tree(call_tree, function)

        print("Unprotected calls tree:")
        for line in tree_lines:
            print(line)

        # Show missing lock details
        print("\nMissing lock details:")
        for i, context in enumerate(unprotected, 1):
            missing_locks = set(required_locks) - context.held_locks
            held_locks = list(context.held_locks) if context.held_locks else []
            print(f"{i:3d}: Missing: {', '.join(missing_locks)}")
            if held_locks:
                print(f"     Held: {', '.join(held_locks)}")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Static analysis tool for kernel function call stacks and lock contexts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lock-trace --max-depth 5 callers schedule
  lock-trace --tree callers schedule  # Tree structure display
  lock-trace --verbose callers schedule  # Show all paths including duplicates
  lock-trace --max-depth 3 callees kmalloc
  lock-trace -f /path/to/cscope.out -s /path/to/source callers schedule
  lock-trace lock-check my_function spinlock_var
  lock-trace --tree lock-check my_function spinlock_var  # Tree display
  lock-trace --verbose lock-check my_function spinlock_var  # Show all paths
  lock-trace lock-context my_function spinlock_var,mutex_var
  lock-trace --tree lock-context my_function  # Tree display (analyze all locks)
  lock-trace --verbose lock-context my_function spinlock_var  # Show all paths for specific lock
  lock-trace unprotected my_function spinlock_var
  lock-trace --tree unprotected my_function spinlock_var
  lock-trace --verbose unprotected my_function spinlock_var,mutex_var
  lock-trace --exclude-functions debug_print,trace_func callers schedule
  lock-trace --exclude-functions init_func,cleanup_func --tree lock-context critical_func
  lock-trace --exclude-directories drivers,fs callers schedule
  lock-trace -E drivers,fs callers schedule
  lock-trace --exclude-directories drivers --exclude-functions debug_print --tree callers schedule
  lock-trace -E drivers -e debug_print --tree callers schedule
  lock-trace stats my_function
        """,
    )

    parser.add_argument(
        "--database-path",
        "-d",
        default=".",
        help="Path to cscope database directory (default: current directory)",
    )

    parser.add_argument(
        "--cscope-file",
        "-f",
        help="Path to cscope.out file (default: cscope.out in database directory)",
    )

    parser.add_argument(
        "--source-dir",
        "-s",
        help="Path to source code directory (default: same as database directory)",
    )

    parser.add_argument(
        "--max-depth",
        "-m",
        type=int,
        default=10,
        help="Maximum depth for call tracing (default: 1)",
    )

    parser.add_argument(
        "--tree",
        "-t",
        action="store_true",
        help="Display results as tree structure with unique call chains",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all paths including duplicates",
    )

    parser.add_argument(
        "--exclude-functions",
        "-e",
        help="Comma-separated list of functions to exclude from call paths",
    )

    parser.add_argument(
        "--exclude-directories",
        "-E",
        help="Comma-separated list of directories to exclude from call paths",
    )

    parser.add_argument(
        "--enable-callback-search",
        action="store_true",
        default=True,
        help="Enable enhanced callback function search (default: enabled)",
    )

    parser.add_argument(
        "--disable-callback-search",
        action="store_true",
        help="Disable enhanced callback function search",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Callers command
    callers_parser = subparsers.add_parser(
        "callers", help="Trace caller paths to a function"
    )
    callers_parser.add_argument("function", help="Function to trace callers for")

    # Callees command
    callees_parser = subparsers.add_parser(
        "callees", help="Trace callee paths from a function"
    )
    callees_parser.add_argument("function", help="Function to trace callees from")

    # Lock check command
    lock_check_parser = subparsers.add_parser(
        "lock-check", help="Check if function is called with lock protection"
    )
    lock_check_parser.add_argument("function", help="Function to check")
    lock_check_parser.add_argument("lock", help="Lock variable name to check for")

    # Lock context command
    lock_context_parser = subparsers.add_parser(
        "lock-context", help="Analyze lock context for function calls"
    )
    lock_context_parser.add_argument("function", help="Function to analyze")
    lock_context_parser.add_argument(
        "locks",
        nargs="?",
        help="Optional comma-separated list of specific locks to track",
    )

    # Unprotected command
    unprotected_parser = subparsers.add_parser(
        "unprotected", help="Find unprotected calls to a function"
    )
    unprotected_parser.add_argument(
        "function", help="Function that requires protection"
    )
    unprotected_parser.add_argument(
        "required_locks", help="Comma-separated list of required locks"
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Get statistics for a function")
    stats_parser.add_argument("function", help="Function to analyze")

    return parser


async def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Determine callback search setting
    enable_callback_search = True
    if hasattr(args, "disable_callback_search") and args.disable_callback_search:
        enable_callback_search = False

    # Fix argparse issue: subcommand max_depth=None overrides global max_depth
    # If max_depth is None, we need to use the default from the parser
    setup_max_depth = args.max_depth if args.max_depth is not None else 10

    cli = LockTraceCLI()
    await cli.setup(
        args.database_path,
        setup_max_depth,
        getattr(args, "cscope_file", None),
        getattr(args, "source_dir", None),
        enable_callback_search,
    )

    # Parse exclude functions
    exclude_functions = None
    if args.exclude_functions:
        exclude_functions = set(args.exclude_functions.split(","))

    # Parse exclude directories
    exclude_directories = None
    if args.exclude_directories:
        exclude_directories = set(args.exclude_directories.split(","))

    try:
        if args.command == "callers":
            # Use None to let the method use the tracer's default max_depth (set during setup)
            await cli.trace_callers(
                args.function,
                None,
                args.tree,
                args.verbose,
                exclude_functions,
                exclude_directories,
            )

        elif args.command == "callees":
            # Use None to let the method use the tracer's default max_depth (set during setup)
            await cli.trace_callees(
                args.function,
                None,
                args.tree,
                args.verbose,
                exclude_functions,
                exclude_directories,
            )

        elif args.command == "lock-check":
            await cli.check_lock_protection(
                args.function,
                args.lock,
                args.tree,
                args.verbose,
                exclude_functions,
                exclude_directories,
            )

        elif args.command == "lock-context":
            locks = args.locks.split(",") if args.locks else None
            await cli.analyze_lock_context(
                args.function,
                locks,
                args.tree,
                args.verbose,
                exclude_functions,
                exclude_directories,
            )

        elif args.command == "unprotected":
            required_locks = args.required_locks.split(",")
            await cli.find_unprotected_calls(
                args.function,
                required_locks,
                args.tree,
                args.verbose,
                exclude_functions,
                exclude_directories,
            )

        elif args.command == "stats":
            await cli.get_function_stats(args.function)

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_main():
    """Synchronous entry point that runs the async main."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
