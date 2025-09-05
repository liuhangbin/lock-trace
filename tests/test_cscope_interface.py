"""Tests for cscope interface module."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from lock_trace.cscope_interface import (
    CscopeInterface,
    FunctionAssignment,
)


class TestCscopeInterface:
    """Test cases for CscopeInterface."""

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_init_success(self, mock_exists, mock_run):
        """Test successful initialization."""
        mock_exists.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="test output")

        interface = CscopeInterface("/test/path")
        assert str(interface.database_path).endswith("test/path")
        assert str(interface.cscope_file).endswith("cscope.out")
        assert str(interface.source_dir).endswith("test/path")

    @patch("pathlib.Path.exists")
    def test_init_database_not_found(self, mock_exists):
        """Test initialization with missing database."""
        mock_exists.return_value = False

        with pytest.raises(RuntimeError, match="Cscope database file not found"):
            CscopeInterface("/test/path")

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_init_cscope_not_installed(self, mock_run, mock_exists):
        """Test initialization when cscope is not installed."""
        mock_exists.return_value = True
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="cscope command not found"):
            CscopeInterface("/test/path")

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_init_custom_paths(self, mock_exists, mock_run):
        """Test initialization with custom cscope file and source directory."""
        mock_exists.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="test output")

        interface = CscopeInterface(
            database_path="/db/path",
            cscope_file="/custom/cscope.out",
            source_dir="/src/path",
        )

        assert str(interface.database_path).endswith("db/path")
        assert str(interface.cscope_file).endswith("custom/cscope.out")
        assert str(interface.source_dir).endswith("src/path")

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_functions_called_by_success(self, mock_run, mock_exists):
        """Test successful function call query."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(
                returncode=0,
                stdout="file.c func1 123 context line\nfile.c func2 456 another context",
            ),
        ]

        interface = CscopeInterface("/test/path")
        calls = interface.get_functions_called_by("test_func")

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
    @patch("subprocess.run")
    def test_get_functions_calling_success(self, mock_run, mock_exists):
        """Test successful caller query."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=0, stdout="caller.c caller1 789 calling context"),
        ]

        interface = CscopeInterface("/test/path")
        calls = interface.get_functions_calling("test_func")

        assert len(calls) == 1
        assert calls[0].function == "caller1"
        assert calls[0].file == "caller.c"
        assert calls[0].line == 789
        assert calls[0].context == "calling context"

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_parse_cscope_output_invalid_lines(self, mock_run, mock_exists):
        """Test parsing output with invalid lines."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(
                returncode=0,
                stdout="file.c func1 invalid_line context\nfile.c func2 456 valid context",
            ),
        ]

        interface = CscopeInterface("/test/path")
        calls = interface.get_functions_called_by("test_func")

        # Should skip the invalid line and only return the valid one
        assert len(calls) == 1
        assert calls[0].function == "func2"
        assert calls[0].line == 456

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_function_exists_true(self, mock_run, mock_exists):
        """Test function exists check returning true."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=0, stdout="file.c test_func 123 function definition"),
        ]

        interface = CscopeInterface("/test/path")
        assert interface.function_exists("test_func") is True

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_function_exists_false(self, mock_run, mock_exists):
        """Test function exists check returning false."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=1, stdout=""),
        ]

        interface = CscopeInterface("/test/path")
        assert interface.function_exists("nonexistent_func") is False

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_find_function_definition_success(self, mock_run, mock_exists):
        """Test successful function definition search."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=0, stdout="file.c test_func 123 function definition"),
        ]

        interface = CscopeInterface("/test/path")
        definition = interface.find_function_definition("test_func")

        assert definition is not None
        assert definition.function == "test_func"
        assert definition.file == "file.c"
        assert definition.line == 123

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_find_function_definition_not_found(self, mock_run, mock_exists):
        """Test function definition search when not found."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=1, stdout=""),
        ]

        interface = CscopeInterface("/test/path")
        definition = interface.find_function_definition("nonexistent_func")

        assert definition is None

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run, mock_exists):
        """Test timeout handling in queries."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            subprocess.TimeoutExpired("cscope", 30),
        ]

        interface = CscopeInterface("/test/path")

        with pytest.raises(RuntimeError, match="timed out"):
            interface.get_functions_called_by("test_func")

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_find_function_assignments(self, mock_run, mock_exists):
        """Test finding function assignments (callbacks)."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(
                returncode=0,
                stdout="net/hsr/hsr_netlink.c <global> 184 .newlink = hsr_newlink,\nnet/hsr/hsr_netlink.c hsr_newlink 32 static int hsr_newlink(struct net_device *dev,"
            ),
        ]

        interface = CscopeInterface("/test/path")
        assignments = interface.find_function_assignments("hsr_newlink")

        assert len(assignments) == 1
        assert assignments[0].function == "hsr_newlink"
        assert assignments[0].operation == "newlink"
        assert assignments[0].file == "net/hsr/hsr_netlink.c"
        assert assignments[0].line == 184

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_callback_callers_direct_callers_found(self, mock_run, mock_exists):
        """Test callback callers when direct callers are found."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(
                returncode=0,
                stdout="test.c direct_caller 10 direct_caller(hsr_newlink);"
            ),
        ]

        interface = CscopeInterface("/test/path")
        callers = interface.get_callback_callers("hsr_newlink")

        assert len(callers) == 1
        assert callers[0].function == "direct_caller"

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_get_callback_callers_no_direct_with_assignments(self, mock_run, mock_exists):
        """Test callback callers when no direct callers but assignments found."""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(returncode=0, stdout="test output"),  # __init__ validation
            Mock(returncode=0, stdout=""),  # No direct callers
            Mock(
                returncode=0,
                stdout="net/hsr/hsr_netlink.c <global> 184 .newlink = hsr_newlink,"
            ),  # Assignment found
            Mock(
                returncode=0,
                stdout="net/core/rtnetlink.c rtnl_newlink_create 3825 err = ops->newlink(dev, &params, extack);"
            ),  # Operation callers
        ]

        interface = CscopeInterface("/test/path")
        callers = interface.get_callback_callers("hsr_newlink")

        assert len(callers) == 1
        assert callers[0].function == "rtnl_newlink_create"

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_parse_function_assignments(self, mock_run, mock_exists):
        """Test parsing function assignment output."""
        mock_exists.return_value = True
        mock_run.side_effect = [Mock(returncode=0, stdout="test output")]

        interface = CscopeInterface("/test/path")

        output = "net/hsr/hsr_netlink.c <global> 184 .newlink = hsr_newlink,\nnet/hsr/hsr_netlink.c <global> 185 .dellink = hsr_dellink,"
        assignments = interface._parse_function_assignments(output, "hsr_newlink")

        assert len(assignments) == 1
        assert assignments[0].operation == "newlink"
        assert assignments[0].function == "hsr_newlink"

    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    def test_extract_struct_name_from_assignment(self, mock_run, mock_exists):
        """Test extracting structure name from assignment context."""
        mock_exists.return_value = True
        mock_run.side_effect = [Mock(returncode=0, stdout="test output")]

        # Create a mock file with struct definition
        with patch("builtins.open", create=True) as mock_open:
            mock_file_content = [
                "static struct rtnl_link_ops hsr_link_ops = {\n",
                "    .kind = DRV_NAME,\n",
                "    .newlink = hsr_newlink,\n",
                "};\n"
            ]
            mock_open.return_value.__enter__.return_value.readlines.return_value = mock_file_content

            interface = CscopeInterface("/test/path")
            assignment = FunctionAssignment(
                function="hsr_newlink",
                operation="newlink",
                file="net/hsr/hsr_netlink.c",
                line=3,
                context=".newlink = hsr_newlink,"
            )

            struct_name = interface._extract_struct_name_from_assignment(assignment)
            assert struct_name == "rtnl_link_ops"
