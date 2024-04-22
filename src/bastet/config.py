# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Bastet Configuration.

- Options class for storing and passing runtime options.
- Tooling for gathering files that are "in the project".
- Tooling for reading the configuration toml.
"""

from __future__ import annotations as _future_annotations

from collections.abc import Callable, Iterable
from typing import Any

import argparse
import logging
import sys
import tomllib
from pathlib import Path

import gitignore_parser  # type: ignore[import-untyped]

from .reporting import Reporter, reporters
from .tools.tool import PathRepo, ToolDomain

PYPROJECT_NAME = "pyproject.toml"
GITIGNORE_NAME = ".gitignore"

GitIgnore = Callable[[Path], bool]


class BastetConfiguration:  # pylint: disable=too-few-public-methods
    """
    Configuration for a Bastet run.
    """

    config: dict[str, Any]

    folders: PathRepo
    reports: Path

    skip_tools: set[str]
    skip_domains: set[ToolDomain]

    reporters: set[type[Reporter]]

    def __init__(self, logger: logging.Logger, args: argparse.Namespace) -> None:
        """
        Setup runtime configuration.

        This function:
         - Detects the project's root directory.
         - Loads default configuration from pyproject.toml.
         - Merges in the command line options.
         - Determines the reporters to select.
         - Determines the domains and tools to exclude.
         - Builds out the list of folders to scan.
        """

        logger.debug("Receive CLI args %s", args)

        # Find the "root" of the repo (where the pyproject.toml should be).
        if args.root:
            root_dir = Path().resolve()
        else:
            logger.debug("Auto detecting repo root")
            root_dir = _find_pyproject(logger) or Path.cwd()

        logger.debug("Root Dir set to %s", root_dir)

        # Load the config file version of the config.
        self.config = _load_config(logger, root_dir)

        # Config the list of reporting engines to use
        self.reporters = set()
        for reporter in args.reporter or self._config_list("reporters", ["note"]):
            if reporter.lower() not in reporters:
                logger.warning("Unknown reporter class %s", reporter)
                continue
            self.reporters.add(reporters[reporter])
        logger.debug("Reporters set to %s")

        # Determine what domains and tools are not to be run.
        # Note: "disabled" and "skip" are distinct lists; the difference is
        # "skip" can only be specified on the CLI. The two lists are merged.
        disabled = args.disable or self._config_list("disable", [])
        disabled += args.skip or []
        self.skip_domains, self.skip_tools = _tools_or_domains(disabled)
        logger.debug("disabled domains: %s", self.skip_domains)
        logger.debug("disabled tools: %s", self.skip_tools)

        # Set up the source folders that will be scanned
        pypath_filter = set(self._config_list("sources", ["src", "tests"]))
        logger.debug("PYTHON_PATH selector set to %s", pypath_filter)

        exclude = args.exclude or self._config_list("exclude", [])
        logger.debug("exclusion list set to %s", exclude)

        # Gather all the paths that are included
        initial_folders = [Path(path) for path in args.folders]
        folders = PathGatherer(logger, root_dir, initial_folders)
        self.folders = folders.gather(exclude, pypath_filter)

    def _config_list(self, key: str, default: list[str]) -> list[str]:
        """
        Get a list from the TOML config, or a default if not set or not a list.
        """
        if key not in self.config:
            return default

        value = self.config[key]

        if isinstance(value, list):
            return value

        return default

    @property
    def domains(self) -> list[ToolDomain]:
        """
        Gets the list of domains that are selected in this config.
        """
        return [domain for domain in ToolDomain if domain not in self.skip_domains]


def add_options(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """
    Add out configuration options to an ArgumentParser.

    The output of that parse will be then be used to create a BastetConfiguration
    instance, which will combine the file-based configuration with the command
    line options to build the overall run configuration.
    """

    parser.add_argument(
        "--root",
        nargs=argparse.OPTIONAL,
        help="Root directory of the project.",
    )
    parser.add_argument(
        "--skip",
        nargs=argparse.ZERO_OR_MORE,
        help="Names of tools and domains to skip (in extension to configured 'disable').",
    )
    parser.add_argument(
        "--disable",
        nargs=argparse.ZERO_OR_MORE,
        help="Names of tools and domains to disable (overrides config).",
    )
    parser.add_argument(
        "--exclude",
        nargs=argparse.ZERO_OR_MORE,
        help="Folder names to exclude from discovery (gitignore format).",
    )
    parser.add_argument(
        "--reporter",
        nargs=argparse.ZERO_OR_MORE,
        help="Class name of a reporter tool to use.",
        choices=reporters.keys(),
    )
    parser.add_argument(
        "folders",
        nargs=argparse.REMAINDER,
        help="List of source files to scan.",
    )

    return parser


class PathGatherer:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """
    Tool for locating PYTHON_PATH and non-namespace python module roots.
    """

    root: Path
    logger: logging.Logger

    _potential_py_path: set[Path]
    _python_path: set[Path]
    _python_module_path: set[Path]
    _python_files: set[Path]
    _exclusion: set[Path]

    def __init__(self, logger: logging.Logger, root: Path, folders: list[Path]) -> None:
        """
        Tool for locating PYTHON_PATH and non-namespace python module roots.
        """

        self.root = root.absolute()
        self.logger = logger

        self._initial_folders = folders
        self._potential_py_path = set()
        self._python_path = set()
        self._python_module_path = set()
        self._python_files = set()
        self._exclusion = set()

    def gather(self, exclude: list[str], pypath_selector: set[str]) -> PathRepo:
        """
        Gathers the PYTHON_PATH and python module paths.

        This considers:
         - PYTHON_PATH should start at a folder with the name in pypath_selector
           (e.g. 'src', 'tests').
         - A module is defined by the presence of a .py file.
         - A folder with a __init__.py is a module in itself, and can't be a PYTHON_PATH.
         - Modules may be namespace modules, and not directly contain files.
         - We should ignore everything in `.git`, `.hg`, and the files matching
           the globs in `.gitignore` in the path or in `.git/info/exclude` in general.

        The result is a PathRepo object listing the detected PYTHON_PATH and top-level
        location of non-namespace modules, along with a complete list of .py files that
        match them.
        """

        self._potential_py_path = self._initial_path()
        self._python_path = set()
        self._python_module_path = set()

        self.logger.debug("Adding '.git' and '.hg' to gitignore list")
        _ignores = [lambda path: path.name in [".git", ".hg"]]

        for rule in exclude:
            self.logger.debug("Adding %s to gitignore list", rule)
            _ignores.append(gitignore_parser.rule_from_pattern(rule, self.root, "config"))

        local_ignores = self.root / ".git" / "info" / "exclude"
        if local_ignores.exists():
            self.logger.debug("Adding %s to gitignore list", local_ignores)
            _ignores.append(gitignore_parser.parse_gitignore(local_ignores, self.root))

        locations_to_scan = self._initial_folders if self._initial_folders else [self.root]
        for location in locations_to_scan:
            if not location.exists():
                self.logger.warning("%s does not exist, can not scan", location)
                continue

            self._scan_dir(location, _ignores, pypath_selector)

        self.logger.debug("PYTHON_PATH:      %s", self._python_path)
        self.logger.debug("Module Roots:     %s", self._python_module_path)

        return PathRepo(
            self.root,
            self.root / "reports",
            frozenset(self._exclusion),
            frozenset(self._python_path),
            frozenset(self._python_files),
            frozenset(self._python_module_path),
        )

    def _initial_path(self) -> set[Path]:
        paths = set()

        for potential in sys.path:
            path = Path(potential).absolute()
            if self.root in path.parents:
                self.logger.debug("Potential PYTHON_PATH: %s", path)
                paths.add(path)

        if self.root not in paths:
            self.logger.debug("Potential PYTHON_PATH: %s", self.root)
            paths.add(self.root)

        return paths

    def _scan_dir(self, path: Path, ignores: list[GitIgnore], selector: set[str]) -> None:
        potential_gitignore = path / GITIGNORE_NAME
        if potential_gitignore.is_file():
            self.logger.debug("Adding %s to gitignore list", potential_gitignore)
            ignores = ignores.copy()
            ignores.append(gitignore_parser.parse_gitignore(potential_gitignore, path))

        if path.name in selector and path not in self._potential_py_path:
            self.logger.debug("Potential PYTHON_PATH: %s", path)
            self._potential_py_path.add(path)

        for file in path.iterdir():
            if any(ignore(file) for ignore in ignores):
                if file.is_dir():
                    self._exclusion.add(file)
                continue

            if file.is_dir():
                self._scan_dir(file, ignores, selector)
                continue

            if file.name.endswith(".py"):
                self._process_python_file(file)

    def _process_python_file(self, file: Path) -> None:
        self._python_files.add(file)

        if self._add_path(self._python_module_path, file.parent, remove_children=True):
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

        if py_root not in self._initial_path():
            self.logger.warning("Detecting %s as a path, but not in PYTHON_PATH", py_root)

        self.logger.debug(
            "Marking %s as PYTHON_PATH entry due to python file %s",
            py_root,
            file,
        )
        self._potential_py_path.remove(py_root)
        self._python_path.add(py_root)

    @staticmethod
    def _add_path(paths: set[Path], path: Path, *, remove_children: bool) -> bool:
        if path in paths:
            return False

        for _path in paths:
            if path.is_relative_to(_path):
                return False

        if remove_children:
            paths.difference_update({x for x in paths if x.is_relative_to(path)})

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


def _tools_or_domains(items: Iterable[str]) -> tuple[set[ToolDomain], set[str]]:
    """
    Splits a list of config references into a set of domains and a set of tools.
    """
    domains = set()
    tools = set()

    _domains = {domain.lower(): domain for domain in ToolDomain}

    for _item in items:
        item = _item.lower()

        if item in _domains:
            domains.add(_domains[item])
        else:
            tools.add(item)

    return domains, tools


def _load_config(logger: logging.Logger, folder: Path) -> dict[str, Any]:
    logger.debug("Loading config from %s", folder)

    file = folder / PYPROJECT_NAME

    if not file.is_file():
        logger.warning("config file %s not found", file)
        return {}

    with file.open("rb") as in_file:
        toml = tomllib.load(in_file)

    config: dict[str, Any] = toml.get("tool", {}).get("bastet", {})

    if not isinstance(config, dict):
        logger.warning("Bad config: '[tool.bastet]' section in %s is not a dict", file)
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
    """
    Run the configuration under debug mode without CLI options.

    Used for debugging the setup and work.
    """

    logger = logging.getLogger("bastet.config")

    logger.debug("Auto detecting repo root")
    root = _find_pyproject(logger) or Path.cwd()

    logger.debug("Root Dir set to %s", root)

    config = _load_config(logger, root)

    pypath_filter = set(config.get("sources", ["src", "tests"]))
    logger.debug("PYTHON_PATH selector set to %s", pypath_filter)

    folders = PathGatherer(logger, root, []).gather([], pypath_filter)

    sorted_folders = sorted(map(str, folders.exclude_dirs), key=len, reverse=True)
    sys.stdout.write("\n-- Excluded paths\n")
    sys.stdout.write("\n".join(sorted_folders))
    sys.stdout.write("\n")

    sorted_folders = sorted(map(str, folders.python_path), key=len, reverse=True)
    sys.stdout.write("\n-- Python paths\n")
    sys.stdout.write("\n".join(sorted_folders))
    sys.stdout.write("\n")

    sorted_folders = sorted(map(str, folders.python_module_path), key=len, reverse=True)
    sys.stdout.write("\n-- Python base module paths\n")
    sys.stdout.write("\n".join(sorted_folders))
    sys.stdout.write("\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
