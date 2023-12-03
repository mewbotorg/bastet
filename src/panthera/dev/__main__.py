# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Front end for the install_deps method.
"""

from __future__ import annotations

import os
from functools import partial

from .install_deps import main as install_deps_main

main = partial(install_deps_main, search_root=os.getcwd())
