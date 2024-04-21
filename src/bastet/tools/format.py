# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Bastet tools which reformat (or otherwise mutate) the source code.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable

import abc
import json
import pathlib
from asyncio import StreamReader

from .exceptions import OutputParsingError, ToolError
from .tool import Annotation, Status, Tool, ToolDomain


class Ruff(Tool):
    """
    Runs 'ruff', a high performance python linter written in rust.

    Theoretically ruff is a superset of a number of other linters used here. It may take over
    as the default linter - for normal runs.
    However, for CI runs before accepting code, it makes sense to run the other linters as
    well.
    There should be no difference, but they are the reference implementations.
    Time is also less of a factor in a rare CI acceptance run.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        Ruff: a general purpose formatting, linting, and auditing tool.

        We do not include it in the Audit domain as there is no good way
        to separate out its linting and audit annotations.
        """

        return {ToolDomain.FORMAT, ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).
        """
        if self.domain == ToolDomain.LINT:
            return [
                "ruff",
                "check",
                "--respect-gitignore",
                "--output-format=json-lines",
                self._paths.root_path,
            ]

        return [
            "ruff",
            "check",
            "--respect-gitignore",
            "--fix",
            "--fix-only",
            self._paths.root_path,
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    def acceptable_exit_codes(self) -> set[int]:
        """
        Status codes from the command that indicate the tool succeeded.

        ruff uses status code 1 whilst linting to indicate tests did not pass.
        """
        return {0, 1}

    async def process_results(
        self,
        data: StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Runs 'ruff', a high performance python linter written in rust.

        Theoretically ruff is a superset of a number of other linters used here.
        It may take over as the default linter - for normal runs.
        However, for CI runs before accepting code, it makes sense to run the
        other linters as well.

        There should be no difference, but they are the reference implementations.
        Time is also less of a factor in a rare CI acceptance run.
        """

        if self.domain == ToolDomain.FORMAT:
            await data.read()
            return

        while not data.at_eof():
            line = await data.readline()

            if not line:
                continue

            try:
                info = json.loads(line)
            except json.JSONDecodeError as e:
                yield OutputParsingError(data=line.decode(), cause=e)
                continue

            yield Annotation(
                Status.ISSUE,
                (
                    pathlib.Path(info["filename"]),
                    info["location"]["row"],
                    info["location"]["column"],
                ),
                info["code"],
                info["message"],
            )


class _DiffProcessorMixin(Tool):
    async def process_diffs(
        self,
        data: StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Process the output of a command that produces diffs.

        The format is assumed to be
        ```
        error: [some text]
        --- path/to/file
        +++ path/to/file
        @@ -n,n +n,n @@
        [patch contents]
        ```

        The initial `error:` line will be passed to the `_tokenize_error`
        abstract method to build out the outline of the annotation, which
        the diff will then be attached to.
        """

        last_annotation: Annotation | None = None

        while not data.at_eof():
            line = (await data.readline()).decode("utf-8", errors="replace")

            if line.startswith("error: "):
                yield self._tokenize_error(line)
                continue

            if line.startswith("--- "):
                if last_annotation:
                    yield last_annotation

                filename = line.removeprefix("--- ").partition("\t")[0]
                file = pathlib.Path(filename.removesuffix(":before"))
                await data.readline()  # Skip the +++ line.
                line = (await data.readline()).decode("utf-8", errors="replace")
                last_annotation = self._diff_header_to_annotation(file, line)

            elif last_annotation and line.startswith("@@ "):
                yield last_annotation
                last_annotation = self._diff_header_to_annotation(
                    last_annotation.source[0],
                    line,
                )

            elif last_annotation:
                last_annotation.add_diff_line(line)

        if last_annotation:
            yield last_annotation

    def _diff_header_to_annotation(self, file: pathlib.Path, line: str) -> Annotation:
        # [@@, old lines, new lines, @@]
        _, _, new, _ = line.strip().split(" ", 3)
        row, add = new.split(",", 1)

        header = f"{self.name} change ({add} lines affected)"

        annotation = Annotation(Status.ISSUE, (file, int(row), None), "edit", header)
        annotation.add_diff_line(line)
        return annotation

    @abc.abstractmethod
    def _tokenize_error(self, error: str) -> Annotation | OutputParsingError:
        """
        Tokenize the error header message line before the diff.
        """


class ISort(_DiffProcessorMixin):
    """
    Run 'isort', an automatic import ordering tool.

    Black handles most formatting updates automatically, maintaining
    readability and code style compliance.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        Black: Code formatting and code style checking.
        """
        return {ToolDomain.FORMAT, ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).
        """
        if self.domain == ToolDomain.FORMAT:
            return ["isort", *self._paths.python_path]

        return ["isort", "--diff", "--quiet", "--check", *self._paths.python_path]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    async def process_results(
        self,
        data: StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Run 'isort', an automatic import ordering tool.

        Black handles most formatting updates automatically, maintaining
        readability and code style compliance.
        """

        if self.domain == ToolDomain.FORMAT:
            await data.read()
            return

        async for note in self.process_diffs(data):
            yield note

    def _tokenize_error(self, error: str) -> Annotation | OutputParsingError:
        return OutputParsingError(data=error)


class Black(_DiffProcessorMixin):
    """
    Run 'black', an automatic formatting tool.

    Black handles most formatting updates automatically, maintaining
    readability and code style compliance.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        Black: Code formatting and code style checking.
        """
        return {ToolDomain.FORMAT, ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Command string to execute (including arguments).

        This will be directly executed (i.e. not in a shell).
        """

        if self.domain == ToolDomain.FORMAT:
            return ["black", *self._paths.python_path]

        return ["black", "--diff", "--no-color", "--quiet", *self._paths.python_path]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    async def process_results(
        self,
        data: StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        """
        Run 'black', an automatic formatting tool.

        Black handles most formatting updates automatically, maintaining
        readability and code style compliance.
        """
        async for note in self.process_diffs(data):
            yield note

    def _tokenize_error(self, error: str) -> Annotation | OutputParsingError:
        # We should, at this point, have a conventional "error: " line.
        error = error.removeprefix("error: ")

        if not error.startswith("cannot format "):
            return OutputParsingError(expected="cannot format", data=error)

        file, reason, line, char, _ = error.removeprefix("cannot format ").split(":", 4)

        source = pathlib.Path(file.strip()), int(line.strip()), int(char.strip())

        return Annotation(
            Status.EXCEPTION,
            source,
            "error",
            reason,
        )
