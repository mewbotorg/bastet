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

from __future__ import annotations as _future_annotations

import argparse
import asyncio
import logging
import os

from . import ReportHandler, ToolRunner
from .config import PantheraConfiguration


def main() -> None:
    """
    Run a full panthera run.
    """

    # Windows hack to allow colour printing in the terminal
    # See https://bugs.python.org/issue30075.
    if os.name == "nt":
        os.system("")  # noqa: S605 S607 # nosec: B605 B607

    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("panthera")
    logger.setLevel(logging.WARNING)

    parser = argparse.ArgumentParser()
    PantheraConfiguration.add_options(parser)
    config = PantheraConfiguration(logger, parser.parse_args())

    reporter = ReportHandler(logger, *[reporter() for reporter in config.reporters])

    runner = ToolRunner(reporter, config)
    asyncio.run(runner(config.domains))


if __name__ == "__main__":
    main()
