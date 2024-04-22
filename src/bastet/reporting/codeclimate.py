# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
# SPDX-FileContributor: Benedict Harcourt <benedict.harcourt@futurenet.com>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Formatter to export 'Code Climate' reports.

These are also the codequality type reports in gitlab.
"""

from __future__ import annotations as _future_annotations

from typing import Any

import json
import pathlib

import bastet.tools.lint
from bastet.tools import Annotation, Status, Tool, ToolDomain, ToolResults

from .abc import Reporter, ReportInstance


class CodeClimate(Reporter):
    """
    Formatter to export 'Code Climate' reports.

    These are also the codequality type reports in gitlab.
    """

    async def create(self, _: Tool) -> ReportInstance | None:
        """
        CodeClimate does not report on tool runs, just a summary.
        """

    async def summarise(self, results: ToolResults) -> None:
        """
        Summarise all tool runs as a Code Climate report.

        Each issue which is a Warning of higher is included in the report.
        """

        report = pathlib.Path("reports/code-climate.json")

        with report.open("w", encoding="utf-8") as outfile:  # noqa: ASYNC101
            json.dump(
                list(
                    map(
                        self._issue_to_code_climate,
                        filter(lambda a: a.status >= Status.WARNING, results.annotations),
                    ),
                ),
                outfile,
                indent=2,
            )

    def _issue_to_code_climate(self, annotation: Annotation) -> dict[str, Any]:
        """
        Convert an Annotation into a Code Climate Issue.

        See https://github.com/codeclimate/platform/blob/master/spec/analyzers/SPEC.md#issues
        """

        tool = annotation.tool.name if annotation.tool else "bastet"
        location = {
            "path": annotation.filename,
            "lines": {
                "begin": annotation.source[1] or 1,
                "end": annotation.source[1] or 1,
            },
        }
        severity = "major"
        categories: list[str] = []

        if annotation.tool and annotation.tool.domain == ToolDomain.AUDIT:
            categories.append("Security")
        if isinstance(annotation.tool, bastet.tools.lint.MyPy):
            categories.append("Bug Risk")
        if "complexity" in annotation.message.lower():
            categories.append("Complexity")
        # This is not a typo, it's catching 'duplication' and 'duplicate'.
        if "duplicat" in annotation.message.lower():
            categories.append("Duplication")

        if not categories:
            categories = ["Style"]
            severity = "minor"

        issue = {
            "type": "issue",
            "check_name": f"{tool} :: {annotation.code}",
            "severity": severity,
            "fingerprint": "bastet-" + str(hash(annotation)),
            "location": location,
            "description": annotation.message,
            "categories": categories,
        }

        if annotation.description:
            issue["content"] = {"body": annotation.description}

        return issue

    async def close(self) -> None:
        """
        No close operation -- everything happens in summarise().
        """
