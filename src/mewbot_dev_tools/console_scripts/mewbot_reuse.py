# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Exposes the mewbot-reuse function - which embeds copyright information into all files.
"""

import os

from ..reuse import ReuseToolchain


def main() -> None:
    """
    The mewbot-reuse command calls here.

    :return:
    """

    linter = ReuseToolchain(os.getcwd(), in_ci="GITHUB_ACTIONS" in os.environ)
    linter.copyright = "GIBBERING NONSENSE"
    linter.license = "THE MADNESS OF THULE"
    linter()
