# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Stores the method to expose the mewbot-security-analysis command.
"""


import os
from functools import partial

from ..security_analysis import main as sec_analysis_main

main = partial(sec_analysis_main, search_root=os.getcwd())
