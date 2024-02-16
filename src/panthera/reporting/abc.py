# SPDX-FileCopyrightText: 2024 Mewbot Developers <mewbot@quicksilver.london>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import AsyncIterable, Awaitable, Callable
from types import TracebackType
from typing import Any, BinaryIO, NamedTuple, Self

import abc
import logging
import subprocess  # nosec: B404
from asyncio import StreamReader, Task, gather, get_running_loop

from panthera.tools import Annotation, Tool, ToolError, ToolResults


class ProcessPipeError(subprocess.SubprocessError):
    def __init__(self) -> None:
        super().__init__("Error creating pipes in subprocess")


class ReportStreams(NamedTuple):
    stdout: StreamReader | BinaryIO | None
    stderr: StreamReader | BinaryIO | None
    annotation_sink: Callable[[Annotation], Awaitable[None]] | None
    exception_sink: Callable[[ToolError], Awaitable[None]] | None


class ReportHandler:
    logger: logging.Logger
    reporters: list[Reporter]

    def __init__(self, logger: logging.Logger, *reporter: Reporter) -> None:
        self.logger = logger
        self.reporters = list(reporter)

    async def __aenter__(self) -> Self:
        self.logger.info("Entering reporter handler")
        return self

    async def report(self, tool: Tool) -> ToolReport:
        self.logger.info("Creating reporter instances for %s", tool)
        reporters = (reporter.create(tool) for reporter in self.reporters)

        return ToolReport(tool, *(x for x in await gather(*reporters) if x))

    async def summarise(self, results: ToolResults) -> None:
        await gather(*(reporter.summarise(results) for reporter in self.reporters))

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await gather(*(reporter.close() for reporter in self.reporters))


class ToolReport:
    _tool: Tool
    _reporters: tuple[ReportInstance, ...]
    _stdout: StreamReader | None
    _stderr: StreamReader | None
    _tasks: list[Task[None]]
    _annotations: list[Annotation]
    _exceptions: list[ToolError]

    def __init__(self, tool: Tool, *reporters: ReportInstance) -> None:
        self._reporters = reporters
        self._tool = tool
        self._stdout = None
        self._stderr = None
        self._tasks = []
        self._annotations = []
        self._exceptions = []  # TODO: ensure this is used everywhere _annotations is.

    def start(self, out: StreamReader, err: StreamReader) -> ToolReport:
        self._stdout = out
        self._stderr = err
        return self

    async def __aenter__(self) -> None:
        if self._stdout is None or self._stderr is None:
            raise ProcessPipeError

        streams = await gather(*(reporter.start() for reporter in self._reporters))
        stdout, stderr, annotation_handlers, exception_handlers = zip(*streams, strict=True)
        loop = get_running_loop()

        results_reader = StreamReader(loop=loop)

        task = loop.create_task(
            mirror_pipe(self._stdout, results_reader, *filter(present, stdout)),
        )
        task.add_done_callback(lambda _: results_reader.feed_eof())

        note_source = self._tool.process_results(results_reader)

        self._tasks = [
            task,
            loop.create_task(mirror_pipe(self._stderr, *filter(present, stderr))),
            loop.create_task(
                self.mirror_notes(
                    note_source,
                    list(filter(present, annotation_handlers)),
                    list(filter(present, exception_handlers)),
                ),
            ),
        ]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await gather(*self._tasks)
        await gather(*(reporter.end() for reporter in self._reporters))

    async def mirror_notes(
        self,
        source: AsyncIterable[Annotation | ToolError],
        annotation_handlers: list[Callable[[Annotation], Awaitable[None]]],
        exception_handlers: list[Callable[[ToolError], Awaitable[None]]],
    ) -> None:
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
        return self._annotations

    @property
    def exceptions(self) -> list[ToolError]:
        return self._exceptions


def present(x: Any) -> bool:  # noqa: ANN401 - intentional use of Any.
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

    if not eol:
        for mirror in sync_mirrors:
            mirror.write(b"\n")
            mirror.flush()
        for a_mirror in async_mirrors:
            a_mirror.feed_data(b"\n")


class Reporter(abc.ABC):
    @abc.abstractmethod
    async def create(self, tool: Tool) -> ReportInstance:
        pass

    @abc.abstractmethod
    async def summarise(self, results: ToolResults) -> None:
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        pass


class ReportInstance(abc.ABC):
    @abc.abstractmethod
    async def start(self) -> ReportStreams:
        pass

    @abc.abstractmethod
    async def end(self) -> None:
        pass


__all__ = [
    "ReportHandler",
    "Reporter",
    "ToolReport",
    "ReportStreams",
    "ReportInstance",
    "Tool",
    "ToolResults",
    "Annotation",
]
