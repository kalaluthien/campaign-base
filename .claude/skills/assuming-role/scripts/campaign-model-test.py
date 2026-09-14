#!/usr/bin/env python3
# witnesses: ModelSwitchKeepsEverySession, Cov_ModelSwitch
"""Prove campaign-model addresses exactly one role's panes, switches each in
place, puts the user's default back, and never does what a hand-off does.

The pane side goes through a fake `run` that records every herdr call and
plays a session: a fresh one runs `/model` at once, one with history shows
the `Switch model?` dialog until an Enter answers it -- the two shapes probed
on rule-check#431. A switch that lands writes the command record and what it
printed into a real transcript file, which the script reads through the
heartbeat's reader, and rewrites a settings file the way the harness does,
which the script must put back (rule-check#431 DECISION 5659640299). What
`ModelSwitchKeepsEverySession` says of the model is checked of the calls:
nothing but `/model` and `/effort` is ever prompted, and no pane is started,
exited or closed.

Then every branch is broken in turn on the script's source, loaded with its
real path so its siblings resolve, and the case named for it must go red by
its own assertion.

Usage: .claude/skills/assuming-role/scripts/campaign-model-test.py
"""
import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]
sys.path.append(str(BASE / "scripts"))
harness = importlib.import_module("suite-harness-test")
check = harness.check
SCRIPT = HERE / "campaign-model.py"
SOURCE = SCRIPT.read_text()


def load(source):
    """The script from `source`, with its real `__file__` so it finds its siblings."""
    m = types.ModuleType("cmodel")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    m.source_text = source
    return m


def assistant(ts, model):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {"model": model}})


def user(text):
    return json.dumps({"type": "user", "timestamp": "2026-09-14T05:00:00.000Z",
                       "message": {"content": text}})


def printed(name, value):
    """What the harness prints when the command took, in the probed words."""
    return {"model": f"Set model to `{value}` and saved as your default for new sessions",
            "effort": f"Set effort level to {value} (saved as your default for new sessions)"}[name]


def has(text, part):
    """`part` in `text`, False when there is no text: a branch that returned
    None must fail its case by assertion, not crash it."""
    return text is not None and part in text


def row(name, pane, status="idle"):
    return {"name": name, "pane": pane, "status": status, "cwd": "/b"}


BOX = "─" * 20 + "\n❯{}\n" + "─" * 20 + "\n"
DEFAULT = {"model": "claude-fable-5-1[1m]", "effortLevel": "high", "other": "kept"}


class Pane:
    """A fake `run` over one pane, one transcript file and one settings file.
    `dialog` is a session with history, `stuck` one whose dialog an Enter does
    not close; `records` False is one whose switch never lands, `rejects` one
    whose `/model` prints a refusal."""

    def __init__(self, path, settings, dialog=False, stuck=False, records=True,
                 rejects=False, prompt_rc=0, box=""):
        self.path, self.settings = path, settings
        self.dialog, self.stuck, self.records, self.rejects = dialog, stuck, records, rejects
        self.prompt_rc, self.box = prompt_rc, box
        self.calls, self.up = [], False

    def append(self, *lines):
        with open(self.path, "a") as fh:
            fh.writelines(line + "\n" for line in lines)

    def landed(self, name, value):
        """What the harness does when a command runs: its record, what it
        printed, and -- when it took -- the default rewritten, with a key some
        other session changed meanwhile."""
        said = f"Model '{value}' not found" if self.rejects and name == "model" else printed(name, value)
        self.append(user(f"<command-name>/{name}</command-name> <command-args>{value}</command-args>"),
                    user(f"<local-command-stdout>{said}</local-command-stdout>"))
        if said.startswith("Model '"):
            return
        data = json.loads(self.settings.read_text()) if self.settings.exists() else {}
        data[{"model": "model", "effort": "effortLevel"}[name]] = value
        data["other"] = "changed meanwhile"
        self.settings.write_text(json.dumps(data, indent=2) + "\n")

    def __call__(self, *args):
        self.calls.append(args)
        out = ""
        if args[1:3] == ("agent", "prompt"):
            if self.prompt_rc:
                return subprocess.CompletedProcess(args, self.prompt_rc, "", "agent_blocked")
            name, _, value = args[4].lstrip("/").partition(" ")
            if name == "model" and self.dialog:
                self.up, self.pending = True, value
            elif self.records:
                self.landed(name, value)
        elif args[1:3] == ("pane", "read"):
            out = BOX.format(self.box) if "detection" in args else (
                "Switch model?\n 1. Yes" if self.up else "")
        elif args[1:3] == ("pane", "send-keys") and self.up and not self.stuck:
            self.up = False
            if self.records:
                self.landed("model", self.pending)
        return subprocess.CompletedProcess(args, 0, out, "")

    def prompts(self):
        return [a[4] for a in self.calls if a[1:3] == ("agent", "prompt")]


@contextlib.contextmanager
def session(m, default=DEFAULT, status="idle", **kw):
    """A transcript file the script's reader finds, a settings file holding
    `default` (None: no file), one planner listed at `status`, and `m.run`
    playing its pane."""
    with tempfile.TemporaryDirectory() as d:
        path, settings = Path(d) / "s.jsonl", Path(d) / "conf" / "settings.json"
        path.write_text(assistant("2026-09-14T04:00:00.000Z", "claude-fable-5-1") + "\n")
        settings.parent.mkdir()
        if default is not None:
            settings.write_text(json.dumps(default, indent=2) + "\n")
        pane = Pane(path, settings, **kw)
        m.run, m.sleep, m.SETTINGS = pane, (lambda s: None), settings
        m.heartbeat.transcript_path = lambda sid: (path, None)
        m.names.herdr_sessions = lambda: ({"a": row("rc-planner-1", "p1", status)}, None)
        try:
            yield pane
        finally:
            settings.parent.chmod(0o755)


@contextlib.contextmanager
def live(m):
    """`main` run for real: HERDR_ENV set, this session's own pane another one."""
    saved = {k: os.environ.get(k) for k in ("HERDR_ENV", "HERDR_PANE_ID")}
    os.environ.update(HERDR_ENV="1", HERDR_PANE_ID="p9")
    try:
        yield
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def run_main(m, *argv):
    """(exit status, what it printed). A raise is an exit of its own, `None`,
    so a case asserts on what happened before it rather than crashing."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = m.main(list(argv))
        except Exception as e:  # noqa: BLE001 -- the script's raise is the observation
            rc = None
            print(f"raised {e.__class__.__name__}: {e}", file=err)
    return rc, out.getvalue() + err.getvalue()


def no_handoff(pane):
    """Nothing a hand-off does: every prompt is /model or /effort, and no
    herdr verb starts, exits or closes anything."""
    bad = [a for a in pane.calls if a[1:3] not in (
        ("agent", "prompt"), ("pane", "read"), ("pane", "send-keys"))]
    bad += [p for p in pane.prompts() if p.split()[0] not in ("/model", "/effort")]
    return bad


def case_runs(m):
    """The runs of one command, read through the heartbeat's reader."""
    r = m.heartbeat.transcript_reading([
        user("<command-name>/model</command-name>"), user("<local-command-stdout>Set model to `Opus 5`</local-command-stdout>"),
        user("<command-name>/effort</command-name>"), user("<command-name>/model</command-name>")])
    return m.runs(r, "model") == ["Set model to `Opus 5`", None], r["commands"]


def case_address(m):
    sessions = {"a": row("rc-planner-1", "p1"), "b": row("rc-worker-2", "p2"),
                "c": row("hd-planner-3", "p3"), "d": row("hd-planner-4", "p4"),
                "e": row("nobody", "p5"), "f": row("tc-planner-6", "p6"),
                "g": row("tc-planner-7", "p7")}
    fable, opus = {"model": "claude-fable-5-1"}, {"model": "claude-opus-5"}
    facts = {"a": (fable, None), "b": (fable, None), "c": (opus, None),
             "d": (fable, None), "e": (fable, None), "f": (None, "no transcript"),
             "g": ({"model": None}, None)}
    got = {r["pane"]: why for _, r, why in m.address(sessions, "planner", "p4", facts, "fable")}
    ok = (got["p1"] is None and has(got["p2"], "another role")
          and has(got["p3"], "claude-opus-5") and has(got["p4"], "own pane")
          and has(got["p5"], "no role word") and has(got["p6"], "no transcript")
          and has(got["p7"], "unknown"))
    every = {r["pane"] for _, r, why in m.address(sessions, "planner", None, facts, None) if why is None}
    return ok and every == {"p1", "p3", "p4", "p6", "p7"}, (got, every)


def case_fresh(m):
    with session(m) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        return (ok and pane.prompts() == ["/model opus", "/effort high"]
                and "dialog" not in said and not no_handoff(pane)), (said, pane.calls)


def case_dialog(m):
    with session(m, dialog=True) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        keys = [i for i, a in enumerate(pane.calls) if a[1:3] == ("pane", "send-keys")]
        effort = [i for i, a in enumerate(pane.calls) if a[-1:] == ("/effort high",)]
        return (ok and has(said, "dialog answered") and len(keys) == 1
                and effort and effort[0] > keys[0] and not no_handoff(pane)), (said, pane.calls)


def case_no_record(m):
    with session(m, records=False) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        return (not ok and pane.prompts() == ["/model opus"]
                and has(said, "may still land")), (said, pane.prompts())


def case_rejected(m):
    """A `/model` that printed a refusal fails at once, with what it printed."""
    with session(m, rejects=True) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opsu", "high")
        return (not ok and has(said, "not found") and pane.prompts() == ["/model opsu"]), said


def case_already_counted(m):
    """A transcript already holding a confirmed /model run is not a confirmation."""
    with session(m, records=False) as pane:
        pane.append(user("<command-name>/model</command-name>"),
                    user(f"<local-command-stdout>{printed('model', 'opus')}</local-command-stdout>"))
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", None)
        return not ok, said


def case_blocked(m):
    with session(m, prompt_rc=1) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        return not ok and has(said, "exited 1") and pane.prompts() == ["/model opus"], said


def case_ready(m):
    with session(m):
        idle = m.ready("a")[1]
    with session(m, status="working"):
        busy = m.ready("a")[1]
        gone = m.ready("zz")[1]
    with session(m, box=" half typed"):
        typed = m.ready("a")[1]
    return (idle is None and has(busy, "not idle") and has(gone, "gone")
            and has(typed, "half typed")), (idle, busy, gone, typed)


def case_main(m):
    """A word with a space is refused before anything is read; a dry run
    prompts nothing, leaves the default alone and prints it."""
    refused, _ = run_main(m, "--role", "planner", "--to", "opus x", "--dry-run")
    with session(m) as pane:
        rc, out = run_main(m, "--role", "planner", "--to", "opus", "--from", "fable", "--dry-run")
        return (refused == 1 and rc == 0 and not pane.prompts()
                and "address  p1" in out
                and "default before: model='claude-fable-5-1[1m]'" in out
                and json.loads(pane.settings.read_text()) == DEFAULT), out


def case_busy_skipped(m):
    """A target that started a turn after the first listing is skipped by the
    fresh read, prompted nothing, and fails the run."""
    with session(m) as pane, live(m):
        calls = []

        def listing():
            calls.append(1)
            return {"a": row("rc-planner-1", "p1", "idle" if len(calls) == 1 else "working")}, None
        m.names.herdr_sessions = listing
        rc, out = run_main(m, "--role", "planner", "--to", "opus")
        return (rc == 1 and not pane.prompts() and "not idle" in out
                and "1 skipped" in out), (rc, out)


def case_unsettled(m):
    """A dialog an Enter did not close is named, and the run warns that the
    switch may still land after the default is put back."""
    with session(m, dialog=True, stuck=True) as pane, live(m):
        rc, out = run_main(m, "--role", "planner", "--to", "opus")
        return (rc == 1 and "the dialog is still up" in out
                and "warning: a switch not confirmed in p1" in out), (rc, out)


def case_restore(m):
    """The default the switches rewrote is put back, a key changed meanwhile
    survives, and the values before and after are printed."""
    with session(m, dialog=True) as pane, live(m):
        rc, out = run_main(m, "--role", "planner", "--to", "opus", "--effort", "max")
        data = json.loads(pane.settings.read_text())
        return (rc == 0 and pane.prompts() == ["/model opus", "/effort max"]
                and data == dict(DEFAULT, other="changed meanwhile")
                and "model='opus' effortLevel='max' -> model='claude-fable-5-1[1m]' effortLevel='high'" in out
                and not no_handoff(pane)), (rc, data, out)


def case_restore_absent(m):
    """A key the default did not hold is removed again, not left behind."""
    with session(m, default={"model": "opus"}) as pane, live(m):
        rc, out = run_main(m, "--role", "planner", "--to", "sonnet", "--effort", "low")
        data = json.loads(pane.settings.read_text())
        return rc == 0 and data == {"model": "opus", "other": "changed meanwhile"}, (rc, data, out)


def case_somebody_else(m):
    """A key holding what this run did not write is somebody else's: left as
    it is, named, and the run fails; the key this run wrote still goes back."""
    with session(m) as pane, live(m):
        real = pane.landed

        def and_somebody_else(name, value):
            real(name, value)
            data = json.loads(pane.settings.read_text())
            data["model"] = "opus[1m]"
            pane.settings.write_text(json.dumps(data, indent=2) + "\n")
        pane.landed = and_somebody_else
        rc, out = run_main(m, "--role", "planner", "--to", "opus", "--effort", "max")
        data = json.loads(pane.settings.read_text())
        return (rc == 1 and data["model"] == "opus[1m]" and data["effortLevel"] == "high"
                and "left model='opus[1m]'" in out), (rc, data, out)


def case_restore_fails(m):
    """A write-back that fails is reported and fails the run."""
    with session(m) as pane, live(m):
        real = pane.landed

        def landed_then_lock(name, value):
            real(name, value)
            pane.settings.parent.chmod(0o555)
        pane.landed = landed_then_lock
        rc, out = run_main(m, "--role", "planner", "--to", "opus")
        return rc == 1 and "FAILED to put back the default" in out, (rc, out)


def case_unreadable(m):
    """No settings to read: refused before any prompt, since nothing could be put back."""
    with session(m, default=None) as pane, live(m):
        rc, out = run_main(m, "--role", "planner", "--to", "opus")
        return rc == 1 and not pane.prompts() and "could not be read" in out, (rc, out)


def case_no_git(m):
    """The DECISION's last line: the script runs no git, so it cannot commit ~/.claude."""
    return '"git"' not in m.source_text and "'git'" not in m.source_text, "a git call in the source"


CASES = {"runs": case_runs, "address": case_address, "fresh": case_fresh,
         "dialog": case_dialog, "no record": case_no_record, "rejected": case_rejected,
         "already counted": case_already_counted, "blocked": case_blocked,
         "ready": case_ready, "main": case_main, "busy skipped": case_busy_skipped,
         "unsettled": case_unsettled, "restore": case_restore,
         "restore absent": case_restore_absent, "somebody else": case_somebody_else,
         "restore fails": case_restore_fails, "unreadable": case_unreadable,
         "no git": case_no_git}

MUTATIONS = [
    ("another command's runs counted", "if cmd == name]", "]", "runs"),
    ("own pane addressed", "elif row[\"pane\"] == own_pane:", "elif False:", "address"),
    ("--from ignored", "elif frm and frm.lower() not in", "elif False and frm.lower() not in", "address"),
    ("dialog left up", 'run("herdr", "pane", "send-keys", pane, "enter")', "None", "dialog"),
    ("a refusal read as a switch", "if new[0].startswith(CONFIRM[name]):", "if True:", "rejected"),
    ("an earlier run counted", "new = runs(f, name)[before:]", "new = runs(f, name)", "already counted"),
    ("/effort sent after a failed /model", "if not ok or not effort:", "if not effort:", "no record"),
    ("prompt failure ignored", "if r.returncode != 0:\n        return False, (f\"`herdr agent prompt`",
     "if False:\n        return False, (f\"`herdr agent prompt`", "blocked"),
    ("busy pane prompted", "if not assign.idle_verdict(row)[0]:", "if False:", "ready"),
    ("the first listing trusted", "fresh, not_ready = ready(sid)", "fresh, not_ready = row, None", "busy skipped"),
    ("a skip read as success", "return 1 if failed or skipped or not restored else 0",
     "return 1 if failed or not restored else 0", "busy skipped"),
    ("the late switch not warned", "            if unsettled:", "            if False:", "unsettled"),
    ("dry run sends", "            if args.dry_run:\n                print(f\"  address",
     "            if False:\n                print(f\"  address", "main"),
    ("default never put back", "restored, said = restore_default(SETTINGS, saved, sent)",
     "restored, said = True, 'skipped'", "restore"),
    ("an absent key left behind", "data.pop(k, None)", "None", "restore absent"),
    ("somebody else's value overwritten", "back = {k: saved[k] for k in sent if now[k] == sent[k]}",
     "back = {k: saved[k] for k in sent}", "somebody else"),
    ("a failed write-back swallowed", "return 1 if failed or skipped or not restored else 0",
     "return 1 if failed or skipped else 0", "restore fails"),
    ("unreadable settings not refused", "if saved is None:", "if False:", "unreadable"),
    ("a git call added", "sleep = time.sleep\n", "sleep = time.sleep\nCOMMIT = (\"git\", \"commit\")\n", "no git"),
]


def main():
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
