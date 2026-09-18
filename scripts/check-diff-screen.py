#!/usr/bin/env python3
"""Log how each file a commit touched reads against the diff screen's five questions, and refuse nothing.

THE READING `diff-screen` in scripts/jev/readings.json, asked through
scripts/campaign-jev.py. The entry holds the five `nouls`, the question they
are composed into, the state's fields, the thresholds and the tier; this reads
them and writes none of them.

WHO RUNS IT: scripts/push-campaign-branch.sh, the post-commit hook, in the
background once it pushed a claim to a GitHub remote. WHY THEN: it is the
cheapest moment that has seen the diff before a reviewer does. Every change a
reviewer reads came through a commit, so the last call on each file before
the review launch holds the screen of the head it reviews. Counted over the 77
fix-round pull requests (sdlc-alloy#458 R2), a file of a commit is 17.2 calls
a pull request. Screening the whole branch at each push is 92.5, and at each
review round 30.4. A `REVIEW` post is after the reading it would steer. The
review launch is an `Agent` call no field of which says it is one.

The log line carries the label `<branch> <sha12> <path>`, an answer per noul
and the time, never the patch. A join finds the pull request by the branch,
and a `REVIEW` defect naming the path by `path:line` as its later fact.

WHAT IT READS: the commit's own files (`git diff-tree`), each file's patch from
the merge-base with the remote's default branch -- `origin/HEAD`, else
`origin/main` -- to the commit, and the paths of the test files that branch
diff changes. The branch in the label is the hook's, passed in: read here it
would be whatever a checkout moved HEAD to after the commit.

WHERE IT LOGS: the base's `runtime/jev.log`, found from this script's own
directory and not from the checkout it reads. The hook runs it in a member
repository's clone too, and a log found from there would land an untracked
`runtime/` in that clone, where `report` never reads it.

  asked      one call a file the commit touched: state `{file: {path, patch},
             changedTests}`, one `noul` question a noul, all five in the call
  passed     a merge commit asks nothing: `git diff-tree` lists no file for
             one, since its files are main's, not the branch's work
  skipped    a binary file, a file whose branch patch is empty, a `git diff`
             that failed, a patch over PATCH_CEILING, a commit with no
             merge-base, or a reading that raised, asks nothing and logs one `skipped` row naming why

THE TIER is `shadow`: every call is logged and nothing is printed, since the
hook's background start discards this process's output.
THE EXIT STATUS IS 0 on every path.

WHERE THIS READING IS KNOWN TO BE WRONG, as seen at jev-1.13.0 on 2026-09-17,
one run and repeats for 147 rows, over 399 files of 77 pull requests (39 a
`REVIEW` defect named, 360 no finding named): at the cut that keeps every
defect file, the highest of the five lets a reviewer skip 44-57 of 399
(11-14%), AUC 0.73; "most added lines" skips 30 (8%), AUC 0.78; "tests changed
or not" skips none. Its lowest defect files are prose: AGENTS.md at 0.12.

Usage: scripts/check-diff-screen.py [<commit> [<branch>]]
"""
import importlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
READING = "diff-screen"
READER = "check-diff-screen.py"
GIT_TIMEOUT = 30
# 55 KB was the largest patch answered in the measurement; 127 KB came back
# `max_tokens_exceeded` (topic-jev).
PATCH_CEILING = 100_000
# THE PATCH'S FORM IS PINNED, not left to the machine's git config: the
# measurement ran under `diff.noprefix` and `diff.algorithm=histogram`, and a
# config without them sends a patch the band was not measured on.
PATCH_FORM = ("--no-prefix", "--diff-algorithm=histogram", "--no-color",
              "--no-ext-diff", "--no-textconv", "--no-renames")
TEST = re.compile(r"(-test\.\w+$|_test\.\w+$|(^|/)checks\.als$|(^|/)tests?/)")
DEFAULT_BRANCH = ("origin/HEAD", "origin/main")


def jev_module():
    """campaign-jev, which holds every step around the call (rule-check#506)."""
    return importlib.import_module("campaign-jev")


def git(*args):
    """stdout, or None when git exited non-zero."""
    p = subprocess.run(["git", *args], capture_output=True, text=True,
                       timeout=GIT_TIMEOUT)
    return p.stdout if p.returncode == 0 else None


def files(commit, base):
    """[(path, why it is skipped or "")] for every file the commit touched."""
    touched = (git("diff-tree", "--no-commit-id", "--name-only", "-r",
                   "--no-renames", commit) or "").split("\n")
    stat = {}
    for line in (git("diff", "--numstat", "--no-renames", base, commit)
                 or "").split("\n"):
        if line:
            added, _removed, path = line.split("\t", 2)
            stat[path] = added
    out = []
    for path in filter(None, touched):
        if path not in stat:
            out.append((path, "the branch's patch of it is empty"))
        elif stat[path] == "-":
            out.append((path, "a binary file"))
        else:
            out.append((path, ""))
    return out, sorted(p for p in stat if TEST.search(p))


def merge_base(commit):
    """The commit's merge-base with the default branch, or ""."""
    return next((b.strip() for b in (git("merge-base", commit, ref)
                                     for ref in DEFAULT_BRANCH) if b), "")


def patches(jev, reader, label, found, base, commit, env):
    """[(path, patch)] of every file `files` found whose patch read and fits
    under `PATCH_CEILING`; a skip row for each other, naming why."""
    out = []
    for path, why in found:
        patch = "" if why else git("diff", *PATCH_FORM, base, commit, "--", path)
        if patch is None:
            why = "git diff failed"
        elif not why and len(patch) > PATCH_CEILING:
            why = f"a patch of {len(patch)} chars, over {PATCH_CEILING}"
        if why:
            jev.skip(reader, f"{label} {path}", why, env, cwd=HERE)
        else:
            out.append((path, patch))
    return out


def main(argv, env=None):
    if len(argv) > 2:
        print("Usage: scripts/check-diff-screen.py [<commit> [<branch>]]",
              file=sys.stderr)
        return 2
    subject = argv[0] if argv else "HEAD"
    try:
        jev = jev_module()
    except Exception:  # noqa: BLE001 -- no log to count a raise in
        return 0
    jev.shielded(READER, subject, lambda: read(argv, subject, jev, env), env,
                 cwd=HERE)
    return 0


def read(argv, subject, jev, env):
    commit = (git("rev-parse", "--verify", "-q", subject + "^{commit}")
              or "").strip()
    branch = argv[1] if len(argv) > 1 else (
        git("symbolic-ref", "--quiet", "--short", "HEAD") or "detached").strip()
    label = f"{branch} {commit[:12] or subject}"
    if not commit:
        jev.skip(READER, label, "the commit does not resolve", env, cwd=HERE)
        return
    base = merge_base(commit)
    if not base:
        jev.skip(READER, label, "no merge-base with origin/HEAD or "
                 "origin/main", env, cwd=HERE)
        return
    entry = jev.load_registry()[READING]
    found, tests = files(commit, base)
    # A KEY ONLY WHERE THE REPOSITORY IS KNOWN, and the sha this reading
    # judged is the one it was given, not the one a commit-time reader would
    # name: this runs over a branch that already has its commits.
    key = jev.commit_key()
    key = {"repo": key["repo"], "commit": commit} if key.get("repo") else {}
    # ONE `judge` CALL A FILE, a question a noul: the entry's `compose` fills
    # the whole question -- criteria and examples included -- from that noul's
    # row of the entry's own `nouls` table, which is what this file composed
    # by hand until now. What the ROW gained is the reading's name, the
    # wording and the KEY -- the repository, the sha and the file -- so a
    # later fix commit on that file can be joined to the answer (sdlc-alloy#458
    # DECISION 5722176509).
    jev.judge_each(
        [{"state": {"file": {"path": path, "patch": patch},
                    "changedTests": tests},
          "read": f"{label} {path}",
          "key": dict(key, path=path) if key else {"path": path}}
         for path, patch in patches(jev, READER, label, found, base, commit,
                                    env)],
        group=entry["group"], reader=READER, env=env, cwd=HERE)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
