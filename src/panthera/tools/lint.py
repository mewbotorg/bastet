#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
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
                yield Annotation(Status.ERROR, None, code, error)
                continue

            if line.startswith(("*" * 10, "-" * 10, "Your code has been rated")):
                continue

            if to_yield := self.foo(line):
                yield to_yield

        if self._annotation:
            yield self._annotation

    def foo(self, line: str) -> Annotation | ToolError | None:
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

            self._annotation = Annotation(Status.FAILED, source, code, error)
        except ValueError as e:
            return OutputParsingError(data=line, cause=e)
        else:
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
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        return ["flake8", *self._paths.python_path]

    def get_environment(self) -> dict[str, str]:
        return {}

    def acceptable_exit_codes(self) -> set[int]:
        return {0, 1}


class MyPy(Tool):
    """
    Runs 'mypy', a python type analyser/linter.

    mypy enforces the requirement for type annotations, and also performs type-checking
    based on those annotations and resolvable constants.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        return [
            "mypy",
            "--strict",
            "--explicit-package-bases",
            *self._paths.python_module_path,
        ]

    def get_environment(self) -> dict[str, str]:
        # MyPy does not use the stock import engine for doing its analysis,
        # so we have to give it additional hints about how the namespace package
        # structure works.
        # See https://mypy.readthedocs.io/en/stable/running_mypy.html#mapping-file-paths-to-modules
        #
        # There are two steps to this:
        #  - We set MYPYPATH equivalent to PYTHONPATH

        return {
            "MYPYPATH": os.pathsep.join(map(str, self._paths.python_path)),
        }

    def acceptable_exit_codes(self) -> set[int]:
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

                last_annotation = Annotation(Status.FAILED, source, code, error)
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
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        return ["pylint", *self._paths.python_path]

    def get_environment(self) -> dict[str, str]:
        return {}


class PyDocStyle(Tool):
    """
    Runs 'pydocstyle', which tests python doc blocks.

    pydocstyle checks for the existence and format of doc strings in all
    python modules, classes, and methods. These will have to be formatted
    with a single headline, arguments, return values and any extra info.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        return {ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        return ["pydocstyle", *self._paths.python_files]

    def get_environment(self) -> dict[str, str]:
        return {}

    async def process_results(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        while not data.at_eof():
            header = (await data.readline()).decode("utf-8")

            if ":" not in header:
                continue

            try:
                file, _, header = header.partition(":")
                line, _, _ = header.partition(" ")

                source = (pathlib.Path(file), int(line), None)
                error = (await data.readline()).decode("utf-8").strip()
                code, _, error = error.partition(": ")

                yield Annotation(Status.FAILED, source, code, error)
            except ValueError as e:
                yield OutputParsingError(cause=e)
            except StopIteration:
                yield OutputParsingError("no data after header")
