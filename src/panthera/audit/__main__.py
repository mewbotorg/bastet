# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the method to expose the mewbot-security-analysis command.
"""

from __future__ import annotations

import argparse
import os

from ..path import gather_paths_standard_locs
from . import SecurityAnalysisToolchain

parser = argparse.ArgumentParser(description="Run security analysis for mewbot")
parser.add_argument(
    "-n",
    "--no-tests",
    action="store_false",
    default=True,
    dest="tests",
    help="Exclude tests from security analysis",
)
parser.add_argument(
    "path",
    nargs="*",
    default=[],
    help="Path of a file or a folder of files for security analysis.",
)
parser.add_argument(
    "--ci",
    dest="in_ci",
    default="GITHUB_ACTIONS" in os.environ,
    action="store_true",
    help="Run in GitHub actions mode",
)

options = parser.parse_args()

paths = options.path or gather_paths_standard_locs(
    search_root=os.getcwd(), tests=options.tests
)
linter = SecurityAnalysisToolchain(*paths, in_ci=options.in_ci)
linter()
