#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Wrapper class for the security analysis toolchain.

Any program which is exposed to the internet, and hs to process user input (as mewbot should be
able to, at least) has to deal with a number of security concerns.
Static security analysis can help with this.
Currently, this runs bandit - a static security analysis toolkit.
More analysis tools may be added.
"""


from __future__ import annotations

from collections.abc import Iterable

import abc
import pprint
import re
import subprocess

from ..toolchain import Annotation, ToolChain

LEVELS = frozenset({"notice", "warning", "error"})


class BanditMixin(ToolChain, abc.ABC):
    """
    Helper class to include bandit function in other tool chains.
    """

    in_ci: bool

    def lint_bandit(self) -> Iterable[Annotation]:
        """
        Run 'bandit', an automatic security analysis tool.

        bandit scans a code base for security vulnerabilities.
        """

        args = ["bandit", "-c", "pyproject.toml", "-r"]

        if not self.in_ci:
            args.extend(["--quiet"])

        result = self.run_tool("Bandit (Security Analysis)", *args)

        if self.check_for_bad_bandit_config(result):
            print(
                "\n"
                "WARNING - bad bandit section in pyproject.toml"
                "\n"
                "Disregard above."
                "\n"
                "Running again with default args"
                "\n"
            )

            args = ["bandit", "-r", "-ll"]

            if not self.in_ci:
                args.extend(["--quiet"])

            result = self.run_tool("Bandit (Security Analysis)", *args)

        yield from lint_bandit_output(result)

    @staticmethod
    def check_for_bad_bandit_config(result: subprocess.CompletedProcess[bytes]) -> bool:
        """
        Check the subprocess output for a KeyError - which indicates a bad config file.

        Not so much bad as not including an absence of a bandit tool section in the file.
        """
        stdout_errors = result.stdout.decode("utf-8").split("\n")
        stderr_errors = result.stderr.decode("utf-8").split("\n")

        for line in stdout_errors + stderr_errors:
            if line.lower().strip() == "keyerror: 'bandit'":
                return True

        return False


class SecurityAnalysisToolchain(BanditMixin):
    """
    Wrapper class for running security analysis tools.

    The output of these tools will be emitted as GitHub annotations (in CI)
    or default human output (otherwise).
    By default, all paths declared to be part of mewbot source - either of the main
    module or any installed plugins - are linted.
    """

    def run(self) -> Iterable[Annotation]:
        """Runs the linting tools in sequence."""

        yield from self.lint_bandit()


def lint_bandit_output(
    result: subprocess.CompletedProcess[bytes],
) -> Iterable[Annotation]:
    """Processes 'bandits' output in to annotations."""
    # Don't want to truncate the example bandit output
    # pylint: disable=line-too-long

    stdout_errors = result.stdout.decode("utf-8").split("\n")
    stderr_errors = result.stderr.decode("utf-8").split("\n")

    # Parsing bandit comment blocks into annotations

    # Line for each individual block
    block: list[str] = []

    for line in stdout_errors + stderr_errors:
        line = line.strip()

        # We have reached the end of a block
        if line.startswith("---------------------------"):
            yield bandit_output_block_to_annotation(block)

        block.append(line)

    # The last block should be ignored - it's just a summary


def bandit_output_block_to_annotation(block: list[str]) -> Annotation:
    """
    Process an output block and produce an annotation from it.

    :param block: The block as a list of strings.
    :return:
    """
    target_block = prepare_target_block(block)

    issue_code = re.findall(r"\[.+]", target_block[0])[0]
    issue_code = issue_code[1:-1]

    # Extracting the severity and confidence - should be on the next line
    severity_confidence_re = r"^(\s+)?Severity:([a-zA-Z\s]+)Confidence:([a-zA-Z\s]+)$"
    severity_confidence_match = re.match(severity_confidence_re, target_block[1])

    assert (
        severity_confidence_match is not None
    ), f"Error parsing {target_block[1]} with regex {severity_confidence_re}"

    try:
        severity = severity_confidence_match.group(2).strip()
    except AttributeError as exp:
        raise NotImplementedError(
            f"Error parsing {target_block[1]} with regex {severity_confidence_re}"
        ) from exp

    try:
        confidence = severity_confidence_match.group(3).strip()
    except AttributeError as exp:
        raise NotImplementedError(
            f"Error parsing {target_block[1]} with regex {severity_confidence_re}"
        ) from exp

    # Scanning forward to try and find a location line
    loc_line_found = False
    loc_line = ""
    for cand_line in target_block[2:]:
        if cand_line.lower().strip().startswith("location"):
            loc_line_found = True
            loc_line = cand_line
            break

    if not loc_line_found:
        raise NotImplementedError(
            f"block does not seem to have a Location line - \n\n{pprint.pformat(block)}"
        )

    problem_path, problem_line, problem_char_pos = get_positions_from_loc_line(loc_line)

    return Annotation(
        level=severity_to_level(severity),
        file=problem_path,
        line=problem_line,
        col=problem_char_pos,
        tool="bandit",
        title=f"Bandit {severity} security warning",
        message=f"{issue_code = } - {severity} security warning with confidence {confidence}",
    )


def prepare_target_block(block: list[str]) -> list[str]:
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
        raise NotImplementedError(
            f"Line starting with '>>' was not found in block\n\n{block}"
        )

    assert target_block[0].startswith(
        ">>"
    ), f"Bad block format \n\n{target_block}\n\n was not in expected format."

    return target_block


def get_positions_from_loc_line(loc_line: str) -> tuple[str, int, int]:
    """
    Parse a location line into the path, line and char pos of the problem.

    :param loc_line:
    :return:
    """
    # Windows uses ':' in its file paths - thus some care needs to be taken to split the tokens
    # down properly
    loc_tokens = loc_line.split(":")

    if len(loc_tokens) == 4:
        problem_path = str(loc_tokens[-3])
        problem_line = int(loc_tokens[-2])
        problem_char_pos = int(loc_tokens[-1])

        return problem_path, problem_line, problem_char_pos

    # Four is the minimum, if : does not appear in the path
    assert len(loc_tokens) > 4, f"{loc_tokens = } not as expected"

    problem_path = ":".join(loc_tokens[1:-2])
    problem_line = int(loc_tokens[-2])
    problem_char_pos = int(loc_tokens[-1])

    return problem_path, problem_line, problem_char_pos


def severity_to_level(severity: str) -> str:
    """
    Turns a bandit severity level into a github notice level.

    :param severity:
    :return:
    """
    if severity.lower() == "low":
        return "notice"
    if severity.lower() in ["medium", "med"]:
        return "warning"
    if severity.lower() == "high":
        return "error"

    raise NotImplementedError(f"severity {severity} not recognized!")
