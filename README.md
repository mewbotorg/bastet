<!--
SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: BSD-2-Clause
-->

# Bastet

Bastet, the cat god, takes all of our test and puts them in one basket.

TODO: Write description.

## Purpose

While developing mewbot we built a number of tools to assist with development.
This mostly consist of tool chains for

 - automatically reformatting code
 - running the linters, include type checking, style guides, and security auditing

The aim of these tools is that, if you run them on a code base, you should
end up with something which conforms to MewBot's guidelines.

## Usage

The dev tools uses path based auto-discovery to locate the relevant code.
Python modules will be discovered in `./src` and `./plugins/*/src`.
Test cases will be discovered in `./tests` and `./plugins/*/tests`.

If your project is in that `src-dir` layout, you can install the dev tools
and then run any of the toolchains.

```sh
pip install bastet

bastet --help
bastet format # Automated formatting, using black/isort/ruff
bastet lint   # Code style and type linting, using black/flake8/ruff/mypy/pylint
bastet audit  # Audit and security checks, using bandit
```

We also recommend that you set up `mewbot-prefilght` as a
[pre-commit or pre-push hook](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks).

## Default Configuration

TODO: Write this section

The recommended `pyproject.toml` for starter projects can be found in

## Advance Config and Debug

You can check what the configuration is doing with `--debug` the debug flag on
a run, or by running `python -m bastet.config` to just run the configuration steps.

## Integrating with CI

TODO: Write this section

## Integrating with Sonar

TODO: Write this section

## Extending with Custom Tools

TODO: Write this section
