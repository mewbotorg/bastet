<!--
SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: BSD-2-Clause
-->

# mewbot-dev-tools

Tools to aid with mewbot development.

## Purpose

While developing mewbot we built a number of tools to assist with development.
This mostly consist of tool chains for
 - running the linters
 - building dev venvs (still forthcoming)
 - building the docs (still forthcoming)
 - gather and run the tests

The aim of these tools is that, if you run them on a code base, you should
end up with something which conforms to mewbot's guidelines.

## Usage

The dev tools uses path based auto-discovery to locate the relevant code.
Python modules will be discovered in `./src` and `./plugins/*/src`.
Test cases will be discovered in `./tests` and `./plugins/*/tests`.

If your project is in that `src-dir` layout, you can install the dev tools
and then run any of the toolchains.

```sh
pip install mewbot-dev-tools

mewbot-install-deps  # Install dependencies from discovered requirements.txt

mewbot-preflight # Run all of the toolchains below

mewbot-lint  # Code style and type linting, using black/flake/ruff/mypy/pylint
mewbot-reuse # Licensing information check, using reuse
mewbot-test  # Run discovered test suites, using pytest
mewbot-security-analysis  # Discover potential security bugs using badnit

mewbot-annotate  # Convert output data into GitHub annotations
```

We also recommend that you setup `mewbot-prefilght` as a
[pre-commit or pre-push hook](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks).

## Future Work

- Ability to opt-out for some linters in pyproject.toml
- Work to discover locations based on pyproject.toml

