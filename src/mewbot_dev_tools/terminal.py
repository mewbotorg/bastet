# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Set of basic tools to improve command line readability.
"""

from __future__ import annotations

from types import TracebackType
from typing import IO

import pprint
import shutil
import sys

from clint.textui import colored  # type: ignore


class CommandDelimiter:
    """Used to more cleanly separate one command in a run from another."""

    tool_name: str
    delim_char: str
    in_ci: bool

    def __init__(self, tool_name: str, in_ci: bool, delim_char: str = "=") -> None:
        """
        Supplied with the name of the tool and the deliminator char to create a display.

        :param delim_char: This will fill the line below and above the tool run
        :param in_ci: Whether to format output for CI pipelines or user terminals
        :param tool_name: The name of the tool which will be run
        """
        self.tool_name = tool_name
        self.in_ci = in_ci
        self.args = args
        self.delim_char = delim_char

    @property
    def terminal_width(self) -> int:
        """
        Recalculated live in case the terminal changes sizes between calls.

        Fallback is to assume 80 char wide - which seems a reasonable minimum for terminal size.
        :return: int terminal width
        """
        return shutil.get_terminal_size()[0]

    def __enter__(self) -> None:
        """Print the welcome message."""

        if self.in_ci:
            sys.stdout.write(f"::group::{self.tool_name}\n")
            sys.stdout.write(f"Running {name} with args = \n{pprint.pformat(arg_list)}\n")
        else:
            trailing_dash_count = min(80, self.terminal_width) - 6 - len(self.tool_name)
            sys.stdout.write(
                colored.white(
                    (
                        self.delim_char * 4
                        + " "
                        + self.tool_name
                        + " "
                        + self.delim_char * trailing_dash_count
                        + "\n\n"
                    ),
                    bold=True,
                ).color_str
            )
        sys.stdout.flush()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Print the exit message."""
        # https://stackoverflow.com/questions/18398672/re-raising-an-exception-in-a-context-handler
        if exc_type:
            return False

        if self.in_ci:
            sys.stdout.write("::endgroup::\n")

        sys.stdout.write("\n")
        sys.stdout.flush()

        return True


class ResultPrinter:
    """Formats the given results dicts into a final output string."""

    results: dict[str, bool]

    def __init__(self, *results: dict[str, bool]) -> None:
        """
        Load the class with dicts to print.

        Keyed with the name of the run and valued with its status.
        """
        self.results = {}

        for result in results:
            self.results.update(result)

    def result_print(self, output: IO[str]) -> None:
        """Print the collected results."""
        all_successful: bool = True

        for run_name, run_succeeded in self.results.items():
            all_successful = all_successful and run_succeeded
            output.write(self.format_result_str(run_name, run_succeeded))

        if all_successful:
            output.write(f"Congratulations! {colored.green('Proceed to Upload')}\n")
        else:
            output.write(f"\nBad news! {colored.red('At least one failure!')}\n")

    @staticmethod
    def format_result_str(proc_name: str, proc_status: bool) -> str:
        """Get a formatted string for an individual result."""
        return (
            f"[{colored.green('PASS') if proc_status else colored.red('FAIL')}] {proc_name}\n"
        )
