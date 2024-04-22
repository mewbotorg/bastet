# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

"""
Reporting system for Bastet.

The reporting section of Bastet controls how the information
obtained from tools is reported to the user. Each Reporter
selected by the configuration gets give the raw and processed
(status, annotations, and exceptions) output from each tool,
along with a full run summary, and will output a formatted report
for machine or human consumption.
"""

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable, Awaitable, Callable
from types import TracebackType
from typing import Any, BinaryIO, NamedTuple, Self

import abc
import logging
import subprocess  # nosec: B404
from asyncio import StreamReader, Task, gather, get_running_loop

from bastet.tools import Annotation, Tool, ToolError, ToolResults


class ProcessPipeError(subprocess.SubprocessError):
    """
    Exception for subprocesses not having stdout/stderr pipes.
    """

    def __init__(self) -> None:
        super().__init__("Error creating pipes in subprocess")


class ReportStreams(NamedTuple):
    """
    The streams/sinks a ReportInstance is requesting for a Tool's output.

    :param stdout:
        An async binary stream reader, or writable binary IO.
        It will be fed a clone of the tools standard output stream.
    :param stderr:
        An async binary stream reader, or writable binary IO.
        It will be fed a clone of the tools standard error stream.
    :param annotation_sink:
        An async callback that will be called with each annotation
        the tool emits.
    :param exception_sink:
        An async callback that will be called with each exception
        the tool emits or is successfully caught by the runner.
    """

    stdout: StreamReader | BinaryIO | None
    stderr: StreamReader | BinaryIO | None
    annotation_sink: Callable[[Annotation], Awaitable[None]] | None
    exception_sink: Callable[[ToolError], Awaitable[None]] | None


class ReportHandler:
    """
    The report handler is responsible for creating Tool Reports and using them for summaries.
    """

    logger: logging.Logger
    reporters: list[Reporter]

    def __init__(self, logger: logging.Logger, *reporter: Reporter) -> None:
        """
        The report handler is responsible for creating Tool Reports and using them for summaries.
        """

        self.logger = logger
        self.reporters = list(reporter)

    async def __aenter__(self) -> Self:
        """
        No-op aenter method to start report collection.
        """

        self.logger.info("Entering reporter handler")
        return self

    async def report(self, tool: Tool) -> ToolReport:
        """
        Create the report aggregator for a specific tool.
        """

        self.logger.info("Creating reporter instances for %s", tool)
        reporters = (reporter.create(tool) for reporter in self.reporters)

        return ToolReport(tool, *(x for x in await gather(*reporters) if x))

    async def summarise(self, results: ToolResults) -> None:
        """
        Calls the summarise function on each Reporter.
        """

        await gather(*(reporter.summarise(results) for reporter in self.reporters))

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Close all the reporters.
        """

        await gather(*(reporter.close() for reporter in self.reporters))


class ToolReport:
    """
    Report/Results for running a tool.

    Handles:
     - Starting the reporter instances.
     - Processing the annotations and tool errors.
     - Streaming data to where it has been requested.
     - Recording the tool's results for the summary.
    """

    _tool: Tool
    _reporters: tuple[ReportInstance, ...]
    _stdout: StreamReader | None
    _stderr: StreamReader | None
    _tasks: list[Task[None]]
    _annotations: list[Annotation]
    _exceptions: list[ToolError]

    def __init__(self, tool: Tool, *reporters: ReportInstance) -> None:
        """
        Report/Results for running a tool.

        :param tool:
            The tool being called, used for the process_results() function.
        :param reporters:
            The reporting tools that we are using.
        """
        self._reporters = reporters
        self._tool = tool
        # Streams coming from the tools
        self._stdout = None
        self._stderr = None
        # Tasks being used to process the tool's output
        self._tasks = []
        # Record of the annotations and exceptions for the summary
        self._annotations = []
        self._exceptions = []

    def start(self, out: StreamReader, err: StreamReader) -> ToolReport:
        """
        Starts up the reporting for a tool.

        :param out:
            The standard output stream from the Tool subprocess
        :param err:
            The standard error stream from the Tool subprocess
        """

        self._stdout = out
        self._stderr = err
        return self

    async def __aenter__(self) -> None:
        """
        Starts the report stream for this tool.

        Each reporter instance is started, and their requested streams
        combined into lists for each of the four stream types.
        Stdout is sent to the tool's process_results function in order
        to create the Annotation and Exceptions, which are in turn
        fed to the report handlers.
        """

        if self._stdout is None or self._stderr is None:
            raise ProcessPipeError

        loop = get_running_loop()

        # Collect all requested streams from reporters
        streams = await gather(*(reporter.start() for reporter in self._reporters))
        # Handle the case where no reporter does per-tool reports.
        streams.append(ReportStreams(None, None, None, None))
        # Organise them into lists for each type of stream
        stdout, stderr, annotation_handlers, exception_handlers = zip(*streams, strict=True)

        # Create the special stream for the tool's process_results function
        # to read the tool's stdout from.
        results_reader = StreamReader(loop=loop)

        # Create the stdout processing loop. This copies the stdout stream
        # from the subprocess to each of the reporters that requested it,
        # plus the tool's process_results function.
        stdout_task = mirror_pipe(self._stdout, results_reader, *filter(present, stdout))

        # Similar for standard error, but without the extra stream to the tool.
        stderr_task = mirror_pipe(self._stderr, *filter(present, stderr))

        # Set up the tool's process_results function, which generates Annotations and ToolErrors.
        note_source = self._annotate_tool(self._tool.process_results(results_reader))
        notes_task = self.mirror_notes(
            note_source,
            list(filter(present, annotation_handlers)),
            list(filter(present, exception_handlers)),
        )

        # Register the three operations as async tasks, and store them
        # to clean up in __aexit__.
        self._tasks = [
            loop.create_task(stdout_task),
            loop.create_task(stderr_task),
            loop.create_task(notes_task),
        ]

    async def _annotate_tool(
        self,
        source: AsyncIterable[Annotation | ToolError],
    ) -> AsyncIterable[Annotation | ToolError]:
        async for item in source:
            if isinstance(item, Annotation):
                item.tool = self._tool
            yield item

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Ensure that all reporter tasks have exited, and call end() on all reporters.
        """

        await gather(*self._tasks)
        await gather(*(reporter.end() for reporter in self._reporters))
        self._tasks = []
        self._reporters = ()

    async def mirror_notes(
        self,
        source: AsyncIterable[Annotation | ToolError],
        annotation_handlers: list[Callable[[Annotation], Awaitable[None]]],
        exception_handlers: list[Callable[[ToolError], Awaitable[None]]],
    ) -> None:
        """
        Copies notes and exceptions being generated from a tool into all reporters.

        Each ReportInstance that has provided and annotation sink or an
        exception sink will receive copies of each annotation or exception
        respectively. They are also added to this ToolReport's internal
        buffers, for use in summaries.
        """

        async for note in source:
            if isinstance(note, Annotation):
                self._annotations.append(note)
                await gather(*(sink(note) for sink in annotation_handlers))
            elif isinstance(note, ToolError):
                self._exceptions.append(note)
                await gather(*(sink(note) for sink in exception_handlers))
            else:
                raise TypeError

    @property
    def annotations(self) -> list[Annotation]:
        """
        All annotations emitted during the Tool.
        """
        return self._annotations

    @property
    def exceptions(self) -> list[ToolError]:
        """
        All exceptions raised during the Tool.
        """
        return self._exceptions


def present(x: Any) -> bool:  # noqa: ANN401 - intentional use of Any.
    """
    Filter function for 'is not None'.
    """

    return x is not None


async def mirror_pipe(pipe: StreamReader, *mirrors: BinaryIO | StreamReader) -> None:
    """
    Read a pipe from a subprocess into a buffer whilst mirroring it to another pipe.
    """

    sync_mirrors: set[BinaryIO] = {
        mirror for mirror in mirrors if not isinstance(mirror, StreamReader)
    }
    async_mirrors: set[StreamReader] = {
        mirror for mirror in mirrors if isinstance(mirror, StreamReader)
    }

    # Whether the mirrored content ended with an end of line character.
    # If it does not, we will automatically append one to the outputs.
    # It defaults to true because an empty file/stream is considered to
    # end in a new line (the one what logically proceeds the file).
    eol = True

    while not pipe.at_eof():
        block = await pipe.read(4096)

        # Only do anything if content appeared.
        if not block:
            continue

        # Check whether we have an end of line
        eol = block.endswith(b"\n")

        # Forward the data
        for mirror in sync_mirrors:
            mirror.write(block)
            mirror.flush()
        for a_mirror in async_mirrors:
            a_mirror.feed_data(block)

    # Handle the case where the output did not end in an EOL
    trail = b"\n" if not eol else b""

    # We don't have a way to indicate an EOF to BinaryIO
    # short of closing it. As some systems may be using
    # the same output multiple times, we do not want to
    # close any underlying file handles.
    for mirror in sync_mirrors:
        mirror.write(trail)
        mirror.flush()

    # For the async pipes, we expect that they will work
    # out what to do about closing once they receive an
    # EOF marker.
    for a_mirror in async_mirrors:
        a_mirror.feed_data(trail)
        a_mirror.feed_eof()


class Reporter(abc.ABC):
    """
    Abstract Reporter class.

    The reporter is responsible for generating ReportInstances for tools
    being run, and/or for summarising the overall results at the end of
    a Bastet run.
    """

    @abc.abstractmethod
    async def create(self, tool: Tool) -> ReportInstance | None:
        """
        Creates a per-tool Report Instance for the given tool.

        This instance will then be able to request the raw streams,
        or the processed annotation and exceptions, from the Tools.
        """

    @abc.abstractmethod
    async def summarise(self, results: ToolResults) -> None:
        """
        Process and potentially output the results for the entire run.

        This is only expected to be called once, after all tools have
        been run. ReportInstances may not have exited at the time this
        is called. For cleanup operations, see the close method.
        """

    @abc.abstractmethod
    async def close(self) -> None:
        """
        Perform any shutdown processes.

        This function will be called after all tools are run,
        all ReportInstances have been ended, and all summarise
        methods have completed.
        """


class ReportInstance(abc.ABC):
    """
    Reporting instance for one specific Tool run.

    These objects will be created by a reporter for each individual tool.
    In the start call they present sinks for stdout, stderr, annotations,
    and exceptions, which the runner will feed the data into.

    When complete, end() will be called to allow the tool to perform
    any cleanup.
    """

    @abc.abstractmethod
    async def start(self) -> ReportStreams:
        """
        Perform any startup for this report, and pass the runner the requests streams.
        """

    @abc.abstractmethod
    async def end(self) -> None:
        """
        Perform any shutdown and cleanup actions for this report.
        """


__all__ = [
    "ReportHandler",
    "Reporter",
    "ToolReport",
    "ReportStreams",
    "ReportInstance",
]
