"""Tests for lock analyzer module."""

from unittest.mock import AsyncMock, Mock

import pytest

from lock_trace.call_tracer import CallPath
from lock_trace.cscope_interface import FunctionCall
from lock_trace.lock_analyzer import LockAnalyzer, LockContext, LockOperation, LockType


class TestLockAnalyzer:
    """Test cases for LockAnalyzer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cscope = Mock()
        self.mock_tracer = Mock()
        # Make async methods return AsyncMock
        self.mock_cscope.get_functions_called_by = AsyncMock()
        self.mock_tracer.get_unique_call_chains = AsyncMock()
        self.analyzer = LockAnalyzer(self.mock_cscope, self.mock_tracer)

    def test_init(self):
        """Test LockAnalyzer initialization."""
        assert self.analyzer.cscope == self.mock_cscope
        assert self.analyzer.call_tracer == self.mock_tracer
        assert hasattr(self.analyzer, "_compiled_patterns")

    def test_identify_spinlock_operation(self):
        """Test identification of spinlock operations."""
        # Test spinlock acquire
        call = FunctionCall("spin_lock", "file.c", 10, "spin_lock(&my_lock);")
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.SPINLOCK
        assert operations[0].operation == "acquire"
        assert operations[0].lock_name == "my_lock"
        assert operations[0].function == "test_func"

    def test_identify_mutex_operation(self):
        """Test identification of mutex operations."""
        # Test mutex acquire
        call = FunctionCall("mutex_lock", "file.c", 10, "mutex_lock(&my_mutex);")
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.MUTEX
        assert operations[0].operation == "acquire"
        assert operations[0].lock_name == "my_mutex"
        assert operations[0].function == "test_func"

    def test_identify_lock_release(self):
        """Test identification of lock release operations."""
        # Test spinlock release
        call = FunctionCall("spin_unlock", "file.c", 10, "spin_unlock(&my_lock);")
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.SPINLOCK
        assert operations[0].operation == "release"
        assert operations[0].lock_name == "my_lock"
        assert operations[0].function == "test_func"

    def test_extract_lock_name_simple(self):
        """Test extraction of lock variable name."""
        # Test simple case with &variable
        name = self.analyzer._extract_lock_name("spin_lock(&my_lock);", "spin_lock")
        assert name == "my_lock"

        # Test case without &
        name = self.analyzer._extract_lock_name("spin_lock(my_lock);", "spin_lock")
        assert name == "my_lock"

    def test_extract_lock_name_fallback(self):
        """Test fallback when lock name cannot be extracted."""
        name = self.analyzer._extract_lock_name("complex_call();", "complex_call")
        assert name == "complex_call"

    @pytest.mark.asyncio
    async def test_find_lock_operations(self):
        """Test finding lock operations in a function."""
        # Mock function calls
        calls = [
            FunctionCall("spin_lock", "file.c", 10, "spin_lock(&lock1);"),
            FunctionCall("mutex_lock", "file.c", 20, "mutex_lock(&lock2);"),
            FunctionCall("regular_func", "file.c", 30, "regular_func();"),
        ]

        self.mock_cscope.get_functions_called_by.return_value = calls

        operations = await self.analyzer.find_lock_operations("test_func")

        # Should find 2 lock operations (spin_lock and mutex_lock)
        assert len(operations) == 2

        lock_names = [op.lock_name for op in operations]
        assert "lock1" in lock_names
        assert "lock2" in lock_names

    @pytest.mark.asyncio
    async def test_analyze_path_locks(self):
        """Test analyzing locks along a call path."""
        # Mock call path
        call_path = CallPath(functions=["func_a", "func_b", "func_c"], depth=2)

        # Mock lock operations for each function
        async def mock_find_operations(func):
            if func == "func_a":
                return [
                    LockOperation(
                        "lock1",
                        LockType.SPINLOCK,
                        "acquire",
                        "func_a",
                        "file.c",
                        10,
                        "context",
                    )
                ]
            elif func == "func_b":
                return [
                    LockOperation(
                        "lock2",
                        LockType.MUTEX,
                        "acquire",
                        "func_b",
                        "file.c",
                        20,
                        "context",
                    )
                ]
            elif func == "func_c":
                return [
                    LockOperation(
                        "lock1",
                        LockType.SPINLOCK,
                        "release",
                        "func_c",
                        "file.c",
                        30,
                        "context",
                    )
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope calls for call order filtering
        def mock_get_called_by(func):
            if func == "func_b":
                return [FunctionCall("func_c", "file.c", 25, "func_c();")]
            return []

        self.mock_cscope.get_functions_called_by.side_effect = mock_get_called_by

        context = await self.analyzer._analyze_path_locks(call_path)

        assert context.function == "func_c"
        assert context.call_path == ["func_a", "func_b", "func_c"]
        # Both lock1 and lock2 are held when entering func_c
        # (func_c's internal operations are not considered)
        assert "lock2" in context.held_locks
        assert "lock1" in context.held_locks  # held when entering func_c

    @pytest.mark.asyncio
    async def test_check_lock_protection(self):
        """Test checking lock protection for a function."""
        # Mock call paths
        mock_paths = [
            CallPath(functions=["caller1", "target"], depth=1),
            CallPath(functions=["caller2", "target"], depth=1),
        ]

        self.mock_tracer.trace_callers.return_value = mock_paths

        # Mock lock contexts
        async def mock_analyze_context(
            func,
            locks,
            unique_only=True,
            exclude_functions=None,
            exclude_directories=None,
        ):
            if locks == ["test_lock"]:
                return [
                    LockContext("target", {"test_lock"}, ["caller1", "target"], []),
                    LockContext("target", set(), ["caller2", "target"], []),
                ]
            return []

        self.analyzer.analyze_lock_context = mock_analyze_context

        results = await self.analyzer.check_lock_protection("target", "test_lock")

        assert len(results) == 2
        assert results["caller1 -> target"] is True
        assert results["caller2 -> target"] is False

    @pytest.mark.asyncio
    async def test_find_unprotected_calls(self):
        """Test finding unprotected calls."""
        # Mock analyze_lock_context to return contexts
        mock_contexts = [
            LockContext("target", {"lock1"}, ["path1", "target"], []),  # protected
            LockContext("target", set(), ["path2", "target"], []),  # unprotected
            LockContext(
                "target", {"lock1", "lock2"}, ["path3", "target"], []
            ),  # protected
        ]

        async def mock_analyze_context(
            func,
            locks=None,
            unique_only=True,
            exclude_functions=None,
            exclude_directories=None,
        ):
            return mock_contexts

        self.analyzer.analyze_lock_context = mock_analyze_context

        unprotected = await self.analyzer.find_unprotected_calls(
            "target", ["lock1", "lock2"]
        )

        # Should find 2 unprotected paths (path2 missing both, path1 and path3 missing lock2)
        assert len(unprotected) == 2

    @pytest.mark.asyncio
    async def test_get_lock_summary(self):
        """Test getting lock usage summary."""
        # Mock analyze_lock_context
        mock_contexts = [
            LockContext("target", {"lock1"}, ["path1", "target"], []),
            LockContext("target", set(), ["path2", "target"], []),
            LockContext("target", {"lock1", "lock2"}, ["path3", "target"], []),
        ]

        async def mock_analyze_context(
            func, locks=None, unique_only=True, exclude_functions=None
        ):
            return mock_contexts

        self.analyzer.analyze_lock_context = mock_analyze_context

        summary = await self.analyzer.get_lock_summary("target")

        assert summary["function"] == "target"
        assert summary["total_call_paths"] == 3
        assert summary["protected_paths"] == 2
        assert summary["unprotected_paths"] == 1
        assert set(summary["locks_encountered"]) == {"lock1", "lock2"}
        assert summary["lock_count"] == 2

    def test_rcu_lock_detection(self):
        """Test RCU lock detection and matching."""
        # Test RCU lock name extraction (now returns actual function name)
        rcu_context = "rcu_read_lock();"
        lock_name = self.analyzer._extract_lock_name(rcu_context, "rcu_read_lock")
        assert lock_name == "rcu_read_lock"

        # Test RCU lock matching (generic targets) - _var suffix no longer supported
        assert self.analyzer._lock_matches_target("rcu_read_lock", ["rcu_var"]) is False
        assert self.analyzer._lock_matches_target("rcu_read_lock", ["rcu"]) is True
        assert (
            self.analyzer._lock_matches_target("rcu_read_unlock", ["rcu_var"]) is False
        )

        # Test specific RCU matching
        assert (
            self.analyzer._lock_matches_target("rcu_read_lock", ["rcu_read_lock"])
            is True
        )
        assert (
            self.analyzer._lock_matches_target("rcu_read_lock", ["rcu_read_unlock"])
            is False
        )

        # Test non-RCU locks
        assert self.analyzer._lock_matches_target("other_lock", ["rcu_var"]) is False

        # Test RCU display names - now always returns actual lock name
        display_name_generic = self.analyzer._get_display_lock_name(
            "rcu_read_lock", ["rcu_var"]
        )
        assert display_name_generic == "rcu_read_lock"

        display_name_specific = self.analyzer._get_display_lock_name(
            "rcu_read_lock", ["rcu_read_lock"]
        )
        assert display_name_specific == "rcu_read_lock"

    @pytest.mark.asyncio
    async def test_rcu_lock_context_analysis(self):
        """Test RCU lock context analysis with target locks."""
        # Mock call path with RCU operations
        mock_path = CallPath(functions=["caller", "target"], depth=1)

        # Mock RCU lock operations (now returns actual function name)
        async def mock_find_operations(func):
            if func == "caller":
                return [
                    LockOperation(
                        "rcu_read_lock",  # RCU locks now get actual function name
                        LockType.RCU,
                        "acquire",
                        "caller",
                        "file.c",
                        10,
                        "rcu_read_lock();",
                    )
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope calls for call order filtering
        def mock_get_called_by(func):
            if func == "caller":
                return [FunctionCall("target", "file.c", 15, "target();")]
            return []

        self.mock_cscope.get_functions_called_by.side_effect = mock_get_called_by

        # Test with generic RCU target - should show actual lock name
        context_generic = await self.analyzer._analyze_path_locks(mock_path, ["rcu"])
        assert "rcu_read_lock" in context_generic.held_locks
        assert context_generic.function == "target"

        # Test with specific RCU target
        context_specific = await self.analyzer._analyze_path_locks(
            mock_path, ["rcu_read_lock"]
        )
        assert "rcu_read_lock" in context_specific.held_locks
        assert context_specific.function == "target"

    @pytest.mark.asyncio
    async def test_call_order_filtering(self):
        """Test that lock operations are filtered by call order."""
        # Mock call path where locks occur after target function call
        mock_path = CallPath(functions=["caller", "target"], depth=1)

        # Mock operations - spin_lock after target call at line 15
        async def mock_find_operations(func):
            if func == "caller":
                return [
                    LockOperation(
                        "lock_before",
                        LockType.SPINLOCK,
                        "acquire",
                        "caller",
                        "file.c",
                        10,  # Before target call at line 15
                        "spin_lock(&lock_before);",
                    ),
                    LockOperation(
                        "lock_after",
                        LockType.SPINLOCK,
                        "acquire",
                        "caller",
                        "file.c",
                        20,  # After target call at line 15
                        "spin_lock(&lock_after);",
                    ),
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope to return target call at line 15
        def mock_get_called_by(func):
            if func == "caller":
                return [FunctionCall("target", "file.c", 15, "target();")]
            return []

        self.mock_cscope.get_functions_called_by.side_effect = mock_get_called_by

        context = await self.analyzer._analyze_path_locks(mock_path)

        # Should only show lock_before (line 10), not lock_after (line 20)
        assert "lock_before" in context.held_locks
        assert "lock_after" not in context.held_locks
        assert context.function == "target"

    @pytest.mark.asyncio
    async def test_lock_operations_display_includes_releases(self):
        """Test that lock operations display includes both acquire and release operations."""
        # Mock call path with acquire and release operations
        mock_path = CallPath(functions=["caller", "target"], depth=1)

        # Mock operations with both acquire and release
        async def mock_find_operations(func):
            if func == "caller":
                return [
                    LockOperation(
                        "test_lock",
                        LockType.SPINLOCK,
                        "acquire",
                        "caller",
                        "file.c",
                        10,
                        "spin_lock(&test_lock);",
                    ),
                    LockOperation(
                        "test_lock",
                        LockType.SPINLOCK,
                        "release",
                        "caller",
                        "file.c",
                        20,
                        "spin_unlock(&test_lock);",
                    ),
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope to return target call at line 15 (between acquire and release)
        def mock_get_called_by(func):
            if func == "caller":
                return [FunctionCall("target", "file.c", 15, "target();")]
            return []

        self.mock_cscope.get_functions_called_by.side_effect = mock_get_called_by

        context = await self.analyzer._analyze_path_locks(mock_path)

        # Should show test_lock as held (acquired before target call at line 15)
        assert "test_lock" in context.held_locks
        assert context.function == "target"

        # Should display only operations from calling functions (not target function)
        assert len(context.lock_operations) == 2
        operations = {(op.operation, op.function) for op in context.lock_operations}
        assert ("acquire", "caller") in operations
        assert ("release", "caller") in operations

    @pytest.mark.asyncio
    async def test_function_name_in_lock_operations(self):
        """Test that lock operations show the caller function name, not the lock function name."""
        # Mock the cscope interface to return lock function calls
        mock_calls = [
            FunctionCall("spin_lock", "file.c", 10, "spin_lock(&test_lock);"),
            FunctionCall("spin_unlock", "file.c", 20, "spin_unlock(&test_lock);"),
        ]
        self.mock_cscope.get_functions_called_by.return_value = mock_calls

        operations = await self.analyzer.find_lock_operations("test_function")

        # Should find 2 lock operations
        assert len(operations) == 2

        # All operations should show the caller function name, not the lock function name
        for op in operations:
            assert op.function == "test_function"
            assert op.function != "spin_lock"
            assert op.function != "spin_unlock"

    def test_identify_rtnl_lock_operations(self):
        """Test identification of RTNL lock operations."""
        # Test rtnl_lock operation
        call = FunctionCall("rtnl_lock", "net/core/rtnetlink.c", 10, "rtnl_lock();")
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.CUSTOM
        assert operations[0].operation == "acquire"
        assert operations[0].lock_name == "rtnl_lock"
        assert operations[0].function == "test_func"

        # Test rtnl_unlock operation
        call = FunctionCall("rtnl_unlock", "net/core/rtnetlink.c", 20, "rtnl_unlock();")
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.CUSTOM
        assert operations[0].operation == "release"
        assert operations[0].lock_name == "rtnl_unlock"

        # Test rtnl_net_lock operation with variable
        call = FunctionCall(
            "rtnl_net_lock",
            "net/core/rtnetlink.c",
            30,
            "rtnl_net_lock(&rtnl_net_lock);",
        )
        operations = self.analyzer._identify_lock_operation(call, "test_func")

        assert len(operations) == 1
        assert operations[0].lock_type == LockType.CUSTOM
        assert operations[0].operation == "acquire"
        assert operations[0].lock_name == "rtnl_net_lock"


class TestLockOperation:
    """Test cases for LockOperation."""

    def test_creation(self):
        """Test LockOperation creation."""
        op = LockOperation(
            lock_name="test_lock",
            lock_type=LockType.SPINLOCK,
            operation="acquire",
            function="test_func",
            file="test.c",
            line=10,
            context="spin_lock(&test_lock);",
        )

        assert op.lock_name == "test_lock"
        assert op.lock_type == LockType.SPINLOCK
        assert op.operation == "acquire"
        assert op.function == "test_func"
        assert op.file == "test.c"
        assert op.line == 10
        assert op.context == "spin_lock(&test_lock);"


class TestLockContext:
    """Test cases for LockContext."""

    def test_creation(self):
        """Test LockContext creation."""
        context = LockContext(
            function="test_func",
            held_locks={"lock1", "lock2"},
            call_path=["caller", "test_func"],
            lock_operations=[],
        )

        assert context.function == "test_func"
        assert context.held_locks == {"lock1", "lock2"}
        assert context.call_path == ["caller", "test_func"]
        assert context.lock_operations == []


class TestLockAnalyzerExcludeFunctions:
    """Test cases for LockAnalyzer exclude functions functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cscope = Mock()
        self.mock_tracer = Mock()
        # Make async methods return AsyncMock
        self.mock_cscope.get_functions_called_by = AsyncMock()
        self.mock_tracer.get_unique_call_chains = AsyncMock()
        self.analyzer = LockAnalyzer(self.mock_cscope, self.mock_tracer)

    @pytest.mark.asyncio
    async def test_analyze_lock_context_with_exclude_functions(self):
        """Test analyze_lock_context with excluded functions."""
        # Mock tracer to return paths with excluded functions
        included_path = CallPath(functions=["caller", "target"], depth=1)

        self.mock_tracer.get_unique_call_chains.return_value = [included_path]

        # Mock required dependencies
        self.mock_cscope.get_functions_called_by.return_value = []

        exclude_functions = {"excluded_func"}
        contexts = await self.analyzer.analyze_lock_context(
            "target", unique_only=True, exclude_functions=exclude_functions
        )

        # Verify that tracer was called with exclude_functions
        self.mock_tracer.get_unique_call_chains.assert_called_once_with(
            "target", exclude_functions=exclude_functions, exclude_directories=None
        )

        # Should return the filtered contexts
        assert isinstance(contexts, list)

    @pytest.mark.asyncio
    async def test_check_lock_protection_with_exclude_functions(self):
        """Test check_lock_protection with excluded functions."""
        # Mock analyze_lock_context to return filtered results
        mock_context = LockContext(
            function="target",
            held_locks={"test_lock"},
            call_path=["caller", "target"],
            lock_operations=[],
        )
        self.analyzer.analyze_lock_context = AsyncMock(return_value=[mock_context])

        exclude_functions = {"excluded_func"}
        results = await self.analyzer.check_lock_protection(
            "target", "test_lock", unique_only=True, exclude_functions=exclude_functions
        )

        # Verify that analyze_lock_context was called with exclude_functions
        self.analyzer.analyze_lock_context.assert_called_once_with(
            "target", ["test_lock"], True, exclude_functions, None
        )

        # Should return filtered results
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_find_unprotected_calls_with_exclude_functions(self):
        """Test find_unprotected_calls with excluded functions."""
        # Mock analyze_lock_context to return filtered results
        mock_context = LockContext(
            function="target",
            held_locks=set(),
            call_path=["caller", "target"],
            lock_operations=[],
        )
        self.analyzer.analyze_lock_context = AsyncMock(return_value=[mock_context])

        exclude_functions = {"excluded_func"}
        results = await self.analyzer.find_unprotected_calls(
            "target",
            ["test_lock"],
            unique_only=True,
            exclude_functions=exclude_functions,
        )

        # Verify that analyze_lock_context was called with exclude_functions
        self.analyzer.analyze_lock_context.assert_called_once_with(
            "target", ["test_lock"], True, exclude_functions, None
        )

        # Should return filtered results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_analyze_lock_context_with_exclude_directories(self):
        """Test analyze_lock_context with exclude_directories parameter."""
        # Mock the call tracer to return paths
        mock_paths = [
            CallPath(functions=["caller_from_drivers", "target_func"], depth=1),
            CallPath(functions=["caller_from_kernel", "target_func"], depth=1),
        ]
        self.mock_tracer.get_unique_call_chains.return_value = mock_paths

        # Mock cscope to return empty lists for function calls (to avoid iteration errors)
        self.mock_cscope.get_functions_called_by.return_value = []

        # Call the method with exclude_directories
        exclude_directories = {"drivers"}
        results = await self.analyzer.analyze_lock_context(
            "target_func", exclude_directories=exclude_directories
        )

        # Verify that the call tracer was called with exclude_directories
        self.mock_tracer.get_unique_call_chains.assert_called_once_with(
            "target_func",
            exclude_functions=None,
            exclude_directories=exclude_directories,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_check_lock_protection_with_exclude_directories(self):
        """Test check_lock_protection with exclude_directories parameter."""
        # Mock the analyze_lock_context method
        mock_context = LockContext(
            function="target_func",
            held_locks={"my_lock"},
            call_path=["caller", "target_func"],
            lock_operations=[],
        )

        # Mock analyze_lock_context to verify it's called with correct parameters
        original_analyze = self.analyzer.analyze_lock_context
        self.analyzer.analyze_lock_context = AsyncMock(return_value=[mock_context])

        exclude_directories = {"drivers"}
        results = await self.analyzer.check_lock_protection(
            "target_func", "my_lock", exclude_directories=exclude_directories
        )

        # Verify that analyze_lock_context was called with exclude_directories
        self.analyzer.analyze_lock_context.assert_called_once_with(
            "target_func", ["my_lock"], True, None, exclude_directories
        )

        assert isinstance(results, dict)
        self.analyzer.analyze_lock_context = original_analyze

    @pytest.mark.asyncio
    async def test_find_unprotected_calls_with_exclude_directories(self):
        """Test find_unprotected_calls with exclude_directories parameter."""
        # Mock the analyze_lock_context method
        mock_context = LockContext(
            function="target_func",
            held_locks=set(),  # No locks held - should be unprotected
            call_path=["caller", "target_func"],
            lock_operations=[],
        )

        # Mock analyze_lock_context to verify it's called with correct parameters
        original_analyze = self.analyzer.analyze_lock_context
        self.analyzer.analyze_lock_context = AsyncMock(return_value=[mock_context])

        exclude_directories = {"drivers"}
        required_locks = ["my_lock"]
        results = await self.analyzer.find_unprotected_calls(
            "target_func", required_locks, exclude_directories=exclude_directories
        )

        # Verify that analyze_lock_context was called with exclude_directories
        self.analyzer.analyze_lock_context.assert_called_once_with(
            "target_func", required_locks, True, None, exclude_directories
        )

        assert isinstance(results, list)
        self.analyzer.analyze_lock_context = original_analyze

    @pytest.mark.asyncio
    async def test_analyze_path_locks_no_target_locks_shows_protection(self):
        """Test that analyze_path_locks returns protection info when no target_locks specified."""
        # Mock call path
        call_path = CallPath(functions=["func_a", "func_b"], depth=1)

        # Mock lock operations - func_a has a complete lock section (acquire + release)
        async def mock_find_operations(func):
            if func == "func_a":
                return [
                    LockOperation(
                        "rtnl_lock",
                        LockType.CUSTOM,
                        "acquire",
                        "func_a",
                        "file.c",
                        10,
                        "rtnl_lock();",
                    ),
                    LockOperation(
                        "rtnl_unlock",
                        LockType.CUSTOM,
                        "release",
                        "func_a",
                        "file.c",
                        20,
                        "rtnl_unlock();",
                    ),
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope calls for call order filtering
        self.mock_cscope.get_functions_called_by.return_value = [
            FunctionCall("func_b", "file.c", 15, "func_b();")
        ]

        # Test with target_locks=None (no specific locks requested)
        context = await self.analyzer._analyze_path_locks(call_path, target_locks=None)

        # Internal analyzer behavior: when no target_locks, still shows protection evidence
        assert context.function == "func_b"
        assert context.call_path == ["func_a", "func_b"]
        assert "rtnl_lock" in context.held_locks  # Should show protection evidence
        assert len(context.lock_operations) == 2  # Operations should be shown

    @pytest.mark.asyncio
    async def test_analyze_path_locks_with_target_locks_shows_protection(self):
        """Test that analyze_path_locks returns held_locks when target_locks specified."""
        # Mock call path
        call_path = CallPath(functions=["func_a", "func_b"], depth=1)

        # Mock lock operations - func_a has a complete lock section (acquire + release)
        async def mock_find_operations(func):
            if func == "func_a":
                return [
                    LockOperation(
                        "rtnl_lock",
                        LockType.CUSTOM,
                        "acquire",
                        "func_a",
                        "file.c",
                        10,
                        "rtnl_lock();",
                    ),
                    LockOperation(
                        "rtnl_unlock",
                        LockType.CUSTOM,
                        "release",
                        "func_a",
                        "file.c",
                        20,
                        "rtnl_unlock();",
                    ),
                ]
            return []

        self.analyzer.find_lock_operations = AsyncMock(side_effect=mock_find_operations)

        # Mock cscope calls for call order filtering
        self.mock_cscope.get_functions_called_by.return_value = [
            FunctionCall("func_b", "file.c", 15, "func_b();")
        ]

        # Test with target_locks specified
        context = await self.analyzer._analyze_path_locks(
            call_path, target_locks=["rtnl"]
        )

        # When target_locks are specified and locks provide protection, held_locks should show protection
        assert context.function == "func_b"
        assert context.call_path == ["func_a", "func_b"]
        assert "rtnl_lock" in context.held_locks  # Should show protection evidence
        assert len(context.lock_operations) == 2  # Operations should still be shown
