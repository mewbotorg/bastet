#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Run this script before submitting to git.

This preforms a number of check and normalization functions, including
 - reuse
 - lint
 - test

The aim is to make sure the code is fully tested and ready to be submitted to git.
All tools which should be run before submission will be run.
This script is intended to be run locally.
"""
from typing import Optional

import os

from .lint import LintToolchain
from .path import gather_paths
from .reuse import ReuseToolchain
from .terminal import CommandDelimiter
from .test import TestToolchain
from .toolchain import Annotation, ToolChain


class PreflightToolChain(ToolChain):
    """
    Class to run the tools in sequence.
    """

    def __init__(self, search_root: Optional[str] = None) -> None:
        """
        Starts up the class.
        """

        self.search_root = os.curdir if search_root is None else search_root

        super().__init__(self.search_root, in_ci=False, search_root=search_root)

    def run(self) -> list[Annotation]:
        """
        Run all needed tools in sequence.

        Reuse - Will be run against the current position.
        :return:
        """

        self.run_reuse()
        self.run_lint()
        self.run_test()

        return []

    def run_reuse(self) -> None:
        """
        Run the reuse tool and store the result.

        :return:
        """
        with CommandDelimiter("Starting reuse run", False):
            reuse_tool = ReuseToolchain(
                *self.folders, in_ci=self.in_ci, search_root=self.search_root
            )

            for _ in reuse_tool.run():
                ...

            self.run_success.update(reuse_tool.run_success)

    def run_lint(self) -> None:
        """
        Run the lint toolchain and store the result.

        :return:
        """
        with CommandDelimiter("Starting linting run", False):
            target_paths = gather_paths("src", "tests")
            linter = LintToolchain(*target_paths, in_ci=False, search_root=self.search_root)

            for _ in linter.run():
                ...

            self.run_success.update(linter.run_success)

    def run_test(self) -> None:
        """Run the test suite - store the results."""
        with CommandDelimiter("Starting testing run", False):
            paths = list(gather_paths("tests"))
            tester = TestToolchain(*paths, in_ci=False, search_root=self.search_root)

            for _ in tester.run():
                ...

            self.run_success.update(tester.run_success)


def main(search_root: Optional[str] = None) -> None:
    """
    Run the main security analysis program(s).

    :param search_root:
    :return:
    """
    preflight_toolchain = PreflightToolChain(search_root=search_root)
    preflight_toolchain()


if __name__ == "__main__":
    main()
