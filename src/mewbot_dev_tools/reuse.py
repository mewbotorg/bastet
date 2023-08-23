# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Uses the reuse tool to ensure copyright info is present in all files.
"""

from __future__ import annotations

from typing import Any

import os

from .toolchain import Annotation, ToolChain


# Presented as a class to make accessing some properties of the run easier.
class ReuseToolchain(ToolChain):
    """
    Represents a run of the reuse program.
    """
    copyright: str
    license: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Need an __init__ to allow use to modify the constants on a class level.

        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)

        self.copyright = "Mewbot Developers <mewbot@quicksilver.london>"
        self.license = "BSD-2-Clause"

    def run(self) -> list[Annotation]:
        """Execute reuse and return the status of the run."""
        args: list[str] = [
            "reuse",
            "annotate",
            "--merge-copyrights",
            "--copyright",
            self.copyright,
            "--license",
            self.license,
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
