#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Output Annotations from previous CI stages in GitHub CI format.

When running the tools like mewbot.tools.lint or mewbot.tools.test,
problem annotations are recorded in JSON format. This aggregates
a number of those JSON files into one formatted annotation per line
with problems.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

import json
import os
import pathlib
import textwrap

from .toolchain import Annotation, ToolChain


class Annotate(ToolChain):
    """
    Output Annotations from previous CI stages in GitHub CI format.

    When running the tools like mewbot.tools.lint or mewbot.tools.test,
    problem annotations are recorded in JSON format. This aggregates
    a number of those JSON files into one formatted annotation per line
    with problems.
    """

    def __init__(self, search_root: Optional[str]) -> None:
        """
        Starts up the class.
        """

        self.search_root = os.curdir if search_root is None else search_root

        super().__init__("reports", in_ci="GITHUB_ACTIONS" in os.environ)

    def __call__(self) -> None:
        """
        Output Annotations from previous CI stages in GitHub CI format.
        """

        issues = self.run()
        issues = self.group_issues(issues)
        self.github_list(list(issues))

    def run(self) -> Iterable[Annotation]:
        """Collect the annotations from `reports/annotations-*.json`."""

        for path, _, files in os.walk("./reports"):
            for file in files:
                if file.startswith("annotations-") and file.endswith(".json"):
                    yield from self.load_file(os.path.join(path, file))

    @staticmethod
    def load_file(path: str) -> Iterable[Annotation]:
        """Load all the annotations from a JSON file."""

        with open(path, "r", encoding="utf-8") as issue_file:
            for datum in json.load(issue_file):
                yield Annotation(**datum)

    def group_issues(self, annotations: Iterable[Annotation]) -> Iterable[Annotation]:
        """
        Regroups the input annotations into one annotation per line of code.

        Annotations from the same file and line are grouped together.
        Items on the same line and file with the same text are treated as a
        single item.
        If a line has one item (after de-duplication), that item is returned
        unchanged. Otherwise, an aggregate annotation for that line is returned.
        """

        grouping: dict[tuple[str, str, int], set[Annotation]] = {}

        # Group annotations by file and line.
        for annotation in annotations:
            path = pathlib.Path(annotation.file).absolute()
            group = (annotation.level, str(path), annotation.line)
            grouping.setdefault(group, set()).add(annotation)

        # Process the groups
        for (level, file, line), issues in grouping.items():
            # Single item groups are returned as-is.
            if len(issues) == 1:
                yield issues.pop()
                continue

            title = f"{len(issues)} Issues on this line"
            message = "\n\n".join(self.format_sub_issue(issue) for issue in issues)

            yield Annotation(level, file, line, 0, "annotator", title, message)

    @staticmethod
    def format_sub_issue(issue: Annotation) -> str:
        """
        Converts an existing annotation into a line of text.

        This line can then be placed into an aggregate annotation.
        """

        if not issue.message:
            return f"- [{issue.tool}] {issue.title.strip()}"
        if not issue.title:
            return f"- [{issue.tool}] {issue.message.strip()}"

        return (
            f"- [{issue.tool}] {issue.title.strip()}\n"
            f"{textwrap.indent(issue.message.strip(), '  ')}"
        )

    @staticmethod
    def github_list(issues: list[Annotation]) -> None:
        """
        Outputs the annotations in the format for GitHub actions.

        These are presented as group at the end of output as a work-around for
        the limit of 10 annotations per check run actually being shown on a commit or merge.
        """

        print("::group::Annotations")
        for issue in sorted(issues):
            print(issue)
        print("::endgroup::")

        print("Total Issues:", len(issues))


if __name__ == "__main__":
    Annotate()()
