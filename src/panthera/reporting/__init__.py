# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

# SPDX-License-Identifier: BSD-2-Clause

"""
Reporting subsystem for Panthera.

Reporters take the output from Tools (status, annotations, and exceptions)
and generate reports for machine or human consumption.
"""

from __future__ import annotations as _future_annotations

from .abc import Reporter, ReportHandler
from .console import AnnotationReporter, ConsoleReporter, GitHubReporter

__all__ = [
    "ReportHandler",
    "ConsoleReporter",
    "GitHubReporter",
    "AnnotationReporter",
    "Reporter",
]
