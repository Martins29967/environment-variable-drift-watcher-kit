"""Core implementation for the environment variable drift watcher.

The watcher is deliberately simple: at construction time it stores the
startup environment, then on each tick it compares the values currently
in ``os.environ`` for a caller-provided set of keys against the
previously observed values. When a value differs (type-for-type) from
the previous sample it emits a ``DriftEvent``.

A few design decisions, made explicitly so the tests cannot be read as
ambiguity:

* A missing key and an empty string are DIFFERENT observations. The
  internal representation uses a sentinel (``_MISSING``) for absence,
  never ``None`` and never ``""``, because environment variables are
  strings and a real empty string is a legitimate, observable value.
* A key that disappears (``_MISSING``) or reappears is a change.
* Timestamps are obtained from an injectable ``clock`` callable so tests
  never depend on wall-clock time.
* The handler is called synchronously during ``tick``; the library does
  not start threads or timers. The caller owns the scheduling loop.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional

WatchKey = str
WatchValue = Optional[str]


class _MissingSentinel:
    """Internal sentinel that is distinct from any real environment value.

    ``None`` is rejected because some users naturally map a missing
    variable to ``None``; by using a dedicated sentinel we avoid any
    collision with a value the caller might reasonably try to observe.
    """

    _instance: "Optional[_MissingSentinel]" = None

    def __new__(cls) -> "_MissingSentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<missing>"

    def __bool__(self) -> bool:
        return False


_MISSING = _MissingSentinel()


class DriftEvent:
    """A single observed change to a watched environment variable."""

    __slots__ = ("timestamp", "key", "old_value", "new_value")

    def __init__(
        self,
        timestamp: float,
        key: WatchKey,
        old_value: WatchValue,
        new_value: WatchValue,
    ) -> None:
        self.timestamp = timestamp
        self.key = key
        self.old_value = old_value
        self.new_value = new_value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DriftEvent):
            return NotImplemented
        return (
            self.timestamp == other.timestamp
            and self.key == other.key
            and self.old_value == other.old_value
            and self.new_value == other.new_value
        )

    def __repr__(self) -> str:
        return (
            "DriftEvent(timestamp=%r, key=%r, old_value=%r, new_value=%r)"
            % (self.timestamp, self.key, self.old_value, self.new_value)
        )


class DriftWatcher:
    """Watch a fixed set of environment keys for value drift.

    Args:
        keys: Names of environment variables to observe.
        handler: Called synchronously with a ``DriftEvent`` on each change.
        environ: Mapping used as the environment source. Defaults to
            ``os.environ``. Accepting the mapping explicitly makes the
            watcher trivial to test without monkeypatching globals.
        clock: Callable returning the current time as a number. Defaults
            to ``time.time``. Injected so tests never touch the wall clock.

    Notes:
        The first call to ``tick`` establishes the baseline by capturing
        the startup snapshot; it never emits an event even if the
        environment changed between construction and that first tick.
        Subsequent calls compare against the last observed state.
    """

    def __init__(
        self,
        keys: List[WatchKey],
        handler: Callable[[DriftEvent], None],
        environ: Optional["os._Environ[str]"] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if not isinstance(keys, list):
            raise TypeError("keys must be a list")
        if not callable(handler):
            raise TypeError("handler must be callable")
        for k in keys:
            if not isinstance(k, str):
                raise TypeError("each key must be a str")

        self._keys = list(keys)
        self._handler = handler
        self._environ = environ if environ is not None else os.environ
        self._clock = clock if clock is not None else self._default_clock
        self._previous: "Optional[dict]" = None

    @staticmethod
    def _default_clock() -> float:
        import time

        return time.time()

    def _sample(self) -> "dict":
        """Capture the current values for every watched key.

        Missing keys are recorded as the ``_MISSING`` sentinel so that a
        later appearance is detectable as a real change, not masked by a
        ``None`` collision.
        """
        env = self._environ
        return {k: (env[k] if k in env else _MISSING) for k in self._keys}

    def tick(self) -> List[DriftEvent]:
        """Sample the environment and emit one event per changed key.

        Returns the list of emitted events (empty if nothing changed).
        The first call establishes the baseline and always returns an
        empty list.
        """
        current = self._sample()
        if self._previous is None:
            self._previous = current
            return []

        ts = self._clock()
        events: List[DriftEvent] = []
        for key in self._keys:
            old = self._previous.get(key, _MISSING)
            new = current[key]
            if old is _MISSING or new is _MISSING:
                if old is not new:
                    events.append(
                        DriftEvent(
                            timestamp=ts,
                            key=key,
                            old_value=None if old is _MISSING else old,
                            new_value=None if new is _MISSING else new,
                        )
                    )
            else:
                if old != new:
                    events.append(
                        DriftEvent(
                            timestamp=ts,
                            key=key,
                            old_value=old,
                            new_value=new,
                        )
                    )

        self._previous = current
        for ev in events:
            self._handler(ev)
        return events
