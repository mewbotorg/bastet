# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Exposes the mewbot-reuse function - which embeds copyright information into all files.
"""

from __future__ import annotations

from typing import Optional

import json
import os

from .reuse import ReuseToolchain


def load_copyright_file() -> tuple[Optional[str], Optional[str]]:
    """
    Attempts to load a copyright.json standard from the cwd.

    If there is one.
    :return:
    """
    if not os.path.exists("copyright.json"):
        return None, None

    with open("copyright.json", encoding="utf-8") as json_infile:
        copyright_info = json.load(json_infile)
        assert isinstance(copyright_info, dict)

    new_copyright = None
    if "copyright" in copyright_info.keys():
        new_copyright = str(copyright_info["copyright"])

    new_licence = None
    if "license" in copyright_info.keys():
        new_licence = str(copyright_info["license"])

    return new_copyright, new_licence


def main() -> None:
    """
    The mewbot-reuse command calls here.

    :return:
    """

    linter = ReuseToolchain(os.getcwd(), in_ci="GITHUB_ACTIONS" in os.environ)

    new_copyright, new_licence = load_copyright_file()
    if new_copyright is not None:
        linter.copyright = new_copyright
    if new_licence is not None:
        linter.license = new_licence

    linter()
