#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Tools for detecting paths at which source files are installed.

This file, when called directly, prints out a set of values for PYTHONPATH.
As such, it can not rely on anything that would be loaded using PYTHONPATH,
i.e. we can not use any other mewbot code from this file.
"""

from typing import Iterable, Optional

import itertools
import os
import pathlib


def scan_paths(
    root: pathlib.Path, *filters: str, recursive: bool = True
) -> Iterable[pathlib.Path]:
    """Scan for folders with a given name in the provided path."""

    if not recursive:
        yield from [root / name for name in filters if (root / name).exists()]
        return

    for path, children, files in os.walk(root):
        for name in filters:
            if name in children or name in files:
                yield pathlib.Path(path) / name


def gather_paths(*filters: str, search_root: Optional[str] = None) -> Iterable[str]:
    """
    Locates all folders with the given names in this project's code locations.

    :param filters: A list of dirs to search within
    :param search_root: If provided, start the search here.
                        If not, use os.curdir
    """
    if search_root is not None:
        root = pathlib.Path(search_root)
    else:
        root = pathlib.Path(os.curdir)

    locations = itertools.chain(
        scan_paths(root, *filters, recursive=False),
        scan_paths(root / "plugins", *filters),
    )

    return (str(x.absolute()) for x in locations)


def gather_paths_standard_locs(
    search_root: Optional[str], tests: bool = False
) -> Iterable[str]:
    """
    Gather paths from the standard locations.

    Currently "src" and "tests".
    :return:
    """
    paths = (
        gather_paths("src", "tests", search_root=search_root)
        if tests
        else gather_paths("src", search_root=search_root)
    )
    return paths


if __name__ == "__main__":
    # When called directly, this module output the value of the PYPATH environment variable
    print(os.pathsep.join(gather_paths("src")))
