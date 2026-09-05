#!/usr/bin/env python3
"""Cases for campaign-name-session.py, run against a fake `herdr` on PATH.

The fake records every call to a log and answers `agent list` with whatever
status the case asks for, so each case pins one branch: the name rule, the
one-prompt-per-pane refusal, and the three wordings the pane's status decides.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("campaign-name-session.py")

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(args) + "\n")
if args[:2] == ["agent", "list"]:
    if os.environ.get("FAKE_LIST_FAILS"):
        print("list broke", file=sys.stderr); sys.exit(1)
    agents = json.loads(os.environ.get("FAKE_AGENTS", "[]"))
    print(json.dumps({"result": {"agents": agents}}))
elif args[:2] == ["agent", "rename"]:
    if os.environ.get("FAKE_RENAME_FAILS"):
        print("rename broke", file=sys.stderr); sys.exit(1)
    print(json.dumps({"result": {"agent": {"name": args[3]}}}))
elif args[:2] == ["agent", "prompt"]:
    if os.environ.get("FAKE_PROMPT_FAILS"):
        print("prompt broke", file=sys.stderr); sys.exit(1)
    print(json.dumps({"result": {"type": "agent_prompted"}}))
else:
    sys.exit(1)
'''


def run(argv, agents=None, list_fails=False, rename_fails=False,
        prompt_fails=False):
    """(completed process, list of recorded herdr calls)."""
    with tempfile.TemporaryDirectory() as d:
        bin_dir = Path(d) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "herdr"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        log = Path(d) / "calls"
        env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                   FAKE_LOG=str(log), FAKE_AGENTS=json.dumps(agents or []))
        if list_fails:
            env["FAKE_LIST_FAILS"] = "1"
        if rename_fails:
            env["FAKE_RENAME_FAILS"] = "1"
        if prompt_fails:
            env["FAKE_PROMPT_FAILS"] = "1"
        r = subprocess.run([sys.executable, str(SCRIPT), *argv], env=env,
                           capture_output=True, text=True)
        calls = ([json.loads(l) for l in log.read_text().splitlines()]
                 if log.exists() else [])
        return r, calls


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}  {detail}".rstrip())

    def prompts(calls):
        return [c for c in calls if c[:2] == ["agent", "prompt"]]

    r, calls = run(["w1:p1", "campaign-1-reviewer-1"])
    check("a role the rule does not admit is refused with nothing applied",
          r.returncode == 1 and not calls and "reviewer" in r.stderr,
          f"exit {r.returncode} calls {calls}")

    # THE RETIRED ROLE WORD. `executor` was a role this pattern admitted until
    # #185's rename; nothing but the alternation refuses it now, so this case
    # is the alternation's only reader. Put `executor` back and it is the one
    # that reddens. The assertion is on the message and not the exit status:
    # every other bad name exits 1 too, and what a session carrying the old
    # word needs told is the word that replaced it.
    r, calls = run(["w1:p1", "campaign-1-executor-5"])
    check("the retired role word `executor` is refused, and the message names "
          "`worker`",
          r.returncode == 1 and not calls
          and "campaign-1-executor-5" in r.stderr and "worker" in r.stderr,
          f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    r, calls = run(["w1:p1", "campaign-1-worker-5"],
                   agents=[{"pane_id": "w1:p1", "agent_status": "idle"}])
    check("...and the word that replaced it is admitted beside it",
          r.returncode == 0 and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename campaign-1-worker-5",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "campaign-1-planner-1", "w1:p1", "campaign-1-worker-3"])
    check("one pane named twice is refused before anything is applied",
          r.returncode == 1 and not calls and "named more than once" in r.stderr,
          f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    r, calls = run(["w1:p1", "campaign-1-worker-3", "w1:p2", "campaign-1-reviewer-1"])
    check("a bad name in the last pair leaves the first pair unapplied too",
          r.returncode == 1 and not calls, f"exit {r.returncode} calls {calls}")

    idle = [{"pane_id": "w1:p1", "agent_status": "idle"}]
    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=idle)
    check("an idle pane's rename is reported as sent",
          r.returncode == 0 and "/rename sent (confirm" in r.stdout
          and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename campaign-1-worker-3",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")
    check("...and both names were set: herdr rename, then list, then prompt",
          [c[:2] for c in calls] == [["agent", "rename"], ["agent", "list"],
                                     ["agent", "prompt"]]
          and calls[0][2:] == ["w1:p1", "campaign-1-worker-3"],
          f"calls {calls}")

    done = [{"pane_id": "w1:p1", "agent_status": "done"}]
    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=done)
    check("a done pane is idle by herdr's own definition, so it reads as sent",
          r.returncode == 0 and "/rename sent (confirm" in r.stdout
          and "queued" not in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r}")

    blocked = [{"pane_id": "w1:p1", "agent_status": "blocked"}]
    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=blocked)
    check("a blocked pane gets the herdr name and no prompt, exit 2",
          r.returncode == 2 and "NOT sent" in r.stdout and "blocked" in r.stdout
          and not prompts(calls)
          and [c[:2] for c in calls] == [["agent", "rename"], ["agent", "list"]],
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=idle, rename_fails=True)
    check("a failed herdr rename is reported, sends no prompt for that pane, exit 2",
          r.returncode == 2 and "herdr name  FAILED: rename broke" in r.stdout
          and not prompts(calls), f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=idle, prompt_fails=True)
    check("a failed herdr prompt is reported after the herdr name applied, exit 2",
          r.returncode == 2 and "harness     FAILED: prompt broke" in r.stdout
          and "herdr name  campaign-1-worker-3" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    working = [{"pane_id": "w1:p1", "agent_status": "working"}]
    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=working)
    check("a working pane's rename is sent once and reported as queued",
          r.returncode == 0 and "/rename queued: the pane is working" in r.stdout
          and "merges into the name" in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "campaign-1-worker-3"], list_fails=True)
    check("an unreadable agent list is said, and the rename is still sent",
          r.returncode == 0 and "status could not be read" in r.stdout
          and "list broke" in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "campaign-1-worker-3"], agents=idle[:0])
    check("a pane absent from the list is said, not read as idle",
          r.returncode == 0 and "not in herdr agent list" in r.stdout
          and "/rename sent (confirm" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    two = [{"pane_id": "w1:p1", "agent_status": "idle"},
           {"pane_id": "w1:p2", "agent_status": "working"}]
    r, calls = run(["w1:p1", "campaign-1-worker-3", "w1:p2", "campaign-1-planner-4"],
                   agents=two)
    check("two different panes in one call each get one prompt and their own wording",
          r.returncode == 0 and len(prompts(calls)) == 2
          and "w1:p1  harness     /rename sent" in r.stdout
          and "w1:p2  harness     /rename queued" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
