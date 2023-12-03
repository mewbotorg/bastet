# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
This script is responsible for constructing a venv which you can use for mewbot dev.

Execute it with the python interpreter you wish to use as the basis for the venv.
This script takes two arguments
 - a folder which __must__ exist on the file system
 - a name for the venv
venv names are only permitted to use [a-zA-Z0-9_-].

This is for reasons of security.
After the venv is created, a number of other commands need to be run in it.
As such, the venv needs to be activated.
Thus, it's name needs to be passed to the shell (or some equivalent operation - e.g. writing out a
script.
Which is a potentially quite significant security hole.
Therefore, the requirement on the file name.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, ClassVar, List, Optional, TypeVar

import argparse
import enum
import itertools
import ntpath
import os
import pathlib
import platform as sys_platform
import posixpath
import re
import shutil
import string
import subprocess
import sys

# pylint: disable=wrong-import-position,too-many-lines

SEPERATOR = "=" * 50


# -1 - Set construction conditions
assert os.path.exists(__file__) and os.path.isfile(
    __file__
), f"{__file__ = } did not exist. Something is odd."

TOOLS_FOLDER_PATH = os.path.split(__file__)[0]
assert os.path.isdir(TOOLS_FOLDER_PATH), f"{TOOLS_FOLDER_PATH = } does not exist."

INSTALL_DEPS_PATH = os.path.join(TOOLS_FOLDER_PATH, "install_deps.py")
assert os.path.isfile(INSTALL_DEPS_PATH), f"{INSTALL_DEPS_PATH = } does not exist"

MEWBOT_MODULE_PATH = os.path.split(TOOLS_FOLDER_PATH)[0]
assert os.path.isdir(TOOLS_FOLDER_PATH), f"{MEWBOT_MODULE_PATH = } does not exist."

SRC_PATH = os.path.split(MEWBOT_MODULE_PATH)[0]
assert os.path.isdir(SRC_PATH), f"{SRC_PATH = } does not exist."

MEWBOT_REPO_PATH = os.path.split(SRC_PATH)[0]
assert os.path.isdir(
    MEWBOT_REPO_PATH
), f"{MEWBOT_REPO_PATH = } does not exist. Are you sure your installing from source?"
print(f"Using {MEWBOT_REPO_PATH = }")

TOOLS_PATH = os.path.join(MEWBOT_REPO_PATH, "tools")
assert os.path.isdir(TOOLS_PATH), f"{TOOLS_PATH = } does not exist."
print(f"With {TOOLS_PATH = }")

MEWBOT_PLUGINS_DIR = os.path.join(MEWBOT_REPO_PATH, "plugins")
assert os.path.isdir(MEWBOT_PLUGINS_DIR), f"{MEWBOT_PLUGINS_DIR = } does not exist"

SHELL_NEEDED = bool(os.name == "nt")


#######################################################
#
# - NAME VALIDATION LOGIC
#
# Code for this validator adapted from https://github.com/thombashi/pathvalidate
#
#         THIS SECTION is Licensed under MIT. See below.
#
#         The MIT License (MIT)
#
#     Copyright (c) 2016 Tsuyoshi Hombashi
#
#     Permission is hereby granted, free of charge, to any person obtaining a copy
#     of this software and associated documentation files (the "Software"), to deal
#     in the Software without restriction, including without limitation the rights
#     to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#     copies of the Software, and to permit persons to whom the Software is
#     furnished to do so, subject to the following conditions:
#
#     The above copyright notice and this permission notice shall be included in all
#     copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#     IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#     FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#     AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#     LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#     OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#     SOFTWARE.

# pylint: disable=consider-using-generator
unprintable_ascii_chars = tuple(
    [chr(c) for c in range(128) if chr(c) not in string.printable]
)

DEFAULT_MIN_LEN = 1
_DEFAULT_MAX_FILENAME_LEN = 255
_re_whitespaces = re.compile(r"^[\s]+$")

INVALID_CHAR_ERR_MSG_TMPL = "invalids=({invalid}), value={value}"

# imo it's not worth renaming to satisfy pylint that a TypeVar shouldn't end with "Type"
PathType = TypeVar("PathType", str, pathlib.Path)  # pylint: disable=invalid-name


def _is_not_null_string(value: Any) -> bool:
    """Check if a value is a null string."""
    try:
        return len(value.strip()) > 0
    except AttributeError:
        return False


def is_null_string(value: Any) -> bool:
    """Does the string value have content."""
    if value is None:
        return True

    try:
        return len(value.strip()) == 0
    except AttributeError:
        return False


def validate_pathtype(text: PathType, allow_whitespaces: bool = False) -> None:
    """Validate something which claims to be a path is of the right type."""
    if _is_not_null_string(text) or isinstance(text, pathlib.Path):
        return

    if allow_whitespaces and _re_whitespaces.search(str(text)):
        return

    if is_null_string(text):
        raise ValidationError(reason=ErrorReason.NULL_NAME)

    raise TypeError(f"text must be a string: actual={type(text)}")


def to_str(name: PathType) -> str:
    """Coerce a pathlike object to a str."""
    if isinstance(name, pathlib.Path):
        return str(name)
    return name


def findall_to_str(match: List[Any]) -> str:
    """Takes a match object and returns all found elements as a str."""
    return ", ".join([repr(text) for text in match])


def _to_error_code(code: int) -> str:
    """Takes a error code and returns a human readable form."""
    return f"PV{code:04d}"


@enum.unique
class ErrorReason(enum.Enum):
    """Validation error reasons."""

    NULL_NAME = (_to_error_code(1001), "NULL_NAME", "the value must not be an empty")
    RESERVED_NAME = (_to_error_code(1002), "RESERVED_NAME", "name used by platform")
    INVALID_CHARACTER = (_to_error_code(1100), "INVALID_CHARACTER", "invalid chas found")
    INVALID_LENGTH = (_to_error_code(1101), "INVALID_LENGTH", "invalid str length")
    FOUND_ABS_PATH = (
        _to_error_code(1200),
        "FOUND_ABS_PATH",
        "found abs, expect rel path",
    )
    MALFORMED_ABS_PATH = (
        _to_error_code(1201),
        "MALFORMED_ABS_PATH",
        "malformed abs path",
    )
    INVALID_AFTER_SANITIZE = (
        _to_error_code(2000),
        "INVALID_AFTER_SANITIZE",
        "san broke path",
    )

    def __init__(self, code: str, name: str, description: str) -> None:
        """Init the class."""
        self._name = name
        self.code = code
        self.description = description

    def __str__(self) -> str:
        """String rep of the class."""
        return f"[{self.code}] {self.description}"


@enum.unique
class Platform(enum.Enum):
    """All valid platform."""

    #: POSIX compatible. note that absolute paths cannot specify this.
    POSIX = "POSIX"

    #: platform independent. note that absolute paths cannot specify this.
    UNIVERSAL = "universal"

    LINUX = "Linux"
    WINDOWS = "Windows"
    MACOS = "macOS"


PlatformType = TypeVar("PlatformType", str, Platform)  # pylint: disable=invalid-name


def normalize_platform(name: Optional[PlatformType]) -> Platform:
    """Bring the current platform into normalized form."""
    if isinstance(name, Platform):
        return name

    if name:
        name = name.strip().casefold()

        if name == "posix":
            return Platform.POSIX

        if name == "auto":
            name = sys_platform.system().casefold()

        if name in ["linux"]:
            return Platform.LINUX

        if name and name.startswith("win"):
            return Platform.WINDOWS

        if name in ["mac", "macos", "darwin"]:
            return Platform.MACOS

    return Platform.UNIVERSAL


class BaseFile:
    """Base class for the file name validator."""

    INVALID_PATH_CHARS: ClassVar[str] = "".join(unprintable_ascii_chars)
    INVALID_FILENAME_CHARS: ClassVar[str] = INVALID_PATH_CHARS + "/"
    INVALID_WIN_PATH_CHARS: ClassVar[str] = INVALID_PATH_CHARS + ':*?"<>|\t\n\r\x0b\x0c'
    INVALID_WIN_FILENAME_CHARS: ClassVar[str] = (
        INVALID_FILENAME_CHARS + INVALID_WIN_PATH_CHARS + "\\"
    )

    @property
    def max_len(self) -> int:
        """Max permitted length of a name."""
        return self._max_len

    def validate_abspath(self, value: str) -> None:
        """Check a given abspath in the form of a str."""
        raise NotImplementedError("Must be overridden.")

    # Not worth reworking the base class that much
    def __init__(  # pylint: disable=too-many-arguments
        self,
        max_len: int,
        fs_encoding: Optional[str],
        check_reserved: bool,
        platform_max_len: Optional[int] = None,
        platform: Optional[PlatformType] = None,
    ) -> None:
        """Startup the base file."""
        self.platform = normalize_platform(platform)
        self._check_reserved = check_reserved

        if platform_max_len is None:
            platform_max_len = self._get_default_max_path_len()

        if max_len <= 0:
            self._max_len = platform_max_len
        else:
            self._max_len = max_len

        self._max_len = min(self._max_len, platform_max_len)

        if fs_encoding:
            self._fs_encoding = fs_encoding
        else:
            self._fs_encoding = sys.getfilesystemencoding()

    def _is_posix(self) -> bool:
        return self.platform == Platform.POSIX

    def _is_universal(self) -> bool:
        return self.platform == Platform.UNIVERSAL

    def _is_linux(self, include_universal: bool = False) -> bool:
        if include_universal:
            return self.platform in (Platform.UNIVERSAL, Platform.LINUX)

        return self.platform == Platform.LINUX

    def _is_windows(self, include_universal: bool = False) -> bool:
        if include_universal:
            return self.platform in (Platform.UNIVERSAL, Platform.WINDOWS)

        return self.platform == Platform.WINDOWS

    def _is_macos(self, include_universal: bool = False) -> bool:
        if include_universal:
            return self.platform in (Platform.UNIVERSAL, Platform.MACOS)

        return self.platform == Platform.MACOS

    def _get_default_max_path_len(self) -> int:
        if self._is_linux():
            return 4096

        if self._is_windows():
            return 260

        if self._is_posix() or self._is_macos():
            return 1024

        return 260  # universal


RE_INVALID_FILENAME = re.compile(
    f"[{re.escape(BaseFile.INVALID_FILENAME_CHARS):s}]", re.UNICODE
)
_RE_INVALID_WIN_FILENAME = re.compile(
    f"[{re.escape(BaseFile.INVALID_WIN_FILENAME_CHARS):s}]", re.UNICODE
)


class ValidationError(ValueError):
    """
    Exception class of validation errors.

    .. py:attribute:: reason

        The cause of the error.

        Returns:
            :py:class:`~pathvalidate.error.ErrorReason`:
    """

    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        """Startup the exception."""
        self.platform: Optional[Platform] = kwargs.pop("platform", None)
        self.reason: Optional[ErrorReason] = kwargs.pop("reason", None)
        self.description: Optional[str] = kwargs.pop("description", None)
        self.reserved_name: str = kwargs.pop("reserved_name", "")
        self.reusable_name: Optional[bool] = kwargs.pop("reusable_name", None)
        self.__fs_encoding: Optional[str] = kwargs.pop("fs_encoding", None)

        try:
            super().__init__(*args[0], **kwargs)
        except IndexError:
            super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        """String containing all error info."""
        item_list = []
        header = ""

        if self.reason:
            header = str(self.reason)

        if Exception.__str__(self):
            item_list.append(Exception.__str__(self))

        if self.platform:
            item_list.append(f"target-platform={self.platform.value}")
        if self.description:
            item_list.append(f"description={self.description}")
        if self.reusable_name is not None:
            item_list.append(f"reusable_name={self.reusable_name}")
        if self.__fs_encoding:
            item_list.append(f"fs-encoding={self.__fs_encoding}")

        if item_list:
            header += ": "

        return header + ", ".join(item_list).strip()

    def __repr__(self, *args: Any, **kwargs: Any) -> str:
        """Reliable repr of the exception."""
        return self.__str__(*args, **kwargs)


class ReservedNameError(ValidationError):
    """
    Exception raised when a string matched a reserved name.
    """

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Error caused by the string matching a system reserved name."""
        kwargs["reason"] = ErrorReason.RESERVED_NAME

        super().__init__(args, **kwargs)


class InvalidCharError(ValidationError):
    """
    Exception raised when includes invalid character(s) within a string.
    """

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Startup the exception."""
        kwargs["reason"] = ErrorReason.INVALID_CHARACTER

        super().__init__(args, **kwargs)


class BaseValidator(BaseFile):
    """Base class for the file name validator."""

    def _validate_max_len(self) -> None:
        if self.max_len < 1:
            raise ValueError("max_len must be greater or equal to one")

        if self.min_len > self.max_len:
            raise ValueError("min_len must be lower than max_len")

    def __init__(  # pylint: disable=too-many-arguments
        self,
        min_len: int,
        max_len: int,
        fs_encoding: Optional[str],
        check_reserved: bool,
        platform_max_len: Optional[int] = None,
        platform: Optional[PlatformType] = None,
    ) -> None:
        """Startup the base validator."""
        if min_len <= 0:
            min_len = DEFAULT_MIN_LEN
        self.min_len = max(min_len, 1)

        super().__init__(
            max_len=max_len,
            fs_encoding=fs_encoding,
            check_reserved=check_reserved,
            platform_max_len=platform_max_len,
            platform=platform,
        )

        self._validate_max_len()

    def validate_abspath(self, value: str) -> None:
        """Check a given abspath in the form of a str."""
        raise NotImplementedError("Must be overridden.")


class FileNameValidator(BaseValidator):
    """File name validator class."""

    _WINDOWS_RESERVED_FILE_NAMES = ("CON", "PRN", "AUX", "CLOCK$", "NUL") + tuple(
        f"{name:s}{num:d}" for name, num in itertools.product(("COM", "LPT"), range(1, 10))
    )
    _MACOS_RESERVED_FILE_NAMES = (":",)

    reserved_keywords = _WINDOWS_RESERVED_FILE_NAMES + _MACOS_RESERVED_FILE_NAMES

    def _is_reserved_keyword(self, value: str) -> bool:
        return value in self.reserved_keywords

    def __init__(  # pylint: disable=too-many-arguments
        self,
        min_len: int = DEFAULT_MIN_LEN,
        max_len: int = _DEFAULT_MAX_FILENAME_LEN,
        fs_encoding: Optional[str] = None,
        platform: Optional[PlatformType] = None,
        check_reserved: bool = True,
    ) -> None:
        """Start up the file name validator."""
        super().__init__(
            min_len=min_len,
            max_len=max_len,
            fs_encoding=fs_encoding,
            check_reserved=check_reserved,
            platform_max_len=_DEFAULT_MAX_FILENAME_LEN,
            platform=platform,
        )

    def _validate_reserved_keywords(self, name: str) -> None:
        if not self._check_reserved:
            return

        root_name = self.__extract_root_name(name)
        if self._is_reserved_keyword(root_name.upper()):
            raise ReservedNameError(
                f"'{root_name}' is a reserved name",
                reusable_name=False,
                reserved_name=root_name,
                platform=self.platform,
            )

    @staticmethod
    def __extract_root_name(path: str) -> str:
        return os.path.splitext(os.path.basename(path))[0]

    def validate_abspath(self, value: str) -> None:
        """Check a given abspath in the form of a str."""
        err = ValidationError(
            description=f"found an absolute path ({value}), expected a filename",
            platform=self.platform,
            reason=ErrorReason.FOUND_ABS_PATH,
        )

        if self._is_windows(include_universal=True):
            if ntpath.isabs(value):
                raise err

        if posixpath.isabs(value):
            raise err

    def validate(self, value: PathType) -> None:
        """Validate a candidate file name."""
        validate_pathtype(
            value, allow_whitespaces=not self._is_windows(include_universal=True)
        )

        unicode_filename = to_str(value)
        byte_ct = len(unicode_filename.encode(self._fs_encoding))

        self.validate_abspath(unicode_filename)

        err_kwargs = {
            "reason": ErrorReason.INVALID_LENGTH,
            "platform": self.platform,
            "fs_encoding": self._fs_encoding,
        }
        if byte_ct > self.max_len:
            raise ValidationError(
                [
                    f"filename is too long: expected<={self.max_len:d} bytes, "
                    f"actual={byte_ct:d} bytes"
                ],
                **err_kwargs,
            )
        if byte_ct < self.min_len:
            raise ValidationError(
                [
                    f"filename is too short: expected>={self.min_len:d} bytes, "
                    f"actual={byte_ct:d} bytes"
                ],
                **err_kwargs,
            )

        self._validate_reserved_keywords(unicode_filename)

        if self._is_windows(include_universal=True):
            self.__validate_win_filename(unicode_filename)
        else:
            self.__validate_unix_filename(unicode_filename)

    def __validate_unix_filename(self, unicode_filename: str) -> None:
        match = RE_INVALID_FILENAME.findall(unicode_filename)
        if match:
            raise InvalidCharError(
                INVALID_CHAR_ERR_MSG_TMPL.format(
                    invalid=findall_to_str(match), value=repr(unicode_filename)
                )
            )

    def __validate_win_filename(self, unicode_filename: str) -> None:
        match = _RE_INVALID_WIN_FILENAME.findall(unicode_filename)
        if match:
            raise InvalidCharError(
                INVALID_CHAR_ERR_MSG_TMPL.format(
                    invalid=findall_to_str(match), value=repr(unicode_filename)
                ),
                platform=Platform.WINDOWS,
            )

        if unicode_filename in (".", ".."):
            return

        kb_2829981_err_tmpl = "{}. Refer: https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/file-folder-name-whitespace-characters"  # noqa: E501  # pylint: disable=line-too-long

        if unicode_filename[-1] in (" ", "."):
            raise InvalidCharError(
                INVALID_CHAR_ERR_MSG_TMPL.format(
                    invalid=re.escape(unicode_filename[-1]), value=repr(unicode_filename)
                ),
                platform=Platform.WINDOWS,
                description=kb_2829981_err_tmpl.format(
                    "Do not end a file or directory name with a space or a period"
                ),
            )

        if unicode_filename[0] in (" "):
            raise InvalidCharError(
                INVALID_CHAR_ERR_MSG_TMPL.format(
                    invalid=re.escape(unicode_filename[0]), value=repr(unicode_filename)
                ),
                platform=Platform.WINDOWS,
                description=kb_2829981_err_tmpl.format(
                    "Do not start a file or directory name with a space"
                ),
            )


# - NAME VALIDATION LOGIC & MIT LICENSED SECTION ENDS HERE
#
#######################################################


class BasicCommandDelimiter:
    """
    Used to more cleanly separate one command in a run from another.

    Stripped down version of the one in mewbot.tools.terminal.
    This script is intended to be purely standalone.
    """

    tool_name: str
    delim_char: str

    def __init__(self, tool_name: str, delim_char: str = "=") -> None:
        """
        Supplied with the name of the tool and the deliminator char to create a display.

        :param delim_char: This will fill the line below and above the tool run
        :param tool_name: The name of the tool which will be run
        """
        self.tool_name = tool_name
        self.delim_char = delim_char

    @property
    def terminal_width(self) -> int:
        """
        Recalculated live in case the terminal changes sizes between calls.

        Fallback is to assume 80 char wide - which seems a reasonable minimum for terminal size.
        :return: int terminal width
        """
        return shutil.get_terminal_size()[0]

    def __enter__(self) -> None:
        """Print the welcome message."""

        trailing_dash_count = min(80, self.terminal_width) - 6 - len(self.tool_name)
        sys.stdout.write(
            self.delim_char * 4
            + " "
            + self.tool_name
            + " "
            + self.delim_char * trailing_dash_count
            + "\n"
        )

    sys.stdout.flush()

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        """Print the exit message."""
        # https://stackoverflow.com/questions/18398672/re-raising-an-exception-in-a-context-handler
        if exc_type:
            return False

        sys.stdout.write("\n")
        sys.stdout.flush()

        return True


#######################################################

#######################################################
#
# - MAIN PROGRAM


def main(venv_args: argparse.Namespace) -> bool:
    """Automate the process of generating a venv for mewbot dev work."""

    # 0 - Validate input
    with BasicCommandDelimiter(tool_name="0 - Validating Input"):
        venv_path = _validate_input(venv_args.base_folder, venv_args.venv_name)

        # egg-info folders seem to be generated using an install from setup.py.
        # Annoying, removing them breaks the pip they were installed from.
        # Instead, they can be moved to elsewhere in the path of the venv we're building
        # But, for sanity, we need there not to be egg-info folders in the build directory
        # (this script will, eventually, move them somewhere sensible)
        bad_egg_info_paths = _check_for_egg_info_folders(
            src_path=SRC_PATH, plugins_path=MEWBOT_PLUGINS_DIR
        )
        assert not bad_egg_info_paths, (
            f"egg_info folders detected at {bad_egg_info_paths} - please remove them. "
            f"Failure to do so may result in a non-functional python install elsewhere on "
            f"the system."
        )

    # 1 - Build Venv
    with BasicCommandDelimiter(tool_name="1 - Building Venv"):
        _build_venv(venv_path)

    # 2 - Validate venv
    with BasicCommandDelimiter(tool_name="2 - Validate Venv"):
        activation_path = _validate_venv(venv_path)

    # 2.5 - Change environmental variables so we're using the venv as default python
    #       This mirrors the actual process of activating a venv
    os.environ["VIRTUAL_ENV"] = venv_path
    os.environ["PATH"] = f"\"{os.path.join(venv_path, 'Scripts')}\";{os.environ['PATH']}"

    # windows default
    venv_python_path = os.path.join(venv_path, "Scripts", "python.exe")
    # unix default
    if not os.path.exists(venv_python_path):
        venv_python_path = os.path.join(venv_path, "bin", "python")
    if not os.path.exists(venv_python_path):
        raise NotImplementedError(
            f"venv python not found at \"{os.path.join(venv_path, 'Scripts', 'python.exe')}\""
            f" or \"{os.path.join(venv_path, 'bin', 'python')}\". "
            "Please add a new case to this code."
        )

    # 3 - Update venv pip
    with BasicCommandDelimiter(tool_name="3 - Update venv pip"):
        # Using the venv path directly reduces the chance of polluting the main python install
        # (theoretically eliminates it. Should not be needed, but good as a backup measure)
        subprocess.run(
            [
                venv_python_path,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
            ],
            shell=SHELL_NEEDED,  # nosec B602
            check=True,
        )

    # 4 - Install all deps into the venv using the install_deps script
    with BasicCommandDelimiter(tool_name="4 - Install all deps into the venv"):
        _install_all_deps(
            mewbot_repo_path=MEWBOT_REPO_PATH, venv_python_path=venv_python_path
        )

    # 5 - install the plugins
    with BasicCommandDelimiter(tool_name="5 - install the plugins"):
        _install_all_plugins(
            mewbot_repo_path=MEWBOT_REPO_PATH,
            venv_python_path=venv_python_path,
            mewbot_plugins_dir=MEWBOT_PLUGINS_DIR,
        )

    # 6 - Wipe the placeholder installs for the mewbot submodules
    #     These have installed from pypi and are no longer needed
    with BasicCommandDelimiter(tool_name="6 - Wipe pypi placeholder installs"):
        _wipe_pypi_installs(venv_python_path)

    # 7 - Install the sub-modules in editable form
    with BasicCommandDelimiter(tool_name="7 - Install the sub-modules in editable form"):
        _install_local_submodules(venv_python_path)

    # 8 - Move the egg-info folders somewhere sensible
    with BasicCommandDelimiter(tool_name="8 - Rehome egg-info folders"):
        _rehome_egg_info_folders(
            src_path=SRC_PATH, plugins_path=MEWBOT_PLUGINS_DIR, venv_path=venv_path
        )

    # 9 - Run tests on the venv
    with BasicCommandDelimiter(tool_name="9 - Run tests on the venv"):
        _test_build_venv(venv_python_path)

    # 10 - Tell the user we're done
    if sys_platform.system().lower() != "windows":
        print(f'\n\nvenv prepared - activate via "source {activation_path}"')
    else:
        print(f'\n\nvenv prepared - activate via "{activation_path}"')

    # If we reach this point, everything should be okay
    return True


def _validate_input(base_folder: str, venv_name: str) -> str:
    """
    Confirm that the input from the command line is valid under the set criteria.

    E.g. _hopefully_ not going to cause a really embarrassing security hole.
    :return:
    """
    base_folder = os.path.abspath(base_folder)
    if not os.path.exists(base_folder):
        raise NotImplementedError(f"{base_folder = } must exist.")

    FileNameValidator().validate(venv_name)

    venv_path = os.path.join(base_folder, venv_name)
    assert not os.path.exists(
        venv_path
    ), f"Cannot generate venv at {venv_path = } - there is something there."

    # With the reserved names eliminated ... restrict to ascii
    hopefully_safe_regex = r"^[0-9A-Za-z_\-]+$"
    assert re.match(
        hopefully_safe_regex, venv_name
    ), f'venv name must match regex "{hopefully_safe_regex}"'

    return venv_path


def _check_for_egg_info_folders(src_path: str, plugins_path: str) -> list[str]:
    """
    As part of the setup.py run process some egg-info folders are generated - check for them.

    If they exist, they will be overwritten by this process.
    Which may break other things.
    (In particular, the python install which generated them may no longer be able to register
    mewbot as a valid, editable package).
    Our solution, to prevent conflicts (and to allow mypy to work - as they register as folders
    without .py files to it, which causes it to fail) is to (eventually) move them into the root
    folder of the venv for which they have been created - here the venv we're generating.

    :param src_path:
    :param plugins_path:
    :return:
    """
    print(f"Checking {src_path} and {plugins_path} for egg-info folders.")

    bad_paths: list[str] = []

    for cand_path in [src_path, plugins_path]:
        obj_list = os.listdir(cand_path)

        for obj_name in obj_list:
            cand_obj = os.path.join(cand_path, obj_name)

            if not os.path.isdir(cand_obj):
                continue

            if cand_obj.endswith(".egg-info"):
                bad_paths.append(cand_obj)

    return bad_paths


def _build_venv(venv_path: str) -> None:
    """
    Execute the commands needed to build the venv.

    :return:
    """
    current_exec = sys.executable
    print(f"Building venv using {current_exec = } in {venv_path = }")
    subprocess.run(
        [current_exec, "-m", "venv", venv_path], check=True, shell=SHELL_NEEDED  # nosec B602
    )


def _validate_venv(venv_path: str) -> str:
    """
    Validate the venv and return the path to the activation script.

    :param venv_path:
    :return:
    """
    if sys_platform.system() != "Windows":
        activation_path = os.path.join(venv_path, "bin", "activate")
    else:
        activation_path = os.path.join(venv_path, "Scripts", "activate")

    assert os.path.isfile(activation_path), f"{activation_path = } not found in venv"
    print(f'venv created - to activate use activation_path = "{activation_path}"')

    if sys_platform.system().lower() != "windows":
        # Cannot actually run this check on a linux like environment
        return activation_path
    subprocess.run(
        [
            activation_path,
        ],
        check=True,
        shell=SHELL_NEEDED,  # nosec B602
    )

    return activation_path


def _install_all_deps(mewbot_repo_path: str, venv_python_path: str) -> None:
    """
    Install all deps in the venv.

    :param mewbot_repo_path:
    :param venv_python_path: Path to the python executable in the venv
    :return:
    """
    os.chdir(mewbot_repo_path)
    # This still permits the script to run - despite apparently failing
    subprocess.run([venv_python_path, "setup.py", "develop"], check=False)
    subprocess.run(
        [venv_python_path, "-m", "mewbot.tools.install_deps"],
        check=True,
        shell=SHELL_NEEDED,  # nosec B602
    )

    print(SEPERATOR)
    print("Pip list in current state")
    subprocess.run(
        [venv_python_path, "-m", "pip", "list"], check=True, shell=SHELL_NEEDED  # nosec B602
    )
    print(SEPERATOR)


def _install_all_plugins(
    mewbot_plugins_dir: str, venv_python_path: str, mewbot_repo_path: str
) -> None:
    """
    Install all the plugins in the venv.

    :param mewbot_plugins_dir:
    :param venv_python_path:
    :param mewbot_repo_path:
    :return:
    """
    for plugin_name in os.listdir(mewbot_plugins_dir):
        print(f"About to attempt to install {plugin_name = }")

        # 5.1 - Generate a path to the folder of the plugin subdir
        plugin_dir = os.path.join(mewbot_plugins_dir, plugin_name)

        # 5.2 - Validate that the folder exists
        assert os.path.isdir(plugin_dir), f"{plugin_dir = } could not be found"

        # 5.3 - Check for setup.py - without if, we cannot install
        plugin_setup_py_file = os.path.join(plugin_dir, "setup.py")

        if not os.path.isfile(plugin_setup_py_file):
            print(f"{plugin_setup_py_file = } did not exist - skipping.")
            continue

        # 5.4 - cd into the directory
        os.chdir(plugin_dir)

        # 5.5 - execute
        try:
            subprocess.run(
                [venv_python_path, "setup.py", "develop"],
                check=True,
                shell=SHELL_NEEDED,  # nosec B602
            )
        except subprocess.CalledProcessError:
            print(f"Cannot install {plugin_name} - bad setup.py?")

    os.chdir(mewbot_repo_path)

    print(SEPERATOR)
    print("Pip list in current state")
    subprocess.run(
        [venv_python_path, "-m", "pip", "list"], check=True, shell=SHELL_NEEDED  # nosec B602
    )
    print(SEPERATOR)


def _wipe_pypi_installs(venv_python_path: str) -> None:
    """
    Some mewbot modules will have installed from pypi - remove them.

    We want all the mewbot modules to be the locally editable versions.

    :param venv_python_path:
    :return:
    """
    # Not all of these should be installed, but the methodology might have changed.
    for module_name in ["mewbot-api", "mewbot-core", "mewbot-io", "mewbot-test"]:
        subprocess.run(
            [
                venv_python_path,
                "-m",
                "pip",
                "uninstall",
                "-y",
                module_name,
            ],
            check=True,
            shell=SHELL_NEEDED,  # nosec B602
        )


def _install_local_submodules(venv_python_path: str) -> None:
    """
    Install locally editable versions of the submodules.

    :param venv_python_path: Path to the python interpreter in the venv
    :return:
    """

    for module_name in ["core", "api", "io", "test"]:
        subprocess.run(
            [venv_python_path, "setup.py", module_name, "develop"],
            check=True,
            shell=SHELL_NEEDED,  # nosec B602
        )

    print(SEPERATOR)


def _rehome_egg_info_folders(src_path: str, plugins_path: str, venv_path: str) -> bool:
    """
    As part of the setup.py run process some egg-info folders are generated - move them.

    They should, at this point, exist.
    They can be moved directly into the venv.

    :param src_path:
    :param plugins_path:
    :return:
    """
    # Deal with the src folder
    _do_egg_info_move(src_path, venv_path)

    # Deal with the plugins folder
    plugins_top_level = os.listdir(plugins_path)
    for plugin_folder in plugins_top_level:
        plugin_src_path = os.path.join(plugins_path, plugin_folder, "src")
        if not os.path.isdir(plugin_src_path):
            print(f"{plugin_src_path = } in {plugin_folder = } did not exist.")
            continue

        _do_egg_info_move(plugin_src_path, venv_path)

    return True


def _do_egg_info_move(src_folder_path: str, venv_path: str) -> None:
    """
    Actually move the egg_info folder.

    Pip will report the location of the editable files incorrectly after this.
    However, testing has shown they still import from the correct location.
    Somehow.
    """
    obj_list = os.listdir(src_folder_path)

    for obj_name in obj_list:
        cand_obj = os.path.join(src_folder_path, obj_name)

        if not os.path.isdir(cand_obj):
            continue

        if not cand_obj.endswith(".egg-info"):
            continue

        new_egg_info_path = os.path.join(venv_path, obj_name)

        print(f"Moving {cand_obj} to {new_egg_info_path}")
        shutil.move(src=cand_obj, dst=new_egg_info_path)


def _test_build_venv(venv_python_path: str) -> None:
    """
    Install locally editable versions of the submodules.

    :param venv_python_path: Path to activate the venv.
    :return:
    """
    subprocess.run(
        [
            venv_python_path,
            __file__,
            "placeholder",
            "not_sure_why_needed",
            "-t",
        ],
        check=True,
        shell=SHELL_NEEDED,  # nosec B602
    )


#
#######################################################


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("base_folder", default=os.getcwd())
    parser.add_argument("venv_name", default="test_mewbot_venv")

    parsed_args = parser.parse_args()

    sys.exit(0 if main(parsed_args) else 1)
