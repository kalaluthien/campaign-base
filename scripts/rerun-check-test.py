#!/usr/bin/env python3
# witnesses: M2c_AFreshReviewAfterThePushLands
"""Prove rerun-check re-runs `check` exactly when a REVIEW names the head.

One case per branch the script takes, each named after it, and each asserting
on the word and on whether `gh run rerun` was called -- the two things a
mutation of that branch changes. M2c is the scenario: a review taken after the
push still lands, and this is what makes it land without a hand step.

NO CASE REACHES THE NETWORK. `gh` is a script this writes onto PATH which
answers from a JSON state file and logs every call it gets, so a case can say
which calls were made and not only what came back. Every case runs the real
script end to end, and the real check-merge-review.py behind it, because the
gate's verdict is the input this script is about.

Usage: scripts/rerun-check-test.py
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "rerun-check.py"
CHECK_YML = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "check.yml"
HEAD = "8ca2609f3b1d4e7a9c0b25d8e6f41a3b7c9d0e2f"
OTHER = "fb1bd4f2a7c3e59018d4b6f0a2c8e1d7b3f9a0c5e"
BRANCH = "rule-check/274-review-rerun"
RUN_ID = 34464501480
RAN, FAILED = [], []

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path))
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(args) + "\n")
line = " ".join(args)

def out(value, status=0):
    print(value if isinstance(value, str) else json.dumps(value))
    sys.exit(status)

def pop(key):
    seq = state[key]
    now = seq.pop(0) if len(seq) > 1 else seq[0]
    json.dump(state, open(state_path, "w"))
    return now

# Only the fields asked for, as gh answers: a query that forgets one must not
# be handed it.
def asked(answer):
    fields = args[args.index("--json") + 1].split(",")
    return {k: v for k, v in answer.items() if k in fields}

if args[:2] == ["pr", "view"]:
    head = pop("heads")
    out(asked({"headRefOid": head, "headRefName": state.get("branch", "")}) if head else {})
if args[:1] == ["api"]:
    body = state.get("comments", []) if "/issues/" in line else []
    out(body, state.get("api_status", 0))
if args[:2] == ["run", "list"]:
    out(state.get("runs", []), state.get("list_status", 0))
if args[:2] == ["run", "view"]:
    now = pop("views")
    out(asked(now) if isinstance(now, dict) else now, state.get("view_status", 0))
if args[:2] == ["run", "rerun"]:
    out("", state.get("rerun_status", 0))
sys.stderr.write("fake gh: no answer for " + line + "\n")
sys.exit(99)
'''


def gate_step():
    spec = importlib.util.spec_from_loader(
        "rerun_check", importlib.machinery.SourceFileLoader("rerun_check", str(SCRIPT)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GATE_STEP


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


def review(sha):
    return {"user": {"login": "kalaluthien"},
            "body": f"REVIEW rule-check-worker-9: narrowed round at {sha[:7]}, no findings"}


def view(status, conclusion="", failed=()):
    """A `gh run view --json status,conclusion,jobs` answer. A skipped step in
    every one, since a real run has them (34478543559 has two) and a step that
    did not fail must not be read as one that did."""
    steps = [{"name": "Every suite", "conclusion": "success"},
             {"name": "Fetch the Alloy jar", "conclusion": "skipped"}]
    steps += [{"name": n, "conclusion": "failure"} for n in failed]
    return {"status": status, "conclusion": conclusion,
            "jobs": [{"name": "check", "steps": steps}]}


def state(heads=(HEAD,), reviewed=True, views=None, **extra):
    s = {"heads": list(heads), "branch": BRANCH,
         "comments": [review(HEAD if reviewed else OTHER)],
         "runs": [{"databaseId": RUN_ID}],
         "views": views or [view("completed", "failure", [gate_step()])]}
    s.update(extra)
    return s


def call(root, st, *args):
    """(word, returncode, everything printed, the gh calls made)."""
    (root / "state.json").write_text(json.dumps(st))
    log = root / "gh.log"
    log.write_text("")
    env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
               FAKE_GH_STATE=str(root / "state.json"), FAKE_GH_LOG=str(log))
    argv = list(args) or ["274", "--repo", "o/r", "--poll", "0", "--polls", "3"]
    try:
        p = subprocess.run([str(SCRIPT), *argv], capture_output=True, text=True,
                           env=env, timeout=30)
    except subprocess.TimeoutExpired:
        return "timeout", None, "", log.read_text().splitlines()
    text = (p.stdout or "") + (p.stderr or "")
    word = text.split(" ", 1)[0].strip() if text else ""
    return word, p.returncode, text, log.read_text().splitlines()


def reran(calls):
    return [c for c in calls if c.startswith("run rerun")]


def expect(name, got, word, code, rerun):
    w, c, text, calls = got
    want = [f"run rerun {RUN_ID} -R o/r"] if rerun else []
    check(name, (w, c, reran(calls)) == (word, code, want),
          f"{w} {c} {reran(calls)} :: {text[:200]}")


def main() -> int:
    # The step name this script waits on is the one check.yml gives the gate.
    # Renamed there alone, every red run would read `red` and none re-run.
    check("GATE_STEP names a step in check.yml",
          f"- name: {gate_step()}\n" in CHECK_YML.read_text(), gate_step())

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "bin").mkdir()
        gh = root / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)

        # The ordinary comment on a pull request nobody has reviewed at its
        # head. Nothing to re-run, and not a failure.
        got = call(root, state(reviewed=False))
        expect("no REVIEW at the head is unreviewed, and nothing is re-run",
               got, "unreviewed", 0, False)
        check("...and it never looked for a run to re-run",
              not [c for c in got[3] if c.startswith("run list")], str(got[3]))

        got = call(root, state(api_status=1))
        expect("a gate that could not look is unknown, and nothing is re-run",
               got, "unknown", 2, False)

        got = call(root, state(heads=[None]))
        expect("a pull request with no readable head is unknown", got, "unknown", 2, False)
        check("...and says it was the head, not a crash",
              "headRefOid" in got[2] and "crashed" not in got[2], got[2])

        got = call(root, state(), "274", "--polls", "many")
        expect("a bad argument is unknown, the word still first", got, "unknown", 2, False)
        check("...and says it was the arguments, not a crash",
              "arguments:" in got[2] and "crashed" not in got[2], got[2])

        # THE BRANCH THIS EXISTS FOR: reviewed at the head, and the run for
        # that head failed at the gate alone because it read the comments
        # before the REVIEW was posted.
        got = call(root, state())
        expect("a REVIEW at the head re-runs a run red at the gate alone",
               got, "rerun", 0, True)
        lists = [c for c in got[3] if c.startswith("run list")]
        check("...and the run it looked for is this pull request's, at the head",
              len(lists) == 1 and all(f in lists[0] for f in
                                      (f"--commit {HEAD}", f"--branch {BRANCH}",
                                       "--event pull_request")), str(lists))

        # Red somewhere else too: a re-run replays the whole job to the same
        # red, on every later comment.
        got = call(root, state(views=[view("completed", "failure",
                                           ["Every command comes out as its `expect` clause says",
                                            gate_step()])]))
        expect("a run red at another step as well is red, and not re-run",
               got, "red", 0, False)
        got = call(root, state(views=[view("completed", "cancelled")]))
        expect("a run that ended with no failed step is red, and not re-run",
               got, "red", 0, False)

        got = call(root, state(views=[view("completed", "success")]))
        expect("a green run at the head is left alone", got, "green", 0, False)

        got = call(root, state(runs=[]))
        expect("no run for the head is no-run, and nothing is re-run", got, "no-run", 0, False)

        # Still running when the REVIEW arrives: its gate step may already
        # have read the comments, so wait for it to finish and then judge.
        got = call(root, state(views=[view("in_progress"),
                                      view("completed", "failure", [gate_step()])]))
        expect("a run in progress is waited for, then re-run when it ends red",
               got, "rerun", 0, True)
        check("...having polled it rather than re-running at once",
              len([c for c in got[3] if c.startswith("run view")]) >= 2, str(got[3]))

        # A push during the wait: the run waited for is no longer the head's.
        got = call(root, state(heads=[HEAD, HEAD, OTHER],
                               views=[view("in_progress"),
                                      view("completed", "failure", [gate_step()])]))
        expect("a branch that moved during the wait is moved, and not re-run",
               got, "moved", 0, False)

        got = call(root, state(heads=[HEAD, HEAD, None],
                               views=[view("in_progress"),
                                      view("completed", "failure", [gate_step()])]))
        expect("a head unreadable after the wait is unknown, and not re-run",
               got, "unknown", 2, False)
        check("...and says it was the head, not a crash",
              "headRefOid" in got[2] and "crashed" not in got[2], got[2])

        got = call(root, state(views=[view("in_progress")]))
        expect("a run still going after the last poll is unknown, not re-run",
               got, "unknown", 2, False)
        check("...and it says how many polls it made", "3 poll(s)" in got[2], got[2])

        got = call(root, state(list_status=1))
        expect("a run list that failed is unknown", got, "unknown", 2, False)
        check("...and names the call that failed",
              "gh run list" in got[2] and "exited 1" in got[2], got[2])

        got = call(root, state(runs={"databaseId": RUN_ID}))
        expect("a run list that is not a list is unknown", got, "unknown", 2, False)
        check("...and says so", "not a list" in got[2], got[2])

        got = call(root, state(view_status=1))
        expect("a run view that failed is unknown", got, "unknown", 2, False)
        check("...and names the call that failed",
              "gh run view" in got[2] and "exited 1" in got[2], got[2])

        got = call(root, state(views=[[1, 2]]))
        expect("a run view that is not an object is unknown", got, "unknown", 2, False)
        check("...and says what it answered", "answered [1, 2]" in got[2], got[2])

        got = call(root, state(rerun_status=1))
        expect("a re-run GitHub refused is unknown", got, "unknown", 2, True)
        check("...and names the re-run as what was refused", "gh run rerun" in got[2], got[2])

    for name in FAILED:
        print(f"FAIL {name}")
    print(f"rerun-check-test: {len(RAN) - len(FAILED)}/{len(RAN)} passed")
    return 1 if FAILED or not RAN else 0


if __name__ == "__main__":
    sys.exit(main())
