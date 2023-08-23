"""
Provides support for the linting toolchain.
"""
import os

from ..lint import LintToolchain, parse_lint_options
from ..path import gather_paths


def main() -> None:
    """
    Needed for script packaging.

    :return:
    """
    options = parse_lint_options()

    paths = options.path
    if not paths:
        paths = (
            gather_paths("src", "tests", search_root=os.getcwd())
            if options.tests
            else gather_paths("src", search_root=os.getcwd())
        )

    linter = LintToolchain(*paths, in_ci=options.in_ci)
    linter()


if __name__ == "__main__":
    main()
