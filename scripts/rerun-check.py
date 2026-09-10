#!/usr/bin/env python3
"""Re-run a pull request's `check` once a REVIEW names its head, so no hand re-run is needed.

    rerun-check.py <pr> [--repo OWNER/REPO] [--poll SECONDS] [--polls N]

.github/workflows/review-rerun.yml runs this on every comment and every review
posted on a pull request. A comment fires no `pull_request` event, so before
this the `check` run that read the comments too early stayed red until somebody
typed `gh run rerun <id>` -- on the path of every merge here.

WHAT IT DOES, in order, and the word it prints first for each branch:

  unknown     the head, the gate, the run list, a poll or the re-run could not
              be read or was refused; status 2
  unreviewed  check-merge-review.py found no REVIEW naming the head, so a
              re-run would go red again; nothing is touched
  no-run      no `check` run exists for the head yet; the one that starts
              reads the REVIEW itself
  green       the head's run ended green; it already read the REVIEW
  rerun       the head's run ended red, and it has been re-run

A run still in progress is WAITED FOR, not skipped: its gate step is the last
one and may have read the comments a moment before the REVIEW was posted, so
only its conclusion says whether a re-run is due. The wait is bounded by
`--polls`, and running out of polls is `unknown`, not a pass.

THE GATE IS ASKED, NOT RESTATED. What counts as a REVIEW at the head is
check-merge-review.py's to say; this reads its first word.

The job is named `rerun`, never `check`: `check` is the required context on
`main`, and a second job answering to that name would be a second verdict on it.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "check-merge-review.py"
WORKFLOW = "check.yml"


def load_gate():
    spec = importlib.util.spec_from_loader(
        "check_merge_review",
        importlib.machinery.SourceFileLoader("check_merge_review", str(GATE)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The gate's own line, printed UNDER the word, never before it: a caller reads
# the first word of the output.
GATE_SAID = []


def say(word, line):
    print(f"{word} rerun-check: {line}")
    for said in GATE_SAID:
        print(f"  the gate said: {said}")
    return 2 if word == "unknown" else 0


def gate_word(repo, pr, head):
    """(word, what the gate printed). The gate's own first word, one of its
    GATE_WORDS, or None when it printed something else."""
    p = subprocess.run([sys.executable, str(GATE), str(pr), "--repo", repo,
                        "--head", head], capture_output=True, text=True)
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return (text.split(" ", 1)[0] if text else None), text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pr", type=int)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--poll", type=float, default=30,
                    help="seconds between reads of a run still in progress")
    ap.add_argument("--polls", type=int, default=60,
                    help="reads of a run in progress before giving up")
    a = ap.parse_args(argv)

    try:
        gate = load_gate()
    except Exception as e:                      # noqa: BLE001 -- reported
        return say("unknown", f"{GATE.name} will not load: {e}")
    repo = a.repo or gate.default_repo()[0]
    if not repo:
        return say("unknown", "no --repo, and no default repository to read")

    head, why = gate.head_of(repo, a.pr)
    if why:
        return say("unknown", why)

    word, text = gate_word(repo, a.pr, head)
    GATE_SAID.append(text)
    if word == "unreviewed":
        return say("unreviewed", f"no REVIEW names {head} on {repo}#{a.pr}; "
                                 f"a re-run would go red again")
    if word != "reviewed":
        return say("unknown", f"the gate answered {word!r}, not `reviewed`")

    runs, why = gate.gh_json(
        f"gh run list {WORKFLOW} at {head}", "gh", "run", "list", "-R", repo,
        "--workflow", WORKFLOW, "--commit", head, "--event", "pull_request",
        "--limit", "1", "--json", "databaseId,status,conclusion")
    if why:
        return say("unknown", why)
    if not isinstance(runs, list):
        return say("unknown", f"gh run list answered {type(runs).__name__}, not a list")
    if not runs:
        return say("no-run", f"no {WORKFLOW} run exists for {head} yet; "
                             f"the one that starts reads the REVIEW itself")
    run = runs[0]
    rid = run.get("databaseId")

    polls = 0
    while run.get("status") != "completed":
        if polls >= a.polls:
            return say("unknown", f"run {rid} for {head} is still "
                                  f"{run.get('status')!r} after {polls} poll(s)")
        time.sleep(a.poll)
        polls += 1
        run, why = gate.gh_json(f"gh run view {rid}", "gh", "run", "view",
                                str(rid), "-R", repo, "--json",
                                "databaseId,status,conclusion")
        if why:
            return say("unknown", why)
        if not isinstance(run, dict):
            return say("unknown", f"gh run view {rid} answered {json.dumps(run)[:80]}")

    if run.get("conclusion") == "success":
        return say("green", f"run {rid} for {head} is already green "
                            f"({polls} poll(s))")

    code, _, err = gate.run("gh", "run", "rerun", str(rid), "-R", repo)
    if code != 0:
        return say("unknown", f"gh run rerun {rid} exited {code}: "
                              f"{(err or '').strip()[:200]}")
    return say("rerun", f"run {rid} for {head} ended {run.get('conclusion')!r} "
                        f"and is re-running ({polls} poll(s))")


def guarded() -> int:
    """A crash is a reading not made, and says so rather than passing."""
    try:
        return main()
    except Exception as e:                      # noqa: BLE001 -- reported
        return say("unknown", f"crashed: {e.__class__.__name__}: {e}")


if __name__ == "__main__":
    sys.exit(guarded())
