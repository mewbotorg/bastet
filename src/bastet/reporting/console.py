# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Console/Terminal Annotation Reporter.

This reports all non-"Passed" annotations and all exceptions.
This outputs in a similar style to ruff and pylint's defaults,
but ensures a consistent `<location> [<code>]: <message>` format.
Additional description will appear indented on the next line.
Diffs are not shown. It attempts to ensure that the locations
are handled by in-IDE terminals as useful clickable links.

After all tool outputs have been collected, a summary is shown.
This is the overall status, the tool's domain and name,
and the number of non-passes annotations. If there were
more than zero Pass annotations, that count is also shown.

The final line of output is a simple human friendly "all pass"
or "some failures" message.
"""

from __future__ import annotations as _future_annotations

import shutil
import sys
import textwrap
import traceback

import colorama

from bastet.tools import Annotation, Status, Tool, ToolError, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


class AnnotationReporter(Reporter):
    """
    Console/Terminal Annotation Reporter.

    This reports all non-"Passed" annotations and all exceptions.
    This outputs in a similar style to ruff and pylint's defaults,
    but ensures a consistent `<location> [<code>]: <message>` format.
    Additional description will appear indented on the next line.
    Diffs are not shown. It attempts to ensure that the locations
    are handled by in-IDE terminals as useful clickable links.

    After all tool outputs have been collected, a summary is shown.
    This is the overall status, the tool's domain and name,
    and the number of non-passes annotations. If there were
    more than zero Pass annotations, that count is also shown.

    The final line of output is a simple human friendly "all pass"
    or "some failures" message.
    """

    async def create(self, tool: Tool) -> ReportInstance:
        """
        Get the tool annotation reporter for the given tool.
        """
        return _AnnotationReporter(tool)

    async def summarise(self, results: ToolResults) -> None:
        """
        Print the collected results.

        This shows the overall status for each tool, along with a count
        of how many passing and non-passing annotations.
        """

        sys.stdout.write(terminal_header("Summary"))

        for tool, result in results.results.items():
            sys.stdout.write(
                self.format_result_str(
                    tool.domain,
                    tool.name,
                    result.annotation_count(Status.PASSED),
                    result.annotation_above(Status.FIXED),
                    result.success,
                ),
            )

        sys.stdout.write("\n")
        if results.success:
            sys.stdout.write(
                f"All checks passed! {_color('Proceed to Upload', colorama.Fore.GREEN)}\n",
            )
        else:
            sys.stdout.write(f"\nBad news! {_color('At least one failure!', colorama.Fore.RED)}\n")

    async def close(self) -> None:
        """
        No cleanup for this class (we write to stdout).
        """

    @staticmethod
    def format_result_str(
        domain: str,
        tool_name: str,
        pass_count: int,
        annotation_count: int,
        status: Status,
    ) -> str:
        """
        Get a formatted string for a tool's individual result.

        This is the overall status, the tool's domain and name,
        and the number of non-passes annotations. If there were
        more than zero Pass annotations, that count is also shown.
        """

        status_text = color_by_status(short_stats(status), status)

        basic = f"[{status_text}] {(domain + ' :: ' + tool_name):18s} {annotation_count:3d} issues"

        if pass_count:
            basic += f" {pass_count:3d} passed"

        return basic + "\n"


class _AnnotationReporter(ReportInstance):
    """
    Console/Terminal Annotation Reporter.

    This reports all non-"Passed" annotations and all exceptions.
    This outputs in a similar style to ruff and pylint's defaults,
    but ensures a consistent `<location> [<code>]: <message>` format.
    Additional description will appear indented on the next line.
    Diffs are not shown. It attempts to ensure that the locations
    are handled by in-IDE terminals as useful clickable links.
    """

    tool: Tool
    _header_written: bool = False

    def __init__(self, tool: Tool) -> None:
        """
        Console/Terminal Annotation Reporter.
        """

        self.tool = tool

    async def start(self) -> ReportStreams:
        """
        Request annotations ond exceptions from the tool.

        Annotations are passwrd to the handle_annotation function,
        and exception to the handle_exception function.
        """

        return ReportStreams(None, None, self.handle_annotation, self.handle_exception)

    def header(self) -> None:
        """
        Emit a header tile for this tool, if not already emitted.

        We don't want to put a header until we have actual content to post.
        """

        if self._header_written:
            return

        self._header_written = True
        sys.stdout.write(terminal_header(f"{self.tool.domain} :: {self.tool.name}"))
        sys.stdout.flush()

    async def handle_annotation(self, annotation: Annotation) -> None:
        """
        Outputs Annotations (except passes).

        This formats in a similar style to ruff and pylint's defaults,
        but ensures a consistent `<location> [<code>]: <message>` format.
        Additional description will appear indented on the next line.
        Diffs are not shown.

        The location is formatted so IDEs like JetBrain's PyCharm will make
        them clickable links taking you to the location of the code.
        """

        if annotation.status == Status.PASSED:
            return

        # Output the header line for this tool (if we haven't already)
        self.header()

        a = annotation
        sys.stdout.write(f"{a.file_str} [{color_by_status(a.code, a.status)}]: {a.message}\n")

        if annotation.description:
            sys.stdout.write(textwrap.indent(annotation.description.rstrip(), "  "))
            sys.stdout.write("\n")

        sys.stdout.flush()

    async def handle_exception(self, problem: ToolError) -> None:
        """
        Outputs the exception as just the exception without a full stack trace.
        """

        # Output the header line for this tool (if we haven't already)
        self.header()

        sys.stdout.write("".join(traceback.format_exception_only(ToolError, value=problem)))
        sys.stdout.write("\n")
        sys.stdout.flush()

    async def end(self) -> None:
        """
        No cleanup for this class (we write to stdout).
        """


def terminal_header(content: str) -> str:
    """
    Puts a heading line across the width of the terminal.

    Width is recalculated live in case the terminal changes sizes between calls.
    Fallback is to assume 80 char wide - which seems a reasonable minimum for terminal size.

    :return: int terminal width
    """
    width = shutil.get_terminal_size()[0]
    trailing_dash_count = min(80, width) - 6 - len(content)

    colored_text = _color(
        f"{'=' * 4} {content} {'=' * trailing_dash_count}",
        colorama.Fore.WHITE,
        bold=True,
    )

    return f"\n{colored_text}\n"


def color_by_status(content: str, status: Status) -> str:
    """
    Terminal colours representing different status.
    """

    mapping = {
        Status.EXCEPTION: colorama.Fore.RED,
        Status.ISSUE: colorama.Fore.RED,
        Status.WARNING: colorama.Fore.YELLOW,
        Status.FIXED: colorama.Fore.YELLOW,
        Status.PASSED: colorama.Fore.GREEN,
    }

    return _color(content, mapping.get(status, colorama.Fore.RESET))


def _color(data: str, color: str, *, bold: bool = False) -> str:
    """
    Create an ANSI-formatted coloured string.
    """

    if color == colorama.Fore.RESET:
        return data

    if bold:
        return color + colorama.Style.BRIGHT + data + colorama.Style.RESET_ALL

    return color + data + colorama.Fore.RESET


def short_stats(status: Status) -> str:
    """
    Four letter version of the status for tabular output.
    """
    mapping = {
        Status.EXCEPTION: "ERR!",
        Status.ISSUE: "FAIL",
        Status.WARNING: "WARN",
        Status.FIXED: "+FIX",
        Status.PASSED: "PASS",
    }

    return mapping.get(status, "ERR!")
