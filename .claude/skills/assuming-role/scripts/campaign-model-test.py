#!/usr/bin/env python3
# witnesses: ModelSwitchKeepsEverySession, Cov_ModelSwitch
"""Prove campaign-model addresses exactly one role's panes, switches each in
place, and never does what a hand-off does.

The pane side goes through a fake `run` that records every herdr call and
plays a session: a fresh one records `/model` at once, one with history
shows the `Switch model?` dialog until an Enter answers it -- the two shapes
probed on rule-check#431. The transcript is a real file the fake appends to,
so the script's own reader confirms the switch. What `ModelSwitchKeepsEverySession`
says of the model is checked of the calls: nothing but `/model` and `/effort`
is ever prompted, and no pane is started, exited or closed.

Then every branch is broken in turn on the script's source, loaded with its
real path so its siblings resolve, and the case named for it must go red by
its own assertion.

Usage: .claude/skills/assuming-role/scripts/campaign-model-test.py
"""
import contextlib
import importlib
import io
import json
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
    return m


def assistant(ts, model, **kw):
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"model": model}, **kw})


def command(name, args):
    return json.dumps({"type": "user", "timestamp": "2026-09-14T05:00:00Z",
                       "message": {"content": f"<command-name>/{name}</command-name>"
                                              f" <command-args>{args}</command-args>"}})


def has(text, part):
    """`part` in `text`, False when there is no text: a branch that returned
    None must fail its case by assertion, not crash it."""
    return text is not None and part in text


def row(name, pane, status="idle"):
    return {"name": name, "pane": pane, "status": status, "cwd": "/b"}


BOX = "─" * 20 + "\n❯{}\n" + "─" * 20 + "\n"


class Pane:
    """A fake `run` over one pane and one transcript file. `dialog` is a
    session with history; `records` False is one whose switch never lands."""

    def __init__(self, path, dialog=False, records=True, prompt_rc=0, box=""):
        self.path, self.dialog, self.records = path, dialog, records
        self.prompt_rc, self.box = prompt_rc, box
        self.calls, self.up = [], False

    def append(self, line):
        with open(self.path, "a") as fh:
            fh.write(line + "\n")

    def __call__(self, *args):
        self.calls.append(args)
        out = ""
        if args[1:3] == ("agent", "prompt"):
            if self.prompt_rc:
                return subprocess.CompletedProcess(args, self.prompt_rc, "", "agent_blocked")
            name, _, value = args[4].lstrip("/").partition(" ")
            if name == "model" and self.dialog:
                self.up = True
            elif self.records:
                self.append(command(name, value))
        elif args[1:3] == ("pane", "read"):
            out = BOX.format(self.box) if "detection" in args else (
                "Switch model?\n 1. Yes" if self.up else "")
        elif args[1:3] == ("pane", "send-keys") and self.up:
            self.up = False
            if self.records:
                self.append(command("model", "opus"))
        return subprocess.CompletedProcess(args, 0, out, "")

    def prompts(self):
        return [a[4] for a in self.calls if a[1:3] == ("agent", "prompt")]


@contextlib.contextmanager
def session(m, **kw):
    """A transcript file the script's reader finds, and `m.run` playing its pane."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "s.jsonl"
        path.write_text(assistant("2026-09-14T04:00:00Z", "claude-fable-5-1") + "\n")
        pane = Pane(path, **kw)
        m.run, m.sleep = pane, (lambda s: None)
        m.heartbeat.transcript_path = lambda sid: (path, None)
        yield pane


def no_handoff(pane):
    """Nothing a hand-off does: every prompt is /model or /effort, and no
    herdr verb starts, exits or closes anything."""
    bad = [a for a in pane.calls if a[1:3] not in (
        ("agent", "prompt"), ("pane", "read"), ("pane", "send-keys"))]
    bad += [p for p in pane.prompts() if p.split()[0] not in ("/model", "/effort")]
    return bad


def case_facts(m):
    lines = [assistant("2026-09-14T01:00:00Z", "claude-fable-5-1"),
             assistant("2026-09-14T03:00:00Z", "claude-opus-5"),
             assistant("2026-09-14T02:00:00Z", "claude-sonnet-5"),
             assistant("2026-09-14T04:00:00Z", "<synthetic>"),
             assistant("2026-09-14T05:00:00Z", "claude-haiku-4-5", isSidechain=True),
             command("model", "opus"), command("effort", "high"), "not json"]
    f = m.transcript_facts(lines)
    want = {"model": "claude-opus-5", "model_cmds": 1, "effort_cmds": 1}
    return {k: f[k] for k in want} == want, f


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
        return (ok and "dialog answered" in said and len(keys) == 1
                and effort and effort[0] > keys[0] and not no_handoff(pane)), (said, pane.calls)


def case_no_record(m):
    with session(m, records=False) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        return (not ok and pane.prompts() == ["/model opus"]
                and "no /model record" in said), (said, pane.prompts())


def case_already_counted(m):
    """A transcript already holding a /model record is not a confirmation."""
    with session(m, records=False) as pane:
        pane.append(command("model", "opus"))
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", None)
        return not ok, said


def case_blocked(m):
    with session(m, prompt_rc=1) as pane:
        ok, said = m.switch(row("rc-planner-1", "p1"), "a", "opus", "high")
        return not ok and "exited 1" in said and pane.prompts() == ["/model opus"], said


def case_ready(m):
    with session(m, box="") as pane:
        idle = m.ready(row("rc-planner-1", "p1"))
        busy = m.ready(row("rc-planner-1", "p1", status="working"))
    with session(m, box=" half typed") as pane:
        typed = m.ready(row("rc-planner-1", "p1"))
    return (idle is None and has(busy, "not idle") and has(typed, "half typed")), (idle, busy, typed)


def case_main(m):
    """A word with a space is refused before anything is read; a dry run
    prompts nothing and still names the settings rewrite."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        refused = m.main(["--role", "planner", "--to", "opus x", "--dry-run"])
    with session(m) as pane:
        m.names.herdr_sessions = lambda: ({"a": row("rc-planner-1", "p1")}, None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = m.main(["--role", "planner", "--to", "opus", "--from", "fable", "--dry-run"])
        return (refused == 1 and rc == 0 and not pane.prompts()
                and "address  p1" in out.getvalue()
                and "settings.json" in out.getvalue()), (err.getvalue(), out.getvalue())


CASES = {"facts": case_facts, "address": case_address, "fresh": case_fresh,
         "dialog": case_dialog, "no record": case_no_record,
         "already counted": case_already_counted, "blocked": case_blocked,
         "ready": case_ready, "main": case_main}

MUTATIONS = [
    ("sidechain read as the session", 'or r.get("isSidechain")', "", "facts"),
    ("synthetic read as a model", 'model != "<synthetic>"', "True", "facts"),
    ("own pane addressed", "elif row[\"pane\"] == own_pane:", "elif False:", "address"),
    ("--from ignored", "elif frm and frm.lower() not in", "elif False and frm.lower() not in", "address"),
    ("dialog left up", 'run("herdr", "pane", "send-keys", pane, "enter")', "None", "dialog"),
    ("an earlier record counted", "f[counter] > before", "f[counter] >= before", "already counted"),
    ("/effort sent after a failed /model", "if not ok or not effort:", "if not effort:", "no record"),
    ("prompt failure ignored", "if r.returncode != 0:\n        return False, (f\"`herdr agent prompt`",
     "if False:\n        return False, (f\"`herdr agent prompt`", "blocked"),
    ("busy pane prompted", "if not assign.idle_verdict(row)[0]:", "if False:", "ready"),
    ("dry run sends", "        if args.dry_run:\n            print(f\"  address", "        if False:\n            print(f\"  address", "main"),
]


def main():
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
