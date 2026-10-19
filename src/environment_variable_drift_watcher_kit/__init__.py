"""environment_variable_drift_watcher_kit

Periodically snapshots process environment variables and emits a structured
event when an observed value changes at runtime after startup.
"""

from .core import DriftEvent, DriftWatcher, WatchKey, WatchValue

__all__ = ["DriftEvent", "DriftWatcher", "WatchKey", "WatchValue"]
