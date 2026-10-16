#!/usr/bin/env python3
"""Linux/X11 visible native pair: build pinned sources, launch, capture, compare.

A MoonBit Wayland surface is hosted in an owned Weston X11 output. Neither it
nor the Rust X11 window is a mock or an offscreen substitute. Failed setup
and missing observations are unverified, never passing evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contracts import validate_scenarios
from run import prepare_moonbit, source

PREFIX = "GPUI_NATIVE_LAB "
ROLES = ("upstream", "moonbit")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def log_command(argv, cwd, env, output, timeout):
    started = time.monotonic()
    out, err = output.with_suffix(".stdout"), output.with_suffix(".stderr")
    try:
        with out.open("wb") as stdout, err.open("wb") as stderr:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stdout,
                                    stderr=stderr, timeout=timeout, check=False)
        status = {"returncode": result.returncode, "timed_out": False}
    except subprocess.TimeoutExpired:
        status = {"returncode": None, "timed_out": True}
    except OSError as exc:
        err.write_text(str(exc))
        status = {"returncode": None, "timed_out": False, "error": type(exc).__name__}
    return {**status, "command": argv, "elapsed_ms": round((time.monotonic()-started)*1000),
            "stdout": str(out.relative_to(output.parent.parent)),
            "stderr": str(err.relative_to(output.parent.parent))}


def build_pair(args, output, env, pins, manifest):
    build = output / "build"
    build.mkdir()
    sources = {"upstream": args.upstream_source.resolve(), "moonbit": args.moonbit_source.resolve()}
    for role, path in sources.items():
        manifest["sources"][role] = source(path, pins[role]["revision"], role, pins[role]["version"])
    rust_dir = build / "rust-adapter"
    shutil.copytree(ROOT / "adapters/linux_rust", rust_dir)
    shutil.copy2(ROOT / "adapters/native_rust/Cargo.lock", rust_dir / "Cargo.lock")
    cargo = rust_dir / "Cargo.toml"
    cargo.write_text(cargo.read_text().replace(
        '"../../../zed-source/crates/gpui"', json.dumps(str(sources["upstream"] / "crates/gpui"))
    ).replace(
        '"../../../zed-source/crates/gpui_platform"', json.dumps(str(sources["upstream"] / "crates/gpui_platform"))
    ))
    moon_dir = prepare_moonbit(sources["moonbit"], build, ROOT / "adapters/linux_moonbit")
    # Generate target-specific, untracked Wayland protocol bindings in the isolated copy.
    protocol = log_command(
        ["sh", "scripts/prepare_ubuntu.sh"], moon_dir, env,
        build / "wayland-protocol-prepare", 60,
    )
    files = ("xdg-shell-client-protocol.h", "xdg-shell-protocol.c",
             "text-input-v1-client-protocol.h", "text-input-v1-protocol.c")
    protocol["generated_sha256"] = {
        name: sha256(moon_dir / "ubuntu" / name)
        for name in files if (moon_dir / "ubuntu" / name).is_file()
    }
    manifest["protocol_generation"] = protocol
    if protocol["returncode"] != 0 or len(protocol["generated_sha256"]) != len(files):
        manifest["reasons"].append("moonbit: private Wayland protocol generation failed")
        return {}
    # A separate target directory avoids writing into the upstream Zed checkout.
    rust_env = {**env, "CARGO_TARGET_DIR": str(build / "rust-target")}
    specs = {
        "upstream": (
            ["cargo", "+1.98.1", "build"] + ([] if args.online else ["--offline"]) +
            ["--manifest-path", str(cargo)], ROOT, rust_env,
            build / "rust-target/debug/gpui-conformance-linux-lab"
        ),
        "moonbit": (
            ["moon", "build", "--target", "native", "--deny-warn", "conformance_probe"],
            moon_dir, env,
            moon_dir / "_build/native/debug/build/conformance_probe/conformance_probe.exe"
        ),
    }
    executables = {}
    for role in ROLES:
        command, cwd, run_env, exe = specs[role]
        entry = log_command(command, cwd, run_env, build / role, args.build_timeout)
        if role == "upstream" and (rust_dir / "Cargo.lock").is_file():
            out_lock = output / "rust-resolved-Cargo.lock"
            shutil.copy2(rust_dir / "Cargo.lock", out_lock)
            entry["resolved_lock_sha256"] = sha256(out_lock)
            entry["resolved_lock_path"] = out_lock.name
        manifest["builds"][role] = entry
        if entry["returncode"] != 0 or not exe.is_file():
            manifest["reasons"].append(f"{role}: native build did not produce an executable")
            continue
        retained = output / role / "fixture"
        retained.parent.mkdir()
        shutil.copy2(exe, retained)
        retained.chmod(retained.stat().st_mode | 0o100)
        executables[role] = retained
        entry["executable_sha256"] = sha256(retained)
    for role, path in sources.items():
        source(path, pins[role]["revision"], role, pins[role]["version"])
    return executables


def window_rows():
    result = subprocess.run(["wmctrl", "-lpG"], capture_output=True, text=True, timeout=3, check=True)
    rows = []
    for line in result.stdout.splitlines():
        cells = line.split(None, 7)
        if len(cells) >= 7:
            try:
                rows.append({"id": cells[0], "pid": int(cells[2]), "x": int(cells[3]),
                             "y": int(cells[4]), "width": int(cells[5]), "height": int(cells[6])})
            except ValueError:
                continue
    return rows


def owned_window(pid):
    rows = [row for row in window_rows() if row["pid"] == pid]
    return rows[0] if len(rows) == 1 else None


def await_window(pid, proc, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end and proc.poll() is None:
        row = owned_window(pid)
        if row:
            return row
        time.sleep(.1)
    return None


def weston_window(pid, proc, log_path, timeout):
    """Identify a Weston-owned X11 output omitted from EWMH window lists."""
    end = time.monotonic() + timeout
    while time.monotonic() < end and proc.poll() is None:
        text = log_path.read_text(errors="replace") if log_path.exists() else ""
        ids = set(re.findall(r"x11 output \d+x\d+, window id (\d+)", text))
        if len(ids) == 1:
            window_id = f"0x{int(next(iter(ids))):08x}"
            check = subprocess.run(["xwininfo", "-id", window_id], capture_output=True,
                                   text=True, timeout=3, check=False)
            output = check.stdout
            size = [re.search(rf"^\s*{key}:\s*(\d+)\s*$", output, re.MULTILINE)
                    for key in ("Width", "Height")]
            if (check.returncode == 0 and all(size)
                    and "Map State: IsViewable" in output):
                return {"id": window_id, "pid": pid, "width": int(size[0][1]),
                        "height": int(size[1][1]),
                        "source": "owned_weston_stderr_verified_by_xwininfo",
                        "visibility": "IsViewable"}
        time.sleep(.1)
    return None


def move_resize(window_id, x, y, width, height, *, direct=False):
    if direct:
        commands = [["xdotool", "windowsize", window_id, str(width), str(height)],
                    ["xdotool", "windowmove", window_id, str(x), str(y)]]
        results = [subprocess.run(command, capture_output=True, text=True,
                                  timeout=5, check=False) for command in commands]
        return {"returncode": max(result.returncode for result in results),
                "stderr": "\n".join(result.stderr.strip() for result in results if result.stderr),
                "method": "xdotool_direct_X11"}
def ewmh_move_resize(window_id, x, y, width, height):
    result = subprocess.run(["wmctrl", "-ir", window_id, "-e",
                             f"0,{x},{y},{width},{height}"], capture_output=True, text=True,
                            timeout=5, check=False)
    return {"returncode": result.returncode, "stderr": result.stderr.strip(), "method": "EWMH"}


def events(path, role, token):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith(PREFIX):
            continue
        try:
            record = json.loads(line[len(PREFIX):])
            if (record.get("protocol") == 1 and record.get("implementation") == role
                    and record.get("run_token") == token and isinstance(record.get("event"), str)):
                records.append(record)
        except (ValueError, AttributeError):
            continue
    return records


def has_event(records, name, width=None, height=None, scale=None):
    for record in records:
        if record["event"] != name:
            continue
        expected = {"width": width, "height": height, "scale": scale}
        if all(v is None or (isinstance(record.get(k), (float, int)) and
                            abs(record[k] - v) <= .05) for k, v in expected.items()):
            return True
    return False


def wait_frames(logs, token, procs, started_at, width, height, timeout):
    start = time.monotonic()
    first = {}
    while time.monotonic() - start < timeout:
        for role in ROLES:
            if role not in first and has_event(events(logs[role], role, token), "frame_ready",
                                               width, height, 1.0):
                first[role] = round((time.monotonic() - started_at[role]) * 1000)
        if len(first) == 2 or any(procs[role].poll() is not None for role in ROLES):
            break
        time.sleep(.05)
    return first


def point_color(pixel_case, x, y):
    left, top, width, height = pixel_case["rect"]
    return tuple(pixel_case["color"][:3] if left <= x < left+width and top <= y < top+height
                 else pixel_case["background"][:3])


def inspect_images(paths, pixel_case, scale):
    images = {}
    observations = {}
    for role, path in paths.items():
        with Image.open(path) as original:
            image = original.convert("RGB")
        images[role] = image
        width, height = image.size
        expected_size = (round(pixel_case["width"] * scale), round(pixel_case["height"] * scale))
        samples = []
        for x, y in pixel_case["points"]:
            xx, yy = int(x * scale), int(y * scale)
            actual = image.getpixel((xx, yy)) if 0 <= xx < width and 0 <= yy < height else None
            expected = point_color(pixel_case, x, y)
            samples.append({"xy": [x, y], "actual": list(actual) if actual else None,
                            "expected": list(expected), "matches_fixture": actual == expected})
        observations[role] = {
            "path": path.name, "sha256": sha256(path), "size": [width, height],
            "expected_size": list(expected_size),
            "samples": samples, "fixture_match": image.size == expected_size and
            all(s["matches_fixture"] for s in samples)
        }
    if images["upstream"].size == images["moonbit"].size:
        a, b = images["upstream"], images["moonbit"]
        diff_count = sum(p != q for p, q in zip(a.getdata(), b.getdata()))
    else:
        diff_count = None
    same_samples = all(
        a["actual"] == b["actual"]
        for a, b in zip(observations["upstream"]["samples"], observations["moonbit"]["samples"])
    )
    return {"captures": observations, "different_pixels": diff_count,
            "same_sample_colors": same_samples,
            "status": "pass" if same_samples and all(
                obs["fixture_match"] for obs in observations.values()) else "mismatch"}


def capture(window_id, path):
    result = subprocess.run(["import", "-window", window_id, str(path)],
                            capture_output=True, text=True, timeout=15, check=False)
    return result.returncode == 0 and path.is_file() and path.stat().st_size > 0


def spawn(args, env, folder, name):
    stdout = (folder / f"{name}.stdout").open("wb")
    stderr = (folder / f"{name}.stderr").open("wb")
    try:
        proc = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=stdout,
                                stderr=stderr, start_new_session=True)
        return proc
    finally:
        stdout.close()
        stderr.close()


def stop_owned(process):
    if process.poll() is not None:
        return process.returncode
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        # The recorded PID is the root of this task's own new process group.
        os.killpg(process.pid, signal.SIGKILL)
        return process.wait(timeout=3)


def run_visible(args, out, executables, manifest, scenarios, token):
    width, height = (scenarios["cases"][0][k] for k in ("width", "height"))
    resized = scenarios["cases"][0]["resize"]
    env = os.environ.copy()
    rust_env = {**env, "XDG_SESSION_TYPE": "x11"}
    rust_env.pop("WAYLAND_DISPLAY", None)
    rust_env.pop("WAYLAND_SOCKET", None)
    # XDG_RUNTIME_DIR must not make the AF_UNIX socket exceed Linux sun_path's 108-byte limit.
    runtime = Path(tempfile.mkdtemp(prefix="gpui-lab-"))
    runtime.chmod(0o700)
    socket = "gpui-lab-" + token[:12]
    weston_env = {**env, "XDG_RUNTIME_DIR": str(runtime), "XDG_SESSION_TYPE": "x11"}
    weston_args = ["weston", "--backend=x11-backend.so", "--shell=kiosk-shell.so",
                   f"--width={width}", f"--height={height}", f"--socket={socket}",
                   "--idle-time=0"]
    moon_env = {**weston_env, "WAYLAND_DISPLAY": socket, "XDG_SESSION_TYPE": "wayland"}
    moon_env.pop("WAYLAND_SOCKET", None)
    shared = {"GPUI_SCENARIOS": json.dumps(scenarios, separators=(",", ":")),
              "GPUI_RUN_TOKEN": token, "GPUI_NEGATIVE_CONTROL": "1" if args.negative_control else "0"}
    spawned = {}
    logs = {role: out / f"{role}.stdout" for role in ROLES}
    try:
        spawned["weston"] = spawn(weston_args, weston_env, out, "weston")
        manifest["processes"]["weston"] = {"pid": spawned["weston"].pid, "command": weston_args}
        end = time.monotonic() + args.start_timeout
        while time.monotonic() < end and spawned["weston"].poll() is None:
            if (runtime / socket).is_socket():
                break
            time.sleep(.1)
        if not (runtime / socket).is_socket():
            manifest["reasons"].append("owned Weston X11 compositor did not expose its Wayland socket")
            return
        started_at = {}
        for role, run_env in (("upstream", rust_env), ("moonbit", moon_env)):
            child = spawn([str(executables[role])], {**run_env, **shared}, out, role)
            spawned[role] = child
            started_at[role] = time.monotonic()
            manifest["processes"][role] = {"pid": child.pid, "executable_sha256": sha256(executables[role])}
        windows = {}
        rust_window = await_window(spawned["upstream"].pid, spawned["upstream"], args.start_timeout)
        if rust_window is not None:
            windows["upstream"] = rust_window
        compositor_window = await_window(spawned["weston"].pid, spawned["weston"], 2)
        if compositor_window is None:
            compositor_window = weston_window(spawned["weston"].pid, spawned["weston"],
                                              out / "weston.stderr", args.start_timeout)
        if compositor_window is not None:
            windows["moonbit"] = compositor_window
        manifest["windows"] = windows
        if len(windows) != 2 or windows["upstream"]["id"] == windows["moonbit"]["id"]:
            manifest["reasons"].append("exactly one X11 top-level window per owned Rust/Weston process was not identified")
            return
        manifest["placement"] = {
            role: (move_resize(windows[role]["id"], x, 40, width, height, direct=True)
                   if role == "moonbit" else ewmh_move_resize(windows[role]["id"], x, 40, width, height))
            for role, x in (("upstream", 40), ("moonbit", 80 + width))
        }
        first = wait_frames(logs, token, spawned, started_at, width, height, args.start_timeout)
        manifest["time_from_process_spawn_to_frame_poll_ms"] = first
        if len(first) != 2:
            manifest["diagnostic_frames"] = {}
            for role in ROLES:
                image_path = out / f"{role}-diagnostic.png"
                if capture(windows[role]["id"], image_path):
                    manifest["diagnostic_frames"][role] = {
                        "path": image_path.name, "sha256": sha256(image_path),
                        "qualified": False,
                    }
            manifest["reasons"].append("both native processes did not report a correct-size, scale-1 frame")
            return
        time.sleep(.4)
        captured = {}
        for role in ROLES:
            frame = out / f"{role}.png"
            if capture(windows[role]["id"], frame):
                captured[role] = frame
        if len(captured) != 2:
            manifest["reasons"].append("native compositor pixel capture missing for one or both windows")
            return
        manifest["pixels"] = inspect_images(captured, scenarios["cases"][1], 1.0)
        if args.interactive:
            print("Both native windows are available. Press Ctrl+C here to stop; resize comparison will be unverified.", flush=True)
            try:
                while all(spawned[r].poll() is None for r in ROLES):
                    time.sleep(.25)
            except KeyboardInterrupt:
                pass
            manifest["reasons"].append("interactive mode did not run controlled resize")
            return
        manifest["resize_request"] = {
            role: (move_resize(windows[role]["id"], x, 40, resized[0], resized[1], direct=True)
                   if role == "moonbit" else ewmh_move_resize(windows[role]["id"], x, 40, resized[0], resized[1]))
            for role, x in (("upstream", 40), ("moonbit", 80 + resized[0]))
        }
        time.sleep(args.resize_settle)
        native = {role: events(logs[role], role, token) for role in ROLES}
        manifest["native_events"] = native
        resize_confirmed = {
            role: has_event(native[role], "resized", resized[0], resized[1], 1.0)
            for role in ROLES
        }
        resized_images = {}
        resize_sizes = {}
        for role in ROLES:
            image_path = out / f"{role}-resized.png"
            if capture(windows[role]["id"], image_path):
                resized_images[role] = {"path": image_path.name, "sha256": sha256(image_path)}
                with Image.open(image_path) as image:
                    resize_sizes[role] = list(image.size)
        manifest["resize"] = {"requested": resized, "event_confirmed": resize_confirmed,
                              "captures": resized_images, "actual_capture_sizes": resize_sizes,
                              "status": "pass" if all(resize_confirmed.values()) and
                              all(resize_sizes.get(role) == resized for role in ROLES)
                              else "unverified"}
        if manifest["resize"]["status"] != "pass":
            manifest["reasons"].append("requested resize was not confirmed by both native event streams")
    finally:
        for role in ("upstream", "moonbit", "weston"):
            if role in spawned:
                manifest["processes"].setdefault(role, {})["exit_code"] = stop_owned(spawned[role])
        manifest["native_events"] = {
            role: events(logs[role], role, token) for role in ROLES
        }
        shutil.rmtree(runtime)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source", type=Path, default=ROOT.parent / "zed-source")
    parser.add_argument("--moonbit-source", type=Path, default=ROOT.parent / "gpui-reference")
    parser.add_argument("--candidate-revision", help="explicit full gpui.mbt commit SHA")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--build-timeout", type=int, default=1200)
    parser.add_argument("--start-timeout", type=int, default=20)
    parser.add_argument("--resize-settle", type=float, default=2.)
    args = parser.parse_args(argv)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    pins = json.loads((ROOT / "pins.json").read_text())
    if args.candidate_revision:
        if len(args.candidate_revision) != 40 or any(c not in "0123456789abcdef" for c in args.candidate_revision):
            parser.error("candidate revision must be a full lowercase SHA")
        pins["moonbit"]["revision"] = args.candidate_revision
    scenarios = json.loads((ROOT / "native_scenarios.json").read_text())
    validate_scenarios(scenarios)
    token = str(uuid.uuid4())
    manifest = {"schema_version": 1, "status": "unverified", "created_at": stamp(),
                "platform": {"os": platform.system(), "machine": platform.machine(),
                             "display_set": bool(os.environ.get("DISPLAY")),
                             "x11_host": True, "moonbit_backend": "Wayland/EGL via Weston X11",
                             "upstream_backend": "X11 GPUI native",
                             "requested_scale": 1.0},
                "pins": pins, "scenario_sha256": sha256(ROOT / "native_scenarios.json"),
                "run_token": token, "builds": {}, "sources": {}, "processes": {},
                "negative_control": args.negative_control, "reasons": []}
    (out / "scenarios.json").write_text(json.dumps(scenarios, indent=2) + "\n")
    try:
        build = build_pair(args, out, os.environ.copy(), pins, manifest)
        if len(build) == 2 and not args.build_only:
            required = ("weston", "wmctrl", "xdotool", "xwininfo", "import")
            missing = [name for name in required if shutil.which(name) is None]
            if platform.system() != "Linux" or not os.environ.get("DISPLAY") or missing:
                manifest["reasons"].append("X11 execution prerequisites absent: " +
                                           ", ".join(missing or ["Linux DISPLAY"]))
            else:
                run_visible(args, out, build, manifest, scenarios, token)
        elif args.build_only:
            manifest["reasons"].append("build-only: visible X11 windows and GPU pixels not executed")
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        manifest["reasons"].append(f"{type(exc).__name__}: {exc}")
    pixel = manifest.get("pixels", {}).get("status")
    resize = manifest.get("resize", {}).get("status")
    if pixel == "mismatch":
        manifest["status"] = "mismatch"
    elif pixel == "pass" and resize == "pass" and not manifest["reasons"]:
        manifest["status"] = "pass"
    (out / "comparison.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": manifest["status"], "reasons": manifest["reasons"],
                      "pixel_status": pixel, "resize_status": resize}))
    return {"pass": 0, "mismatch": 1, "unverified": 2}[manifest["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
