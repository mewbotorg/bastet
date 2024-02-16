# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Callable, Iterable
from typing import Any

import argparse
import logging
import os
import sys
import tomllib
from pathlib import Path

import gitignore_parser  # type: ignore[import-untyped]

from .reporting import AnnotationReporter, Reporter
from .tools.tool import PathRepo, ToolDomain

PYPROJECT_NAME = "pyproject.toml"
GITIGNORE_NAME = ".gitignore"

GitIgnore = Callable[[Path], bool]


class PantheraConfiguration:
    @staticmethod
    def add_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        parser.add_argument(
            "--root",
            nargs=argparse.OPTIONAL,
            help="Root directory of the project.",
        )
        parser.add_argument(
            "--skip",
            nargs=argparse.ZERO_OR_MORE,
            help="Names of tools and domains to skip.",
        )
        parser.add_argument(
            "--disable",
            nargs=argparse.ZERO_OR_MORE,
            help="Names of tools and domains to disable.",
        )
        parser.add_argument(
            "--exclude",
            nargs=argparse.ZERO_OR_MORE,
            help="Folder names to exclude from discovery.",
        )
        parser.add_argument(
            "--reporter",
            nargs=argparse.ZERO_OR_MORE,
            help="Class name of a reporter tool to use.",
        )
        parser.add_argument(
            "folders",
            nargs=argparse.REMAINDER,
            help="List of source files to scan.",
        )

        return parser

    config: dict[str, Any]

    root_dir: Path
    folders: PathRepo

    skip_tools: set[str]
    skip_domains: set[ToolDomain]

    reporters: set[type[Reporter]]

    def __init__(self, logger: logging.Logger, args: argparse.Namespace) -> None:
        logger.debug("Receive CLI args %s", args)

        if args.root:
            self.root_dir = Path().resolve()
        else:
            logger.debug("Auto detecting repo root")
            self.root_dir = _find_pyproject(logger) or Path.cwd()

        logger.debug("Root Dir set to %s", self.root_dir)

        self.config = _load_config(logger, self.root_dir)

        pypath_filter = set(self._config_list("sources", ["src", "test"]))
        logger.debug("PYTHON_PATH selector set to %s", pypath_filter)

        coverage_filter = set(self._config_list("coverage_ignore", ["test"]))
        logger.debug("PYTHON_PATH coverage ignore selector set to %s", coverage_filter)

        self.folders = PathGatherer(logger, self.root_dir).gather(
            pypath_filter,
            coverage_filter,
        )

        self.reporters = {AnnotationReporter}
        self.skip_tools, self.skip_domains = set()

    def _tools_or_domains(self, items: Iterable[str]) -> tuple[set[ToolDomain], set[str]]:
        domains = set()
        tools = set()

        _domains = {domain.lower(): domain for domain in ToolDomain}

        for item in items:
            if item.lower() in _domains:
                domains.add()
            if item in ToolDomain:
                pass

        return domains, tools

    def _config_list(self, key: str, default: list[str]) -> list[str]:
        if key not in self.config:
            return default

        value = self.config[key]

        if isinstance(value, list):
            return value

        # TODO: make this happen again (in a config parsing/building class
        # logger warning("Config option %s should be a list, got %s", key, type(value))
        return default

    @property
    def domains(self) -> list[ToolDomain]:
        return [ToolDomain.FORMAT, ToolDomain.LINT, ToolDomain.AUDIT]


class PathGatherer:
    root: Path
    logger: logging.Logger

    _initial_py_path: frozenset[Path]
    _potential_py_path: set[Path]
    _python_path: set[Path]
    _python_module_path: set[Path]
    _python_files: set[Path]

    _pypath_selector: set[str]

    def __init__(self, logger: logging.Logger, root: Path) -> None:
        self.root = root.absolute()
        self.logger = logger

        self._potential_py_path = set()
        self._python_path = set()
        self._python_module_path = set()
        self._python_files = set()

    def gather(self, pypath_selector: set[str], coverage_exclude: set[str]) -> PathRepo:
        self._potential_py_path = self._initial_path()
        self._initial_py_path = frozenset(self._potential_py_path)
        self._python_path = set()
        self._python_module_path = set()
        self._pypath_selector = pypath_selector

        self.logger.debug("Adding '.git' and '.hg' to gitignore list")
        _ignores = [lambda path: path.name in [".git", ".hg"]]

        local_ignores = self.root / ".git" / "info" / "exclude"
        if local_ignores.exists():
            self.logger.debug("Adding %s to gitignore list", local_ignores)
            _ignores.append(gitignore_parser.parse_gitignore(local_ignores, self.root))

        self._scan_dir(self.root, _ignores)

        coverage_path = {
            path for path in self._python_path if path.name not in coverage_exclude
        }

        self.logger.debug("PYTHON_PATH:      %s", self._python_path)
        self.logger.debug("Coverage targets: %s", coverage_path)
        self.logger.debug("Module Roots:     %s", self._python_module_path)

        return PathRepo(
            self.root,
            self._python_path,
            coverage_path,
            self._python_files,
            self._python_module_path,
        )

    def _initial_path(self) -> set[Path]:
        paths = set()

        for potential in sys.path:
            path = Path(potential).absolute()
            if self.root in path.parents:
                self.logger.debug("Potential PYTHON_PATH: %s", path)
                paths.add(path)

        return paths

    def _scan_dir(self, path: Path, ignores: list[GitIgnore]) -> None:
        potential_gitignore = path / GITIGNORE_NAME
        if potential_gitignore.is_file():
            self.logger.debug("Adding %s to gitignore list", potential_gitignore)
            ignores = ignores.copy()
            ignores.append(gitignore_parser.parse_gitignore(potential_gitignore, path))

        if path.name in self._pypath_selector and path not in self._potential_py_path:
            self.logger.debug("Potential PYTHON_PATH: %s", path)
            self._potential_py_path.add(path)

        for file in path.iterdir():
            if any(ignore(file) for ignore in ignores):
                continue

            if file.is_dir():
                self._scan_dir(file, ignores)
                continue

            if file.name.endswith(".py"):
                self._process_python_file(file)

    def _process_python_file(self, file: Path) -> None:
        self._python_files.add(file)

        if self._add_path(self._python_module_path, file.parent):
            self.logger.debug("Marking %s as a module path", file.parent)

        if self._closest_relative(self._python_path, file):
            return

        # Module roots can't be a PYTHONPATH entry
        my_dir_cant_by_pypath = (file.parent / "__init__.py").exists()

        py_root = self._closest_relative(
            self._potential_py_path,
            file.parent if my_dir_cant_by_pypath else file,
        )

        if not py_root:
            self.logger.debug("Unable to locate a potential PYTHONPATH for %s", file)
            return

        if py_root not in self._initial_py_path:
            self.logger.warning("Detecting %s as a path, but not in PYTHON_PATH", py_root)

        self.logger.debug(
            "Marking %s as PYTHON_PATH entry due to python file %s",
            py_root,
            file,
        )
        self._potential_py_path.remove(py_root)
        self._python_path.add(py_root)

    @staticmethod
    def _add_path(paths: set[Path], path: Path) -> bool:
        if path in paths:
            return False

        for _path in paths:
            if path.is_relative_to(_path):
                return False

        paths.add(path)
        return True

    @staticmethod
    def _closest_relative(paths: set[Path], path: Path) -> Path | None:
        _closest: Path | None = None
        for _path in paths:
            if _path not in path.parents:
                continue

            if _closest and _closest.is_relative_to(_path):
                continue

            _closest = _path

        return _closest


def _load_config(logger: logging.Logger, folder: Path) -> dict[str, Any]:
    logger.debug("Loading config from %s", folder)

    file = folder / PYPROJECT_NAME

    if not file.is_file():
        logger.warning("config file %s not found", file)
        return {}

    with file.open("rb") as in_file:
        toml = tomllib.load(in_file)

    config: dict[str, Any] = toml.get("tool", {}).get("panthera", {})

    if not isinstance(config, dict):
        logger.warning("Bad config: '[tool.panthera]' section in %s is not a dict", file)
        config = {}

    logger.debug("Loaded config: %s", config)
    return config


def _find_pyproject(logger: logging.Logger) -> Path | None:
    """
    Search for file pyproject.toml in the parent directories recursively.

    It resolves symlinks, so if there is any symlink up in the tree,
    it does not respect them.
    """
    current_dir = Path.cwd().resolve()

    while True:
        if (current_dir / PYPROJECT_NAME).is_file():
            logger.debug("Selecting %s due to %s", current_dir, PYPROJECT_NAME)
            return current_dir

        if (current_dir / ".git").is_dir():
            logger.debug("Selecting %s due to .git folder", current_dir)
            return current_dir

        if (current_dir / ".hg").is_dir():
            logger.debug("Selecting %s due to .hg folder", current_dir)
            return current_dir

        if current_dir == current_dir.parent:
            logger.error("No repo root found before hitting root directory.")
            return None

        current_dir = current_dir.parent


def main() -> None:
    logger = logging.getLogger("panthera.config")

    logger.debug("Auto detecting repo root")
    root = _find_pyproject(logger) or Path.cwd()

    logger.debug("Root Dir set to %s", root)

    config = _load_config(logger, root)

    pypath_filter = set(config.get("sources", ["src", "tests"]))
    logger.debug("PYTHON_PATH selector set to %s", pypath_filter)

    folders = PathGatherer(logger, root).gather(pypath_filter, set())
    sorted_folders = sorted(map(str, folders.python_path), key=len, reverse=True)

    sys.stdout.write(os.pathsep.join(sorted_folders))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
