# SPDX-FileCopyrightText: 2023 - 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Runs the Bastet toolchain based on the configuration.

This takes in the configuration, and a report handler,
and gathers all the permitted domains and tools.
These are run, with the outputs sent to the reporting
handler.
"""

from __future__ import annotations as _future_annotations

import asyncio
import os
import subprocess  # nosec

from .config import BastetConfiguration
from .reporting import ReportHandler
from .tools import (
    Annotation,
    Tool,
    ToolDomain,
    ToolError,
    ToolResults,
    get_available_tools,
)


class BastetRunner:  # pylint: disable=too-few-public-methods
    """
    Runs the Bastet toolchain based on the configuration.

    This takes in the configuration, and a report handler,
    and gathers all the permitted domains and tools.
    These are run, with the outputs sent to the reporting
    handler.
    """

    reporter: ReportHandler
    config: BastetConfiguration
    timeout: int = 30

    def __init__(self, config: BastetConfiguration, reporter: ReportHandler) -> None:
        """
        Runs the Bastet toolchain based on the configuration.

        :param config:
            Combined file and command line configuration.
        :param reporter:
            The selected reporting systems.
        """

        self.reporter = reporter
        self.config = config

    async def run(self) -> ToolResults:
        """
        Run the tool chain, calling each selected tool and processing the results.

        This function will iterate through the selected domains
        """

        # Ensure the reporting location exists.
        self.config.folders.report_path.mkdir(parents=True, exist_ok=True)

        results = ToolResults()

        domain: ToolDomain
        async with self.reporter:
            for domain in gather_domains(self.config):
                tools = gather_tools(domain, self.config)

                for tool in tools:
                    exit_code, annotations, exceptions = await self._run_tool(tool)
                    await results.record(tool, annotations, exceptions, exit_code)

        await self.reporter.summarise(results)

        return results

    async def _run_tool(
        self,
        tool: Tool,
    ) -> tuple[int, list[Annotation], list[ToolError]]:
        """
        Helper function to run an external program as a check.

        The output of the tool is copied to the tool's own process_results
        function, and to all reporters that request it. The reports can
        also request the standard error stream, and/or the annotations being
        produced by the process_results function.

        :param tool:
            The tool definition to run.
        """

        # In some edge cases, like configuring pytest, the reporting toolchain
        # may reconfigure the tool slightly. Thus, we create the report before
        # fetching the command.
        reporter = await self.reporter.report(tool)

        command = tool.get_command()

        env = os.environ.copy()
        env.update(tool.get_environment())

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

        return return_code, reporter.annotations, reporter.exceptions


def gather_domains(config: BastetConfiguration) -> list[ToolDomain]:
    """
    Select all Domains we are going to run in this Bastet run.

    :param config:
        The configuration indicating what domains to skip.
    """
    return [d for d in ToolDomain if d not in config.skip_domains]


def gather_tools(domain: ToolDomain, config: BastetConfiguration) -> list[Tool]:
    """
    Select all Tools we are going to run in this Bastet run.

    This works by:
     - Finding all available tools on the system.
     - Checking which are used for the selected domain.
     - Removing any disabled by the configuration.

    :param domain:
        The tool domain to select tools for.
    :param config:
        The configuration options for this bastet run.
    """

    return [
        tool(domain, config.folders)
        for tool in get_available_tools()
        if tool.__name__.lower() not in config.skip_tools and domain in tool.domains()
    ]


__all__ = ["ReportHandler", "BastetRunner"]
