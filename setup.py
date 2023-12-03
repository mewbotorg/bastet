# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import pathlib

import setuptools


def get_version():
    """
    Get a version string from environment variables, or the panthera package.

    :return:
    """

    if "RELEASE_VERSION" in os.environ:
        return os.environ["RELEASE_VERSION"]

    import panthera

    return panthera.__version__


# Finding the right README.md and inheriting the mewbot licence
root_repo_dir = pathlib.Path(__file__).parent

with (root_repo_dir / "README.md").open("r", encoding="utf-8") as rmf:
    long_description = rmf.read()

with (root_repo_dir / "requirements.txt").open("r", encoding="utf-8") as rf:
    requirements = list(x for x in rf.read().splitlines(False) if x and not x.startswith("#"))

# Reading the LICENSE file and parsing the results
# LICENSE file should contain a symlink to the licence in the LICENSES folder
# Held in the root of the repo
license_file = root_repo_dir / "LICENSE.md"
if license_file.is_symlink():
    license_identifier = license_file.readlink().stem
else:
    with license_file.open("r", encoding="utf-8") as license_data:
        license_file = root_repo_dir / license_data.read().strip()
    license_identifier = license_file.stem

# There are a number of bits of special sauce in this call
# - You can fill it out manually - for your project
# - You can copy this and make the appropriate changes
# - Or you can run "mewbot make_namespace_plugin" - and follow the onscreen instructions.
#   Which should take care of most of the fiddly bits for you.
setuptools.setup(
    name="panthera",
    version=get_version(),
    python_requires=">=3.10",
    install_requires=requirements,

    author="MewBot Org",
    author_email="mewbot@quicksilver.london",
    maintainer="MewBot Org",
    maintainer_email="mewbot@quicksilver.london",

    description="Panthera Python Developers Tools (https://github.com/mewbotorg/panthera)",
    long_description=long_description,
    long_description_content_type="text/markdown",

    url="https://github.com/mewler/mewbot",
    project_urls={
        "Bug Tracker": "https://github.com/mewler/mewbot/issues",
    },

    license=license_identifier,
    license_file=str(license_file.absolute()),

    package_dir={"": "src"},
    package_data={"": ["py.typed"]},
    # see https://packaging.python.org/en/latest/specifications/entry-points/
    entry_points={
        "console_scripts": [
            "mewbot-lint=panthera.lint.__main__:main",
            "mewbot-reuse=panthera.format.reuse:main",
            "mewbot-test=panthera.test.__main__:main",
            "mewbot-security-analysis=panthera.audit.__main__:main",
            "mewbot-preflight=panthera.__main__:main",
            "mewbot-install-deps=panthera.dev.install_deps:main",
            "mewbot-annotate=panthera.annotation:main",
        ]
    },

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",

        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",

        f"License :: OSI Approved :: {license_identifier}",
        "Operating System :: OS Independent",
    ],
)
