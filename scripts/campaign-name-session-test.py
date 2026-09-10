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

# The subject moved under the skill that owns the role machinery (#227);
# the suite stays here, where CI's `scripts/*-test.*` loop finds it, and
# resolves its subject by path as acquire-repo-test.py does.
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SCRIPT = (BASE / ".claude" / "skills" / "assuming-role" / "scripts"
          / "campaign-name-session.py")

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
elif args[:2] == ["agent", "read"]:
    # TEXT, NOT JSON, which is what herdr actually returns here, and it
    # refuses a working pane. THE SCREEN HAS TWO STATES because the subject
    # reads it twice, once before the prompt and once after: a fake with one
    # state cannot tell an echo this rename produced from one already there.
    sent = [json.loads(l) for l in open(os.environ["FAKE_LOG"])]
    prompted = [c[3] for c in sent if c[:2] == ["agent", "prompt"]]
    if os.environ.get("FAKE_READ_FAILS"):
        print("agent_busy", file=sys.stderr); sys.exit(1)
    if prompted and os.environ.get("FAKE_READ_FAILS_AFTER"):
        print("agent_busy", file=sys.stderr); sys.exit(1)
    if prompted:
        screen = os.environ.get(
            "FAKE_SCREEN_AFTER",
            # what a real session prints one turn later, inside its own
            # decoration -- the line is never alone on the screen
            "  \u23bf  Session renamed to: " + prompted[-1].split()[-1])
    else:
        screen = os.environ.get("FAKE_SCREEN", "nothing here yet")
    print(screen)
else:
    sys.exit(1)
'''


def run(argv, agents=None, list_fails=False, rename_fails=False,
        prompt_fails=False, read_fails=False, read_fails_after=False,
        screen=None, screen_after=None):
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
        if read_fails:
            env["FAKE_READ_FAILS"] = "1"
        if read_fails_after:
            env["FAKE_READ_FAILS_AFTER"] = "1"
        if screen is not None:
            env["FAKE_SCREEN"] = screen
        if screen_after is not None:
            env["FAKE_SCREEN_AFTER"] = screen_after
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

    r, calls = run(["w1:p1", "machinery-reviewer-1"])
    check("a role the rule does not admit is refused with nothing applied",
          r.returncode == 1 and not calls and "reviewer" in r.stderr,
          f"exit {r.returncode} calls {calls}")

    # THE RETIRED ROLE WORD. `executor` was a role this pattern admitted until
    # #185's rename; nothing but the alternation refuses it now, so this case
    # is the alternation's only reader. Put `executor` back and it is the one
    # that reddens. The assertion is on the message and not the exit status:
    # every other bad name exits 1 too, and what a session carrying the old
    # word needs told is the word that replaced it.
    r, calls = run(["w1:p1", "machinery-executor-5"])
    check("the retired role word `executor` is refused, and the message names "
          "`worker`",
          r.returncode == 1 and not calls
          and "machinery-executor-5" in r.stderr and "worker" in r.stderr,
          f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    r, calls = run(["w1:p1", "machinery-worker-5"],
                   agents=[{"pane_id": "w1:p1", "agent_status": "idle"}])
    check("...and the word that replaced it is admitted beside it",
          r.returncode == 0 and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename machinery-worker-5",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    # THE RETIRED CAMPAIGN TOKEN, now refused (#237). It was admitted beside
    # the slug for one window; the window closed when the last `machinery/`
    # pull request merged. Nothing refuses it by name -- `RESERVED` bars a
    # `campaign` segment, so `machinery` is simply not a slug, which is the
    # same branch the case two below reads. Both are kept: this one says what
    # a session carrying the old name is told, and that one says why.
    r, calls = run(["w1:p1", "campaign-1-worker-5"])
    check("the retired `campaign-<N>` name form is refused",
          r.returncode == 1 and not calls and "campaign-1-worker-5" in r.stderr,
          f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    r, calls = run(["w1:p1", "machinery-worker-6"],
                   agents=[{"pane_id": "w1:p1", "agent_status": "idle"}])
    check("a slug name is admitted",
          r.returncode == 0 and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename machinery-worker-6",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    # THE THREE SLUG CONDITIONS, ONE CASE EACH. Each name below fails exactly
    # one of them and satisfies the other two, so dropping any one condition
    # from `slug_ok` turns exactly one of these green.
    for name, why in [
            ("Machinery-worker-6", "not kebab-case: a capital"),
            # ONE CHARACTER OVER, not far over: a 28-character slug was
            # refused at 20 and at 10 alike, so it named no number. This one
            # goes green the moment the ceiling moves back up.
            ("abcdefghijk-worker-6",
             "over the ceiling: 11 characters of slug"),
            ("campaign-machinery-worker-6", "a `campaign` segment"),
            ("machinery-planner-worker-6", "a `planner` segment"),
            # THE BASE'S OWN DIRECTORY NAMES. A campaign slugged `spec` would
            # name a directory the base already owns, and guard-corpus -- which
            # classifies a recorded path it cannot stat -- would read that
            # campaign's whole tree as the base's own.
            ("runtime-worker-6", "a `runtime` segment"),
            ("scripts-worker-6", "a `scripts` segment"),
            # `none` IS THE WORD every reader here answers with when it found
            # nothing, so a campaign wearing it could never be scaffolded or
            # closed -- each caller would read its own slug as a failed reading.
            ("none-worker-6", "a `none` segment"),
            ("spec-worker-6", "a `spec` segment")]:
        r, calls = run(["w1:p1", name])
        check(f"a slug with {why} is refused",
              r.returncode == 1 and not calls and name in r.stderr,
              f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    # ...AND THE OTHER SIDE OF THE SAME NUMBER. Together with the 11-character
    # refusal above this pins SLUG_CEILING at 10 exactly: one of the two goes
    # red for any other value.
    r, calls = run(["w1:p1", "abcdefghij-worker-6"],
                   agents=[{"pane_id": "w1:p1", "agent_status": "idle"}])
    check("a slug at the ceiling exactly is admitted",
          r.returncode == 0 and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename abcdefghij-worker-6",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    # A NAME WITH TWO ROLE WORDS parses one way or not at all. Barring the role
    # words from the slug is what makes that true; admit them and `foo-worker-3`
    # becomes a slug and this name a valid one.
    r, calls = run(["w1:p1", "foo-worker-3-worker-5"])
    check("a name carrying two role words is refused rather than read two ways",
          r.returncode == 1 and not calls, f"exit {r.returncode} calls {calls}")

    r, calls = run(["w1:p1", "machinery-planner-1", "w1:p1", "machinery-worker-3"])
    check("one pane named twice is refused before anything is applied",
          r.returncode == 1 and not calls and "named more than once" in r.stderr,
          f"exit {r.returncode} calls {calls} err {r.stderr[:200]}")

    r, calls = run(["w1:p1", "machinery-worker-3", "w1:p2", "machinery-reviewer-1"])
    check("a bad name in the last pair leaves the first pair unapplied too",
          r.returncode == 1 and not calls, f"exit {r.returncode} calls {calls}")

    idle = [{"pane_id": "w1:p1", "agent_status": "idle"}]
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle)
    check("an idle pane's rename is waited on and reported as applied",
          r.returncode == 0
          and "/rename applied: the pane printed" in r.stdout
          and "Session renamed to: machinery-worker-3" in r.stdout
          and len(prompts(calls)) == 1
          and prompts(calls)[0][3] == "/rename machinery-worker-3",
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")
    check("...and the pane was read BEFORE the prompt as well as after",
          [c[:2] for c in calls] == [["agent", "rename"], ["agent", "list"],
                                     ["agent", "read"], ["agent", "prompt"],
                                     ["agent", "read"]]
          and calls[0][2:] == ["w1:p1", "machinery-worker-3"],
          f"calls {calls}")

    # THE ECHO ALREADY ON THE SCREEN. Renaming a pane to the name it already
    # carries is the ordinary case -- every session sets its name at start --
    # and that pane still holds the line from last time. Counted rather than
    # looked for, so the old one confirms nothing.
    stale = "  x  Session renamed to: machinery-worker-3"
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle,
                   screen=stale, screen_after=stale)
    check("an echo that was on the screen before the prompt confirms nothing",
          r.returncode == 0 and "/rename sent, not applied yet" in r.stdout
          and "were there before the prompt" in r.stdout
          and "applied:" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    # A LONGER NAME WITH THIS ONE AS ITS PREFIX. `<n>` is an unbounded digit
    # run, so `machinery-worker-1` sits inside `machinery-worker-12`'s echo and
    # a substring test would read the wrong pane's confirmation.
    r, calls = run(["w1:p1", "machinery-worker-1"], agents=idle,
                   screen_after="  x  Session renamed to: machinery-worker-12")
    check("a longer name holding this one as a prefix is not the echo",
          r.returncode == 0 and "/rename sent, not applied yet" in r.stdout
          and "applied:" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    # AND THE ECHO MUST NAME THIS NAME AT ALL. Without this, a wanted literal
    # of just `Session renamed to:` passes every case above.
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle,
                   screen_after="  x  Session renamed to: upkeep-planner-9")
    check("another session's echo on this pane is not this rename's",
          r.returncode == 0 and "/rename sent, not applied yet" in r.stdout
          and "applied:" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    # THE BASELINE ITSELF CAN FAIL, and then there is no verdict to give: a
    # missing baseline is not a baseline of zero.
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle, read_fails=True)
    check("a pane unreadable before the prompt gets no verdict, not a false one",
          r.returncode == 0
          and "could not be read before the prompt" in r.stdout
          and "agent_busy" in r.stdout and "applied:" not in r.stdout
          and "not applied yet" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    # THE TWO WAYS THE ECHO DOES NOT COME, kept apart because the caller acts
    # on them the same way and the person debugging does not: a pane that
    # printed something else, and a read herdr refused. Each asserts the reason
    # it prints, not just the wording they share -- a case asserting only
    # "not applied yet" would pass with either branch gone.
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle,
                   screen="nothing like it here",
                   screen_after="nothing like it here")
    check("a pane that never echoes is reported as sent and not applied",
          r.returncode == 0 and "/rename sent, not applied yet" in r.stdout
          and "the pane never printed it" in r.stdout
          and "applied:" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")
    check("...and the read was retried, not asked once",
          len([c for c in calls if c[:2] == ["agent", "read"]]) > 1,
          f"calls {calls}")

    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle,
                   read_fails_after=True)
    check("a read herdr refused after the prompt is a not-yet, naming what "
          "herdr said",
          r.returncode == 0 and "/rename sent, not applied yet" in r.stdout
          and "agent_busy" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    done = [{"pane_id": "w1:p1", "agent_status": "done"}]
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=done)
    check("a done pane is idle by herdr's own definition, so it is waited on",
          r.returncode == 0 and "/rename applied" in r.stdout
          and "queued" not in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r}")

    blocked = [{"pane_id": "w1:p1", "agent_status": "blocked"}]
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=blocked)
    check("a blocked pane gets the herdr name and no prompt, exit 2",
          r.returncode == 2 and "NOT sent" in r.stdout and "blocked" in r.stdout
          and not prompts(calls)
          and [c[:2] for c in calls] == [["agent", "rename"], ["agent", "list"]],
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle, rename_fails=True)
    check("a failed herdr rename is reported, sends no prompt for that pane, exit 2",
          r.returncode == 2 and "herdr name  FAILED: rename broke" in r.stdout
          and not prompts(calls), f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle, prompt_fails=True)
    check("a failed herdr prompt is reported after the herdr name applied, exit 2",
          r.returncode == 2 and "harness     FAILED: prompt broke" in r.stdout
          and "herdr name  machinery-worker-3" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    working = [{"pane_id": "w1:p1", "agent_status": "working"}]
    r, calls = run(["w1:p1", "machinery-worker-3"], agents=working)
    check("a working pane's rename is sent once and reported as queued",
          r.returncode == 0 and "/rename queued: the pane is working" in r.stdout
          and "merges into the name" in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "machinery-worker-3"], list_fails=True)
    check("an unreadable agent list is said, and the rename is still sent",
          r.returncode == 0 and "status could not be read" in r.stdout
          and "list broke" in r.stdout and len(prompts(calls)) == 1,
          f"exit {r.returncode} out {r.stdout!r} calls {calls}")

    r, calls = run(["w1:p1", "machinery-worker-3"], agents=idle[:0])
    check("a pane absent from the list is said, not read as idle",
          r.returncode == 0 and "not in herdr agent list" in r.stdout
          and "/rename sent (confirm" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    two = [{"pane_id": "w1:p1", "agent_status": "idle"},
           {"pane_id": "w1:p2", "agent_status": "working"}]
    r, calls = run(["w1:p1", "machinery-worker-3", "w1:p2", "machinery-planner-4"],
                   agents=two)
    check("two different panes in one call each get one prompt and their own wording",
          r.returncode == 0 and len(prompts(calls)) == 2
          and "w1:p1  harness     /rename applied" in r.stdout
          and "w1:p2  harness     /rename queued" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")
    # A WORKING PANE IS NOT READ AT ALL. herdr refuses `agent read` on one, and
    # the wait is scoped to the two statuses that can answer; without this case
    # the scoping could go and only a timing change would show it.
    check("...and the working pane was never read, only the idle one",
          set(c[2] for c in calls if c[:2] == ["agent", "read"]) == {"w1:p1"},
          f"calls {calls}")

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
