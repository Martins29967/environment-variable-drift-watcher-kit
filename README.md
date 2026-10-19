# environment-variable-drift-watcher-kit

Periodically snapshots a fixed set of process environment variables and emits a structured `DriftEvent` when an observed value changes at runtime after startup.

```python
from environment_variable_drift_watcher_kit import DriftWatcher, DriftEvent

def handle(event: DriftEvent) -> None:
    print(f"{event.key}: {event.old_value!r} -> {event.new_value!r} @ {event.timestamp}")

watcher = DriftWatcher(["PATH", "DEBUG", "DATABASE_URL"], handle)

# Call this from your own scheduler (loop, signal handler, etc.):
watcher.tick()
```

## Why this exists

Some long-running processes mutate their own environment at runtime (via `os.environ` assignments, test harnesses, or libraries that re-read configuration into the process env). When that happens, the value a startup log recorded can silently drift from the value the process actually uses minutes or hours later. This watcher gives you a single, dependency-free way to notice those drifts and react.

The trade-off: the watcher is deliberately pull-based. It does not spawn a thread, install a signal handler, or hook `os.environ.__setitem__`. You call `tick()` when you want to check. That keeps the surface area small and the behaviour deterministic, at the cost of you owning the scheduling loop.

## The awkward edge

A missing key and an empty-string key are treated as different observations. `DriftEvent.old_value` / `new_value` use `None` to mean "the key was absent from the environment", so a real empty string (`""`) is reported as the string `""`, not as `None`. If your code maps "unset" and "empty" to the same thing, normalise before comparing — this library will not collapse them for you.

The first `tick()` establishes the baseline and never emits events, even if the environment changed between construction and that first call.
