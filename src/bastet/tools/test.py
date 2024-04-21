# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Bastet tool runner for working with PyTest.

PyTest is a unit test/general purpose testing system for python.

The integration with bastet is "marginal" -- this Tool class works
not by parsing any command line output, but instead by parsing the
JUnit report generated as part of the run.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable, Iterable

import asyncio
import importlib.util
import inspect
import pathlib
from xml.etree.ElementTree import (
    Element,  # nosec=B405 This is for typing, defusedxml for parsing.
)

import defusedxml.ElementTree

from .tool import Annotation, Status, Tool, ToolDomain


class PyTest(Tool):
    """
    Bastet tool runner for working with PyTest.

    PyTest is a unit test/general purpose testing system for python.

    The integration with bastet is "marginal" -- this Tool class works
    not by parsing any command line output, but instead by parsing the
    JUnit report generated as part of the run.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        """
        PyTest is in the Test domain.
        """
        return {ToolDomain.TEST}

    def get_command(self) -> list[str | pathlib.Path]:
        """
        Pytest command -- runs with coverage by default.
        """
        return [
            "pytest",
            f"--junit-xml={(self._paths.report_path / 'junit-test.xml')!s}",
            f"--cov-report=html:{self._paths.report_path!s}",
            f"--cov-report=xml:{(self._paths.report_path / 'coverage.xml')!s}",
            *(f"--cov={module!s}" for module in self._paths.python_module_path),
        ]

    def get_environment(self) -> dict[str, str]:
        """
        Environment variables to set when calling this tool.
        """
        return {}

    def acceptable_exit_codes(self) -> set[int]:
        """
        Accept all exit codes that don't represent a processing error.

        From https://docs.pytest.org/en/stable/reference/exit-codes.html:
         - Exit code 0: All tests were collected and passed successfully
         - Exit code 1: Tests were collected and run but some of the tests failed
         - Exit code 2: Test execution was interrupted by the user
         - Exit code 3: Internal error happened while executing tests
         - Exit code 4: pytest command line usage error
         - Exit code 5: No tests were collected
        """
        return {0, 1, 5}

    async def process_results(self, data: asyncio.StreamReader) -> AsyncIterable[Annotation]:
        """
        'Process output' from PyTest.

        This actually just throws the output away, then reads the junit XML
        and processes that instead.
        """
        while not data.at_eof():
            await data.read(1024)

        tree = defusedxml.ElementTree.parse(self._paths.report_path / "junit-test.xml")
        for annotation in self._process_junit(tree.getroot()):
            yield annotation

    def _process_junit(self, node: Element) -> Iterable[Annotation]:
        for testsuite in node.findall("testsuite"):
            yield from self._process_junit(testsuite)

        for testcase in node.findall("testcase"):
            name = testcase.attrib.get("name", "[unknown test]")
            source = _get_testcase_source(testcase.attrib.get("classname", ""), name)

            for failure in testcase:
                yield Annotation(
                    Status.ISSUE,
                    source,
                    "pass",
                    failure.attrib["message"],
                    failure.text,
                )
                break
            else:
                yield Annotation(Status.PASSED, source, "pass", name)


def _get_testcase_source(test_class: str, test_name: str) -> tuple[str, int, int] | str | None:
    """
    Extract the location of a testcase based on junit info.

    The junit output format from pytest has the 'classname' be the class or module
    the test function was defined in, and the 'test name' be the function and
    (for parametrized tests) the ID of the parameter set.
    """

    # ignore any parameter set info.
    test_name = test_name.partition("[")[0]

    try:
        # Assume we're looking at a function in a module.
        module = importlib.import_module(test_class)
    except ImportError:
        try:
            mod, _, test_class = test_class.rpartition(".")
            module = importlib.import_module(mod)
        except ImportError:
            return None

        if test_class not in module.__dict__:
            return module.__file__

        nearest = module.__dict__[test_class]
        if test_name in nearest.__dict__:
            nearest = nearest.__dict__[test_name]

        file = inspect.getsourcefile(nearest) or ""
        _, line = inspect.findsource(nearest)
        return file, line, 0

    # The 'classname' is a module
    if test_name not in module.__dict__:
        return module.__file__

    file = inspect.getsourcefile(module.__dict__[test_name]) or ""
    _, line = inspect.findsource(module.__dict__[test_name])
    return file, line, 0
