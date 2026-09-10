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
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "rerun-check.py"
HEAD = "8ca2609f3b1d4e7a9c0b25d8e6f41a3b7c9d0e2f"
OTHER = "fb1bd4f2a7c3e59018d4b6f0a2c8e1d7b3f9a0c5e"
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

if args[:2] == ["pr", "view"]:
    out({"headRefOid": state["head"]} if state.get("head") else {})
if args[:1] == ["api"]:
    body = state.get("comments", []) if "/issues/" in line else []
    out(body, state.get("api_status", 0))
if args[:2] == ["run", "list"]:
    out(state.get("runs", []), state.get("list_status", 0))
if args[:2] == ["run", "view"]:
    views = state["views"]
    now = views.pop(0) if len(views) > 1 else views[0]
    json.dump(state, open(state_path, "w"))
    out(now)
if args[:2] == ["run", "rerun"]:
    out("", state.get("rerun_status", 0))
sys.stderr.write("fake gh: no answer for " + line + "\n")
sys.exit(99)
'''


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


def review(sha):
    return {"user": {"login": "kalaluthien"},
            "body": f"REVIEW rule-check-worker-9: narrowed round at {sha[:7]}, no findings"}


def run_row(status, conclusion=""):
    return {"databaseId": RUN_ID, "status": status, "conclusion": conclusion}


def call(root, state):
    """(word, returncode, everything printed, the gh calls made)."""
    (root / "state.json").write_text(json.dumps(state))
    log = root / "gh.log"
    log.write_text("")
    env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
               FAKE_GH_STATE=str(root / "state.json"), FAKE_GH_LOG=str(log))
    try:
        p = subprocess.run([str(SCRIPT), "274", "--repo", "o/r", "--poll", "0",
                            "--polls", "3"], capture_output=True, text=True,
                           env=env, timeout=30)
    except subprocess.TimeoutExpired:
        return "timeout", None, "", log.read_text().splitlines()
    text = (p.stdout or "") + (p.stderr or "")
    word = text.split(" ", 1)[0].strip() if text else ""
    return word, p.returncode, text, log.read_text().splitlines()


def reran(calls):
    return [c for c in calls if c.startswith("run rerun")]


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "bin").mkdir()
        gh = root / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)

        # The ordinary comment: a NOTE or a REPORT on a pull request nobody
        # has reviewed at its head. Nothing to re-run, and not a failure.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(OTHER)],
            "runs": [run_row("completed", "failure")], "views": [{}]})
        check("no REVIEW at the head is unreviewed, and nothing is re-run",
              (word, code, reran(calls)) == ("unreviewed", 0, []),
              f"{word} {code} {reran(calls)}")
        check("...and it never looked for a run to re-run",
              not [c for c in calls if c.startswith("run list")], str(calls))

        # The gate could not read the comments: no verdict, so no re-run,
        # and a status that says the reading was not made.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)], "api_status": 1,
            "runs": [run_row("completed", "failure")], "views": [{}]})
        check("a gate that could not look is unknown, and nothing is re-run",
              (word, code, reran(calls)) == ("unknown", 2, []),
              f"{word} {code} {reran(calls)}")

        # No head: there is no sha to find a run for.
        word, code, text, calls = call(root, {"head": None, "views": [{}]})
        check("a pull request with no readable head is unknown",
              (word, code, reran(calls)) == ("unknown", 2, []),
              f"{word} {code} {reran(calls)}")
        check("...and says it was the head, not a crash",
              "headRefOid" in text and "crashed" not in text, text)

        # THE BRANCH THIS EXISTS FOR: reviewed at the head, and the run for
        # that head finished red because it read the comments before the
        # REVIEW was posted.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)],
            "runs": [run_row("completed", "failure")], "views": [{}]})
        check("a REVIEW at the head re-runs the red run for that head",
              (word, code, reran(calls)) == ("rerun", 0, [f"run rerun {RUN_ID} -R o/r"]),
              f"{word} {code} {reran(calls)}")
        check("...and the run it looked for is the head's",
              any(c.startswith("run list") and f"--commit {HEAD}" in c
                  for c in calls), str(calls))

        # Already green: the run read the REVIEW itself. Re-running would
        # replay the whole job for nothing.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)],
            "runs": [run_row("completed", "success")], "views": [{}]})
        check("a green run at the head is left alone",
              (word, code, reran(calls)) == ("green", 0, []),
              f"{word} {code} {reran(calls)}")

        # No run for the head yet: the one about to start reads the REVIEW.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)], "runs": [], "views": [{}]})
        check("no run for the head is no-run, and nothing is re-run",
              (word, code, reran(calls)) == ("no-run", 0, []),
              f"{word} {code} {reran(calls)}")

        # Still running when the REVIEW arrives: its gate step may already
        # have read the comments, so wait for it to finish and then judge.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)],
            "runs": [run_row("in_progress")],
            "views": [run_row("in_progress"), run_row("completed", "failure")]})
        check("a run in progress is waited for, then re-run when it ends red",
              (word, code, reran(calls)) == ("rerun", 0, [f"run rerun {RUN_ID} -R o/r"]),
              f"{word} {code} {reran(calls)}")
        check("...having polled it rather than re-running at once",
              len([c for c in calls if c.startswith("run view")]) >= 2, str(calls))

        # A wait with no end: the polls run out, and that is said, not passed.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)],
            "runs": [run_row("in_progress")], "views": [run_row("in_progress")]})
        check("a run still going after the last poll is unknown, not re-run",
              (word, code, reran(calls)) == ("unknown", 2, []),
              f"{word} {code} {reran(calls)}")
        check("...and it says how many polls it made",
              "3 poll(s)" in text, text)

        # The run list itself failed.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)], "list_status": 1,
            "views": [{}]})
        check("a run list that failed is unknown",
              (word, code, reran(calls)) == ("unknown", 2, []),
              f"{word} {code} {reran(calls)}")
        check("...and names the call that failed",
              "gh run list" in text and "exited 1" in text, text)

        # The re-run was asked for and refused: the job is still red.
        word, code, text, calls = call(root, {
            "head": HEAD, "comments": [review(HEAD)], "rerun_status": 1,
            "runs": [run_row("completed", "failure")], "views": [{}]})
        check("a re-run GitHub refused is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")
        check("...and names the re-run as what was refused",
              "gh run rerun" in text, text)

    for name in FAILED:
        print(f"FAIL {name}")
    print(f"rerun-check-test: {len(RAN) - len(FAILED)}/{len(RAN)} passed")
    return 1 if FAILED or not RAN else 0


if __name__ == "__main__":
    sys.exit(main())
