<!--
SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: BSD-2-Clause
-->

# Bastet

> Bastet, the cat god, takes all of our tests and puts them in one basket.

Bastet is another attempt to simplify linting and testing python projects.
It runs a range of linting tools, parses the output, and outputs reports
in different formats based on the use case.

The aim of these tools is that, if you run them on a code base, you should
end up with something which conforms to your organisations style guidelines,
and passes a variety of 

## Functionality

While developing mewbot we built a number of tools to assist with development.

This mostly consist of tool chains for:

 - Automatically reformatting code.
 - Managing license / copyright information. 
 - Running static analysis tooling.
 - Checking the code base against style requirements.
 - Running unit tests.

And it can output in a variety of ways:

 - Simple lists of issues for local development.
 - CI output format for GitHub workflows
 - Reports for ingestion by Sonar.

## Usage

The dev tools uses path based auto-discovery to locate the relevant code.
Python modules will be discovered in folders called `src` and `test`
which are not exclude by version control.

If your project is in that `src-dir` layout, you can install `bastet`
and then run any of the toolchains.

```sh
pip install bastet

# Runs all the tools
bastet

# You can also run just some tools or sections
bastet --help
bastet --skip format pylint
```

We also recommend that you set up `bastet` as a
[pre-commit or pre-push hook](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks).

## Configuration

The default unconfirmed mode of Bastet is to run all of its tools (be they
code formatting, linting, or auditing) and outputting a list of issues.

The [recommended `pyproject.toml`](examples/pyproject.toml) to set up your
project can be found in the `examples` folder. It enables all of the `ruff`
linting rules, excluding a few which conflict with each other.
It also disables the `black` and `isort` formatting tools, which `ruff`
provides an implementation of.

### Advance Config and Debug

You can check what the configuration is doing with `--debug` the debug flag on
a run, or by running `python -m bastet.config` to just run the configuration steps.

### Integration with Sonar

Using the `sonar` reporter will output a number of files into `reports`
for Sonar to ingest.

Ensure that Sonar is above to read the output from Bastet's run in your CI setup,
and then configure the following properties in Sonar's admin or your
`sonar-project.properties` file:

```properties
sonar.python.coverage.reportPaths=reports/coverage.xml
sonar.python.xunit.reportPaths=reports/junit-*.xml
sonar.python.ruff.reportPaths=reports/ruff.txt
sonar.python.pylint.reportPaths=reports/pylint.txt
```

### Integration with Gitlab

Bastet can produce up to three reports that GitLab can directly integrate into
merge requests (code quality, test results, and coverage) using the `gitlab`
reporter. A sample CI stage can be found in [`examples/gitlab-ci.yml`](examples/gitlab-ci.yml).
