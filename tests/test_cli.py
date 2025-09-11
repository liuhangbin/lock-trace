"""Tests for the CLI module."""

import io
from unittest.mock import AsyncMock, patch

import pytest

from lock_trace.cli import LockTraceCLI
from lock_trace.lock_analyzer import LockContext, LockOperation, LockType


class TestLockTraceCLI:
    """Test class for LockTraceCLI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = LockTraceCLI()

        # Mock the dependencies
        self.mock_cscope = AsyncMock()
        self.mock_tracer = AsyncMock()
        self.mock_analyzer = AsyncMock()

        self.cli.cscope = self.mock_cscope
        self.cli.tracer = self.mock_tracer
        self.cli.analyzer = self.mock_analyzer

    @pytest.mark.asyncio
    async def test_analyze_lock_context_without_locks_shows_none(self):
        """Test that analyze_lock_context shows 'None' when no specific locks are requested."""
        # Mock function exists check
        self.mock_cscope.function_exists.return_value = True

        # Mock lock context with actual held locks
        mock_context = LockContext(
            function="target_func",
            held_locks={"spin_lock_bh"},  # Function actually holds locks
            call_path=["caller_func", "target_func"],
            lock_operations=[
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "acquire",
                    "caller_func",
                    "file.c",
                    10,
                    "spin_lock_bh(&lock);",
                ),
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "release",
                    "caller_func",
                    "file.c",
                    20,
                    "spin_unlock_bh(&lock);",
                ),
            ],
        )

        self.mock_analyzer.analyze_lock_context.return_value = [mock_context]

        # Capture stdout
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            await self.cli.analyze_lock_context(
                function="target_func",
                locks=None,  # No specific locks requested
                tree=False,
                verbose=False,
            )

        output = captured_output.getvalue()

        # Should show "None" for held locks when no specific locks are requested
        assert "Held locks: None" in output
        # Should still show lock operations for analysis
        assert "acquire spin_lock_bh (spinlock)" in output
        assert "release spin_lock_bh (spinlock)" in output

    @pytest.mark.asyncio
    async def test_analyze_lock_context_with_locks_shows_actual_locks(self):
        """Test that analyze_lock_context shows actual held locks when specific locks are requested."""
        # Mock function exists check
        self.mock_cscope.function_exists.return_value = True

        # Mock lock context with matching held locks
        mock_context = LockContext(
            function="target_func",
            held_locks={"spin_lock_bh"},  # Function holds the requested lock type
            call_path=["caller_func", "target_func"],
            lock_operations=[
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "acquire",
                    "caller_func",
                    "file.c",
                    10,
                    "spin_lock_bh(&lock);",
                ),
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "release",
                    "caller_func",
                    "file.c",
                    20,
                    "spin_unlock_bh(&lock);",
                ),
            ],
        )

        self.mock_analyzer.analyze_lock_context.return_value = [mock_context]

        # Capture stdout
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            await self.cli.analyze_lock_context(
                function="target_func",
                locks=["spin"],  # Specific lock type requested
                tree=False,
                verbose=False,
            )

        output = captured_output.getvalue()

        # Should show "Tracking locks" when specific locks are requested
        assert "Tracking locks: spin" in output
        # Should show actual held locks, not "None"
        assert "Held locks: spin_lock_bh" in output
        # Should show lock operations
        assert "acquire spin_lock_bh (spinlock)" in output
        assert "release spin_lock_bh (spinlock)" in output

    @pytest.mark.asyncio
    async def test_analyze_lock_context_with_locks_no_match_shows_none(self):
        """Test that analyze_lock_context shows 'None' when requested locks are not held."""
        # Mock function exists check
        self.mock_cscope.function_exists.return_value = True

        # Mock lock context without held locks (no match for requested lock)
        mock_context = LockContext(
            function="target_func",
            held_locks=set(),  # No locks held
            call_path=["caller_func", "target_func"],
            lock_operations=[
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "acquire",
                    "caller_func",
                    "file.c",
                    10,
                    "spin_lock_bh(&lock);",
                ),
                LockOperation(
                    "spin_lock_bh",
                    LockType.SPINLOCK,
                    "release",
                    "caller_func",
                    "file.c",
                    20,
                    "spin_unlock_bh(&lock);",
                ),
            ],
        )

        self.mock_analyzer.analyze_lock_context.return_value = [mock_context]

        # Capture stdout
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            await self.cli.analyze_lock_context(
                function="target_func",
                locks=["mutex"],  # Request different lock type
                tree=False,
                verbose=False,
            )

        output = captured_output.getvalue()

        # Should show "Tracking locks" when specific locks are requested
        assert "Tracking locks: mutex" in output
        # Should show "None" since no matching locks are held
        assert "Held locks: None" in output
        # Should still show lock operations
        assert "acquire spin_lock_bh (spinlock)" in output

    @pytest.mark.asyncio
    async def test_analyze_lock_context_function_not_found(self):
        """Test that analyze_lock_context handles non-existent functions."""
        # Mock function does not exist
        self.mock_cscope.function_exists.return_value = False

        # Capture stderr
        captured_error = io.StringIO()
        with patch("sys.stderr", captured_error):
            await self.cli.analyze_lock_context(
                function="nonexistent_func", locks=None, tree=False, verbose=False
            )

        error_output = captured_error.getvalue()

        # Should show error message for non-existent function
        assert "Error: Function 'nonexistent_func' not found" in error_output

        # Should not call analyzer if function doesn't exist
        self.mock_analyzer.analyze_lock_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_lock_context_no_call_paths_found(self):
        """Test that analyze_lock_context handles functions with no call paths."""
        # Mock function exists but has no call paths
        self.mock_cscope.function_exists.return_value = True
        self.mock_analyzer.analyze_lock_context.return_value = []

        # Capture stdout
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            await self.cli.analyze_lock_context(
                function="isolated_func", locks=None, tree=False, verbose=False
            )

        output = captured_output.getvalue()

        # Should show "No call paths found" message
        assert "No call paths found for analysis." in output
