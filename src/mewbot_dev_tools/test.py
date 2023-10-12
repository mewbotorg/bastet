#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Run tests using pytest, optionally with coverage information.

The output of these tools will be emitted as GitHub annotations (in CI)
or default human output (otherwise).
By default, all test declared to be part of mewbot test suite (either core or plugins) are run.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

import argparse
import glob
import os

from .path import gather_paths
from .toolchain import Annotation, ToolChain


class TestToolchain(ToolChain):
    """
    Run tests using pytest, optionally with coverage information.

    The output of these tools will be emitted as GitHub annotations (in CI)
    or default human output (otherwise).
    By default, all test declared to be part of mewbot test suite (either core or plugins) are run.
    """

    coverage: bool = False
    covering: list[str] = []

    def run(self) -> Iterable[Annotation]:
        """Run the test suite."""

        args = self.build_pytest_args()

        result = self.run_tool("PyTest (Testing Framework)", *args)

        if result.returncode < 0:
            yield Annotation("error", "tools/test.py", 1, 1, "pytest", "Tests Failed", "")

    def build_pytest_args(self) -> list[str]:
        """
        Build out the `pytest` command.

        This varies based on what output types are requested (human vs code
        readable), and whether coverage is enabled.
        Due to issues with pytest-cov handling, parallelisation is disabled
        when coverage is enabled
        https://github.com/pytest-dev/pytest-cov/blob/master/CHANGELOG.rst#400-2022-09-28
        """

        args = [
            "pytest",
            "--new-first",  # Do un-cached tests first -- likely to be more relevant.
            "--durations=0",  # Report all tests that take more than 1s to complete
            "--durations-min=1",
            "--junitxml=reports/junit.xml",
            "-vv",
        ]

        if not self.coverage:
            args.append("--dist=load")  # Distribute between processes based on load
            args.append("--numprocesses=auto")  # Run processes equal to CPU count
            return args

        # Enable coverage tracking for code in all requested folders
        for target_path in self.covering:
            args.append(f"--cov={target_path}")

        args.append("--cov-report=xml:reports/coverage.xml")  # Record coverage summary in XML

        if self.in_ci:
            # Simple terminal output
            args.append("--cov-report=term")
        else:
            # Output to terminal, showing only lines which are not covered
            args.append("--cov-report=term-missing")
            # Output to html, coverage is the folder containing the output
            args.append("--cov-report=html:coverage")

        return args


def parse_test_options() -> argparse.Namespace:
    """Parse command line argument for the test tools."""

    parser = argparse.ArgumentParser(description="Run tests for mewbot")
    parser.add_argument(
        "--ci",
        dest="in_ci",
        action="store_true",
        help="Run test in GitHub actions mode",
        default="GITHUB_ACTIONS" in os.environ,
    )
    parser.add_argument(
        "--cov",
        dest="coverage",
        action="store_true",
        default=False,
        help="Enable coverage reporting",
    )
    parser.add_argument(
        "--cover",
        nargs="*",
        dest="covering",
        help="Apply coverage only to provided paths (implies --cov)",
    )
    parser.add_argument(
        "path", nargs="*", default=[], help="Path of a file or a folder of files."
    )

    return parser.parse_args()


def main(search_root: Optional[str] = None) -> None:
    """
    Collect and run the tests.

    :return:
    """
    options = parse_test_options()
    paths = options.path or list(gather_paths("tests", search_root=search_root))

    testing = TestToolchain(*paths, in_ci=options.in_ci)

    # Set up coverage, if requested
    testing.coverage = options.coverage or options.covering or options.in_ci
    testing.covering = options.covering or gather_files(gather_paths("src"))

    testing()


def gather_files(base_paths: Iterable[str]) -> list[str]:
    """
    Used to explicitly declare all the .py files of interest for coverage.
    """
    base_paths = list(base_paths)

    rtn_list: list[str] = []
    rtn_list.extend(base_paths)

    for base_path in base_paths:
        rtn_list.extend(list(glob.glob("**/*.py", root_dir=base_path, recursive=True)))

    return rtn_list


if __name__ == "__main__":
    main()
