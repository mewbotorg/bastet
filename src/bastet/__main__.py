# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Run this script before submitting to git.

This preforms a number of check and normalization functions, including
 - reuse
 - lint
 - audit

The aim is to make sure the code is fully tested and ready to be submitted to git.
All tools which should be run before submission will be run.
"""

from __future__ import annotations as _future_annotations

import argparse
import asyncio
import logging
import os
import sys

from . import BastetRunner, ReportHandler, config
from .tools import Annotation


def main() -> None:
    """
    Run a full bastet run.
    """

    # Windows hack to allow colour printing in the terminal
    # See https://bugs.python.org/issue30075.
    if os.name == "nt":
        os.system("")  # noqa: S605 S607 # nosec: B605 B607

    # Set up logging defaults.
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("bastet")
    logger.setLevel(logging.WARNING)

    # Prepare the CLI argument parsing.
    parser = argparse.ArgumentParser()
    config.add_options(parser)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # Build the options based on the config file + CLI arguments.
    cli_options = parser.parse_args()
    if cli_options.debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    options = config.BastetConfiguration(logger, cli_options)

    # Set up the root directory for annotations
    Annotation.set_root(options.folders.root_path)

    # Gather the selected reporters.
    reporter = ReportHandler(logger, *[reporter() for reporter in options.reporters])

    # Build and run the async runner.
    runner = BastetRunner(options, reporter)
    results = asyncio.run(runner.run())
    sys.exit(0 if results.success else 1)


if __name__ == "__main__":
    main()
