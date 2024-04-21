# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Support classes for running a series of tools across a codebase.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable
from typing import NamedTuple

import abc
import asyncio
import dataclasses
import enum
import pathlib
from collections import Counter  # pylint: disable=ungrouped-imports

from .exceptions import InvalidDomainError, ProcessError, ToolError


class ToolDomain(enum.StrEnum):
    """
    The domains we group tooling operations into.

    :param FORMAT:
        Automated fixes to the code to comply with formatting and layout
        requirements.
    :param LINT:
        Checks for coding and formatting errors.
    :param AUDIT:
        Checks for security and resilience errors.
    :param TEST:
        Unit, functional, and integration tests.
    """

    FORMAT = "Format"
    LINT = "Lint"
    AUDIT = "Audit"
    TEST = "Test"


class Status(enum.Enum):
    """
    The Status of a Tool run or Annotation.

    :param PASSED:
        The test, check, or tool passed with no problems.
    :param FIXED:
        The tool performed an automatic fix of a problem.
    :param WARNING:
        The tool encountered a warning. This is reserved only
        for warning related to the tooling itself, not the code
        that is being checked. For example, a bad configuration
        value would be a warning, whereas a minor code problem
        would still be an ISSUE.
    :param ISSUE:
        A check, test, or tool was run successfully and reported
        a problem, issue etc.
        This is the bulk of what the tools will be returning
    :param EXCEPTION:
        The tooling encountered an error whilst running.
    """

    PASSED = "Passed"
    FIXED = "Fixed"
    WARNING = "Warning"
    ISSUE = "Failed"
    EXCEPTION = "Error"

    def __lt__(self, other: Status) -> bool:
        """
        Total ordering for Status enum.
        """
        return _STATUS_ORDERING[self] < _STATUS_ORDERING[other]

    def __gt__(self, other: Status) -> bool:
        """
        Total ordering for Status enum.
        """
        return _STATUS_ORDERING[self] > _STATUS_ORDERING[other]

    def __ge__(self, other: Status) -> bool:
        """
        Total ordering for Status enum.
        """
        return other == self or self.__gt__(other)


_STATUS_ORDERING = {name: idx for idx, name in enumerate(Status)}


class ToolResult(NamedTuple):
    """
    The collected results of a specific tool run.

    :param success:
        The overall status of the tool run. This will be equal to the highest
        annotation severity, unless an unhandled exception occurred in the tool,
        in which case it will be set to the Exception status.
    :param exit_code:
        The shell exit code of the Tool
    :param annotation_counts:
        Count of the number of annotations from the Tool grouped be Status.
    """

    success: Status
    exit_code: int
    annotation_counts: dict[Status, int]

    def annotation_above(self, status: Status) -> int:
        """
        Returns a count of annotations at or higher severity than the given Status.
        """
        return sum(v for k, v in self.annotation_counts.items() if k >= status)

    def annotation_count(self, status: Status) -> int:
        """
        Returns a count of annotations for the given Status.
        """
        return self.annotation_counts.get(status, 0)


class Tool(abc.ABC):
    """
    A Tool represents something Bastet can run to validate code.

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
        """
        Tool domain and info for logging and debugging.
        """
        return f"<{self._domain}:{self.name}@{id(self)}>"

    @property
    def name(self) -> str:
        """
        The name of the tool for logging.
        """
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """
        A summary of the tool.
        """
        return self.__class__.__doc__ or self.__class__.__name__

    @property
    def domain(self) -> ToolDomain:
        """
        The domain this instance of the tool is running in.
        """
        return self._domain

    @abc.abstractmethod
    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).

        FIXME: this is wrong, rewrite with truth.
        This will be directly executed (i.e. not in a shell).
        The list of root folders is provided in an argument;
        the tool should be configured to examine these recursively.
        """

    @abc.abstractmethod
    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.

        These will be merged into the environment that bastet
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
        yield Annotation(Status.EXCEPTION, None, "bad-class", "Abstract Method Called")

    def acceptable_exit_codes(self) -> set[int]:
        """
        Status codes from the command that indicate the tool succeeded.

        The tool succeeding refers to whether it was able to produce all
        annotations, not whether they all passed. If the tool has specific
        an exit code for "the code did not pass checks", it should be added
        to this set.
        The tool run will be considered overall passed if it exits
        with one of these codes, and did not produce any annotations
        with a 'issue' or 'exception' status.
        """
        return {0}


class ToolResults:  # pylint: disable=too-few-public-methods
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
            status = Status.EXCEPTION
        elif annotations:
            status = max(annotation_levels)
        else:
            status = Status.PASSED

        self.success = self.success and (status < Status.ISSUE)
        self.annotations.extend(annotations)
        self.exceptions.extend(exceptions)
        self.results[tool] = ToolResult(status, exit_code, annotation_levels)


@dataclasses.dataclass
class Annotation:
    """
    Dataclass for an annotation/note output from a Tool.

    It has three data points that categorise it:
     - the tool that generated the annotation;
     - the annotation's status;
     - and the location in the source code

    The annotation's status defines combines the concept of
    log levels with the testing pass/fail/error into one short
    list of severities.
    The source can either be the project as a whole,
    a specific file, or a specific line within a file.

    Attached to this metadata is a message, an error code,
    and optionally a description with more information.
    """

    _CWD = pathlib.Path.cwd().absolute()

    @classmethod
    def set_root(cls, path: pathlib.Path) -> None:
        """
        Mark the root directory for annotations.

        Paths will be normalised, formatted, and printed relative to this path.
        Changing this after creating annotations is not supported, and the
        behaviour is undefined.
        """

        cls._CWD = path

    @classmethod
    def _normalise_source(
        cls,
        source: tuple[pathlib.Path | str, int | None, int | None] | str | pathlib.Path | None,
    ) -> tuple[pathlib.Path, int, int]:
        """
        Take all representations of the Source and encode as (file, line, column).

        The source can either be the project as a whole (input of None),
        a specific file, or a specific line and column within a file.
        """

        if not source:
            return cls._CWD, 0, 0

        if isinstance(source, str):
            source = pathlib.Path(source)

        if isinstance(source, pathlib.Path):
            return source.absolute(), 0, 0

        if isinstance(source[0], str):
            return pathlib.Path(source[0]).absolute(), source[1] or 0, source[2] or 0

        return source[0].absolute(), source[1] or 0, source[2] or 0

    status: Status
    source: tuple[pathlib.Path, int, int]
    tool: Tool | None
    code: str

    message: str
    description: str | None
    diff: list[str] | None

    def __init__(  # pylint: disable=R0913 # noqa: PLR0913 - 6 args is "ok" here.
        self,
        status: Status,
        source: tuple[pathlib.Path | str, int | None, int | None] | pathlib.Path | str | None,
        code: str,
        message: str,
        description: str | None = None,
    ) -> None:
        """
        Create an annotation.

        :param Status status:
            What 'status' to associate with this annotation. See the Status class for details.
        :param source:
            Where the annotation relates to in the code.
        :param str code:
            An identifying error code for this type of issue. Many linting tools use these
            to index documentation, and to exclude certain tests in their configurations.
            If the tool does not supply one, choose a unique and concise description of the issue.
        :param str message:
            The error message to be present to the user
        :param description:
            An optional and potentially multi line description of the error,
            why it is considered an error, how to fix it, or links to external references.
            This should not include diffs, which instead should be attached using the
            add_diff_line method.
        """

        self.tool = None
        self.status = status
        self.source = self._normalise_source(source)
        self.code = code.strip()
        self.message = message.strip()
        self.description = description.strip() if description else None
        self.diff = None

    @property
    def filename(self) -> str:
        """
        Returns the filename of the annotation relative to the project root.

        This does not include the line number.
        If the path is the project root, '.' is returned.
        """

        root = self._CWD

        if self.source[0] == root:
            return "."

        return str(self.source[0].relative_to(self._CWD))

    @property
    def file_str(self) -> str:
        """
        Returns the project path of the file, with the line number and column if set.

        The returned string is relative to the project root (which many UIs will
        convert into a link). If the path is the project root, it returns just '[project]'.
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
        """
        Sorts annotations by file path and then line number.
        """

        if not isinstance(other, Annotation):
            return False

        if self.same_source(other.source):
            return self.code < other.code

        return self.source < other.source

    def same_source(self, source: tuple[pathlib.Path, int | None, int | None] | None) -> bool:
        """
        Check if another Annotation source normalises to this Annotation's source.
        """
        return self._normalise_source(source) == self.source

    def add_note(self, info: str) -> None:
        """
        Adds additional context to the annotation.

        Each call will add a new line of text to the notes.
        """
        if self.description:
            self.description += "\n" + info.rstrip()
        else:
            self.description = info.rstrip()

    def add_diff_line(self, line: str) -> None:
        """
        Adds a line of text to an inline diff.

        Tools that are outputting diffs in their Annotations are responsible
        for ensuring diffs are 'correct'. Diffs are assumed to be in the
        file associated with the annotation, so the first line should be the
        block header (`@@ -n,n +n,n@@`).
        """

        if not self.diff:
            self.diff = []

        self.diff.append(line)


@dataclasses.dataclass(frozen=True)
class PathRepo:
    """
    Repository for storing the paths we are analysing.

    This is used to help tools be aware of the files and folders that
    should be processed.

    :param root_path:
        The root of the project, that paths are relative to.
    :param root_path:
        The path to write reports into.
    :param exclude_dirs:
        High level directories excluded by ignore files and the config.
        This does not include individual files.
    :param python_path:
        The roots of python source files, which will contain top-level modules and packages.
    :param python_files:
         A list of all python source files. Primarily for outputting 'passed' annotations.
    :param python_module_path:
        List of paths to folders that contain python packages,
        excluding namespace packages (which are empty and confuse some tools).
    """

    root_path: pathlib.Path
    report_path: pathlib.Path
    exclude_dirs: frozenset[pathlib.Path]
    python_path: frozenset[pathlib.Path]
    python_files: frozenset[pathlib.Path]
    python_module_path: frozenset[pathlib.Path]
