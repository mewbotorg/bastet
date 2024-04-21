# SPDX-FileCopyrightText: 2021 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Wrapper class for the security analysis toolchain.

Any program which is exposed to the internet, and has to process user input
has to deal with a number of security concerns.

Static security analysis can help with this.
Currently, this runs bandit - a static security analysis toolkit.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable

import asyncio
import json
import pathlib

from .exceptions import OutputParsingError
from .tool import Annotation, Status, Tool, ToolDomain


class Bandit(Tool):
    """
    Run 'bandit', an automatic security analysis tool.

    bandit scans a code base for security vulnerabilities.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        Bandit: a security tool.
        """
        return {ToolDomain.AUDIT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).
        """
        pyproject = self._paths.root_path / "pyproject.toml"

        return [
            "bandit",
            "-c",
            pyproject.absolute(),
            "--format",
            "json",
            "--exclude",
            ",".join(
                [str(x) for x in self._paths.exclude_dirs],
            ),
            "-r",
            self._paths.root_path,
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    async def process_results(self, data: asyncio.StreamReader) -> AsyncIterable[Annotation]:
        """
        Processes 'bandits' output in to annotations.
        """

        raw_data = await data.read()

        try:
            results = json.loads(raw_data)
        except json.JSONDecodeError as err:
            raise OutputParsingError(expected="valid json", cause=err) from err

        for error in results["errors"]:
            yield Annotation(Status.EXCEPTION, None, "err", str(error))

        for problem in results["results"]:
            severity = problem["issue_severity"]
            confidence = problem["issue_confidence"]

            yield Annotation(
                Status.ISSUE,
                (pathlib.Path(problem["filename"]), problem["line_number"], problem["col_offset"]),
                problem["test_id"],
                problem["issue_text"],
                (
                    f"({severity} severity / {confidence} confidence) "
                    f"CWE-{problem['issue_cwe']['id']} {problem['more_info']}"
                ),
            )

        for file, metrics in results["metrics"].items():
            if file == "_totals":
                continue

            del metrics["loc"]
            del metrics["nosec"]

            if not sum(metrics.values()):
                yield Annotation(
                    Status.PASSED,
                    pathlib.Path(file),
                    "pass",
                    "All bandit checks passed",
                )
