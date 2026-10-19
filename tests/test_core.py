import unittest

from environment_variable_drift_watcher_kit import DriftEvent, DriftWatcher


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._t = start

    def __call__(self) -> float:
        self._t += 1.0
        return self._t


class RecordingHandler:
    def __init__(self):
        self.events = []

    def __call__(self, event: DriftEvent) -> None:
        self.events.append(event)


class DriftWatcherTest(unittest.TestCase):
    def test_first_tick_is_baseline_and_emits_nothing(self):
        env = {"PATH": "/usr/bin"}
        handler = RecordingHandler()
        w = DriftWatcher(["PATH"], handler, environ=env, clock=FakeClock())
        events = w.tick()
        self.assertEqual(events, [])
        self.assertEqual(handler.events, [])

    def test_no_change_emits_nothing(self):
        env = {"PATH": "/usr/bin"}
        handler = RecordingHandler()
        w = DriftWatcher(["PATH"], handler, environ=env, clock=FakeClock())
        w.tick()
        events = w.tick()
        self.assertEqual(events, [])
        self.assertEqual(handler.events, [])

    def test_value_change_emits_event_with_old_and_new(self):
        env = {"PATH": "/usr/bin"}
        handler = RecordingHandler()
        clock = FakeClock()
        w = DriftWatcher(["PATH"], handler, environ=env, clock=clock)
        w.tick()
        env["PATH"] = "/usr/local/bin"
        events = w.tick()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].key, "PATH")
        self.assertEqual(events[0].old_value, "/usr/bin")
        self.assertEqual(events[0].new_value, "/usr/local/bin")
        self.assertEqual(events[0].timestamp, 1.0)
        self.assertEqual(handler.events, events)

    def test_missing_key_then_present_is_a_change(self):
        env = {}
        handler = RecordingHandler()
        w = DriftWatcher(["DEBUG"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["DEBUG"] = "1"
        events = w.tick()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].key, "DEBUG")
        self.assertIsNone(events[0].old_value)
        self.assertEqual(events[0].new_value, "1")

    def test_present_key_then_missing_is_a_change(self):
        env = {"DEBUG": "1"}
        handler = RecordingHandler()
        w = DriftWatcher(["DEBUG"], handler, environ=env, clock=FakeClock())
        w.tick()
        del env["DEBUG"]
        events = w.tick()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].old_value, "1")
        self.assertIsNone(events[0].new_value)

    def test_empty_string_is_a_real_value_distinct_from_missing(self):
        env = {"TOKEN": ""}
        handler = RecordingHandler()
        w = DriftWatcher(["TOKEN"], handler, environ=env, clock=FakeClock())
        w.tick()
        # Empty -> non-empty is a change.
        env["TOKEN"] = "abc"
        events = w.tick()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].old_value, "")
        self.assertEqual(events[0].new_value, "abc")

    def test_empty_string_to_missing_is_a_change(self):
        env = {"TOKEN": ""}
        handler = RecordingHandler()
        w = DriftWatcher(["TOKEN"], handler, environ=env, clock=FakeClock())
        w.tick()
        del env["TOKEN"]
        events = w.tick()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].old_value, "")
        self.assertIsNone(events[0].new_value)

    def test_multiple_changes_in_one_tick_each_get_an_event(self):
        env = {"A": "1", "B": "2", "C": "3"}
        handler = RecordingHandler()
        w = DriftWatcher(["A", "B", "C"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["A"] = "x"
        env["B"] = "y"
        events = w.tick()
        self.assertEqual([e.key for e in events], ["A", "B"])
        self.assertEqual([e.old_value for e in events], ["1", "2"])
        self.assertEqual([e.new_value for e in events], ["x", "y"])

    def test_change_back_within_one_tick_not_detected(self):
        env = {"PATH": "/usr/bin"}
        handler = RecordingHandler()
        w = DriftWatcher(["PATH"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["PATH"] = "/other"
        env["PATH"] = "/usr/bin"
        events = w.tick()
        self.assertEqual(events, [])

    def test_change_then_revert_across_ticks_emits_two_events(self):
        env = {"PATH": "/usr/bin"}
        handler = RecordingHandler()
        w = DriftWatcher(["PATH"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["PATH"] = "/other"
        first = w.tick()
        self.assertEqual(len(first), 1)
        env["PATH"] = "/usr/bin"
        second = w.tick()
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].old_value, "/other")
        self.assertEqual(second[0].new_value, "/usr/bin")

    def test_constructor_rejects_non_list_keys(self):
        with self.assertRaises(TypeError):
            DriftWatcher(("PATH",), lambda e: None, environ={})

    def test_constructor_rejects_non_string_keys(self):
        with self.assertRaises(TypeError):
            DriftWatcher(["PATH", 42], lambda e: None, environ={})

    def test_constructor_rejects_non_callable_handler(self):
        with self.assertRaises(TypeError):
            DriftWatcher(["PATH"], "not a handler", environ={})

    def test_handler_invoked_synchronously_in_tick_order(self):
        env = {"A": "1", "B": "2"}
        seen = []

        def handler(ev):
            seen.append(ev.key)

        w = DriftWatcher(["A", "B"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["A"] = "x"
        env["B"] = "y"
        w.tick()
        self.assertEqual(seen, ["A", "B"])

    def test_tick_returns_events_list_in_addition_to_calling_handler(self):
        env = {"K": "v1"}
        handler = RecordingHandler()
        w = DriftWatcher(["K"], handler, environ=env, clock=FakeClock())
        w.tick()
        env["K"] = "v2"
        returned = w.tick()
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0].new_value, "v2")
        self.assertEqual(handler.events, returned)


if __name__ == "__main__":
    unittest.main()
