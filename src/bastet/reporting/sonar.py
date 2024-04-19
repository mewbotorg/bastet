# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations as _future_annotations

from typing import IO

import pathlib

from bastet.tools import Tool, ToolResults

from .abc import Reporter, ReportInstance, ReportStreams


class Sonar(Reporter):
    async def create(self, tool: Tool) -> ReportInstance:
        if tool.name.lower() not in ["ruff", "pylint"]:
            return NoReport()

        return SonarReport(pathlib.Path("reports") / f"{tool.name.lower()}.txt")

    async def summarise(self, results: ToolResults) -> None:
        pass

    async def close(self) -> None:
        pass


class NoReport(ReportInstance):
    async def start(self) -> ReportStreams:
        return ReportStreams(None, None, None, None)

    async def end(self) -> None:
        pass


class SonarReport(ReportInstance):
    name: pathlib.Path
    file: IO[bytes] | None

    def __init__(self, name: pathlib.Path) -> None:
        self.name = name
        self.file = None

    async def start(self) -> ReportStreams:
        self.file = self.name.open("wb")

        return ReportStreams(self.file, None, None, None)

    async def end(self) -> None:
        if self.file:
            self.file.flush()
            self.file.close()
