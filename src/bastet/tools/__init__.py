# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Helper for locating all available tools.

This currently just returns a hard-coded list.
"""

from __future__ import annotations as _future_annotations

from .audit import Bandit
from .exceptions import ToolError
from .format import Black, ISort, Ruff
from .lint import Flake8, MyPy, PyLint
from .reuse import Reuse
from .test import PyTest
from .tool import Annotation, Status, Tool, ToolDomain, ToolResult, ToolResults


def get_available_tools() -> list[type[Tool]]:
    """
    Helper for locating all available tools.

    This currently just returns a hard-coded list.
    TODO: Implement this properly.
    """
    return [
        Reuse,
        Ruff,
        ISort,
        Black,
        MyPy,
        Flake8,
        PyLint,
        Bandit,
        PyTest,
    ]


__all__ = [
    "Annotation",
    "Status",
    "Tool",
    "ToolDomain",
    "ToolError",
    "ToolResult",
    "ToolResults",
    "get_available_tools",
]
