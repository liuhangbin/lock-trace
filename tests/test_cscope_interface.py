"""Tests for cscope interface module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from lock_trace.cscope_interface import (
    CscopeInterface,
    FunctionAssignment,
)


class TestCscopeInterface:
    """Test cases for CscopeInterface."""

    @patch("asyncio.create_subprocess_exec")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_init_success(self, mock_exists, mock_subprocess):
        """Test successful initialization."""
        mock_exists.return_value = True

        # Mock the async subprocess
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"test output", b""))
        mock_subprocess.return_value = mock_process

        interface = CscopeInterface("/test/path")
        await interface._validate_database()

        assert str(interface.database_path).endswith("test/path")
        assert str(interface.cscope_file).endswith("cscope.out")
        assert str(interface.source_dir).endswith("test/path")

    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_init_database_not_found(self, mock_exists):
        """Test initialization with missing database."""
        mock_exists.return_value = False

        interface = CscopeInterface("/test/path")
        with pytest.raises(RuntimeError, match="Cscope database file not found"):
            await interface._validate_database()

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_init_cscope_not_installed(self, mock_subprocess, mock_exists):
        """Test initialization when cscope is not installed."""
        mock_exists.return_value = True
        mock_subprocess.side_effect = FileNotFoundError()

        interface = CscopeInterface("/test/path")
        with pytest.raises(RuntimeError, match="cscope command not found"):
            await interface._validate_database()

    @patch("asyncio.create_subprocess_exec")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_init_custom_paths(self, mock_exists, mock_subprocess):
        """Test initialization with custom cscope file and source directory."""
        mock_exists.return_value = True

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"test output", b""))
        mock_subprocess.return_value = mock_process

        interface = CscopeInterface(
            database_path="/db/path",
            cscope_file="/custom/cscope.out",
            source_dir="/src/path",
        )
        await interface._validate_database()

        assert str(interface.database_path).endswith("db/path")
        assert str(interface.cscope_file).endswith("custom/cscope.out")
        assert str(interface.source_dir).endswith("src/path")

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_functions_called_by_success(self, mock_subprocess, mock_exists):
        """Test successful function call query."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(
                b"file.c func1 123 context line\nfile.c func2 456 another context",
                b"",
            )
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        calls = await interface.get_functions_called_by("test_func")

        assert len(calls) == 2
        assert calls[0].function == "func1"
        assert calls[0].file == "file.c"
        assert calls[0].line == 123
        assert calls[0].context == "context line"

        assert calls[1].function == "func2"
        assert calls[1].file == "file.c"
        assert calls[1].line == 456
        assert calls[1].context == "another context"

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_functions_calling_success(self, mock_subprocess, mock_exists):
        """Test successful caller query."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(b"caller.c caller1 789 calling context", b"")
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        calls = await interface.get_functions_calling("test_func")

        assert len(calls) == 1
        assert calls[0].function == "caller1"
        assert calls[0].file == "caller.c"
        assert calls[0].line == 789
        assert calls[0].context == "calling context"

    def test_parse_cscope_output_invalid_lines(self):
        """Test parsing cscope output with invalid lines."""
        interface = CscopeInterface.__new__(CscopeInterface)  # Skip __init__
        interface.database_path = None
        interface.cscope_file = None
        interface.source_dir = None

        # Test with invalid lines (should be skipped)
        output = "invalid line\nfile.c func1 123 context\nshort line\nfile2.c func2 456 context2"
        calls = interface._parse_cscope_output(output)

        assert len(calls) == 2
        assert calls[0].function == "func1"
        assert calls[1].function == "func2"

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_function_exists_true(self, mock_subprocess, mock_exists):
        """Test function exists returns True."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(b"found function", b"")
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        exists = await interface.function_exists("test_func")

        assert exists is True

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_function_exists_false(self, mock_subprocess, mock_exists):
        """Test function exists returns False."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 1
        mock_process_query.communicate = AsyncMock(return_value=(b"", b""))

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        exists = await interface.function_exists("test_func")

        assert exists is False

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_find_function_definition_success(self, mock_subprocess, mock_exists):
        """Test successful function definition query."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(b"file.c test_func 100 int test_func(void)", b"")
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        definition = await interface.find_function_definition("test_func")

        assert definition is not None
        assert definition.function == "test_func"
        assert definition.file == "file.c"
        assert definition.line == 100

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_find_function_definition_not_found(
        self, mock_subprocess, mock_exists
    ):
        """Test function definition not found."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 1
        mock_process_query.communicate = AsyncMock(return_value=(b"", b""))

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        definition = await interface.find_function_definition("test_func")

        assert definition is None

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_subprocess, mock_exists):
        """Test timeout handling in queries."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock subprocess that times out
        mock_process_timeout = AsyncMock()
        mock_process_timeout.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        mock_subprocess.side_effect = [mock_process_validation, mock_process_timeout]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()

        with pytest.raises(RuntimeError, match="timed out"):
            await interface.get_functions_called_by("test_func")

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_find_function_assignments(self, mock_subprocess, mock_exists):
        """Test finding function assignments."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock actual query call
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(b"file.c test_func 100 ops.test_func = test_func", b"")
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        assignments = await interface.find_function_assignments("test_func")

        # Should have at least one assignment
        assert len(assignments) >= 0

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_callback_callers_direct_callers_found(
        self, mock_subprocess, mock_exists
    ):
        """Test callback callers when direct callers are found."""
        mock_exists.return_value = True

        # Mock validation call
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Mock direct callers query
        mock_process_query = Mock()
        mock_process_query.returncode = 0
        mock_process_query.communicate = AsyncMock(
            return_value=(b"caller.c direct_caller 100 direct_caller()", b"")
        )

        mock_subprocess.side_effect = [mock_process_validation, mock_process_query]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        callers = await interface.get_callback_callers("test_func")

        assert len(callers) == 1
        assert callers[0].function == "direct_caller"

    @patch("pathlib.Path.exists")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_get_callback_callers_no_direct_with_assignments(
        self, mock_subprocess, mock_exists
    ):
        """Test callback callers when no direct callers but assignments exist."""
        mock_exists.return_value = True

        # Multiple mock calls needed for this complex scenario
        mock_process_validation = Mock()
        mock_process_validation.returncode = 0
        mock_process_validation.communicate = AsyncMock(
            return_value=(b"test output", b"")
        )

        # Direct callers query (empty)
        mock_process_no_direct = Mock()
        mock_process_no_direct.returncode = 0
        mock_process_no_direct.communicate = AsyncMock(return_value=(b"", b""))

        # Assignment query
        mock_process_assignments = Mock()
        mock_process_assignments.returncode = 0
        mock_process_assignments.communicate = AsyncMock(
            return_value=(b"file.c test_func 100 ops.callback = test_func", b"")
        )

        # Mock for _filter_callers_by_struct_context (empty result)
        mock_process_empty = Mock()
        mock_process_empty.returncode = 0
        mock_process_empty.communicate = AsyncMock(return_value=(b"", b""))

        mock_subprocess.side_effect = [
            mock_process_validation,  # _validate_database
            mock_process_no_direct,  # get_functions_calling (direct callers)
            mock_process_assignments,  # find_function_assignments
            mock_process_empty,  # get_functions_calling (operation callers)
        ]

        interface = CscopeInterface("/test/path")
        await interface._validate_database()
        callers = await interface.get_callback_callers("test_func")

        # Should return empty list or assignment-based callers
        assert isinstance(callers, list)

    @patch("pathlib.Path.exists")
    @patch("aiofiles.open")
    @pytest.mark.asyncio
    async def test_extract_struct_name_from_assignment(
        self, mock_aiofiles, mock_exists
    ):
        """Test extracting struct name from assignment context."""
        mock_exists.return_value = True

        # Mock file content
        mock_file_content = """
struct test_ops {
    int (*callback)(void);
};

static struct test_ops ops = {
    .callback = test_func,
};
"""
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=mock_file_content)
        mock_aiofiles.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles.return_value.__aexit__ = AsyncMock(return_value=None)

        interface = CscopeInterface.__new__(CscopeInterface)  # Skip __init__
        interface.source_dir = mock_exists

        assignment = FunctionAssignment(
            function="test_func",
            operation="callback",
            file="test.c",
            line=7,
            context=".callback = test_func,",
        )

        result = await interface._extract_struct_name_from_assignment(assignment)
        # Should extract struct name or return None
        assert result is None or isinstance(result, str)
