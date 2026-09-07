#!/usr/bin/env python3
"""Read the repositories installed on this machine, say whether each install
shows what was merged, and carry a merge into one.

    scripts/campaign-installed.py list  <body>
    scripts/campaign-installed.py check <body> [owner/repo]
    scripts/campaign-installed.py reach <body> <owner/repo> <sha>

<body> is the campaign README or `runtime/campaign-issue-body-derived.md`: any
file whose `## Repos` list `scripts/campaign-repos.py` reads, and that reader is
the ONE parser of the list and of the installed marker on an entry,
`- owner/repo (installed: <path>, apply: <command>)`. This file never parses a
line of it; it imports `read_repos` and quotes its refusal.

WHAT AN INSTALLED REPOSITORY IS (kalaluthien/campaign-base#239). One checked
out where it is used -- `~/.claude` for dotclaude, the base root for the base --
and so one with TWO checkouts once a campaign clones it: the install, and the
clone under `<campaign>/repos/` where the work happens. A merge lands on
GitHub and in nobody's install; before #239 the base alone had a rule for that
step, as prose in AGENTS.md, and every other install was reached by whoever
remembered. The model is `Machine.installed` and `Machine.current` in
`spec/campaign/directory/system.als`: a MergePullRequest empties `current`
for the repository, `Reach` refills it, and `reachDiscipline` says a campaign
does not close while a machine holding it has an install behind.

THE BASE IS ALWAYS THE FIRST ROW. `## Repos` refuses an entry naming it, so
its marker cannot be written in any list; it is `BASE_ROW` below, at the base
root `campaign-claim.py`'s `base_root` resolves -- the main checkout, from a
worktree or from a clone under a campaign directory alike -- with
`scripts/install-hooks.sh` as its `apply`. That is AGENTS.md's former "base as
its own member" section as one row of this rule.

THE THREE READINGS, and what each prints so a bare verdict never stands alone:

  list    every row, `owner/repo  <path>  <apply|->`, the base first. Reads no
          disk beyond the body.
  check   per row: the install's HEAD, its remote's default branch after a
          fetch, and one word -- `current` when HEAD contains the remote's
          default branch, `behind <n>` when it does not, or why it could not
          be read: `absent`, `not a checkout`, `a checkout of <other>`,
          `could not fetch`. Then the verdict line, `<n> row(s) read, <m>
          behind, <k> unread` and `clear` or `NOT clear`; exit 1 on anything
          but clear. An unread row is NOT clear: `I could not look` is not
          `I looked and it is current`, and a check that read nothing must not
          pass. The named failing case in the suite is the marker present and
          the step skipped: an install behind its remote, read as `behind 1`.
          An `owner/repo` narrows it to one row, the base included when named.
  reach   the post-merge step for one row. Refuses when the repository has no
          row (`nothing to reach`, exit 0: it is not installed, and that is an
          answer), when <sha> is not on the remote's default branch (merge
          first), when the install is not on that branch (somebody is working
          in the install, which is what the clone is for), or when the
          fast-forward or `apply` fails, printing what git or the command said.
          Otherwise fast-forwards the install to the remote's default branch,
          runs `apply` in the install, and prints `reached owner/repo at
          <path>: HEAD <sha> contains <sha>; apply ...` -- the line a REPORT
          quotes.

WHO RUNS WHAT. Whoever merges runs `reach` for the repository the merge landed
in and puts its line in the REPORT (AGENTS.md § Installed repositories);
`closing-campaign` step 2 runs `check` over the README and refuses on NOT
clear. Both read this machine, which is the bound machine by the one-campaign-
one-machine rule, and neither concludes anything about another.

The default branch is what `origin/HEAD` names, `main` when the checkout never
recorded one. Git's own words are quoted on every failure, whitespace folded.
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_APPLY = "scripts/install-hooks.sh"


def load(name, filename):
    src = HERE / filename
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


REPOS = load("campaign_repos", "campaign-repos.py")
CLAIM = load("campaign_claim", "campaign-claim.py")


def git(path, *args):
    """(returncode, stdout, stderr folded) for one git command in `path`."""
    r = subprocess.run(["git", "-C", path, *args], capture_output=True,
                       text=True)
    return r.returncode, r.stdout.strip(), " ".join(r.stderr.split())[:200]


def rows(body_path):
    """([(owner/repo, install path, apply)], why) -- the installed rows, the
    base first. `why` names what could not be read."""
    try:
        text = Path(body_path).read_text(encoding="utf-8")
    except OSError as e:
        return None, f"cannot read {body_path}: {e.strerror}"
    listed, why = REPOS.read_repos(text)
    if why:
        return None, f"campaign-repos refused {body_path}: {why}"
    base, why = CLAIM.base_root()
    if why:
        return None, why
    out = [(REPOS.BASE_REPO, base, BASE_APPLY)]
    for slug, installed, apply in listed:
        if installed is not None:
            out.append((slug, os.path.expanduser(installed), apply))
    return out, None


def default_branch(path):
    rc, out, _ = git(path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return out.split("/", 1)[1] if rc == 0 and "/" in out else "main"


def read_install(slug, path):
    """(word, detail) for one install: what was read and one word on it.
    Every branch prints what it read; the word is what the verdict counts."""
    if not os.path.isdir(path):
        return "absent", f"{path} is not a directory"
    rc, top, err = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        return "not a checkout", f"{path}: {err}"
    rc, url, err = git(path, "remote", "get-url", "origin")
    if rc != 0:
        return "not a checkout", f"{path} has no origin: {err}"
    # The last two path components name the repository however the URL is
    # spelled: `git@github.com:owner/repo.git`, `https://.../owner/repo`, or a
    # local path ending in `owner/repo.git`, which is what the suite builds.
    remote = "/".join(url.replace(":", "/").rstrip("/").split("/")[-2:])
    if REPOS.key(remote) != REPOS.key(slug):
        return f"a checkout of {REPOS.slug(remote) or remote}", f"{path} origin {url}"
    branch = default_branch(path)
    rc, _, err = git(path, "fetch", "-q", "origin", branch)
    if rc != 0:
        return "could not fetch", f"{path} origin/{branch}: {err}"
    _, head, _ = git(path, "rev-parse", "--short", "HEAD")
    _, tip, _ = git(path, "rev-parse", "--short", f"origin/{branch}")
    rc, count, err = git(path, "rev-list", "--count", f"HEAD..origin/{branch}")
    if rc != 0:
        return "could not fetch", f"{path} HEAD..origin/{branch}: {err}"
    n = int(count)
    word = "current" if n == 0 else f"behind {n}"
    return word, f"HEAD {head}  origin/{branch} {tip}"


def cmd_list(body_path, _args):
    listed, why = rows(body_path)
    if why:
        print(f"campaign-installed: {why}", file=sys.stderr)
        return 1
    for slug, path, apply in listed:
        print(f"{slug}  {path}  {apply or '-'}")
    print(f"{len(listed)} installed row(s), the base first; read from {body_path}")
    return 0


def cmd_check(body_path, args):
    listed, why = rows(body_path)
    if why:
        print(f"campaign-installed: {why}", file=sys.stderr)
        return 1
    only = args[0] if args else None
    if only is not None:
        listed = [r for r in listed if REPOS.key(r[0]) == REPOS.key(only)]
        if not listed:
            print(f"campaign-installed: {only} has no installed row in "
                  f"{body_path}; nothing to check", file=sys.stderr)
            return 1
    behind = unread = 0
    for slug, path, _apply in listed:
        word, detail = read_install(slug, path)
        print(f"{slug}  {path}  {detail}  -- {word}")
        if word.startswith("behind"):
            behind += 1
        elif word != "current":
            unread += 1
    verdict = "clear" if behind == 0 and unread == 0 else "NOT clear"
    print(f"{len(listed)} row(s) read, {behind} behind, {unread} unread -- {verdict}")
    return 0 if verdict == "clear" else 1


def cmd_reach(body_path, args):
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    only, sha = args
    listed, why = rows(body_path)
    if why:
        print(f"campaign-installed: {why}", file=sys.stderr)
        return 1
    hit = [r for r in listed if REPOS.key(r[0]) == REPOS.key(only)]
    if not hit:
        print(f"{only} has no installed row in {body_path}: nothing to reach")
        return 0
    slug, path, apply = hit[0]
    word, detail = read_install(slug, path)
    if word not in ("current",) and not word.startswith("behind"):
        print(f"campaign-installed: refusing to reach {slug}: {word} ({detail})",
              file=sys.stderr)
        return 1
    branch = default_branch(path)
    rc, _, err = git(path, "merge-base", "--is-ancestor", sha, f"origin/{branch}")
    if rc != 0:
        print(f"campaign-installed: refusing to reach {slug}: {sha} is not on "
              f"origin/{branch} ({err or 'not an ancestor'}); merge first, then "
              f"reach", file=sys.stderr)
        return 1
    rc, on, _ = git(path, "symbolic-ref", "--short", "HEAD")
    if rc != 0 or on != branch:
        print(f"campaign-installed: refusing to reach {slug}: the install at "
              f"{path} is on {on or 'a detached HEAD'}, not {branch}; the install "
              f"is not where work happens", file=sys.stderr)
        return 1
    rc, _, err = git(path, "merge", "--ff-only", f"origin/{branch}")
    if rc != 0:
        print(f"campaign-installed: could not fast-forward {slug} at {path}: "
              f"{err}", file=sys.stderr)
        return 1
    applied = "none"
    if apply:
        r = subprocess.run(apply, shell=True, cwd=path, capture_output=True,
                           text=True)
        if r.returncode != 0:
            said = " ".join((r.stderr or r.stdout).split())[:200]
            print(f"campaign-installed: {slug} fast-forwarded at {path}, but "
                  f"apply `{apply}` exited {r.returncode}: {said}",
                  file=sys.stderr)
            return 1
        applied = f"`{apply}` ran"
    _, head, _ = git(path, "rev-parse", "HEAD")
    print(f"reached {slug} at {path}: HEAD {head} contains {sha}; apply {applied}")
    return 0


COMMANDS = {"list": cmd_list, "check": cmd_check, "reach": cmd_reach}


def main(argv):
    if len(argv) < 2 or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return COMMANDS[argv[0]](argv[1], argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
