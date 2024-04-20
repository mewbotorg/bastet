# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
GitHub reporter: outputs raw tool output, plus summary of annotations.
"""

from __future__ import annotations as _future_annotations

from collections.abc import Iterable

import pathlib
import sys
import textwrap

from bastet.tools import Annotation, Status, Tool, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


class GitHubReporter(Reporter):
    """
    GitHub reporter: outputs raw tool output, plus summary of annotations.
    """

    async def create(self, tool: Tool) -> ReportInstance:
        """
        Setups up the raw reporter (but folded) report for this tool.
        """

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
                f"::error file={issue.filename},line={issue.source[1]},"
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

        if issue.tool:
            header = f"- {issue.tool.name} [{issue.code}] {issue.message}"
        else:
            header = f"- {issue.message}"

        if not issue.description:
            return header

        return f"{header}\n{textwrap.indent(issue.message.strip(), '  ')}"

    async def close(self) -> None:
        """
        No cleanup needed (we only output stdout).
        """


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
