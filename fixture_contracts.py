"""Nonactivating fixture telemetry, distinct from AX or physical-input qualification."""


def validate_native_fixture(value, pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("missing owned process identity")
    if not isinstance(value, dict) or type(value.get("protocol")) is not int or value["protocol"] != 1 or value.get("mode") != "hidden":
        raise ValueError("missing or unknown native fixture safety protocol")
    snapshots = value.get("snapshots")
    phases = ["created", "rendered", "resized", "closed"]
    if not isinstance(snapshots, list) or len(snapshots) != len(phases):
        raise ValueError("incomplete native fixture snapshots")
    window_id = None
    for phase, sample in zip(phases, snapshots):
        if not isinstance(sample, dict) or sample.get("phase") != phase or type(sample.get("pid")) is not int or sample["pid"] != pid:
            raise ValueError("fixture phase or owned process identity differs")
        for key in ("fixture_frontmost", "application_active", "window_visible", "window_key"):
            if sample.get(key) is not False:
                raise ValueError("hidden fixture became visible, key or active")
        if type(sample.get("activation_policy")) is not int or sample["activation_policy"] != 1:
            raise ValueError("native fixture lacks accessory activation policy")
        count, number = sample.get("owned_titled_windows"), sample.get("native_window_id")
        if type(count) is not int or type(number) is not int:
            raise ValueError("invalid native window ownership fields")
        if phase != "closed":
            if count != 1 or number <= 0:
                raise ValueError("expected exactly one owned native window")
            if window_id is not None and number != window_id:
                raise ValueError("native window identity changed during fixture")
            window_id = number
        elif count not in (0, 1) or (count == 1 and number != window_id) or (count == 0 and number != 0):
            raise ValueError("unexpected native window after owned teardown")
