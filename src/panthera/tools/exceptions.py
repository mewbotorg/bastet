# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import subprocess  # nosec: B404


class InvalidDomainError(ValueError):
    def __init__(self, domain: str, tool: str) -> None:
        super().__init__(f"Invalid domain {domain} for {tool}")


class ToolError(Exception):
    pass


class ToolValueError(ToolError):
    def __init__(
        self,
        data: str | None,
        expected: list[str] | None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__("Error parsing message")
        self.__cause__ = cause

        if data and expected:
            super().add_note(f"Saw {data}, expected on of {expected!s}")


class OutputParsingError(ToolError):
    def __init__(
        self,
        expected: str | None = None,
        data: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__("Error parsing message")
        self.__cause__ = cause

        if expected:
            self.add_note(f"Expected: {expected}")
        if data:
            self.add_note(f"Saw: {data}")


class ProcessError(subprocess.CalledProcessError, ToolError):
    pass
