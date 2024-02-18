# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterable

import pathlib
import shutil
import sys
import textwrap
import traceback

from clint.textui import colored  # type: ignore[import-untyped]

from panthera.tools import Annotation, Status, Tool, ToolError, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


class ConsoleReporter(Reporter):
    async def create(self, tool: Tool) -> ReportInstance:
        return _ConsoleReporter(tool)

    async def summarise(self, results: ToolResults) -> None:
        """Print the collected results."""

        sys.stdout.write(terminal_header("Summary"))

        for tool, result in results.results.items():
            sys.stdout.write(self.format_result_str(tool.domain, tool.name, result.success))

        if results.success:
            sys.stdout.write(f"Congratulations! {colored.green('Proceed to Upload')}\n")
        else:
            sys.stdout.write(f"\nBad news! {colored.red('At least one failure!')}\n")

    async def close(self) -> None:
        pass

    @staticmethod
    def format_result_str(domain: str, proc_name: str, success: Status) -> str:
        """Get a formatted string for an individual result."""
        status = colored.green("PASS") if success else colored.red("FAIL")

        return f"[{status}] {domain} :: {proc_name}\n"


class _ConsoleReporter(ReportInstance):
    tool: Tool

    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def start(self) -> ReportStreams:
        sys.stdout.write(terminal_header(f"{self.tool.domain.name} :: {self.tool.name}"))
        sys.stdout.flush()

        return ReportStreams(sys.stdout.buffer, sys.stderr.buffer, None, None)

    async def end(self) -> None:
        sys.stdout.flush()
        sys.stderr.flush()


class AnnotationReporter(Reporter):
    async def create(self, tool: Tool) -> ReportInstance:
        return _AnnotationReporter(tool)

    async def summarise(self, results: ToolResults) -> None:
        """Print the collected results."""

        sys.stdout.write(terminal_header("Summary"))

        for tool, result in results.results.items():
            sys.stdout.write(
                self.format_result_str(
                    tool.domain,
                    tool.name,
                    result.annotation_above(Status.FIXED),
                    result.success,
                ),
            )

        sys.stdout.write("\n")
        if results.success:
            sys.stdout.write(f"Congratulations! {colored.green('Proceed to Upload')}\n")
        else:
            sys.stdout.write(f"\nBad news! {colored.red('At least one failure!')}\n")

    async def close(self) -> None:
        pass

    @staticmethod
    def format_result_str(
        domain: str,
        proc_name: str,
        annotation_count: int,
        status: Status,
    ) -> str:
        """Get a formatted string for an individual result."""
        status = color_by_status(short_stats(status), status)

        return f"[{status}] {domain} :: {proc_name} ({annotation_count} notes)\n"


class _AnnotationReporter(ReportInstance):
    tool: Tool
    _header: bool = False

    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def start(self) -> ReportStreams:
        return ReportStreams(None, None, self.handle_annotation, self.handle_exception)

    def header(self) -> None:
        if self._header:
            return

        self._header = True
        sys.stdout.write(terminal_header(f"{self.tool.domain} :: {self.tool.name}"))
        sys.stdout.flush()

    async def handle_annotation(self, annotation: Annotation) -> None:
        if annotation.status == Status.PASSED:
            return

        self.header()

        a = annotation
        sys.stdout.write(f"{a.file_str} [{color_by_status(a.code, a.status)}]: {a.message}\n")

        if annotation.description:
            sys.stdout.write(textwrap.indent(annotation.description.rstrip(), "  "))
            sys.stdout.write("\n")

        sys.stdout.flush()

    async def handle_exception(self, problem: ToolError) -> None:
        self.header()

        sys.stdout.write("".join(traceback.format_exception_only(problem)))
        sys.stdout.write("\n")
        sys.stdout.flush()

    async def end(self) -> None:
        pass


def terminal_header(content: str) -> str:
    """
    Recalculated live in case the terminal changes sizes between calls.

    Fallback is to assume 80 char wide - which seems a reasonable minimum for terminal size.
    :return: int terminal width
    """
    width = shutil.get_terminal_size()[0]

    trailing_dash_count = min(80, width) - 6 - len(content)
    return (
        "\n"
        + str(colored.white(f"{'=' * 4} {content} {'=' * trailing_dash_count}", bold=True))
        + "\n"
    )


def color_by_status(content: str, status: Status) -> colored.ColoredString:
    mapping = {
        Status.ERROR: "RED",
        Status.FAILED: "RED",
        Status.WARNING: "YELLOW",
        Status.FIXED: "YELLOW",
        Status.PASSED: "GREEN",
    }

    return colored.ColoredString(mapping.get(status, "RESET"), content)


def short_stats(status: Status) -> str:
    mapping = {
        Status.ERROR: "ERR!",
        Status.FAILED: "FAIL",
        Status.WARNING: "WARN",
        Status.FIXED: "+FIX",
        Status.PASSED: "PASS",
    }

    return mapping.get(status, "ERR!")


class GitHubReporter(Reporter):
    async def create(self, tool: Tool) -> ReportInstance:
        return _GitHubReporter(tool)

    async def summarise(self, results: ToolResults) -> None:
        """
        Outputs the annotations in the format for GitHub actions.

        These are presented as group at the end of output as a work-around for
        the limit of 10 annotations per check run actually being shown on a commit or merge.
        """

        issues = list(self.group_issues(results.annotations))

        sys.stdout.write("::group::Annotations\n")
        for issue in sorted(issues):
            description = (issue.description or "").replace("\n", "%0A")
            sys.stdout.write(
                f"::{issue.status} file={issue.filename},line={issue.source[1]},"
                f"col={issue.source[2]},title={issue.message}::{description}\n",
            )
        sys.stdout.write("::endgroup::\n")

        sys.stdout.write(f"Total Issues: {len(issues)}\n")

    def group_issues(self, annotations: Iterable[Annotation]) -> Iterable[Annotation]:
        """
        Regroups the input annotations into one annotation per line of code.

        Annotations from the same file and line are grouped together.
        Items on the same line and file with the same text are treated as a
        single item.
        If a line has one item (after de-duplication), that item is returned
        unchanged. Otherwise, an aggregate annotation for that line is returned.
        """

        grouping: dict[tuple[pathlib.Path, int, int], set[Annotation]] = {}

        # Group annotations by file and line.
        for annotation in annotations:
            if annotation.status < Status.WARNING:
                continue

            grouping.setdefault(annotation.source, set()).add(annotation)

        # Process the groups
        for source, issues in grouping.items():
            # Single item groups are returned as-is.
            if len(issues) == 1:
                yield issues.pop()
                continue

            status = max(issue.status for issue in issues)
            title = f"{len(issues)} issues on this line"
            message = "\n\n".join(self.format_sub_issue(issue) for issue in issues)

            yield Annotation(status, source, "group", title, message)

    @staticmethod
    def format_sub_issue(issue: Annotation) -> str:
        """
        Converts an existing annotation into a line of text.

        This line can then be placed into an aggregate annotation.
        """

        header = f"- {issue.tool.name} [{issue.code}] {issue.message}"

        if not issue.description:
            return header

        return f"{header}\n{textwrap.indent(issue.message.strip(), '  ')}"

    async def close(self) -> None:
        pass


class _GitHubReporter(ReportInstance):
    tool: Tool

    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def start(self) -> ReportStreams:
        sys.stdout.write(f"::group::{self.tool.domain} : {self.tool.name}\n")
        sys.stdout.write(f"Running {self.tool.name}\n")
        sys.stdout.flush()

        return ReportStreams(sys.stdout.buffer, sys.stderr.buffer, None, None)

    async def end(self) -> None:
        sys.stdout.write("::endgroup::\n")
