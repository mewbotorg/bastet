<!--
SPDX-FileCopyrightText: 2021 - 2024 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing

Contributions to this project are welcome, whether minor updates to documentation or entirely new features.
This document outlines the technical and procedural requirements for your work to be included.
All contributions, in any form, must also confirm with the [code of conduct](CODE_OF_CONDUCT.md).

You can see all contributors, past and present, in the [contributors list](CONTRIBUTING.md).
This list is managed using the [AllContributors bot](https://allcontributors.org/docs/en/bot/overview).

> This document is a living document, and will adapt based on the project's needs.
> If some part of this document creates a hindrance, raise an issue explaining the problem.

## Scope: What Lives in this Repository?

MewBot's core provides simple interfaces for developing bot components and a system for loading and running them.
It attempts to do so with a minimum of third party dependencies.
Changes and additions here look to improve the framework of MewBot for developers and runners.

Adding new core functionality that requires additional dependencies needs special consideration,
as it increases both the security footprint and compatibility issues within the project.

When building new components, whether they are input/output modules or utilities for use in behaviours,
consider if they could be a stand-alone repository and package.
The MewBot team is happy to help set up these repositories in the GitHub group.

## Projects and Issues: What Needs Doing?

Issues are a fantastic way of keeping track of what work is needed and who is planning to do it.
You can find all the current initiatives in the projects tab; these show the current areas of focus.

If you are looking for a way to contribute to MewBot, this is a great place to start.
You can either find an existing issue to work on or bring your ideas to the table.
Everyone is welcome to open issues with concerns, thoughts, or suggestions;
make sure to check existing entries for relevant information and plans first.
The team may merge issues as we work towards a common solution, or issues may be closed
if they do not reflect the overall project vision.

Open issues are treated as a collaborative planning space and build an understanding of planned changes.
Discussion allows us to find overlap in both problems and solutions and ensure that any
changes will combine with other ongoing work.

If you want to start on a piece of work:
  find or create an issue describing the work;
  assign it to yourself; and get started.
If another user has the assignment, reach out to them and see if you can help;
coordination is the key to success in open source development.

## Licensing Policy

We ask that code created for the Mewbot project is transferred to the projects'
ownership; this is noted as the copyright being held by
> Mewbot Developers <mewbot@quicksilver.london>

BSD-2-Clause licenses are used for code, Creative Commons v4 for prose (documentation
and examples). 
For completeness with the [SPDX](https://spdx.dev/) spec,
files which have no meaningfully ownable content (generated lock files, gitignore files, etc.),
are marked with the Creative Commons Universal Public Domain license,
as per [the `reuse.software` recommendation](https://reuse.software/faq/#uncopyrightable).

## Code Style

Coding tackles the thorny problem of trying to express logical, computational concepts in a
human-readable and understandable manner. 
Our code style favours the human side.
We seek to find the balance between sections of code that are too large or dense to
comprehend and the problem of too many small pieces of code to understand at once.

Formatting is derived from Python's [PEP8](https://peps.python.org/pep-0008/) as implemented by
[Black](https://pypi.org/project/black/), with line lengths limited to 100 (instead of the traditional 80).

The linting toolchain uses
[Black](https://pypi.org/project/black/),
[Flake8](https://flake8.pycqa.org/en/latest/),
[mypy](http://www.mypy-lang.org/),
[pylint](https://pylint.pycqa.org/en/latest/), and
[pydocstyle](http://www.pydocstyle.org/en/stable/)
to promote best practices for expressing the logical constructs.

Expressing intent is the other key ingredient.
Name code elements (classes, functions, variables) based on what purpose they serve,
and try to organise code to convey the flow of logic.
If there is additional information, use single-line comments.

The "doc-block" at the top of class and functions should start with a quick summary of the purpose and intent.
This summary can be followed by any relevant commentary on the implementation,
such as links to decisions about the structure of the code and notes features that might not be obvious.

The use of comments to note problems or future fixes is discouraged, and merges containing them will not be approved.
Instead, create an issue to track the required change.

## Testing

Testing an application framework which primarily deals with network interactions is always a difficult problem.
The design of mewbot uses a number of components which communicate by passing dataclasses to each other.
This assists with testing by allowing us to craft inputs which can then be injected to produce verifiable outputs.

Tests are performed using the `pytest` testing framework, with tests located in the `tests` folder.
Merge requests should not reduce the overall test coverage of the framework, as calculated by Sonar

## Branches And Commits

The primary branch of this project is called 'mainline'.
It represents the total summation of approved code changes.
The tip of this branch will pass all linting and test stages.
Tested stable versions are marked with git tags; there is no 'stable' branch.

The mainline branch uses a 'semi-linear' branch history, with merge commits only being
used to indicate the start and end of each applied topic branch.
Rebasing code in topic branches is encouraged.

```shell
o - - - - -  o - -  o  (mainline)
 \          / \    /
  o--o--o--o   o--o (<topic 2>)
  (<topic 1>)
```

Each commit in the repo should represent a logical, testable change.
Ideally, they should also pass all linting and testing checks.
When a branch is in active development, this does not need to be strictly adhered to,
and you may wish to hold off on deciding on the commit order until the merge request.

Commit messages, like code elements, starts with a summary of the intent of the change,
and the full version can also include references to the issue(s) it solves and descriptions
of the functional details of the changes.

## Pull Requests: Getting Stuff Into The Project

Before you start work on a new feature, please check the issues to reduce the chance of
duplication of work. If there is not an issue for that work you are planning to do,
create one and describe your intent.
This issue my collect early feedback and suggestions that will help guide your work.

When a piece of work is ready for review (including feedback during development),
you can open a pull request on GitHub. As with code and commits,
the title and description of the request should describe intent and purpose first and foremost.

If the changes are based on an issue, you can invite people involved in the issue as reviewers.
GitHub also notifies the maintainers of all new pull requests.

Pull requests are where this policy primarily gets enforced.
The pull request template will outline the steps.
The reviewers and maintainers will work with you to ensure that your code and commit history are correct and concise.

## Reviewing Merge Requests: How to Give and Interpret Feedback

Reviews on merge requests should be submitted using GitHub's review feature.
Comments generally fall into four categories, but GitHub gives us no way to distinguish between them:
 - Praise: "This is good."
 - Question for the Author: "will this work if [condition]?"
 - Alternative method: "this might be better as a [language feature]."
 - Actual problem: "Because of [x], this change won't work for cute cats."

All four of these are suitable forms of feedback.
This list is not exhaustive but forms a good framework for communicating what you expect the requester to do.
When giving feedback of alternative methods or problems, include a clear description and example (pseudo)code or a link to documentation.

It is up to the reviewer (or a maintainer) to mark a conversation as resolved, not the merge requester.
An exception naturally applies to praise and other comments that do not need a response.
