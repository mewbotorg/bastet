# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Support classes for running a series of tools across the codebase.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable
from typing import NamedTuple

import abc
import asyncio
import dataclasses
import enum
import pathlib
from collections import Counter

from .exceptions import InvalidDomainError, ProcessError, ToolError


class ToolDomain(enum.StrEnum):
    FORMAT = "Format"
    LINT = "Lint"
    AUDIT = "Audit"


class Status(enum.Enum):
    PASSED = "Passed"
    FIXED = "Fixed"
    WARNING = "Warning"
    FAILED = "Failed"
    ERROR = "Error"

    def __lt__(self, other: Status) -> bool:
        return _STATUS_ORDERING[self] < _STATUS_ORDERING[other]

    def __gt__(self, other: Status) -> bool:
        return _STATUS_ORDERING[self] > _STATUS_ORDERING[other]

    def __ge__(self, other: Status) -> bool:
        return other == self or self.__gt__(other)


_STATUS_ORDERING = {name: idx for idx, name in enumerate(Status)}


class ToolResult(NamedTuple):
    success: Status
    exit_code: int
    annotation_counts: dict[Status, int]

    def annotation_above(self, status: Status) -> int:
        return sum(v for k, v in self.annotation_counts.items() if k >= status)

    def annotation_count(self, status: Status) -> int:
        return self.annotation_counts.get(status, 0)


class Tool(abc.ABC):
    """
    A Tool represents something Panthera can run to validate code.

    The tool object is a wrapper around an external program, and
    is responsible for converting the output into a series of annotations.
    """

    _domain: ToolDomain

    @classmethod
    @abc.abstractmethod
    def domains(cls) -> set[ToolDomain]:
        """
        What 'domains' this tool belongs to.

        This represents what kind of checking the tool is useful for.
        Examples include 'formatting', 'linting', and 'testing'.

        A tool may belong to multiple domains, and the behaviour of
        the tool may differ based on the domain it is called for.
        For example, most formatting tools have a check function that
        would belong to the linting domain.
        """

    def __init__(self, domain: ToolDomain, paths: PathRepo) -> None:
        """
        Create an instance of this tool controller for the specified domain.

        This will raise a ValueError if the domain is not one the tool supports.
        It will also
        """

        if domain not in self.domains():
            raise InvalidDomainError(domain, self.name)

        self._domain = domain
        self._paths = paths

    def __repr__(self) -> str:
        return f"<{self._domain}:{self.name}@{id(self)}>"

    @property
    def name(self) -> str:
        """The name of the tool for logging."""
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """A summary of the tool."""
        return self.__class__.__doc__ or self.__class__.__name__

    @property
    def domain(self) -> ToolDomain:
        """The domain this instance of the tool is running in."""
        return self._domain

    @abc.abstractmethod
    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).

        This will be directly executed (i.e. not in a shell).
        The list of root folders is provided in an argument;
        the tool should be configured to examine these recursively.
        """

    @abc.abstractmethod
    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.

        These will be merged into the environment that panthera
        was called in.
        """

    @abc.abstractmethod
    async def process_results(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Process the standard output of the command, and output annotations.

        Each tool is expected to parse the output from the call it
        requested and convert it into a series of annotations.
        If there are errors parsing the output, the Tool can yield
        ToolErrors. Errors reported by the tool (but are parsable)
        should be handled as 'ERROR' status annotations.

        Both the Annotations and ToolErrors will be passed to the
        Reporters, and the ToolResults collection.
        """
        yield Annotation(Status.ERROR, None, "bad-class", "Abstract Method Called")

    def acceptable_exit_codes(self) -> set[int]:
        """
        Status codes from the command that indicate the tool succeeded.

        The tool run will be considered overall successful if it exits
        with one of these codes, and did not produce any annotations
        with a 'failed' or 'error' status.
        """
        return {0}


class ToolResults:
    """
    Result information for a collection of Tool.

    This is the object passed into the Reporter::summarize() function,
    allowing a reporter to give an overview of all output when the Tools
    have been run.

    The result of each tool is recorded and updates the overall success
    status. A Tool is considered to have failed either if it exits with
    an unexpected status code, or emits any Annotations that are errors
    or failures.

    Along with the individual tools results (which are recorded with the
    domain the tool was run in), all annotations and ToolError exceptions
    are collated into a single list.
    """

    success: bool = True
    annotations: list[Annotation]
    exceptions: list[ToolError]
    results: dict[Tool, ToolResult]

    def __init__(self) -> None:
        """
        Creates an empty result set.
        """
        self.success = True
        self.results = {}
        self.annotations = []
        self.exceptions = []

    async def record(
        self,
        tool: Tool,
        annotations: list[Annotation],
        exceptions: list[ToolError],
        exit_code: int,
    ) -> None:
        """
        Add the result of a Tool to this class.

        This will update the success value to False if the tool failed,
        and append the annotations and exceptions from the tool to the lists.
        """

        if exit_code not in tool.acceptable_exit_codes():
            exceptions.append(ProcessError(exit_code, tool.get_command()))

        annotation_levels = Counter(annotation.status for annotation in annotations)

        if exceptions:
            status = Status.ERROR
        elif annotations:
            status = max(annotation_levels)
        else:
            status = Status.PASSED

        self.success = self.success and (status < Status.FAILED)
        self.annotations.extend(annotations)
        self.exceptions.extend(exceptions)
        self.results[tool] = ToolResult(status, exit_code, annotation_levels)


@dataclasses.dataclass
class Annotation:
    """
    Schema for a GitHub action annotation, representing an error.

    TODO: New description
    """

    _CWD = pathlib.Path.cwd().absolute()

    @classmethod
    def set_root(cls, path: pathlib.Path) -> None:
        cls._CWD = path

    @classmethod
    def _normalise_source(
        cls,
        source: tuple[pathlib.Path, int | None, int | None] | pathlib.Path | None,
    ) -> tuple[pathlib.Path, int, int]:
        if not source:
            return cls._CWD, 0, 0

        if isinstance(source, pathlib.Path):
            return source.absolute(), 0, 0

        return source[0].absolute(), source[1] or 0, source[2] or 0

    status: Status
    source: tuple[pathlib.Path, int, int]
    tool: Tool
    code: str

    message: str
    description: str | None
    diff: list[str] | None

    def __init__(  # noqa: PLR0913 - 6 args is "ok" here.
        self,
        status: Status,
        source: tuple[pathlib.Path, int | None, int | None] | pathlib.Path | None,
        code: str,
        message: str,
        description: str | None = None,
    ) -> None:
        self.status = status
        self.source = self._normalise_source(source)
        self.code = code.strip()
        self.message = message.strip()
        self.description = description.strip() if description else None
        self.diff = None

    def json(self) -> dict[str, str | int]:
        """Output this object as a JSON-encodeable dictionary."""

        return dataclasses.asdict(self)

    @property
    def filename(self) -> str:
        root = self._CWD

        if self.source[0] == root:
            return "[project]"

        return str(self.source[0].relative_to(self._CWD))

    @property
    def file_str(self) -> str:
        """
        Returns the project path of the file, with the line number and column if set.
        """
        root = self._CWD

        if self.source[0] == root:
            return "[project]"

        file = str(self.source[0].relative_to(self._CWD))

        if not self.source[1]:
            return file

        return file + ":" + str(self.source[1])

    def __hash__(self) -> int:
        """
        Unique hash of this annotation.

        This is a combination of the source location, tool, and the message code.
        """

        return hash(
            (self.status, self.tool, self.source, self.code),
        )

    def __lt__(self, other: Annotation) -> bool:
        """Sorts annotations by file path and then line number."""

        if not isinstance(other, Annotation):
            return False

        if self.source == other.source:
            return self.code < other.code

        return self.source < other.source

    def same_source(self, source: tuple[pathlib.Path, int | None, int | None] | None) -> bool:
        return self._normalise_source(source) == self.source

    def add_note(self, info: str) -> None:
        if self.description:
            self.description += "\n" + info.rstrip()
        else:
            self.description = info.rstrip()

    def add_diff_line(self, line: str) -> None:
        if not self.diff:
            self.diff = []

        self.diff.append(line)


class PathRepo:
    root_path: pathlib.Path
    python_path: frozenset[pathlib.Path]
    coverage_path: frozenset[pathlib.Path]
    python_files: frozenset[pathlib.Path]
    python_module_path: frozenset[pathlib.Path]

    def __init__(  # noqa: PLR0913
        self,
        root_path: pathlib.Path,
        python_path: set[pathlib.Path],
        coverage_path: set[pathlib.Path],
        python_files: set[pathlib.Path],
        python_module_path: set[pathlib.Path],
    ) -> None:
        self.root_path = root_path
        self.python_path = frozenset(python_path)
        self.coverage_path = frozenset(coverage_path)
        self.python_files = frozenset(python_files)
        self.python_module_path = frozenset(python_module_path)
