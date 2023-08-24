# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the method to expose the mewbot-preflight command.
"""

import os
from functools import partial

from ..preflight import main as preflight_main

main = partial(preflight_main, search_root=os.getcwd())
