# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Tests linting a document.
"""
import os
import tempfile

import pytest

from mewbot_dev_tools.lint import LintOptions
from mewbot_dev_tools.lint import main as lint_main

# pylint: disable = too-few-public-methods


class TestLintToolchain:
    """
    Tests running the linting toolchain against some example files.
    """

    def test_full_lint_run_focus_black(self) -> None:
        """
        Tests that the black and reuse runs preform as expected.

        :return:
        """
        test_code = """

import os, uuid

def some_badly_formated_mess(parameter_ws       , param_two):
    \"\"\"
    This is just intended to be a complete mess.
    :param parameter_ws:
    :param param_two:
    :return:
    \"\"\"
    if isinstance(parameter_ws, str):
        print("Wellllllllll - that's nice")


import pprint

        """

        test_code_post_black = """import os
import uuid


def some_badly_formated_mess(parameter_ws, param_two):
    \"\"\"
    This is just intended to be a complete mess.
    :param parameter_ws:
    :param param_two:
    :return:
    \"\"\"
    if isinstance(parameter_ws, str):
        print("Wellllllllll - that's nice")


import pprint
"""

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_code_path = os.path.join(tmp_dir, "test_file.py")

            with open(test_code_path, "w+", encoding="utf-8") as test_code_file:
                test_code_file.write(test_code)

            # Lint runs and then calls an exit - this is undesirable
            # Note - SystemEit DOES NOT descend from Exception.

            lint_options = LintOptions()
            lint_options.path = [tmp_dir]

            with pytest.raises(SystemExit):
                lint_main(search_root=tmp_dir, programatic_options=lint_options)

            with open(test_code_path, "r", encoding="utf-8") as test_code_file:
                assert test_code_file.read() == test_code_post_black
