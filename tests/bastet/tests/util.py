# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Export hack to make ParameterSet easy to import.
"""

from __future__ import annotations as _future_annotations

from _pytest.mark.structures import ParameterSet

__all__ = ["ParameterSet"]
