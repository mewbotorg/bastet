<!--
SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: BSD-2-Clause
-->

# MyPy

MyPy is a python type analyser/linter.

mypy enforces the requirement for type annotations, and also performs type-checking
based on those annotations and resolvable constants.

## MyPy Failure Modes

The most common issue people will encounter is caused by empty directories
left behind when changing branches. This will only occur locally, as CI
runs use fresh filesystems.

```
(mewbot_venv) C:\mewbot_dev\mewbot> sh tools/lint

Black (Formatter)
=================
All done! ✨ 🍰 ✨
36 files left unchanged.

Flake8
======

MyPy (type checker)
===================
There are no .py[i] files in directory 'C:\mewbot_dev\mewbot\plugins\mewbot-client_for_reddit\tests'

[...clipped...]
```

The solution here is to confirm that the directory is in fact empty, and then
remove it from your copy.

Further information on this issue can be found in https://github.com/mewbotorg/mewbot/issues/180.
