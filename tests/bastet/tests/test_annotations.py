# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Test for core Tool components in Bastet.
"""

from __future__ import annotations as _future_annotations

import pathlib

import pytest
from bastet.tools import Annotation, Status

from .util import ParameterSet

SELF = pathlib.Path(__file__)
SELF_NAME = SELF.name
ROOT = SELF.parent


DATASET_NORMALISE_SOURCE = [
    ParameterSet([None, (ROOT, 0, 0)], [], "root"),
    ParameterSet([ROOT, (ROOT, 0, 0)], [], "root-path"),
    ParameterSet([__file__, (SELF, 0, 0)], [], "file"),
    ParameterSet([pathlib.Path(__file__), (SELF, 0, 0)], [], "path"),
    ParameterSet([(__file__, None, None), (SELF, 0, 0)], [], "file-no-line"),
    ParameterSet([(__file__, 1, None), (SELF, 1, 0)], [], "file-line"),
    ParameterSet([(__file__, 1, 0), (SELF, 1, 0)], [], "file-line"),
    ParameterSet([(__file__, -1, 0), (SELF, -1, 0)], [], "file-line"),
    ParameterSet([(__file__, 1, 1), (SELF, 1, 1)], [], "file-line"),
    ParameterSet([(pathlib.Path(__file__), 1, 0), (SELF, 1, 0)], [], "file-line"),
]

DATASET_TEST_FILENAME = [
    ParameterSet([None, "."], [], "root"),
    ParameterSet([ROOT, "."], [], "root-path"),
    ParameterSet([__file__, SELF_NAME], [], "file"),
    ParameterSet([pathlib.Path(__file__), SELF_NAME], [], "path"),
    ParameterSet([(__file__, None, None), SELF_NAME], [], "file-no-line"),
    ParameterSet([(__file__, 1, None), SELF_NAME], [], "file-line"),
    ParameterSet([(__file__, 1, 0), SELF_NAME], [], "file-line"),
    ParameterSet([(__file__, -1, 0), SELF_NAME], [], "file-line"),
    ParameterSet([(__file__, 1, 1), SELF_NAME], [], "file-line"),
    ParameterSet([(pathlib.Path(__file__), 1, 0), SELF_NAME], [], "file-line"),
]

DATASET_TEST_FILESTR = [
    ParameterSet([None, "[project]"], [], "root"),
    ParameterSet([ROOT, "[project]"], [], "root-path"),
    ParameterSet([__file__, SELF_NAME], [], "file"),
    ParameterSet([pathlib.Path(__file__), SELF_NAME], [], "path"),
    ParameterSet([(__file__, None, None), SELF_NAME], [], "file-no-line"),
    ParameterSet([(__file__, 1, None), f"{SELF_NAME}:1"], [], "file-line"),
    ParameterSet([(__file__, 1, 0), f"{SELF_NAME}:1"], [], "file-line"),
    ParameterSet([(__file__, -1, 0), f"{SELF_NAME}:-1"], [], "file-line"),
    ParameterSet([(__file__, 1, 1), f"{SELF_NAME}:1"], [], "file-line"),
    ParameterSet([(pathlib.Path(__file__), 1, 0), f"{SELF_NAME}:1"], [], "file-line"),
]


class TestAnnotations:
    """
    Tests for the Annotations class.
    """

    @classmethod
    def setup_class(cls) -> None:
        """Ensure annotation paths are calculated relative to this file's directory."""
        Annotation.set_root(ROOT)

    def test_trivial_init(self) -> None:
        """
        Test the dataclass constructor of Annotation for coverage purposes.
        """

        annotation = Annotation(Status.PASSED, None, "code", "message")
        assert annotation.status == Status.PASSED
        assert annotation.source == (ROOT, 0, 0)
        assert annotation.code == "code"
        assert annotation.message == "message"
        assert annotation.description is None
        assert annotation.diff is None

    @pytest.mark.parametrize(("source", "expected"), DATASET_NORMALISE_SOURCE)
    def test_normalise_source(
        self,
        source: tuple[pathlib.Path | str, int | None, int | None] | str | pathlib.Path | None,
        expected: tuple[pathlib.Path, int, int],
    ) -> None:
        """Test cases for the `Annotation._normalise_source` method."""
        normalised_source = Annotation._normalise_source(source)
        assert normalised_source == expected

    @pytest.mark.parametrize(("source", "expected"), DATASET_TEST_FILENAME)
    def test_filename(
        self,
        source: tuple[pathlib.Path | str, int | None, int | None] | str | pathlib.Path | None,
        expected: str,
    ) -> None:
        """Test cases for the `Annotation.filename` method."""
        annotation = Annotation(Status.PASSED, source, "", "")
        assert annotation.filename == expected

    @pytest.mark.parametrize(("source", "expected"), DATASET_TEST_FILESTR)
    def test_filestr(
        self,
        source: tuple[pathlib.Path | str, int | None, int | None] | str | pathlib.Path | None,
        expected: str,
    ) -> None:
        """Test cases for the `Annotation.filestr` method."""
        annotation = Annotation(Status.PASSED, source, "", "")
        assert annotation.file_str == expected
