# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Reporting system for Bastet.

The reporting section of Bastet controls how the information
obtained from tools is reported to the user. Each Reporter
selected by the configuration gets give the raw and processed
(status, annotations, and exceptions) output from each tool,
along with a full run summary, and will output a formatted report
for machine or human consumption.
"""

from __future__ import annotations as _future_annotations

from .abc import Reporter, ReportHandler
from .codeclimate import CodeClimate
from .console import AnnotationReporter
from .file import FileReporter, SonarReporter
from .github import GitHubReporter

reporters: dict[str, type[Reporter]] = {
    "github": GitHubReporter,
    "note": AnnotationReporter,
    "file": FileReporter,
    "sonar": SonarReporter,
    "codeclimate": CodeClimate,
    "gitlab": CodeClimate,
}


__all__ = [
    "reporters",
    "ReportHandler",
    "Reporter",
]
