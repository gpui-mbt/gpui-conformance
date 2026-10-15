"""Pure safety protocol checks; synthetic samples do not establish conformance."""
import copy
import unittest

from fixture_contracts import validate_native_fixture


def fixture():
    return {"protocol": 1, "mode": "hidden", "snapshots": [
        {"phase": phase, "pid": 123, "fixture_frontmost": False,
         "application_active": False, "window_visible": False, "window_key": False,
         "activation_policy": 1, "owned_titled_windows": 1,
         "native_window_id": 456}
        for phase in ("created", "rendered", "resized", "closed")]}


class FixtureContractTests(unittest.TestCase):
    def test_complete_owned_hidden_lifecycle(self):
        validate_native_fixture(fixture(), 123)
        value = fixture()
        value["snapshots"][-1].update(owned_titled_windows=0, native_window_id=0)
        validate_native_fixture(value, 123)

    def test_missing_unknown_or_boolean_protocol_rejected(self):
        for protocol in (None, True, 2, "1"):
            value = fixture()
            value["protocol"] = protocol
            with self.subTest(protocol=protocol), self.assertRaises(ValueError):
                validate_native_fixture(value, 123)

    def test_visible_or_active_or_unknown_state_rejected(self):
        for key in ("fixture_frontmost", "application_active", "window_visible", "window_key"):
            for state in (True, None, 0):
                value = fixture()
                value["snapshots"][1][key] = state
                with self.subTest(key=key, state=state), self.assertRaises(ValueError):
                    validate_native_fixture(value, 123)

    def test_phase_order_and_complete_snapshots_required(self):
        for indices in ([0, 1, 2], [0, 2, 1, 3], [0, 1, 1, 3]):
            value = fixture()
            value["snapshots"] = [copy.deepcopy(value["snapshots"][i]) for i in indices]
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                validate_native_fixture(value, 123)

    def test_pid_must_match_execution(self):
        for pid in (124, None, True, 0):
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                validate_native_fixture(fixture(), pid)

    def test_regular_or_unknown_activation_policy_rejected(self):
        for policy in (0, 2, True, None):
            value = fixture()
            value["snapshots"][0]["activation_policy"] = policy
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                validate_native_fixture(value, 123)

    def test_missing_foreign_or_multiple_windows_rejected(self):
        for count, number in ((0, 0), (2, 456), (1, 0), (1, 789), (True, 456)):
            value = fixture()
            value["snapshots"][2].update(owned_titled_windows=count, native_window_id=number)
            with self.subTest(count=count, number=number), self.assertRaises(ValueError):
                validate_native_fixture(value, 123)

    def test_closed_window_identity_and_count_still_bound(self):
        for count, number in ((0, 456), (1, 789), (2, 456)):
            value = fixture()
            value["snapshots"][-1].update(owned_titled_windows=count, native_window_id=number)
            with self.subTest(count=count, number=number), self.assertRaises(ValueError):
                validate_native_fixture(value, 123)


if __name__ == "__main__":
    unittest.main()
