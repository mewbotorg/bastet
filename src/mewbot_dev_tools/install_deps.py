# SPDX-FileCopyrightText: 2021 - 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Support for automatically installing plugins and dependency for the repo."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

from .path import gather_paths


def main() -> bool:
    """Automatically install all plugins into the current working tree."""

    dot = pathlib.Path(os.curdir)

    file: pathlib.Path | str
    requirements: list[str] = []

    for file in dot.glob("requirements-*.txt"):
        requirements.extend(("-r", str(file)))

    for file in gather_paths("requirements.txt"):
        requirements.extend(("-r", str(file)))

    subprocess.check_call([sys.executable, "-m", "pip", "install", *requirements])
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
