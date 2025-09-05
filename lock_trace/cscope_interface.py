"""Cscope integration module for querying function call relationships."""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class FunctionCall:
    """Represents a function call relationship."""

    function: str
    file: str
    line: int
    context: str


@dataclass
class FunctionAssignment:
    """Represents a function pointer assignment (callback registration)."""

    function: str  # The function being assigned (e.g., hsr_newlink)
    operation: str  # The operation name (e.g., newlink)
    file: str
    line: int
    context: str
    struct_name: Optional[str] = (
        None  # The structure name if detected (e.g., rtnl_link_ops)
    )


class CscopeInterface:
    """Interface for interacting with cscope database."""

    def __init__(
        self,
        database_path: str = ".",
        cscope_file: Optional[str] = None,
        source_dir: Optional[str] = None,
    ):
        """Initialize cscope interface.

        Args:
            database_path: Path to directory containing cscope database (default: current directory)
            cscope_file: Path to cscope.out file (default: cscope.out in database_path)
            source_dir: Path to source code directory (default: same as database_path)
        """
        self.database_path = Path(database_path).resolve()
        self.cscope_file = (
            Path(cscope_file).resolve()
            if cscope_file
            else self.database_path / "cscope.out"
        )
        self.source_dir = (
            Path(source_dir).resolve() if source_dir else self.database_path
        )
        # Note: validation needs to be called separately for async initialization

    async def _validate_database(self) -> None:
        """Validate that cscope database exists."""
        # Check if cscope.out file exists
        if not self.cscope_file.exists():
            raise RuntimeError(f"Cscope database file not found: {self.cscope_file}")

        # Check if source directory exists
        if not self.source_dir.exists():
            raise RuntimeError(f"Source directory not found: {self.source_dir}")

        try:
            # Test cscope with explicit database file
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-0",
                "main",
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            if process.returncode != 0:
                raise RuntimeError(
                    f"Cscope database invalid or corrupted: {self.cscope_file}"
                )
        except FileNotFoundError:
            raise RuntimeError("cscope command not found. Please install cscope.")
        except asyncio.TimeoutError:
            raise RuntimeError("Cscope query timed out. Database may be corrupted.")

    async def get_functions_called_by(self, function: str) -> List[FunctionCall]:
        """Get functions called by the specified function.

        Uses cscope -d -L -2 func to find functions called by func.

        Args:
            function: Name of the function to analyze

        Returns:
            List of FunctionCall objects representing called functions
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-2",
                function,
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0:
                return []

            return self._parse_cscope_output(stdout.decode())

        except asyncio.TimeoutError:
            raise RuntimeError(f"Cscope query for {function} timed out")

    async def get_functions_calling(self, function: str) -> List[FunctionCall]:
        """Get functions that call the specified function.

        Uses cscope -d -L -3 func to find functions that call func.

        Args:
            function: Name of the function to analyze

        Returns:
            List of FunctionCall objects representing calling functions
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-3",
                function,
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0:
                return []

            return self._parse_cscope_output(stdout.decode())

        except asyncio.TimeoutError:
            raise RuntimeError(f"Cscope query for {function} timed out")

    def _parse_cscope_output(self, output: str) -> List[FunctionCall]:
        """Parse cscope output into FunctionCall objects.

        Cscope output format: filename function line_number context

        Args:
            output: Raw cscope output

        Returns:
            List of parsed FunctionCall objects
        """
        calls = []
        for line in output.strip().split("\n"):
            if not line:
                continue

            # Parse cscope output: filename function line_number context
            parts = line.split(" ", 3)
            if len(parts) >= 4:
                file_path = parts[0]
                function_name = parts[1]
                try:
                    line_number = int(parts[2])
                    context = parts[3] if len(parts) > 3 else ""

                    calls.append(
                        FunctionCall(
                            function=function_name,
                            file=file_path,
                            line=line_number,
                            context=context.strip(),
                        )
                    )
                except ValueError:
                    # Skip lines with invalid line numbers
                    continue

        return calls

    async def function_exists(self, function: str) -> bool:
        """Check if a function exists in the cscope database.

        Args:
            function: Name of the function to check

        Returns:
            True if function exists, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-1",
                function,
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            return process.returncode == 0 and bool(stdout.decode().strip())
        except asyncio.TimeoutError:
            return False

    async def find_function_definition(self, function: str) -> Optional[FunctionCall]:
        """Find the definition of a function.

        Uses cscope -d -L -1 func to find function definition.

        Args:
            function: Name of the function to find

        Returns:
            FunctionCall object for the definition, or None if not found
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-1",
                function,
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)

            if process.returncode != 0 or not stdout.decode().strip():
                return None

            calls = self._parse_cscope_output(stdout.decode())
            return calls[0] if calls else None

        except asyncio.TimeoutError:
            return None

    async def find_function_assignments(
        self, function: str
    ) -> List[FunctionAssignment]:
        """Find callback function assignments for the specified function.

        Uses cscope -d -L -0 func to find assignments like .operation = function.

        Args:
            function: Name of the function to analyze

        Returns:
            List of FunctionAssignment objects representing callback assignments
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-0",
                function,
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0:
                return []

            return self._parse_function_assignments(stdout.decode(), function)

        except asyncio.TimeoutError:
            raise RuntimeError(f"Cscope assignment query for {function} timed out")

    def _parse_function_assignments(
        self, output: str, function: str
    ) -> List[FunctionAssignment]:
        """Parse cscope -L -0 output to find function assignments.

        Args:
            output: Raw cscope output
            function: The function being assigned

        Returns:
            List of FunctionAssignment objects
        """
        assignments = []

        # Pattern to match: .operation = function_name,
        assignment_pattern = re.compile(r"\.(\w+)\s*=\s*" + re.escape(function) + r"\b")

        for line in output.strip().split("\n"):
            if not line:
                continue

            # Parse cscope output: filename function/scope line_number context
            parts = line.split(" ", 3)
            if len(parts) >= 4:
                file_path = parts[0]
                # parts[1] is scope (could be function name or <global>)
                try:
                    line_number = int(parts[2])
                    context = parts[3] if len(parts) > 3 else ""

                    # Look for callback assignments
                    match = assignment_pattern.search(context)
                    if match:
                        operation = match.group(1)
                        assignments.append(
                            FunctionAssignment(
                                function=function,
                                operation=operation,
                                file=file_path,
                                line=line_number,
                                context=context.strip(),
                            )
                        )
                except ValueError:
                    continue

        return assignments

    async def get_callback_callers(self, function: str) -> List[FunctionCall]:
        """Get enhanced caller list including callback function callers.

        First tries direct callers, then looks for callback assignments and
        searches for callers of the operation name.

        Args:
            function: Name of the function to analyze

        Returns:
            List of FunctionCall objects representing all possible callers
        """
        # Get direct callers first
        direct_callers = await self.get_functions_calling(function)

        # If we found direct callers, return them
        if direct_callers:
            return direct_callers

        # Look for callback assignments
        assignments = await self.find_function_assignments(function)
        callback_callers = []

        for assignment in assignments:
            # Search for callers of the operation
            operation_callers = await self.get_functions_calling(assignment.operation)

            # Filter callers by structure type context if possible
            filtered_callers = await self._filter_callers_by_struct_context(
                operation_callers, assignment
            )

            callback_callers.extend(filtered_callers)

        return callback_callers

    async def _filter_callers_by_struct_context(
        self, callers: List[FunctionCall], assignment: FunctionAssignment
    ) -> List[FunctionCall]:
        """Filter operation callers by structure type context.

        Attempts to match the structure type from the assignment context
        with the caller context to ensure accurate results.

        Args:
            callers: List of potential callers
            assignment: The function assignment containing context

        Returns:
            Filtered list of callers that match the structure context
        """
        # Try to extract structure name from assignment context
        struct_name = await self._extract_struct_name_from_assignment(assignment)
        if not struct_name:
            # If we can't determine the struct type, return all callers
            return callers

        # Try to get the full structure definition to understand its fields
        struct_info = await self._get_struct_info(struct_name, assignment.file)
        if not struct_info:
            return callers

        # Filter callers based on whether they use a compatible structure
        filtered_callers = []
        for caller in callers:
            if await self._is_caller_using_compatible_struct(
                caller, struct_name, struct_info
            ):
                filtered_callers.append(caller)

        return filtered_callers

    async def _extract_struct_name_from_assignment(
        self, assignment: FunctionAssignment
    ) -> Optional[str]:
        """Extract structure name from assignment context.

        Looks for patterns in the source file around the assignment location.

        Args:
            assignment: The function assignment

        Returns:
            Structure name if detected, None otherwise
        """
        try:
            # Read the source file to analyze context
            file_path = self.source_dir / assignment.file
            if not file_path.exists():
                return None

            import aiofiles

            async with aiofiles.open(file_path, encoding="utf-8", errors="ignore") as f:
                content = await f.read()
                lines = content.splitlines()

            # Look for struct definition around the assignment line
            start_line = max(0, assignment.line - 50)  # Look up to 50 lines before
            end_line = min(
                len(lines), assignment.line + 10
            )  # Look up to 10 lines after

            # Pattern to match struct definitions
            struct_pattern = re.compile(r"struct\s+(\w+)\s+\w+\s*=\s*{")
            static_struct_pattern = re.compile(r"static\s+struct\s+(\w+)\s+\w+\s*=\s*{")

            for i in range(start_line, end_line):
                line = lines[i].strip()

                # Check for struct definition
                match = static_struct_pattern.search(line) or struct_pattern.search(
                    line
                )
                if match:
                    return match.group(1)

        except (OSError, UnicodeDecodeError, IndexError):
            pass

        return None

    async def _get_struct_info(
        self, struct_name: str, context_file: str
    ) -> Optional[dict]:
        """Get information about a structure definition.

        Args:
            struct_name: Name of the structure
            context_file: File where the assignment was found (for context)

        Returns:
            Dictionary with structure information, or None if not found
        """
        try:
            # Use cscope to find the struct definition
            process = await asyncio.create_subprocess_exec(
                "cscope",
                "-d",
                "-f",
                str(self.cscope_file),
                "-L",
                "-1",
                f"struct {struct_name}",
                cwd=self.source_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)

            if process.returncode == 0 and stdout.decode().strip():
                # For now, just return basic info
                return {"name": struct_name, "found": True}

        except asyncio.TimeoutError:
            pass

        return None

    async def _is_caller_using_compatible_struct(
        self, caller: FunctionCall, struct_name: str, struct_info: dict
    ) -> bool:
        """Check if caller is using a compatible structure type.

        This is a simplified implementation that looks for struct name patterns
        in the caller context.

        Args:
            caller: The function call to check
            struct_name: Expected structure name
            struct_info: Structure information

        Returns:
            True if caller appears to use compatible structure
        """
        # Look for the struct name in the caller context
        context_lower = caller.context.lower()
        struct_name_lower = struct_name.lower()

        # Check if the struct name appears in the context
        if struct_name_lower in context_lower:
            return True

        # For now, if we can't determine compatibility, include the caller
        # This can be made more sophisticated with better context analysis
        return True
