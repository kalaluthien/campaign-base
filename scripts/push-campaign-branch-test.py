#!/usr/bin/env python3
"""Cases for push-campaign-branch.sh, run over a fixture repository.

The subject is reached through a SYMLINK in the fixture's own `scripts/`, so
`$0`'s directory is that one and the siblings it calls -- `check-commit-claim.py`
and `check-diff-screen.py` -- are stand-ins, while the code that runs is the
script itself and not a copy. `gh` is a fake on PATH that records its calls.

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
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "push-campaign-branch.sh"
sys.path.append(str(HERE))
harness = importlib.import_module("suite-harness-test")
check, git = harness.check, harness.git

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["GH_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("GH_FAILS"):
    print("gh: could not connect to api.github.com", file=sys.stderr)
    sys.exit(1)
prs = os.environ.get("GH_PRS", "")
if prs:
    print(prs)
'''

FAKE_CLAIM = '#!/bin/sh\necho claim\nexit 0\n'
FAKE_SCREEN = '#!/bin/sh\nexit 0\n'


def run(commits=1, prs="", gh_fails=False, remote_url="https://github.com/x/y.git"):
    """(completed process, the gh calls recorded) after `commits` commits on a
    claim branch over a fixture whose origin fetch url is `remote_url`."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "scripts").mkdir()
        (d / "scripts" / SCRIPT.name).symlink_to(SCRIPT)
        for name, body in (("check-commit-claim.py", FAKE_CLAIM),
                           ("check-diff-screen.py", FAKE_SCREEN)):
            (d / "scripts" / name).write_text(body)
            (d / "scripts" / name).chmod(0o755)
        harness.fake(d / "bin", "gh", FAKE_GH)

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

        branch = "slug/1-topic"
        git(repo, "checkout", "-qb", branch, check=True)
        for i in range(commits):
            harness.write_tree(repo, {f"b{i}.txt": "1"})
            git(repo, "add", "-A", check=True)
            git(repo, "commit", "-qm", f"work {i}", "--no-verify", check=True)

        log = d / "gh-calls"
        env = dict(os.environ, PATH=f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}",
                   GH_LOG=str(log), GH_PRS=prs)
        if gh_fails:
            env["GH_FAILS"] = "1"
        r = subprocess.run(["sh", str(d / "scripts" / SCRIPT.name)], cwd=repo,
                           env=env, capture_output=True, text=True)
        calls = ([json.loads(line) for line in log.read_text().splitlines()]
                 if log.exists() else [])
        return r, calls


def main():
    # THE NAMED FAILING CASE (rule-check#461 rank 6). AGENTS.md § Execution
    # mode: the pull request is opened at the first commit, not when the work
    # is ready. Nothing said so where the first commit happens, so a branch
    # went up pushed and invisible for as many turns as the session took.
    r, calls = run(commits=1)
    check("a branch's first commit with no open pull request announces the line",
          r.returncode == 0 and "gh pr create" in r.stdout
          and "--head slug/1-topic" in r.stdout
          and "first commit" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")
    check("...and it asked gh about this branch's open pull requests",
          [c for c in calls if c[:2] == ["pr", "list"]]
          and "slug/1-topic" in calls[0],
          f"calls {calls}")

    # IT ANNOUNCES AND REFUSES NOTHING: the push is the hook's job, and a
    # commit is never held back over a missing pull request.
    check("...and the push still happened and the exit status is still 0",
          r.returncode == 0 and "pushed slug/1-topic" in r.stdout,
          f"exit {r.returncode} out {r.stdout!r}")

    r, calls = run(commits=1, prs="9")
    check("a branch an open pull request already names is not told to open one",
          r.returncode == 0 and "gh pr create" not in r.stdout,
          f"out {r.stdout!r}")

    # ONLY AT THE FIRST COMMIT, or the line is repeated at every commit of a
    # branch whose session chose not to open one, and stops being read.
    r, calls = run(commits=2)
    check("a branch past its first commit is not told again, and gh is not asked",
          r.returncode == 0 and "gh pr create" not in r.stdout and not calls,
          f"out {r.stdout!r} calls {calls}")

    # AN UNREAD QUESTION IS NOT A YES. A gh that will not run leaves it unknown,
    # and the cost of saying so twice is one glance.
    r, calls = run(commits=1, gh_fails=True)
    check("a gh that will not run is said, quoting what it said",
          r.returncode == 0 and "could not tell whether a pull request" in r.stderr
          and "could not connect" in r.stderr and "gh pr create" not in r.stdout,
          f"exit {r.returncode} out {r.stdout!r} err {r.stderr!r}")

    # A NON-GITHUB REMOTE has no pull request to open, and a fixture's local
    # remote is not one -- the same reading the diff screen is scoped by.
    r, calls = run(commits=1, remote_url="/tmp/not-github.git")
    check("a remote that is not github.com is told nothing and gh is not asked",
          r.returncode == 0 and "gh pr create" not in r.stdout and not calls,
          f"out {r.stdout!r} calls {calls}")

    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
