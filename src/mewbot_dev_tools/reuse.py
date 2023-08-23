# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Uses the reuse tool to ensure copyright info is present in all files.
"""

from __future__ import annotations

import os

from .toolchain import Annotation, ToolChain

COPYRIGHT: str = "Mewbot Developers <mewbot@quicksilver.london>"
LICENSE: str = "BSD-2-Clause"


# Presented as a class to make accessing some properties of the run easier.
class ReuseToolchain(ToolChain):
    """
    Represents a run of the reuse program.
    """

    def run(self) -> list[Annotation]:
        """Execute reuse and return the status of the run."""
        args: list[str] = [
            "reuse",
            "annotate",
            "--merge-copyrights",
            "--copyright",
            COPYRIGHT,
            "--license",
            LICENSE,
            "--skip-unrecognised",
            "--skip-existing",
            "--recursive",
        ]

        self.run_tool("Reuse Annotate", *args)

        args = [
            "reuse",
            "lint",
        ]

        self.run_tool("Reuse Lint", *args, folders=set())

        return []


if __name__ == "__main__":
    linter = ReuseToolchain(os.curdir, in_ci="GITHUB_ACTIONS" in os.environ)
    linter()
