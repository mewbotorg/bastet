# SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import asyncio
import os
import pathlib
import subprocess  # nosec

from .config import PantheraConfiguration
from .reporting import ReportHandler
from .tools import (
    Annotation,
    Tool,
    ToolDomain,
    ToolError,
    ToolResults,
    get_available_tools,
)


class ToolRunner:
    """
    Support class for running a series of tools across the codebase.

    Each tool will be given the same set of folders, and can produce output
    to the console and/or 'annotations' indicating issues with the code.

    The behaviour of this class alters based whether it is being run in 'CI mode'.
    This mode disables all interactive and automated features of the toolchain,
    and instead outputs the state through a series of 'annotations', each one
    representing an issue the tools found.
    """

    reporter: ReportHandler
    config: PantheraConfiguration
    timeout: int = 30

    def __init__(self, reporter: ReportHandler, config: PantheraConfiguration) -> None:
        self.reporter = reporter
        self.config = config

    async def __call__(self, domains: list[ToolDomain]) -> ToolResults:
        # Ensure the reporting location exists.
        pathlib.Path("reports").mkdir(parents=True, exist_ok=True)

        results = ToolResults()

        async with self.reporter:
            for domain in domains:
                tools = self.gather_tools(domain, self.config)

                for tool in tools:
                    command, exit_code, annotations, exceptions = await self.run(tool)
                    await results.record(tool, annotations, exceptions, exit_code)

        await self.reporter.summarise(results)

        return results

    @staticmethod
    def gather_tools(domain: ToolDomain, config: PantheraConfiguration) -> list[Tool]:
        return [
            tool(domain, config.folders)
            for tool in get_available_tools()
            if tool.__name__.lower() not in config.skip_tools and domain in tool.domains()
        ]

    async def run(
        self,
        tool: Tool,
    ) -> tuple[list[str | pathlib.Path], int, list[Annotation], list[ToolError]]:
        """
        Helper function to run an external program as a check.

        The output of the command is made available in three different ways:
          - Output is written to reports/{tool name}.txt
          - Output and Error are returned to the caller
          - Error and Output are copied to the terminal.

        When in CI mode, we add a group header to collapse the output from each
        tool for ease of reading.

        :param tool: The tool definition to rune
        """

        # In some edge cases, like configuring pytest, the reporting toolchain
        # may reconfigure the tool slightly. Thus, we create the report before
        # fetching the command.
        reporter = await self.reporter.report(tool)

        env = tool.get_environment()
        command = tool.get_command()

        env = env.copy()
        env.update(os.environ)  # TODO: this is the wrong way around

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # MyPy validation trick -- ensure the pipes are defined (they will be).
        if not process.stdout or not process.stderr:
            error = f"pipes for process {tool.name} not created"
            raise subprocess.SubprocessError(error)

        async with reporter.start(process.stdout, process.stderr):
            # This is trimmed down version of subprocess.run().
            try:
                await asyncio.wait_for(process.wait(), timeout=self.timeout)
            except TimeoutError:
                process.kill()
                # run uses communicate() on windows. May be needed.
                # However, as we are running the pipes manually, it may not be.
                # Seems not to be
                await process.wait()
            # Re-raise all non-timeout exceptions.
            except Exception:
                process.kill()
                await process.wait()
                raise

        return_code = process.returncode
        return_code = return_code if return_code is not None else 1

        return command, return_code, reporter.annotations, reporter.exceptions


__all__ = ["ReportHandler", "ToolRunner"]
