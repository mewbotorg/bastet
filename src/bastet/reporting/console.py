# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import shutil
import sys
import textwrap
import traceback

from clint.textui import colored  # type: ignore[import-untyped]

from bastet.tools import Annotation, Status, Tool, ToolError, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


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

        sys.stdout.write("".join(traceback.format_exception_only(ToolError, value=problem)))
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
        Status.EXCEPTION: "RED",
        Status.ISSUE: "RED",
        Status.WARNING: "YELLOW",
        Status.FIXED: "YELLOW",
        Status.PASSED: "GREEN",
    }

    return colored.ColoredString(mapping.get(status, "RESET"), content)


def short_stats(status: Status) -> str:
    mapping = {
        Status.EXCEPTION: "ERR!",
        Status.ISSUE: "FAIL",
        Status.WARNING: "WARN",
        Status.FIXED: "+FIX",
        Status.PASSED: "PASS",
    }

    return mapping.get(status, "ERR!")
