# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Reporters which write tool outputs to files.

This includes the simple FileReporter, and a SonarReporter
which only outputs the tools Sonar is able to process.
"""

from __future__ import annotations as _future_annotations

from typing import IO

import pathlib

from bastet.tools import Tool, ToolDomain, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


class FileReporter(Reporter):
    """
    Creates an output file containing the stdout of the tool.

    The file will be put in the configured reports folder,
    and is named for the tool.
    """

    include_domain: bool

    def __init__(self, *, include_domain: bool = True) -> None:
        """
        Creates an output file containing the stdout of the tool.

        The file will be put in the configured reports folder,
        and is named for the tool and domain.

        :param include_domain:
            Whether to include the domain name in the report
            file name to prevent collisions.
        """

        self.include_domain = include_domain

    async def create(self, tool: Tool) -> ReportInstance | None:
        """
        Creates an output file containing the stdout of the tool.

        The file will be put in the configured reports folder,
        and is named for the tool.
        """

        if self.include_domain:
            name = f"{tool.name.lower()}-{tool.domain.name}.txt"
        else:
            name = f"{tool.name.lower()}.txt"

        # This needs a refactor, but we don't want to pass the full config to the reporters.
        return FileReport(tool._paths.report_path / name)  # pylint: disable=W0212 # noqa: SLF001

    async def summarise(self, results: ToolResults) -> None:
        """
        No Summary, as each report is its own file.
        """

    async def close(self) -> None:
        """
        Nothing to close at the run level.
        """


class SonarReporter(FileReporter):
    """
    FileReporter that only reports on Sonar scanner tools.

    Sonar supports importing reports from certain built in
    tools. This reporter allows users to supply `--report sonar`
    to quick get those files.
    """

    def __init__(self) -> None:
        """
        Creates the SonarReporter, which is just a special case of FileReporter.
        """
        super().__init__(include_domain=False)

    async def create(self, tool: Tool) -> ReportInstance | None:
        """
        Creates a File report for tools that Sonar supports ingesting.
        """

        if tool.name.lower() not in ["ruff", "pylint"]:
            return None
        if tool.domain == ToolDomain.FORMAT:
            return None

        return await super().create(tool)


class FileReport(ReportInstance):
    """
    Trivial reporter that dumps output to a file.
    """

    name: pathlib.Path
    file: IO[bytes] | None

    def __init__(self, name: pathlib.Path) -> None:
        """
        Trivial reporter that dumps output to a file.
        """

        self.name = name
        self.file = None

    async def start(self) -> ReportStreams:
        """
        Open a report file for the Sonar-supported tool.
        """
        self.file = self.name.open("wb")

        return ReportStreams(self.file, None, None, None)

    async def end(self) -> None:
        """
        Close the report file.
        """
        if self.file:
            self.file.flush()
            self.file.close()
