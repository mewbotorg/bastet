# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Exception classes for Bastet tool processing.
"""

from __future__ import annotations as _future_annotations

import subprocess  # nosec: B404


class InvalidDomainError(ValueError):
    """
    Attempting to create a Tool running in a domain it does not support.
    """

    def __init__(self, domain: str, tool: str) -> None:
        """
        Attempting to create a Tool running in a domain it does not support.

        :param tool: Name of the tool
        :param domain: The invalid Domain name the request was for.
        """

        super().__init__(f"Invalid domain {domain} for {tool}")


class ToolError(Exception):
    """
    Errors that happen trying to run a Tool.

    ToolErrors are exceptions that can be emitted from the Tool's
    process_results generator function.
    """


class OutputParsingError(ToolError):
    """
    Exception parsing the output text of an external Tool.
    """

    def __init__(
        self,
        expected: str | None = None,
        data: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Exception parsing the output text of an external Tool.

        :param expected:
            The format of data the tool processor was currently expecting, if known.
        :param data:
            The unexpected data the tool outputted, if any.
        :param cause:
            An underlying exception, if one was raised.
        """

        super().__init__("Error parsing message")
        self.__cause__ = cause

        if expected:
            self.add_note(f"Expected: {expected}")
        if data:
            self.add_note(f"Saw: {data}")


class ProcessError(subprocess.CalledProcessError, ToolError):
    """
    Raised when a Tool exits with a status code not in its `acceptable_exit_codes`.
    """
