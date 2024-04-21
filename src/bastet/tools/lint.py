# SPDX-FileCopyrightText: 2021 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Wrapper class for running linting tools.

The output of these tools will be emitted as GitHub annotations (in CI)
or default human output (otherwise).
By default, all paths declared to be part of mewbot source - either of the main
module or any installed plugins - are linted.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable

import abc
import asyncio
import os
import pathlib

from .exceptions import OutputParsingError, ToolError
from .tool import Annotation, Status, Tool, ToolDomain


class _PylintOutputMixin(Tool, abc.ABC):
    _annotation: Annotation | None = None

    async def process_results(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        while not data.at_eof():
            line = (await data.readline()).decode("utf-8", errors="replace")

            if line.startswith("[Errno"):
                code, _, error = line.partition("] ")
                code = code.strip("[]")
                yield Annotation(Status.EXCEPTION, None, code, error)
                continue

            if line.startswith(("*" * 10, "-" * 10, "Your code has been rated")):
                continue

            if to_yield := self._process_line(line):
                yield to_yield

        if self._annotation:
            yield self._annotation

    def _process_line(self, line: str) -> Annotation | ToolError | None:
        annotation = self._annotation

        try:
            file, line_no, col, error = line.strip().split(":", 3)
        except ValueError:
            if self._annotation:
                self._annotation.add_note(line)
            return None

        try:
            source = (pathlib.Path(file), int(line_no), int(col))

            code, _, error = error.strip().partition(" ")
            code = code.strip(":")

            # Start a new annotation
            self._annotation = Annotation(Status.ISSUE, source, code, error)

        except ValueError as e:
            return OutputParsingError(data=line, cause=e)

        # Return the previous complete annotation (if there was one)
        return annotation


class Flake8(_PylintOutputMixin, Tool):
    """
    Runs 'flake8', an efficient code-style enforcer.

    flake8 is a lightweight and fast tool for finding issues relating to
    code-style, import management (both missing and unused) and a range of
    other issue.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        flake8 python code linting.
        """
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).
        """
        return [
            "flake8",
            "--exclude",
            ",".join(
                [str(x) for x in self._paths.exclude_dirs],
            ),
            *self._paths.python_module_path,
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    def acceptable_exit_codes(self) -> set[int]:
        """
        Status codes from the command that indicate the tool succeeded.

        flake8 uses status code 1 whilst linting to indicate tests did not pass.
        """
        return {0, 1}


class MyPy(Tool):
    """
    Runs 'mypy', a python type analyser/linter.

    mypy enforces the requirement for type annotations, and also performs type-checking
    based on those annotations and resolvable constants.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        MyPy: type hint linting and static analysis.
        """
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).

        In order to handle namespace packages, we pass MyPy the list
        of concrete module paths, and set MYPYPATH environment variable.
        See the get_environment function for more details.
        """
        return [
            "mypy",
            "--strict",
            "--explicit-package-bases",
            *self._paths.python_module_path,
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables for MyPy.

        MyPy does not use the stock import engine for doing its analysis,
        so we have to give it additional hints about how the namespace package
        structure works.
        See https://mypy.readthedocs.io/en/stable/running_mypy.html#mapping-file-paths-to-modules

        There are two steps to this:
          - We pass the set of concrete module paths to mypy's command line.
          - We set MYPYPATH equivalent to PYTHONPATH
        """

        return {
            "MYPYPATH": os.pathsep.join(map(str, self._paths.python_path)),
        }

    def acceptable_exit_codes(self) -> set[int]:
        """
        Status codes from the command that indicate the tool succeeded.

        mypy uses status code 1 whilst linting to indicate tests did not pass.
        """
        return {0, 1}

    async def process_results(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Runs 'mypy', a python type analyser/linter.

        mypy enforces the requirement for type annotations, and also performs type-checking
        based on those annotations and resolvable constants.
        """

        last_annotation: Annotation | None = None

        while not data.at_eof():
            line = (await data.readline()).decode("utf-8", errors="replace")

            if ":" not in line or "Success:" in line:
                continue

            try:
                file, line_str, level, error = line.strip().split(":", 3)

                source = (pathlib.Path(file), int(line_str), 0)
                level = level.strip()

                if last_annotation:
                    if level == "note" and last_annotation.same_source(source):
                        last_annotation.add_note(error)
                        continue

                    yield last_annotation

                error, _, code = error.rpartition("  ")
                code = code.strip("[]")

                last_annotation = Annotation(Status.ISSUE, source, code, error)
            except ValueError as e:
                yield OutputParsingError("Unable to read file/line number", line, e)

        if last_annotation:
            yield last_annotation


class PyLint(_PylintOutputMixin, Tool):
    """
    Runs 'pylint', the canonical python linter.

    pylint performs a similar set of checks as flake8, but does so using the full
    codebase as context. As such it will also find similar blocks of code and other
    subtle issues.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        Pylint: General linting for the official python style guide.
        """
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).
        """
        return [
            "pylint",
            "--ignore-paths",
            ",".join(
                [str(x) for x in self._paths.exclude_dirs],
            ),
            *self._paths.python_module_path,
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}
