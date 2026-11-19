"""Optional structured progress without changing normal command-line logging."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_sink: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("conversion_progress", default=None)


def report(stage: str, *, completed: int | None = None, total: int | None = None) -> None:
    sink = _sink.get()
    if sink:
        sink({"event": "progress", "stage": stage, "completed": completed, "total": total})


@contextmanager
def reporting(sink: Callable[[dict[str, Any]], None] | None) -> Iterator[None]:
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)
