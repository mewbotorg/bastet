# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Dummy to make some pylint stuff work for testing.
"""


# pylint:disable=import-outside-toplevel


class TestImports:
    """
    Tests that we can import the expected objects from mewbot_dev_tools.
    """

    def test_imports_annotate(self) -> None:
        """
        Tests that we can import the expected objects from annotate.

        :return:
        """
        from mewbot_dev_tools.annotate import Annotate

        assert Annotate is not None

    def test_imports_docs(self) -> None:
        """
        Tests that we can import the expected objects from the docs.

        :return:
        """
        from mewbot_dev_tools.docs import DocToolchain

        assert DocToolchain is not None

    def test_imports_install_deps(self) -> None:
        """
        Tests that we can import the expected objects from the install_deps script.

        :return:
        """
        from mewbot_dev_tools.install_deps import main

        assert main is not None

    def test_imports_lint(self) -> None:
        """
        Tests that we can import the expected linting tools.

        :return:
        """
        from mewbot_dev_tools.lint import LintToolchain

        assert LintToolchain is not None
