# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Uses the reuse tool to ensure copyright info is present in all files.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable, Iterator

import asyncio
import itertools
import json
import pathlib

from .exceptions import OutputParsingError, ToolError
from .tool import Annotation, Status, Tool, ToolDomain

_COPYRIGHT_FILE = pathlib.Path("copyright.json")
_LICENSE_DIR = pathlib.Path("LICENSES")

_MISSING_CONFIG = Annotation(
    Status.FAILED,
    (_COPYRIGHT_FILE, None, None),
    "no-config",
    "Missing copyright.json",
    "copyright.json should exist in root dir with a copyright and license field.",
)
_MISSING_RIGHT = Annotation(
    Status.FAILED,
    (_COPYRIGHT_FILE, None, None),
    "no-copyright",
    "No copyright in copyright.json",
    "Copyright.json needs to have a 'copyright' field stating who owns the copyright.",
)
_MISSING_LICENSE = Annotation(
    Status.FAILED,
    (_COPYRIGHT_FILE, None, None),
    "no-license",
    "No license in copyright.json",
    (
        "Copyright.json needs to have a 'license' (or 'licence') "
        "field with the default license for files."
    ),
)


class Reuse(Tool):
    """
    Represents a run of the reuse program.
    """

    @classmethod
    def domains(cls) -> set[ToolDomain]:
        return {ToolDomain.FORMAT, ToolDomain.LINT}

    def get_command(self) -> list[str | pathlib.Path]:
        if self.domain == ToolDomain.LINT:
            return ["reuse", "lint", "--json"]

        _copyright, _license = load_copyright_file()

        return [
            "reuse",
            "annotate",
            "--merge-copyrights",
            "--copyright" if _copyright else "",
            _copyright if _copyright else "",
            "--license" if _license else "",
            _license if _license else "",
            "--skip-unrecognised",
            "--skip-existing",
            "--recursive",
            self._paths.root_path,
        ]

    def get_environment(self) -> dict[str, str]:
        return {}

    def acceptable_exit_codes(self) -> set[int]:
        if self.domain == ToolDomain.LINT:
            return {0, 1}

        return super().acceptable_exit_codes()

    async def process_results(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        _copyright, _license = load_copyright_file()

        if not _COPYRIGHT_FILE.exists():
            yield _MISSING_CONFIG

        if not _copyright:
            yield _MISSING_RIGHT

        if not _license:
            yield _MISSING_LICENSE

        generator = (
            self.process_annotate(data)
            if self.domain == ToolDomain.FORMAT
            else self.process_lint(data)
        )
        async for annotation in generator:
            if annotation:
                yield annotation

    def _with_prefix(self, line: bytes, prefix: bytes) -> pathlib.Path | None:
        if not line.startswith(prefix):
            return None

        file = line.removeprefix(prefix).strip()

        return pathlib.Path(file.decode("utf-8", errors="replace"))

    def _with_prefix_and_note(
        self,
        line: bytes,
        prefix: bytes,
    ) -> tuple[pathlib.Path, str] | None:
        if not line.startswith(prefix):
            return None

        line = line.removeprefix(prefix).strip()

        if b"'" not in line:
            return None

        file, _, info = line.decode("utf-8", errors="replace").lstrip("'").partition("'")

        return pathlib.Path(file), info.strip()

    async def process_annotate(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        while line := await data.readline():
            if info := self._with_prefix_and_note(line, b"Skipped file "):
                yield Annotation(Status.PASSED, (info[0], None, None), "reuse", info[1])
                continue

            if path := self._with_prefix(line, b"Successfully changed header of "):
                yield Annotation(
                    Status.FIXED,
                    (path, None, None),
                    "fixed",
                    "Copyright/License info added",
                )
                continue

            yield OutputParsingError(data=line.decode("utf-8", errors="replace"))

    async def process_lint(
        self,
        data: asyncio.StreamReader,
    ) -> AsyncIterable[Annotation | ToolError]:
        output = json.loads(await data.read())

        passed = {pathlib.Path(file["path"]) for file in output["files"]}
        issues = output["non_compliant"]

        for note in itertools.chain(
            self._license_issues(issues),
            self._requested_license_issues(issues, passed),
            self._spdx_issues(issues, passed),
        ):
            yield note

        for path in sorted(passed):
            yield Annotation(Status.PASSED, path, "spdx-compliant", "File passed SPDX spec")

    @staticmethod
    def _requested_license_issues(
        issues: dict[str, dict[str, list[str]]],
        passed: set[pathlib.Path],
    ) -> Iterator[Annotation]:
        for name, files in issues["bad_licenses"].items():
            yield Annotation(
                Status.FAILED,
                None,
                "bad-license",
                f"Bad license {name}",
                f"Referenced in {' '.join(files)}",
            )
            passed.difference_update({pathlib.Path(file) for file in files})

        for name, files in issues["missing_licenses"].items():
            file = _LICENSE_DIR / f"{name}.txt"
            yield Annotation(
                Status.FAILED,
                file,
                "missing-license",
                f"Missing license {name}",
                f"Referenced in {' '.join(files)}",
            )
            passed.difference_update({pathlib.Path(file) for file in files})

    @staticmethod
    def _license_issues(
        issues: dict[str, list[str] | dict[str, str]],
    ) -> Iterator[Annotation]:
        for name in issues["deprecated_licenses"]:
            file = _LICENSE_DIR / f"{name}.txt"
            yield Annotation(
                Status.FAILED,
                file,
                "deprecated-license",
                f"Deprecated license {name}",
            )

        for name in issues["unused_licenses"]:
            file = _LICENSE_DIR / f"{name}.txt"
            yield Annotation(Status.FAILED, file, "unused-license", f"Unused license {name}")

        licenses = issues["licenses_without_extension"]
        if not isinstance(licenses, dict):
            return

        for name, file_name in licenses.items():
            file = pathlib.Path(file_name)
            yield Annotation(
                Status.FAILED,
                file,
                "missing-license",
                f"Missing license {name}",
            )

    @staticmethod
    def _spdx_issues(
        issues: dict[str, list[str]],
        passed: set[pathlib.Path],
    ) -> Iterator[Annotation]:
        for file_name in issues["missing_copyright_info"]:
            file = pathlib.Path(file_name)
            yield Annotation(Status.FAILED, file, "no-copyright", "No SPDX copyright line")
            passed.discard(file)

        for file_name in issues["missing_licensing_info"]:
            file = pathlib.Path(file_name)
            yield Annotation(Status.FAILED, file, "no-license", "No SPDX license line")
            passed.discard(file)

    @staticmethod
    def _template_missing_license(license_name: str, file: pathlib.Path) -> Annotation:
        return Annotation(
            Status.FAILED,
            (file, None, None),
            "missing-license",
            f"Missing License {license_name}",
            f"The license information for {license_name} should be in the LICENSES folder.",
        )

    @staticmethod
    def _template_unused_license(name: str) -> Annotation:
        return Annotation(
            Status.FAILED,
            (pathlib.Path(f"LICENSES/{name}.txt"), None, None),
            "extra-license",
            f"Unused License {name}",
            f"The license {name} is in the LICENSES folder, but is not used by any file.",
        )

    @staticmethod
    def _template_missing_header(file: str) -> Annotation:
        return Annotation(
            Status.FAILED,
            (pathlib.Path(file), None, None),
            "missing-copyright",
            f"Missing copyright in {file}",
            f"{file} is missing SPDX license or copyright headers.",
        )


def load_copyright_file() -> tuple[str | None, str | None]:
    """
    Attempts to load a copyright.json standard from the cwd.

    If there is one.
    :return:
    """
    if not _COPYRIGHT_FILE.exists():
        return None, None

    with _COPYRIGHT_FILE.open("rb") as json_infile:
        copyright_info = json.load(json_infile)

    if not isinstance(copyright_info, dict):
        return None, None

    new_copyright = None
    if "copyright" in copyright_info:
        new_copyright = str(copyright_info["copyright"])

    new_licence = None
    if "license" in copyright_info:
        new_licence = str(copyright_info["license"])
    elif "licence" in copyright_info:
        new_licence = str(copyright_info["licence"])

    return new_copyright, new_licence


__all__ = ["Reuse"]
