# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

import codecs
import os
import setuptools
from pathlib import Path


# From https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
# (the first solution seemed a pretty sensible option for a non-namespaced package)
def read(rel_path):
    """
    Read a file based on it's relatvie path.

    :param rel_path:
    :return:
    """
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    """
    Get a version string looking object from a relative path

    :param rel_path:
    :return:
    """
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


# Finding the right README.md and inheriting the mewbot licence
current_file = Path(__file__)
root_repo_dir = current_file.parents[2]
assert root_repo_dir.exists()

with open(current_file.parent.joinpath("README.md"), "r", encoding="utf-8") as rmf:
    long_description = rmf.read()

with open(current_file.parent.joinpath("requirements.txt"), "r", encoding="utf-8") as rf:
    requirements = list(x for x in rf.read().splitlines(False) if x and not x.startswith("#"))

# Reading the LICENSE file and parsing the results
# LICENSE file should contain a symlink to the licence in the LICENSES folder
# Held in the root of the repo

with Path("LICENSE.md").open("r", encoding="utf-8") as license_file:
    license_text = license_file.read()

cand_full_license_path = Path(license_text.strip())

# We have a symlink to the license - read it
if cand_full_license_path.exists():
    true_license_ident = os.path.splitext(license_text.split(r"/")[-1])[0]

    with cand_full_license_path.open("r", encoding="utf-8") as true_license_file:
        true_license_text = true_license_file.read()

else:
    raise NotImplementedError(
        f"Cannot programmatically determine license_ident from license. "
        f"Link '{license_text}' may be invalid. "
        "If you have added your own license in the LICENSE.md file, please move it to the "
        "LICENSES folder in the root of the repo and replace the LICENSE.md file wih a symlink "
        "to that resource."
    )

# There are a number of bits of special sauce in this call
# - You can fill it out manually - for your project
# - You can copy this and make the appropriate changes
# - Or you can run "mewbot make_namespace_plugin" - and follow the onscreen instructions.
#   Which should take care of most of the fiddly bits for you.
setuptools.setup(
    name="mewbot_dev_tools",
    version=get_version("src/mewbot_dev_tools/__init__.py"),
    author="Alex Cameron",
    install_requires=requirements,
    author_email="mewbot@quicksilver.london",
    description="Mewbot Developers Tools (https://github.com/mewbotorg)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mewler/mewbot",
    project_urls={
        "Bug Tracker": "https://github.com/mewler/mewbot/issues",
    },
    license=true_license_text,
    classifiers=[
        "Programming Language :: Python :: 3",
        f"License :: OSI Approved :: {true_license_ident}",
        "Framework :: mewbot",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_namespace_packages(where="src", include=["mewbot.*"]),
    # see https://packaging.python.org/en/latest/specifications/entry-points/
    entry_points={
        "console_scripts": [
            "mewbot-lint=mewbot_dev_tools.console_scripts.mewbot_lint:main",
            "mewbot-reuse=mewbot_dev_tools.console_scripts.mewbot_reuse:main",
            "mewbot-test=mewbot_dev_tools.console_scripts.mewbot_test:main",
            "mewbot-security-analysis="
            "mewbot_dev_tools.console_scripts.mewbot_security_analysis:main",
            "mewbot-preflight=mewbot_dev_tools.console_scripts.mewbot_preflight:main",
        ]
    },
    python_requires=">=3.10",  # Might be relaxed later
)
