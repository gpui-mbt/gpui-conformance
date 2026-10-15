"""Bounded runner for an explicitly requested owned visible observer fixture."""
import json
import subprocess
import time

from observer_contracts import validate_observation, validate_ready
from run import artifact, execute, now


def execute_observed(executable, env, folder, root, run, dimensions, observer):
    started = now()
    started_mono = time.monotonic()
    timed_out = False
    observation = {"status": "unverified"}
    with (folder/"stdout.log").open("wb") as stdout, (folder/"stderr.log").open("wb") as stderr:
        proc = subprocess.Popen([str(executable)], env=env, stdout=stdout, stderr=stderr, cwd=root)
        try:
            def owned_timeout(limit):
                remaining = 15-(time.monotonic()-started_mono)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired([str(executable)], 15)
                if proc.poll() is not None:
                    raise ValueError("owned fixture exited before observer completion")
                return min(limit, remaining)
            deadline = started_mono+5
            ready_path = folder/"ready.json"
            ready = None
            while proc.poll() is None and time.monotonic() < deadline:
                if ready_path.exists():
                    try:
                        ready = json.loads(ready_path.read_text())
                        break
                    except json.JSONDecodeError:
                        pass
                time.sleep(.01)
            if ready is None:
                raise ValueError("fixture exited or timed out before owned ready record")
            validate_ready(ready, run, proc.pid, executable, dimensions, started)
            observation["ready"] = artifact(ready_path, root)
            controls = []
            # Each invalid identity fails before any window/AX lookup. No other
            # process or window is selected, inspected or sent an action.
            for name, key, value in (("stale-start", "process_start_sec", ready["process_start_sec"]-1),
                                     ("invalid-window", "native_window_id", 0), ("invalid-pid", "pid", 0)):
                bad_path = folder/(name+".json")
                bad_path.write_text(json.dumps({**ready, key: value})+"\n")
                control_record = execute([str(observer), str(bad_path)], env, folder/(name+".stdout"), folder/(name+".stderr"), root, owned_timeout(1))
                control_result = json.loads((folder/(name+".stdout")).read_text())
                if control_record["returncode"] != 0 or control_record["timed_out"] or control_result.get("window_binding") != "unverified" or "window" in control_result:
                    raise ValueError("observer accepted an invalid identity control")
                controls.append({"name":name, "ready":artifact(bad_path,root), "execution":control_record,
                                 "stdout":artifact(folder/(name+".stdout"),root),"stderr":artifact(folder/(name+".stderr"),root)})
            observation["negative_controls"] = controls
            record = execute([str(observer), str(ready_path)], env, folder/"observer.stdout", folder/"observer.stderr", root, owned_timeout(3))
            observation.update(execution=record, stdout=artifact(folder/"observer.stdout", root), stderr=artifact(folder/"observer.stderr", root))
            if record["returncode"] != 0 or record["timed_out"]:
                raise ValueError("owned observer process failed or timed out")
            result = json.loads((folder/"observer.stdout").read_text())
            validate_observation(result, ready)
            owned_timeout(1)
            ack = {"run_token": ready["run_token"], "pid": proc.pid,
                   "native_window_id": ready["native_window_id"], "frame_sequence": ready["frame_sequence"],
                   "observer_completed": True}
            with (folder/"ack.json").open("x") as output:
                json.dump(ack, output)
            observation.update(status="pass", ax_status=result["ax_status"], ax_reason=result.get("ax_reason"),
                               ack=artifact(folder/"ack.json", root))
            code = proc.wait(timeout=max(.1, 15-(time.monotonic()-started_mono)))
        except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
            observation.update(status="unverified", reason=str(exc))
            timed_out = isinstance(exc, subprocess.TimeoutExpired)
            if proc.poll() is None:
                proc.kill()  # Only this owned fixture, never an arbitrary PID/title.
            code = proc.wait()
    finished = now()
    execution = {"command": [str(executable)], "pid": proc.pid, "started_at": started,
                 "finished_at": finished, "returncode": code, "timed_out": timed_out}
    if code != 0:
        observation.update(status="unverified", reason="fixture did not exit normally")
    return execution, observation
