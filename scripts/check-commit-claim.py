#!/usr/bin/env python3
"""Refuse a commit on campaign work whose branch is not a claim.

    check-commit-claim.py --is-claim    ANSWER ONLY, refusing nothing: is the
                                        branch of the checkout this runs in a
                                        claim? 0 yes, 1 no, 2 could not look.
                                        `push-campaign-branch.sh` asks it
                                        rather than matching the branch name
                                        itself, because a glob there was a
                                        second reader of `claim_match` and it
                                        drifted -- `campaign-*/*` went on
                                        matching the retired form alone, so
                                        every `<slug>/` claim cut since #181
                                        committed without ever being pushed.
    check-commit-claim.py [--staged]    pre-commit, run by whichever hook
                                        installed it -- the one
                                        scripts/install-hooks.sh writes in a
                                        repository that ships that script, and
                                        the shim acquire-repo.sh writes in a
                                        clone that does not, which is every
                                        member repository. The flag is accepted
                                        and ignored, since a branch is not a
                                        staged thing.

The commit half of the claim gate; scripts/check-campaign-claim.py is the
pre-tool-use half and holds the reading both share. The model is
`claimBeforeCommit` in spec/campaign/orchestration/scenarios.als: a commit on
a sub-issue by a session's own hands names a sub-issue that session has
claimed. A claim is a `<slug>/<issue>-<topic>` branch whose ref exists
on the remote, so the reading is: the committing checkout is campaign work --
a base tree, or under a campaign directory -- and its branch is a claim.

WHY THIS IS THE GATE THAT HOLDS

The pre-tool-use half reads only a file tool's path and a `gh` write; a shell
write is allowed unread. It lands here. This hook runs in the checkout making
the commit, so it reads that checkout's branch and nothing about where a
session sits, which is the one reading the model asks for. A linked worktree
runs the main checkout's hooks (git resolves `--git-path hooks` to the common
directory), so a commit in a worktree anywhere on disk is judged too.

A DELEGATE'S CLONE HOLDS THIS GATE SINCE #190, and did not before. This line
said #178 and was true only of a clone that ships scripts/install-hooks.sh,
which is this base and no member repository: acquire-repo.sh ran a clone's own
installer when it had one and otherwise wrote a shim carrying the no-main-commits
guard alone. So every member clone -- where delegates do most of their
committing -- ran nothing that reads a claim, and "a shell write lands here" was
true of the base and false of them. Such a clone now gets a hook calling this
file BY ABSOLUTE PATH in the base, because it has no scripts/ of its own to
reach it through; the model gap is `commitGateInstalled` in
spec/campaign/orchestration/scenarios.als.

TWO READINGS, PRINTED APART

Branch-keyed always: `git branch --show-current` of the committing checkout,
and the ref's existence read from the local `origin/` copy first and from the
remote only when that is absent. Session-keyed when `CLAUDE_CODE_SESSION_ID`
is in the environment (it is, in the shell a Bash tool call's `git` inherits):
the session id is printed beside the verdict so a refusal is attributable, and
a person's terminal commit, which carries none, is judged by the branch alone
-- which walls it exactly as it walls a session's. After #176 there is no record a session id could be joined
to, so the id changes what is PRINTED and never what is decided; that is said
here so nobody reads the second line as a second gate. A remote that could not
be asked is printed as such, apart from a ref that was looked for and absent.

EXIT

0 admits the commit. 1 refuses, printing the reading on stderr. Any other
status is this script's own failure.
"""
import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "check-campaign-claim.py"


def load_guard():
    try:
        spec = importlib.util.spec_from_loader(
            "guard", importlib.machinery.SourceFileLoader("guard", str(GUARD)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:                      # noqa: BLE001 -- any of them
        return None, f"{GUARD}: {e.__class__.__name__}: {e}"
    return module, None


def refuse(lines):
    print("check-commit-claim: REFUSING the commit.", file=sys.stderr)
    for line in lines:
        print(f"  {line}", file=sys.stderr)
    return 1


def answer(guard, why) -> int:
    """`--is-claim`: three outcomes, and the caller acts on which one.

    It REFUSES NOTHING. The pre-commit half below is the gate; this exists so
    that a second reader of the branch shape does not have to. `2` is `could
    not look` and is deliberately not folded into `1`: a caller that pushes on
    a claim must be able to tell an answered no from an unread question."""
    if why:
        print(f"check-commit-claim: could not import the claim reading -- "
              f"{why}", file=sys.stderr)
        return 2
    out, git_why, _ = guard.git(["rev-parse", "--show-toplevel"], os.getcwd())
    if out is None:
        print(f"check-commit-claim: git rev-parse --show-toplevel failed in "
              f"{os.getcwd()}: {git_why}", file=sys.stderr)
        return 2
    top = Path(out.strip()).resolve()
    branch, is_claim, source = guard.claim_on(top)
    if is_claim:
        print(f"check-commit-claim: {branch} is a claim ({source})")
        return 0
    if is_claim is None:
        print(f"check-commit-claim: could not read whether "
              f"{branch or 'this checkout'} is a claim: {source}",
              file=sys.stderr)
        return 2
    print(f"check-commit-claim: {branch or 'this checkout'} is not a claim: "
          f"{source}")
    return 1


def main() -> int:
    guard, why = load_guard()
    if "--is-claim" in sys.argv[1:]:
        return answer(guard, why)
    if why:
        return refuse([f"could not import the claim reading -- {why}",
                       "It lives in one script, and this is not it."])
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    who = (f"session {session} (from CLAUDE_CODE_SESSION_ID)" if session
           else "no session id in the environment: a person's commit, judged "
                "by the branch alone")

    out, why, _ = guard.git(["rev-parse", "--show-toplevel"], os.getcwd())
    if out is None:
        return refuse([f"git rev-parse --show-toplevel failed in {os.getcwd()}: "
                       f"{why}", "A hook that cannot find its checkout has "
                       "read nothing."])
    top = Path(out.strip()).resolve()
    # `classify` gained a fourth member in #185: whether the target is
    # campaign-plane SCRATCH -- in a campaign directory and in no checkout of
    # its own. A bool, not a path. This half does not read it: a commit is
    # judged by the branch of the checkout it lands in, and a commit always
    # has one.
    inside, where, _, _ = guard.classify(top)
    if not inside:
        print(f"check-commit-claim: {top} is {where}; not campaign work, "
              f"no claim needed. {who}.")
        return 0

    branch, is_claim, source = guard.claim_on(top)
    if is_claim:
        print(f"check-commit-claim: {top} is {where}; its branch {branch} is a "
              f"claim ({source}). {who}.")
        return 0
    if is_claim is None:
        return refuse([f"{top} is {where}, on {branch}, and the claim could "
                       f"not be read: {source}.", who,
                       "Could not look is not the same as looked and found "
                       "no claim; fetch, or check the remote, and re-run."])
    return refuse([
        f"{top} is {where}, and its branch is not a claim: {source}.", who,
        "A commit on campaign work lands on the sub-issue's claimed branch.",
        "Take the claim: scripts/campaign-claim.py take <campaign issue> "
        "<issue> <topic>, then commit from a checkout on that branch.",
    ])


if __name__ == "__main__":
    sys.exit(main())
