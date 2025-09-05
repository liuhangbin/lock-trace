"""Tests for call tracer module."""

from unittest.mock import AsyncMock

import pytest

from lock_trace.call_tracer import CallGraph, CallPath, CallTracer
from lock_trace.cscope_interface import FunctionCall


class TestCallTracer:
    """Test cases for CallTracer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cscope = AsyncMock()
        # Mock the enhanced callback search method
        self.mock_cscope.get_callback_callers = AsyncMock()
        self.mock_cscope.find_function_definition = AsyncMock()
        self.tracer = CallTracer(self.mock_cscope, max_depth=3)

    def test_init(self):
        """Test CallTracer initialization."""
        assert self.tracer.cscope == self.mock_cscope
        assert self.tracer.max_depth == 3

    @pytest.mark.asyncio
    async def test_trace_callers_simple(self):
        """Test simple caller tracing."""
        # Mock cscope responses for enhanced callback search
        self.mock_cscope.get_callback_callers.side_effect = [
            [FunctionCall("caller1", "file1.c", 10, "context1")],  # target_func callers
            [],  # caller1 callers (none)
        ]

        paths = await self.tracer.trace_callers("target_func")

        assert len(paths) >= 1
        # Should have at least one path starting from target_func
        target_paths = [
            p for p in paths if p.functions and p.functions[-1] == "target_func"
        ]
        assert len(target_paths) >= 1

    @pytest.mark.asyncio
    async def test_trace_callers_max_depth(self):
        """Test caller tracing respects max depth."""
        # Mock a deep call chain
        self.mock_cscope.get_callback_callers.side_effect = [
            [FunctionCall("caller1", "file1.c", 10, "context1")],  # target_func
            [FunctionCall("caller2", "file2.c", 20, "context2")],  # caller1
            [FunctionCall("caller3", "file3.c", 30, "context3")],  # caller2
            [
                FunctionCall("caller4", "file4.c", 40, "context4")
            ],  # caller3 (should be cut off)
        ]

        paths = await self.tracer.trace_callers("target_func", max_depth=2)

        # Verify no path exceeds max depth
        for path in paths:
            assert path.depth <= 2

    @pytest.mark.asyncio
    async def test_trace_callees_simple(self):
        """Test simple callee tracing."""
        # Mock cscope responses
        self.mock_cscope.get_functions_called_by.side_effect = [
            [FunctionCall("callee1", "file1.c", 10, "context1")],  # source_func callees
            [],  # callee1 callees (none)
        ]

        paths = await self.tracer.trace_callees("source_func")

        assert len(paths) >= 1
        # Should have at least one path starting from source_func
        source_paths = [
            p for p in paths if p.functions and p.functions[0] == "source_func"
        ]
        assert len(source_paths) >= 1

    @pytest.mark.asyncio
    async def test_find_call_paths(self):
        """Test finding paths between two functions."""
        # Mock a call chain: func_a -> func_b -> target_func
        self.mock_cscope.get_functions_called_by.side_effect = [
            [FunctionCall("func_b", "file1.c", 10, "context1")],  # func_a calls func_b
            [
                FunctionCall("target_func", "file2.c", 20, "context2")
            ],  # func_b calls target_func
            [],  # target_func calls nothing relevant
        ]

        paths = await self.tracer.find_call_paths("func_a", "target_func")

        # Should find the path func_a -> func_b -> target_func
        target_paths = [
            p
            for p in paths
            if len(p.functions) == 3
            and p.functions[0] == "func_a"
            and p.functions[2] == "target_func"
        ]
        assert len(target_paths) >= 1

    @pytest.mark.asyncio
    async def test_get_function_depth_map(self):
        """Test function depth mapping."""
        # Mock call relationships
        self.mock_cscope.get_functions_called_by.side_effect = [
            [
                FunctionCall("level1_func", "file1.c", 10, "context1")
            ],  # root calls level1
            [
                FunctionCall("level2_func", "file2.c", 20, "context2")
            ],  # level1 calls level2
            [],  # level2 calls nothing
        ]

        depth_map = await self.tracer.get_function_depth_map(["root_func"])

        assert "root_func" in depth_map
        assert depth_map["root_func"] == 0

        if "level1_func" in depth_map:
            assert depth_map["level1_func"] == 1

        if "level2_func" in depth_map:
            assert depth_map["level2_func"] == 2

    @pytest.mark.asyncio
    async def test_get_call_statistics(self):
        """Test call statistics generation."""
        # Mock caller and callee data
        callers = [
            FunctionCall("caller1", "file1.c", 10, "context1"),
            FunctionCall("caller2", "file2.c", 20, "context2"),
            FunctionCall("caller1", "file1.c", 30, "context3"),  # duplicate caller
        ]

        callees = [
            FunctionCall("callee1", "file3.c", 40, "context4"),
            FunctionCall("callee2", "file4.c", 50, "context5"),
        ]

        self.mock_cscope.get_functions_calling.return_value = callers
        self.mock_cscope.get_functions_called_by.return_value = callees

        stats = await self.tracer.get_call_statistics("test_func")

        assert stats["caller_count"] == 3
        assert stats["callee_count"] == 2
        assert stats["unique_callers"] == 2  # caller1 appears twice
        assert stats["unique_callees"] == 2

    @pytest.mark.asyncio
    async def test_circular_dependency_handling(self):
        """Test handling of circular dependencies."""

        # Mock circular call relationship: func_a -> func_b -> func_a
        async def mock_calls(func):
            if func == "func_a":
                return [FunctionCall("func_b", "file1.c", 10, "context1")]
            elif func == "func_b":
                return [FunctionCall("func_a", "file2.c", 20, "context2")]
            else:
                return []

        self.mock_cscope.get_functions_called_by.side_effect = mock_calls

        # Should not get stuck in infinite loop
        paths = await self.tracer.trace_callees("func_a", max_depth=5)

        # Should complete without hanging
        assert isinstance(paths, list)

    @pytest.mark.asyncio
    async def test_trace_callers_with_exclude_functions(self):
        """Test caller tracing with excluded functions."""

        # Mock cscope responses with sufficient return values
        async def mock_get_callback_callers(function):
            if function == "target_func":
                return [
                    FunctionCall("caller1", "file1.c", 10, "context1"),
                    FunctionCall("excluded_func", "file2.c", 20, "context2"),
                ]
            elif function == "caller1":
                return [FunctionCall("caller2", "file3.c", 30, "context3")]
            elif function == "excluded_func":
                return [FunctionCall("caller3", "file4.c", 40, "context4")]
            else:
                return []  # No more callers

        self.mock_cscope.get_callback_callers.side_effect = mock_get_callback_callers

        exclude_functions = {"excluded_func"}
        paths = await self.tracer.trace_callers(
            "target_func", exclude_functions=exclude_functions
        )

        # Check that paths containing excluded_func are filtered out
        for path in paths:
            assert "excluded_func" not in path.functions

    @pytest.mark.asyncio
    async def test_trace_callees_with_exclude_functions(self):
        """Test callee tracing with excluded functions."""

        # Mock cscope responses with sufficient return values
        async def mock_get_functions_called_by(function):
            if function == "source_func":
                return [
                    FunctionCall("callee1", "file1.c", 10, "context1"),
                    FunctionCall("excluded_func", "file2.c", 20, "context2"),
                ]
            elif function == "callee1":
                return [FunctionCall("callee2", "file3.c", 30, "context3")]
            elif function == "excluded_func":
                return [FunctionCall("callee3", "file4.c", 40, "context4")]
            else:
                return []  # No more callees

        self.mock_cscope.get_functions_called_by.side_effect = (
            mock_get_functions_called_by
        )

        exclude_functions = {"excluded_func"}
        paths = await self.tracer.trace_callees(
            "source_func", exclude_functions=exclude_functions
        )

        # Check that paths containing excluded_func are filtered out
        for path in paths:
            assert "excluded_func" not in path.functions

    @pytest.mark.asyncio
    async def test_get_unique_call_chains_with_exclude_functions(self):
        """Test unique call chains with excluded functions."""

        # Mock cscope responses with sufficient return values
        async def mock_get_callback_callers(function):
            if function == "target_func":
                return [
                    FunctionCall("caller1", "file1.c", 10, "context1"),
                    FunctionCall("excluded_func", "file2.c", 20, "context2"),
                ]
            elif function == "caller1":
                return [FunctionCall("caller2", "file3.c", 30, "context3")]
            elif function == "excluded_func":
                return [FunctionCall("caller3", "file4.c", 40, "context4")]
            else:
                return []  # No more callers

        self.mock_cscope.get_callback_callers.side_effect = mock_get_callback_callers

        exclude_functions = {"excluded_func"}
        paths = await self.tracer.get_unique_call_chains(
            "target_func", exclude_functions=exclude_functions
        )

        # Check that paths containing excluded_func are filtered out
        for path in paths:
            assert "excluded_func" not in path.functions

    @pytest.mark.asyncio
    async def test_get_unique_callee_chains_with_exclude_functions(self):
        """Test unique callee chains with excluded functions."""

        # Mock cscope responses with sufficient return values
        async def mock_get_functions_called_by(function):
            if function == "source_func":
                return [
                    FunctionCall("callee1", "file1.c", 10, "context1"),
                    FunctionCall("excluded_func", "file2.c", 20, "context2"),
                ]
            elif function == "callee1":
                return [FunctionCall("callee2", "file3.c", 30, "context3")]
            elif function == "excluded_func":
                return [FunctionCall("callee3", "file4.c", 40, "context4")]
            else:
                return []  # No more callees

        self.mock_cscope.get_functions_called_by.side_effect = (
            mock_get_functions_called_by
        )

        exclude_functions = {"excluded_func"}
        paths = await self.tracer.get_unique_callee_chains(
            "source_func", exclude_functions=exclude_functions
        )

        # Check that paths containing excluded_func are filtered out
        for path in paths:
            assert "excluded_func" not in path.functions

    @pytest.mark.asyncio
    async def test_should_exclude_path(self):
        """Test _should_exclude_path method."""
        # Test with excluded functions
        exclude_functions = {"func_a", "func_b"}

        # Path containing excluded function should be excluded
        assert (
            await self.tracer._should_exclude_path(
                ["func_x", "func_a", "func_y"], exclude_functions
            )
            is True
        )
        assert (
            await self.tracer._should_exclude_path(
                ["func_b", "func_x"], exclude_functions
            )
            is True
        )

        # Path not containing excluded functions should not be excluded
        assert not await self.tracer._should_exclude_path(
            ["func_x", "func_y", "func_z"], exclude_functions
        )

        # Test with no excluded functions
        assert not await self.tracer._should_exclude_path(["func_a", "func_b"], None)
        assert not await self.tracer._should_exclude_path(["func_a", "func_b"], set())

    @pytest.mark.asyncio
    async def test_should_exclude_path_with_directories(self):
        """Test _should_exclude_path method with directory exclusions."""

        # Mock function definitions for directory testing
        async def mock_find_function_definition(function):
            file_map = {
                "func_a": FunctionCall(
                    "func_a", "drivers/net/driver.c", 100, "definition"
                ),
                "func_b": FunctionCall("func_b", "fs/ext4/inode.c", 200, "definition"),
                "func_c": FunctionCall(
                    "func_c", "kernel/sched/core.c", 300, "definition"
                ),
                "func_d": FunctionCall("func_d", "mm/page_alloc.c", 400, "definition"),
            }
            return file_map.get(function)

        self.mock_cscope.find_function_definition = mock_find_function_definition

        # Test excluding drivers directory
        exclude_directories = {"drivers"}

        # Path containing function from drivers should be excluded
        assert (
            await self.tracer._should_exclude_path(
                ["func_c", "func_a"], exclude_directories=exclude_directories
            )
            is True
        )
        assert (
            await self.tracer._should_exclude_path(
                ["func_a"], exclude_directories=exclude_directories
            )
            is True
        )

        # Path not containing functions from drivers should not be excluded
        assert not await self.tracer._should_exclude_path(
            ["func_c", "func_d"], exclude_directories=exclude_directories
        )

        # Test excluding multiple directories
        exclude_directories = {"drivers", "fs"}

        # Path containing function from either excluded directory should be excluded
        assert (
            await self.tracer._should_exclude_path(
                ["func_c", "func_a"], exclude_directories=exclude_directories
            )
            is True
        )
        assert (
            await self.tracer._should_exclude_path(
                ["func_c", "func_b"], exclude_directories=exclude_directories
            )
            is True
        )

        # Path not containing functions from excluded directories should not be excluded
        assert not await self.tracer._should_exclude_path(
            ["func_c", "func_d"], exclude_directories=exclude_directories
        )

        # Test with no excluded directories
        assert not await self.tracer._should_exclude_path(
            ["func_a", "func_b"], exclude_directories=None
        )
        assert not await self.tracer._should_exclude_path(
            ["func_a", "func_b"], exclude_directories=set()
        )

    @pytest.mark.asyncio
    async def test_should_exclude_path_combined_filters(self):
        """Test _should_exclude_path method with both function and directory exclusions."""

        # Mock function definitions for directory testing
        async def mock_find_function_definition(function):
            file_map = {
                "func_a": FunctionCall(
                    "func_a", "drivers/net/driver.c", 100, "definition"
                ),
                "func_b": FunctionCall("func_b", "fs/ext4/inode.c", 200, "definition"),
                "func_c": FunctionCall(
                    "func_c", "kernel/sched/core.c", 300, "definition"
                ),
            }
            return file_map.get(function)

        self.mock_cscope.find_function_definition = mock_find_function_definition

        exclude_functions = {"func_b"}
        exclude_directories = {"drivers"}

        # Path should be excluded if it contains excluded function
        assert (
            await self.tracer._should_exclude_path(
                ["func_c", "func_b"], exclude_functions, exclude_directories
            )
            is True
        )

        # Path should be excluded if it contains function from excluded directory
        assert (
            await self.tracer._should_exclude_path(
                ["func_c", "func_a"], exclude_functions, exclude_directories
            )
            is True
        )

        # Path should not be excluded if it contains neither
        assert not await self.tracer._should_exclude_path(
            ["func_c"], exclude_functions, exclude_directories
        )

    @pytest.mark.asyncio
    async def test_trace_callers_with_exclude_directories(self):
        """Test caller tracing with directory exclusions."""

        # Mock function definitions for directory testing
        async def mock_find_function_definition(function):
            file_map = {
                "caller1": FunctionCall(
                    "caller1", "drivers/net/driver.c", 100, "definition"
                ),
                "caller2": FunctionCall(
                    "caller2", "kernel/sched/core.c", 200, "definition"
                ),
                "target_func": FunctionCall(
                    "target_func", "mm/page_alloc.c", 300, "definition"
                ),
            }
            return file_map.get(function)

        self.mock_cscope.find_function_definition = mock_find_function_definition

        # Mock callers
        async def mock_get_functions_calling(function):
            if function == "target_func":
                return [
                    FunctionCall("caller1", "drivers/net/driver.c", 100, "caller1()"),
                    FunctionCall("caller2", "kernel/sched/core.c", 200, "caller2()"),
                ]
            return []

        async def mock_get_callback_callers(function):
            return []

        self.mock_cscope.get_functions_calling = mock_get_functions_calling
        self.mock_cscope.get_callback_callers = mock_get_callback_callers

        # Test excluding drivers directory
        exclude_directories = {"drivers"}
        paths = await self.tracer.trace_callers(
            "target_func", exclude_directories=exclude_directories
        )

        # Should exclude paths containing functions from drivers directory
        for path in paths:
            assert "caller1" not in path.functions
            # caller2 from kernel should still be included
            if len(path.functions) > 1:
                assert "caller2" in path.functions

    @pytest.mark.asyncio
    async def test_trace_callees_with_exclude_directories(self):
        """Test callee tracing with directory exclusions."""

        # Mock function definitions for directory testing
        async def mock_find_function_definition(function):
            file_map = {
                "source_func": FunctionCall(
                    "source_func", "kernel/sched/core.c", 100, "definition"
                ),
                "callee1": FunctionCall(
                    "callee1", "drivers/net/driver.c", 200, "definition"
                ),
                "callee2": FunctionCall(
                    "callee2", "mm/page_alloc.c", 300, "definition"
                ),
            }
            return file_map.get(function)

        self.mock_cscope.find_function_definition = mock_find_function_definition

        # Mock callees
        async def mock_get_functions_called_by(function):
            if function == "source_func":
                return [
                    FunctionCall("callee1", "drivers/net/driver.c", 200, "callee1()"),
                    FunctionCall("callee2", "mm/page_alloc.c", 300, "callee2()"),
                ]
            return []

        self.mock_cscope.get_functions_called_by = mock_get_functions_called_by

        # Test excluding drivers directory
        exclude_directories = {"drivers"}
        paths = await self.tracer.trace_callees(
            "source_func", exclude_directories=exclude_directories
        )

        # Should exclude paths containing functions from drivers directory
        for path in paths:
            assert "callee1" not in path.functions
            # callee2 from mm should still be included
            if len(path.functions) > 1:
                assert "callee2" in path.functions

    @pytest.mark.asyncio
    async def test_get_unique_call_chains_with_exclude_directories(self):
        """Test unique call chains with directory exclusions."""

        # Mock function definitions for directory testing
        async def mock_find_function_definition(function):
            file_map = {
                "caller1": FunctionCall(
                    "caller1", "drivers/net/driver.c", 100, "definition"
                ),
                "caller2": FunctionCall(
                    "caller2", "kernel/sched/core.c", 200, "definition"
                ),
                "target_func": FunctionCall(
                    "target_func", "mm/page_alloc.c", 300, "definition"
                ),
            }
            return file_map.get(function)

        self.mock_cscope.find_function_definition = mock_find_function_definition

        # Mock callers
        async def mock_get_functions_calling(function):
            if function == "target_func":
                return [
                    FunctionCall("caller1", "drivers/net/driver.c", 100, "caller1()"),
                    FunctionCall("caller2", "kernel/sched/core.c", 200, "caller2()"),
                ]
            return []

        async def mock_get_callback_callers(function):
            return []

        self.mock_cscope.get_functions_calling = mock_get_functions_calling
        self.mock_cscope.get_callback_callers = mock_get_callback_callers

        # Test excluding drivers directory
        exclude_directories = {"drivers"}
        paths = await self.tracer.get_unique_call_chains(
            "target_func", exclude_directories=exclude_directories
        )

        # Should exclude paths containing functions from drivers directory
        for path in paths:
            assert "caller1" not in path.functions

    def test_callback_search_enabled(self):
        """Test CallTracer with callback search enabled."""
        tracer = CallTracer(self.mock_cscope, max_depth=3, enable_callback_search=True)
        assert tracer.enable_callback_search is True

    def test_callback_search_disabled(self):
        """Test CallTracer with callback search disabled."""
        tracer = CallTracer(self.mock_cscope, max_depth=3, enable_callback_search=False)
        assert tracer.enable_callback_search is False

    @pytest.mark.asyncio
    async def test_trace_callers_with_callback_search_enabled(self):
        """Test caller tracing with callback search enabled."""

        # Mock cscope to use callback search
        async def mock_get_callback_callers(function):
            if function == "target_func":
                return [
                    FunctionCall("callback_caller", "file1.c", 10, "ops->target_func()")
                ]
            else:
                return []

        self.mock_cscope.get_callback_callers = mock_get_callback_callers

        tracer = CallTracer(self.mock_cscope, max_depth=3, enable_callback_search=True)
        paths = await tracer.trace_callers("target_func")

        # Should find callback callers
        assert len(paths) >= 1
        found_callback = any("callback_caller" in path.functions for path in paths)
        assert found_callback

    @pytest.mark.asyncio
    async def test_trace_callers_with_callback_search_disabled(self):
        """Test caller tracing with callback search disabled."""

        # Mock normal get_functions_calling
        async def mock_get_functions_calling(function):
            if function == "target_func":
                return [FunctionCall("direct_caller", "file1.c", 10, "direct_caller()")]
            else:
                return []

        self.mock_cscope.get_functions_calling = mock_get_functions_calling

        tracer = CallTracer(self.mock_cscope, max_depth=3, enable_callback_search=False)
        paths = await tracer.trace_callers("target_func")

        # Should only find direct callers
        assert len(paths) >= 1
        found_direct = any("direct_caller" in path.functions for path in paths)
        assert found_direct


class TestCallPath:
    """Test cases for CallPath."""

    def test_str_representation(self):
        """Test string representation of CallPath."""
        path = CallPath(functions=["func_a", "func_b", "func_c"], depth=2)
        assert str(path) == "func_a -> func_b -> func_c"

    def test_empty_path(self):
        """Test empty CallPath."""
        path = CallPath(functions=[], depth=0)
        assert str(path) == ""


class TestCallGraph:
    """Test cases for CallGraph."""

    def test_init(self):
        """Test CallGraph initialization."""
        graph = CallGraph()
        assert isinstance(graph.callers, dict)
        assert isinstance(graph.callees, dict)

        # Test defaultdict behavior
        assert isinstance(graph.callers["nonexistent"], list)
        assert isinstance(graph.callees["nonexistent"], list)
