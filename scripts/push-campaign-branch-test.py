#!/usr/bin/env python3
"""Cases for push-campaign-branch.sh, run over a fixture repository.

The subject is reached through a SYMLINK in the fixture's own `scripts/`, so
`$0`'s directory is that one and the siblings it calls -- `check-commit-claim.py`,
`check-diff-screen.py`, `check-form-behaviour.py` and the `campaign-jev.py`
naming them as the readers a push starts -- are stand-ins, while the
code that runs is the script itself and not a copy. `gh` is a fake on PATH that records its calls.

The fixture's origin has a github.com FETCH url and the bare repository as its
PUSH url, because the announcement is scoped to a github remote and a fixture
cannot push to one.

Usage: scripts/push-campaign-branch-test.py
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "push-campaign-branch.sh"
sys.path.append(str(HERE))
harness = importlib.import_module("suite-harness-test")
check, git = harness.check, harness.git

# FAKE_-PREFIXED, NOT `GH_SLEEP`, WHICH IS THE SUBJECT'S OWN. It was a plain
# assignment there when this was written, and reassigning a name INHERITED from
# the environment keeps it exported -- so the subject overwrote the case's value
# and the fake gh answered at the subject's speed. The subject now READS that
# name as an override, which makes the prefix more necessary, not less: a
# fixture spelling it `GH_SLEEP` would steer the watchdog it is timing.
FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["GH_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
time.sleep(float(os.environ.get("FAKE_GH_SLEEP", "0")))
# A MARKER WRITTEN ONLY IF THE SLEEP RAN OUT, so a case can tell a gh the
# watchdog really killed from one it merely stopped waiting on.
open(os.environ["GH_LOG"] + ".survived", "a").close()
if os.environ.get("GH_FAILS"):
    print("gh: could not connect to api.github.com", file=sys.stderr)
    sys.exit(1)
prs = os.environ.get("GH_PRS", "")
if prs:
    print(prs)
'''

# ALWAYS INSTALLED, for two reasons. It fails on its Nth call when a case asks
# -- the subject takes one temp file for the push's stderr before the one that
# case aims at, so a mktemp failing outright would never reach the second call.
# And it puts every temp file in a directory the case owns, so what the subject
# left behind can be counted: a bare `mktemp` writes to the Darwin user temp
# dir on macOS, IGNORING `TMPDIR`, which is shared with every other process on
# this machine and so cannot be counted against.
FAKE_MKTEMP = '''#!/bin/sh
c=$(cat "$FAKE_MKTEMP_COUNT" 2>/dev/null || echo 0)
c=$((c + 1))
echo "$c" > "$FAKE_MKTEMP_COUNT"
[ "$c" != "$FAKE_MKTEMP_FAILS_AT" ] || { echo "mktemp: no space" >&2; exit 1; }
exec /usr/bin/mktemp "$FAKE_MKTEMP_DIR/tmp.XXXXXXXX"
'''

FAKE_CLAIM = '#!/bin/sh\necho claim\nexit 0\n'
# A READER STAND-IN records which one started, and on what.
FAKE_SCREEN = ('#!/bin/sh\n'
               'echo "$(basename "$0") $2" >> "$READERS_LOG"\n')
# THE REGISTRY STAND-IN names the two readers a push starts, as the real
# `readers-on push` does, beside itself.
FAKE_JEV = ('#!/bin/sh\n'
            '[ "$1 $2" = "readers-on push" ] || exit 2\n'
            'here=$(dirname "$0")\n'
            'echo "$here/check-diff-screen.py"\n'
            'echo "$here/check-form-behaviour.py"\n')
# What the last `run` saw started, since its four values are every case's.
STARTED = []


def run(commits=1, prs="", gh_fails=False, gh_sleep=0, stale=0,
        mktemp_fails_at=0, tries=None, grace=0,
        remote_url="https://github.com/x/y.git"):
    """(completed process, the gh calls recorded) after `commits` commits on a
    claim branch over a fixture whose origin fetch url is `remote_url`.

    The fourth value is what the subject left in the temp directory it was
    pointed at: nothing removes its lookup file but the trap.

    `stale` is how many commits the remote's main has moved since this checkout
    last saw it -- what a worktree holding a claim `campaign-claim take` cut
    server-side actually has. `gh_sleep` is how long the fake gh takes, `tries`
    shortens the subject's watchdog, and `grace` is how long to wait AFTER the
    subject returns before reading whether that gh survived -- read any sooner
    and a gh still sleeping is indistinguishable from one that was killed."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "scripts").mkdir()
        (d / "scripts" / SCRIPT.name).symlink_to(SCRIPT)
        for name, body in (("check-commit-claim.py", FAKE_CLAIM),
                           ("check-diff-screen.py", FAKE_SCREEN),
                           ("check-form-behaviour.py", FAKE_SCREEN),
                           ("campaign-jev.py", FAKE_JEV)):
            (d / "scripts" / name).write_text(body)
            (d / "scripts" / name).chmod(0o755)
        harness.fake(d / "bin", "gh", FAKE_GH)
        harness.fake(d / "bin", "mktemp", FAKE_MKTEMP)
        temps = d / "temps"
        temps.mkdir()

        bare, repo = d / "remote.git", d / "repo"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                       check=True, capture_output=True)
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main", check=True)
        harness.write_tree(repo, {"a.txt": "1"})
        git(repo, "add", "-A", check=True)
        git(repo, "commit", "-qm", "base", "--no-verify", check=True)
        git(repo, "remote", "add", "origin", str(bare), check=True)
        git(repo, "push", "-q", "origin", "main", check=True)
        git(repo, "remote", "set-url", "--push", "origin", str(bare), check=True)
        git(repo, "remote", "set-url", "origin", remote_url, check=True)

        # THE REMOTE'S MAIN MOVES AND THIS CHECKOUT DOES NOT HEAR: the claim
        # is cut from the remote's sha, and nothing fetches main afterwards.
        if stale:
            work = d / "other"
            subprocess.run(["git", "clone", "-q", str(bare), str(work)],
                           check=True, capture_output=True)
            for i in range(stale):
                harness.write_tree(work, {f"m{i}.txt": "1"})
                git(work, "add", "-A", check=True)
                git(work, "commit", "-qm", f"main {i}", "--no-verify", check=True)
            git(work, "push", "-q", "origin", "main", check=True)
            git(repo, "fetch", "-q", str(bare), "main", check=True)
            git(repo, "merge", "-q", "--ff-only", "FETCH_HEAD", check=True)
            # ...and then the tracking ref goes stale again, which is the state
            # a worktree is in from the moment the claim is cut.
            git(repo, "update-ref", "refs/remotes/origin/main",
                f"HEAD~{stale}", check=True)

        branch = "slug/1-topic"
        git(repo, "checkout", "-qb", branch, check=True)
        for i in range(commits):
            harness.write_tree(repo, {f"b{i}.txt": "1"})
            git(repo, "add", "-A", check=True)
            git(repo, "commit", "-qm", f"work {i}", "--no-verify", check=True)

        log = d / "gh-calls"
        env = dict(os.environ, PATH=f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}",
                   GH_LOG=str(log), GH_PRS=prs, FAKE_GH_SLEEP=str(gh_sleep),
                   FAKE_MKTEMP_COUNT=str(d / "mktemp-count"),
                   FAKE_MKTEMP_FAILS_AT=str(mktemp_fails_at),
                   FAKE_MKTEMP_DIR=str(temps),
                   READERS_LOG=str(d / "readers"))
        if tries is not None:
            env["GH_TRIES"] = str(tries)
        if gh_fails:
            env["GH_FAILS"] = "1"
        r = subprocess.run(["sh", str(d / "scripts" / SCRIPT.name)], cwd=repo,
                           env=env, capture_output=True, text=True)
        calls = ([json.loads(line) for line in log.read_text().splitlines()]
                 if log.exists() else [])
        if grace:
            time.sleep(grace)
        survived = Path(str(log) + ".survived").exists()
        readers = d / "readers"
        for _ in range(40):  # they are started unwaited, so wait for both
            if readers.exists() and len(readers.read_text().splitlines()) >= 2:
                break
            time.sleep(0.05)
        STARTED[:] = sorted(readers.read_text().splitlines()
                            if readers.exists() else [])
        return r, calls, survived, sorted(q.name for q in temps.iterdir())


def main():
    # THE NAMED FAILING CASE (rule-check#461 rank 6). AGENTS.md § Execution
    # mode: the pull request is opened at the first commit, not when the work
    # is ready. Nothing said so where the first commit happens, so a branch
    # went up pushed and invisible for as many turns as the session took.
    r, calls, survived, temps = run(commits=1)
    check("a branch's first commit with no open pull request announces the line",
          r.returncode == 0 and "gh pr create" in r.stdout
          and "--head slug/1-topic" in r.stdout
          and "first commit" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")
    check("...and it started each reader the registry says a push starts, on "
          "this branch",
          STARTED == ["check-diff-screen.py slug/1-topic",
                      "check-form-behaviour.py slug/1-topic"], f"started {STARTED}")
    check("...and it asked gh about this branch's open pull requests",
          [c for c in calls if c[:2] == ["pr", "list"]]
          and "slug/1-topic" in calls[0],
          f"calls {calls}")

    # IT ANNOUNCES AND REFUSES NOTHING: the push is the hook's job, and a
    # commit is never held back over a missing pull request.
    check("...and the push still happened and the exit status is still 0",
          r.returncode == 0 and "pushed slug/1-topic" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    r, calls, survived, temps = run(commits=1, prs="9")
    check("a branch an open pull request already names is not told to open one",
          r.returncode == 0 and "gh pr create" not in r.stdout,
          f"out {r.stdout!r}")

    # A STALE `origin/main` USED TO SILENCE IT (pr#487 review, finding 2).
    # `campaign-claim take` cuts the ref from the remote's main sha and never
    # moves this checkout's `origin/main`, so a first-commit count against it
    # read k+1 in a worktree lagging k commits and the line was never said.
    # Nothing counts commits now; the question is only whether an open pull
    # request names the head.
    r, calls, survived, temps = run(commits=1, stale=2)
    check("a genuine first commit is announced even with origin/main stale",
          r.returncode == 0 and "gh pr create" in r.stdout,
          f"out {r.stdout!r} err {r.stderr!r}")

    # AND SAID AGAIN AT THE NEXT COMMIT, which is the trade: the line is true
    # every time it prints, where a miss at the first commit is the defect.
    r, calls, survived, temps = run(commits=2)
    check("a later commit with still no pull request is told again",
          r.returncode == 0 and "gh pr create" in r.stdout,
          f"out {r.stdout!r}")

    # AN UNREAD QUESTION IS NOT A YES. A gh that will not run leaves it unknown,
    # and the cost of saying so twice is one glance.
    r, calls, survived, temps = run(commits=1, gh_fails=True)
    check("a gh that will not run is said, quoting what it said",
          r.returncode == 0 and "could not tell whether a pull request" in r.stderr
          and "could not connect" in r.stderr and "gh pr create" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")

    # A BOUND, because this runs inside post-commit: an unbounded gh hangs
    # every commit on the machine. No `timeout` on PATH here, so the watchdog
    # is by hand, and what it does when it fires is said and not guessed.
    # THE BOUND IS SHORTENED HERE, and the fake gh's sleep set just past it:
    # a case that waited the default 10s out would take ten seconds, and one
    # whose gh slept far longer than the whole run could not tell a gh that was
    # KILLED from one still sleeping when the run ended -- which is how the
    # case below first passed with its own branch broken.
    r, calls, survived, temps = run(commits=1, tries=3, gh_sleep=2, grace=3)
    check("a gh that does not answer is given up on, said, and does not hang",
          r.returncode == 0 and "did not answer" in r.stderr
          and "gh pr create" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")
    # THE NUMBERS ARE STATED, so a reader can time the wait against them.
    check("...and the message states the tries and the sleep between them",
          "3 tries of 0.25s" in r.stderr, f"err {r.stderr!r}")
    # THE KILL REACHES gh ITSELF. Backgrounding a subshell around it makes
    # `$!` the subshell's pid, so the kill reaps a wrapper and leaves gh
    # reparented to pid 1 and still running -- one leak per hung commit, and
    # invisible, since the hook returns either way. Read AFTER the fake gh's
    # own sleep would have run out, so a survivor has had time to say so.
    #
    # BREAKING THIS ONE TAKES TWO COMMANDS IN THE SUBSHELL. `( gh ... ) &` with
    # gh alone is exec'd by sh, so the subshell process BECOMES gh and `$!` is
    # still gh's pid -- the naive break leaves this case green and proves
    # nothing. `( gh ...; : ) &` is the shape that actually reds it.
    check("...and gh itself was killed, not a wrapper around it",
          not survived, "the fake gh ran its sleep out, so it was not killed "
          "and only a wrapper around it was")

    # NOTHING BUT THE TRAP REMOVES THE LOOKUP FILE, on the ordinary path as
    # much as on an interrupt -- the explicit `rm` went when `wait` replaced
    # the second temp file. Deleting the trap line leaves every other case
    # green and leaks one file per commit, for the life of the machine.
    # EACH CARRIES ITS PATH'S OWN MARKER, because an absence confirms whatever
    # was already true: with only `left == []` all four stayed green when the
    # fixture was misdirected so the function never ran at all. The marker says
    # the path was taken; the empty directory then says what it left.
    for name, kw, mark in (
            # STDERR IS WHAT SEPARATES THIS PATH from the two error ones: all
            # three print no announcement, and only this one says nothing at
            # all. The clause here used to be `"names it" not in stdout`, which
            # no output of the subject could ever contain, so it read as a
            # second check and could not fail.
            ("a pull request already names it", {"prs": "9"},
             lambda r: "no open pull request names" not in r.stdout
             and r.stderr == ""),
            ("no pull request names it", {},
             lambda r: "gh pr create" in r.stdout),
            ("gh would not run", {"gh_fails": True},
             lambda r: "could not tell whether a pull request" in r.stderr),
            ("gh never answered", {"tries": 3, "gh_sleep": 2, "grace": 3},
             lambda r: "did not answer" in r.stderr)):
        r2, calls2, _survived, left = run(commits=1, **kw)
        check(f"no temp file is left behind when {name}",
              r2.returncode == 0 and calls2 and mark(r2) and left == [],
              f"exit {r2.returncode} out {r2.stdout!r} err {r2.stderr!r} "
              f"calls {calls2} left {left}")

    # mktemp CAN FAIL ON THE SECOND CALL, disk full mid-run, and a silent
    # return there is the same class of miss as the first-commit count was.
    r, calls, survived, temps = run(commits=1, mktemp_fails_at=2)
    check("a mktemp that fails is said, not returned from silently",
          r.returncode == 0 and "mktemp failed" in r.stderr
          and "pushed slug/1-topic" in r.stdout and not calls,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")

    # A NON-GITHUB REMOTE has no pull request to open, and a fixture's local
    # remote is not one -- the same reading the diff screen is scoped by.
    r, calls, survived, temps = run(commits=1, remote_url="/tmp/not-github.git")
    check("a remote that is not github.com is told nothing and gh is not asked",
          r.returncode == 0 and "gh pr create" not in r.stdout and not calls,
          f"out {r.stdout!r} calls {calls}")

    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
