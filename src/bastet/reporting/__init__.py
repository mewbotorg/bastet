# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

# SPDX-License-Identifier: BSD-2-Clause

"""
Reporting subsystem for Bastet.

Reporters take the output from Tools (status, annotations, and exceptions)
and generate reports for machine or human consumption.
"""

from __future__ import annotations as _future_annotations

from .abc import Reporter, ReportHandler
from .console import AnnotationReporter
from .github import GitHubReporter
from .sonar import Sonar

reporters: dict[str, type[Reporter]] = {
    "github": GitHubReporter,
    "note": AnnotationReporter,
    "sonar": Sonar,
}


__all__ = [
    "reporters",
    "ReportHandler",
    "GitHubReporter",
    "AnnotationReporter",
    "Reporter",
]
