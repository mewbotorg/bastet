# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Support classes for running a series of tools across the codebase.
"""

from __future__ import annotations

from typing import IO, BinaryIO, Iterable, Optional

import abc
import asyncio
import dataclasses
import json
import os
import subprocess
import sys
from io import BytesIO

from .terminal import CommandDelimiter, ResultPrinter


class ToolChain(abc.ABC):
    """
    Support class for running a series of tools across the codebase.

    Each tool will be given the same set of folders, and can produce output
    to the console and/or 'annotations' indicating issues with the code.

    The behaviour of this class alters based whether it is being run in 'CI mode'.
    This mode disables all interactive and automated features of the toolchain,
    and instead outputs the state through a series of 'annotations', each one
    representing an issue the tools found.
    """

    folders: set[str]
    in_ci: bool
    run_success: dict[str, bool]

    timeout: int = 300

    search_root: Optional[str]

    def __init__(self, *folders: str, in_ci: bool, search_root: Optional[str] = None) -> None:
        """
        Sets up a tool chain with the given settings.

        :param folders: The list of folders to run this tool against
        :param in_ci: Whether this is a run being called from a CI pipeline
        """
        self.folders = set(folders)
        self.in_ci = in_ci
        self.run_success = {}

        # If gather paths is called, the search will start here
        self.search_root = search_root

        self.loop = asyncio.get_event_loop()

    def __call__(self) -> None:
        """Runs the tool chain, including exiting the script with an appropriate status code."""
        # Windows hack to allow colour printing in the terminal
        # See https://bugs.python.org/issue30075 and our windows-dev-notes.
        if os.name == "nt":
            os.system("")

        # Ensure the reporting location exists.
        if not os.path.exists("./reports"):
            os.mkdir("./reports")

        issues = list(self.run())

        with open(
            f"./reports/annotations-{self.__class__.__name__}.json", "w", encoding="utf-8"
        ) as output:
            json.dump([issue.json() for issue in issues], output, indent=2)

        self._output_state()
        sys.exit(not self.success or len(issues) > 0)

    @property
    def success(self) -> bool:
        """Returns whether all tool calls have been successful."""

        return all(self.run_success.values())

    @abc.abstractmethod
    def run(self) -> Iterable[Annotation]:
        """
        Abstract function for this tool chain to run its checks.

        The function can call any number of sub-tools.
        It should set `success` to false if any tool errors or raises issues.

        When in CI mode, any issues the tool finds should be returned as Annotations.
        These will then be reported back to the CI runner.

        Outside of CI mode, the toolchain can take the action it deems most appropriate,
        including pretty messages to the user, automatically fixing, or still using annotations.
        """

    def run_tool(
        self,
        name: str,
        *args: str,
        env: dict[str, str] | None = None,
        folders: set[str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Helper function to run an external program as a check.

        The program will have the list of folders appended to the supplied arguments.
        If the process has a non-zero exit code, success is set to False for the chain.

        The output of the command is made available in three different ways:
          - Output is written to reports/{tool name}.txt
          - Output and Error are returned to the caller
          - Mirror Error and Output to the terminal.

        :param name: The user-friendly name of the tools
        :param args: The command line to use. The first value should be the executable path.
        :param env: Environment variables to pass to the sub-process.
        :param folders: Override for the default set of folders for this toolchain. Use with care.
        """

        return self.loop.run_until_complete(
            self.async_run_tool(name, *args, env=env or {}, folders=folders)
        )

    async def async_run_tool(
        self, name: str, *args: str, env: dict[str, str], folders: set[str] | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Helper function to run an external program as a check.

        The program will have the list of folders appended to the supplied arguments.
        If the process has a non-zero exit code, success is set to False for the chain.

        The output of the command is made available in three different ways:
          - Output is written to reports/{tool name}.txt
          - Output and Error are returned to the caller
          - Mirror Error and Output to the terminal.

        :param name: The user-friendly name of the tools
        :param args: The command line to use. The first value should be the executable path.
        :param env: Environment variables to pass to the sub-process.
        :param folders: Override for the default set of folders for this toolchain. Use with care.
        """

        arg_list = list(args)
        arg_list.extend(folders if folders is not None else self.folders)

        run_result = await self._run_utility(name, arg_list, env)
        assert isinstance(run_result, subprocess.CompletedProcess)

        self.run_success[name] = run_result.returncode == 0

        return run_result

    async def _run_utility(
        self, name: str, arg_list: list[str], env: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Helper function to run an external program as a check.

        The output of the command is made available in three different ways:
          - Output is written to reports/{tool name}.txt
          - Output and Error are returned to the caller
          - Error and Output are copied to the terminal.

        When in CI mode, we add a group header to collapse the output from each
        tool for ease of reading.

        :param name: The user-friendly name of the tools
        :param arg_list: The command line to use. The first value should be the executable path.
        :param env: Environment variables to pass to the sub-process.
        """

        # Print output header
        with CommandDelimiter(name, self.in_ci):
            env = env.copy()
            env.update(os.environ)

            process = await asyncio.create_subprocess_exec(
                *arg_list,
                stdin=subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # MyPy validation trick -- ensure the pipes are defined (they will be).
            if not process.stdout or not process.stderr:
                raise ValueError(f"pipes for process {name} not created")

            with open(f"reports/{name}.txt", "wb") as log_file:
                # Set up the mirroring readers on the two output pipes.
                task_out = self.loop.create_task(
                    read_pipe(process.stdout, sys.stdout.buffer, log_file)
                )
                task_err = self.loop.create_task(read_pipe(process.stderr, sys.stderr.buffer))

                # This is trimmed down version of subprocess.run().
                try:
                    await asyncio.wait_for(process.wait(), timeout=self.timeout)
                except TimeoutError:
                    process.kill()
                    # run uses communicate() on windows. May be needed.
                    # However, as we are running the pipes manually, it may not be.
                    # Seems not to be
                    await process.wait()
                # Re-raise all non-timeout exceptions.
                except:  # noqa: E722
                    process.kill()
                    await process.wait()
                    raise
                finally:  # Ensure the other co-routines complete.
                    stdout_buffer = await task_out
                    stderr_buffer = await task_err

            return_code = process.returncode
            return_code = return_code if return_code is not None else 1

            run = subprocess.CompletedProcess(
                arg_list, return_code, stdout_buffer.read(), stderr_buffer.read()
            )

        return run

    def _output_state(self) -> None:
        ResultPrinter(self.run_success).result_print(sys.stdout)


async def read_pipe(pipe: asyncio.StreamReader, *mirrors: BinaryIO) -> IO[bytes]:
    """
    Read a pipe from a subprocess into a buffer whilst mirroring it to another pipe.
    """

    buffer = BytesIO()

    while not pipe.at_eof():
        block = await pipe.readline()
        for mirror in mirrors:
            mirror.write(block)
            mirror.flush()
        buffer.write(block)

    buffer.seek(0)
    return buffer


@dataclasses.dataclass
class Annotation:
    """
    Schema for a GitHub action annotation, representing an error.
    """

    level: str
    file: str
    line: int
    col: int
    tool: str
    title: str
    message: str

    def __str__(self) -> str:
        """Outputs annotations in the format used in GitHub Actions checker."""

        mess = self.message.replace("\n", "%0A")
        return (
            f"::{self.level} file={self.file},line={self.line},"
            f"col={self.col},title={self.title.strip()}::{mess.strip()}"
        )

    def json(self) -> dict[str, str | int]:
        """Output this object as a JSON-encodeable dictionary."""

        return dataclasses.asdict(self)

    def __hash__(self) -> int:
        """Unique hash of this annotation."""

        return hash(
            (self.level, self.file, self.line, self.col, self.tool, self.title, self.message)
        )

    def __lt__(self, other: Annotation) -> bool:
        """Sorts annotations by file path and then line number."""

        if not isinstance(other, Annotation):
            return False

        return self.file < other.file or self.file == other.file and self.line < other.line
