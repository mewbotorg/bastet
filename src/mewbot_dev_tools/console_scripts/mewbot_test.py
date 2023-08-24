# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Collects and runs all tests in the cwd.
"""

import os
from functools import partial

from ..test import main as mewbot_test

main = partial(mewbot_test, search_root=os.getcwd())
