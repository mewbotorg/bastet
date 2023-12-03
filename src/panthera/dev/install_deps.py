# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Support for automatically installing plugins and dependency for the repo.

No command line argument is provided for this - to make it more likely people will correctly call
it with the interpreter of the venv they're trying to build.
"""

from __future__ import annotations

from typing import Optional

import os
import pathlib
import pprint
import subprocess
import sys

from ..path import gather_paths


def main(search_root: Optional[str] = None) -> bool:
    """Automatically install all plugins into the current working tree."""

    dot = pathlib.Path(os.curdir if search_root is None else search_root)

    file: pathlib.Path | str
    requirements: list[str] = []
    requirements_files: list[str] = []

    for file in dot.glob("requirements-*.txt"):
        requirements.extend(("-r", str(file)))
        requirements_files.extend((str(file),))

    for file in gather_paths("requirements.txt"):
        requirements.extend(("-r", str(file)))
        requirements_files.extend((str(file),))

    print(
        "Installing dependencies\n"
        f"base_dir: {str(dot.absolute())}"
        f"\n{pprint.pformat(requirements_files)}\n"
        "will be installed."
    )

    subprocess.check_call([sys.executable, "-m", "pip", "install", *requirements])
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
