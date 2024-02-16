#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
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
import pathlib
import re

from .exceptions import OutputParsingError
from .tool import Annotation, Status, Tool, ToolDomain


class Bandit(Tool):
    """
    Run 'bandit', an automatic security analysis tool.

    bandit scans a code base for security vulnerabilities.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        return {ToolDomain.AUDIT}

    def get_command(self) -> list[str | pathlib.Path]:
        # TODO: bandit supports custom formats, should be easier to parse.
        return ["bandit", "-c", "pyproject.toml", "-r", *self._paths.python_path]

    def get_environment(self) -> dict[str, str]:
        return {}

    async def process_results(self, data: asyncio.StreamReader) -> AsyncIterable[Annotation]:
        """Processes 'bandits' output in to annotations."""

        # Line for each individual block
        block: list[str] = []

        while not data.at_eof():
            line = (await data.readline()).decode("utf-8", errors="replace").strip()

            # We have reached the end of a block
            if line.startswith("---------------------------"):
                yield bandit_output_block_to_annotation(block)
                block = []

            block.append(line)

        # The last block should be ignored - it's just a summary


def bandit_output_block_to_annotation(block: list[str]) -> Annotation:
    """
    Process an output block and produce an annotation from it.

    :param block: The block as a list of strings.
    :return:
    """
    [issue_line, level, cwe, docs, location, *_] = _prepare_target_block(block)

    issue_code, _, issue = issue_line.removeprefix(">> Issue: ").partition(" ")
    issue_code = issue_code.strip("[]")

    sev_head, severity, conf_head, confidence = re.split(r" +", level.strip())

    if sev_head != "Severity:" or conf_head != "Confidence:":
        raise OutputParsingError(expected="Severity: / Confidence:", data=issue_line)

    if not location.startswith("Location: "):
        raise OutputParsingError(expected="Location:", data=location)

    problem_path, problem_line, problem_char_pos = _get_position_from_loc_line(location)

    return Annotation(
        Status.FAILED,
        (problem_path, problem_line, problem_char_pos),
        issue_code,
        issue,
        f"({severity} severity / {confidence} confidence) {cwe} {docs}",
    )


def _prepare_target_block(block: list[str]) -> list[str]:
    """
    Take a block and bring it into standard target block form.

    :param block:
    :return:
    """
    target_block = []
    for i, line in enumerate(block):
        if line.startswith(">>"):
            target_block = block[i:]
            break

    if not target_block:
        raise OutputParsingError(
            expected="Block beginning with '>>'",
            data="\n".join(block),
        )

    if not target_block[0].startswith(">>"):
        raise OutputParsingError(expected="Block beginning with '>>'", data=target_block[0])

    return target_block


def _get_position_from_loc_line(loc_line: str) -> tuple[pathlib.Path, int, int]:
    """
    Parse a location line into the path, line and char pos of the problem.

    :param loc_line:
    :return:
    """
    # Windows uses ':' in its file paths - thus some care needs to
    # be taken to split the tokens down properly.
    location, _, char = loc_line.removeprefix("Location: ").rpartition(":")
    location, _, line = location.rpartition(":")

    return pathlib.Path(location.strip()), int(line), int(char)
