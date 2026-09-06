#!/usr/bin/env python3
"""Print everything that exists only on this machine for one campaign.

The close deletes a campaign directory, and nothing recovers what was only in
it. This is the one reader of that question -- "what would the delete destroy,
and what on this campaign's own branches has never left this machine?" -- so
closing-campaign step 2 is one call to this script rather than nine git
commands in prose. A second reader written by hand somewhere else is what
drifts, which is the same reason spec/campaign/github/system.als's settlement has exactly
one implementation, `campaign-tracker settlement`.

It reads two places, and the second only when it is handed one:

  the base        this campaign's own <slug>/ branches and the
                  worktrees on them -- a base sub-issue is worked there, never
                  under repos/ -- plus the base's single working tree, which
                  cannot be scoped to a campaign and so is reported without
                  being counted
  the directory   every checkout under <campaign-dir>/repos/, one at a time,
                  never one git command across member repositories, with
                  anything under runtime/ this script cannot name reported
                  beside them

Rows, not checks: the checks overlap on purpose -- a branch can be both unpushed
and unmerged -- so the report merges to one row per thing at risk and names
every check that found it. `<kind>` is one of: uncommitted, ignored, unpushed
commit, stash, worktree, unmerged branch.

Three readings this script exists to get right, each a failure that raises no
error (all probed; the evidence is in
.claude/skills/closing-campaign/references/gotchas.md):

  repos/ absent is not repos/ unreadable. A campaign with no member repository
  legitimately has no repos/ at all; a repos/ that exists and cannot be read is
  a reading that failed. While the enumeration carried 2>/dev/null the two
  looked identical, and a close read a repo-less campaign where there were
  checkouts it was not allowed to see. Absent prints "no member checkout" and
  the reading continues; unreadable exits 1, and so does an unreadable campaign
  directory or runtime/ one level up.

  A checkout is what git says it is, never what `.git` looks like. With
  --separate-git-dir, and in every linked worktree, `.git` is a file, so a
  stat test drops the whole checkout from the verdict and the close reads clear
  over uncommitted work.

  git status --porcelain never lists ignored files, so the obvious command for
  "nothing local is left" answers clean over a checkout holding a .env, a build
  directory or a downloaded fixture -- every one of which dies with the delete.
  Only --ignored is evidence.

  After a squash merge, ancestry is the wrong test. Squash is the default merge
  here, and it writes a new commit onto the upstream, so `branch --no-merged`
  calls a landed topic branch unmerged forever; paired with --delete-branch it is
  absent from the remote too, which is the exact signature of work that exists
  only on this machine. The discriminator is content: a branch whose own paths
  carry nothing beyond the upstream is noted as landed and not counted, and one
  already on the remote is noted as pushed and not counted. The comparison is
  scoped to the paths the branch itself touched, because a branch cut before
  the upstream moved on differs on files it never edited.

  A place that could not be read denies `clear`. Two REPORT lines say a check
  never ran -- a directory under repos/ that is not a checkout, and a repository
  whose default branch will not resolve, so no branch of it could be judged
  merged or landed. An absence of findings from a check that never ran is not an
  absence of findings: while those lines only informed, a run that skipped every
  member checkout still summarised `clear`, which is what licenses the delete.
  Such a run now says NOT clear and counts the unread places separately from the
  found ones. The other REPORT lines -- the base's own working tree, and any
  runtime/ entry this script cannot name -- are findings it chose not to count,
  not places it failed to look, and they still do not block.

Exit status is about the reading, never the verdict: 0 means the reading
completed and the last line says clear or NOT clear; 1 means the reading itself
failed and nothing may be concluded from it.

scripts/check-rule-readers.py is the second reader that keeps this claim true: it
refuses a commit that stages a `git status`, `git worktree list`, `git
for-each-ref`, `git stash list`, `git diff --quiet` or `git branch --no-merged`
as code in any tracked markdown outside scripts/ -- inside a fence or a
four-space indent, reading the index rather than the working tree. It catches
a pasted copy, not a re-implementation that names nothing; see its header.
Removing the guard returns this line to being a hope.

Usage: scripts/campaign-local-work.py <campaign-issue-number> [campaign-dir]

`campaign-dir` may be relative or absolute; the script resolves it. Callers do
not have to know, which is the point -- the caller who would have got it wrong
is the one not reading this.
"""
import os
import subprocess
import sys


def refuse(why):
    """Stop, on stdout -- step 2 keeps the redirected report, and a refusal that
    went to stderr would leave that artifact reading like a truncated clean one."""
    print(f"  -- REFUSE: {why}")
    raise SystemExit(1)


def run(cwd, *args, check=True):
    """Stdout of one command, or SystemExit -- a failed read is not an empty one."""
    out = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if out.returncode != 0 and check:
        refuse(f"`{' '.join(args)}` failed in {cwd}; nothing was checked\n"
               f"{out.stderr.strip()}")
    return out.stdout.rstrip("\n")


def git(repo, *args, check=True):
    return run(repo, "git", "-C", repo, *args, check=check)


def base_root():
    """The main checkout, resolved the one sanctioned way (AGENTS.md § The three planes)."""
    here = os.path.dirname(os.path.abspath(__file__))
    common = git(here, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return os.path.realpath(os.path.dirname(common))


def slug(repo):
    """owner/repo from the checkout's own origin, so a row names the repository."""
    url = git(repo, "remote", "get-url", "origin", check=False)
    if not url:
        return os.path.basename(repo)
    return "/".join(url.rstrip("/").removesuffix(".git").replace(":", "/").split("/")[-2:])


class Report:
    """Rows keyed by the thing at risk, so overlapping checks merge into one."""

    def __init__(self):
        self.rows = {}
        self.notes = []
        self.skipped = 0

    def add(self, repo, kind, ident, check, clears, note="", counted=True):
        row = self.rows.setdefault((repo, ident), {
            "kind": kind, "checks": [], "clears": clears,
            "note": note, "counted": counted})
        if check not in row["checks"]:
            row["checks"].append(check)
        # A branch that is both unpushed and unmerged is one thing to push.
        if clears == "push":
            row["kind"], row["clears"] = kind, clears
        if note and note not in row["note"]:
            row["note"] = (row["note"] + "; " + note).strip("; ")
        row["counted"] = row["counted"] or counted

    def report(self, line):
        self.notes.append(line)

    def unread(self, line):
        """A place the reading did not happen. Reported like a note, but it also
        denies `clear`: an absence of findings from a check that never ran is
        not an absence of findings, and `clear` is what licenses the delete."""
        self.notes.append(line)
        self.skipped += 1

    def counted(self):
        return [k for k, v in self.rows.items() if v["counted"]]


def default_branch(repo, name, rep):
    """origin/HEAD, or the remote's own symref when this checkout never set it."""
    upstream = git(repo, "symbolic-ref", "--quiet", "--short",
               "refs/remotes/origin/HEAD", check=False)
    if not upstream:
        head = git(repo, "ls-remote", "--symref", "origin", "HEAD", check=False)
        ref = [l for l in head.splitlines() if l.startswith("ref:")]
        upstream = "origin/" + ref[0].split()[1].removeprefix("refs/heads/") if ref else ""
    if not upstream:
        # unread, not report: its own message says no branch could be judged,
        # which is a check that did not run. The sibling case one function down
        # already denies `clear` for that reason and this one is the same kind.
        rep.unread(f"REPORT: {name}: cannot resolve the default branch, so no "
                   "branch could be judged merged or landed -- read it by hand")
    return upstream


def read_branches(repo, name, rep, upstream, refspec=("refs/heads/",)):
    """One row per branch, from both readings of "has this left the machine?".

    Unpushed commits and `--no-merged` overlap on purpose: a branch can be both,
    and it is still one thing to push. So they are read together and the row
    says what clears it.
    """
    unmerged = set()
    if upstream:
        unmerged = {b.strip().lstrip("* +").strip()
                    for b in git(repo, "branch", "--no-merged", upstream).splitlines()
                    if b.strip() and not b.strip().startswith("(")}
    for br in run(repo, "git", "-C", repo, "for-each-ref",
                  "--format=%(refname:short)", *refspec).splitlines():
        commits = git(repo, "log", "--oneline", br, "--not", "--remotes").splitlines()
        if not commits and br not in unmerged:
            continue
        checks = []
        if commits:
            checks.append(f"git log {br} --not --remotes")
        if br in unmerged:
            checks.append(f"git branch --no-merged {upstream}")
        kind = "unpushed commit" if commits else "unmerged branch"
        clears = "push" if commits else "merge"

        local = git(repo, "rev-parse", br, check=False)
        remote = git(repo, "rev-parse", "--verify", f"origin/{br}", check=False)
        if local and local == remote:
            note, counted = "pushed", False
        elif upstream:
            note, counted = landed(repo, br, upstream, name, rep)
        else:
            note, counted = "no upstream to compare against", True
        # An uncounted row is not work to move: saying "clears by push" over a
        # branch already pushed or already landed sends the reader to do it again.
        if not counted:
            clears = "nothing to clear"
        for check in checks:
            rep.add(name, kind, br, check, clears, note=note, counted=counted)


def landed(repo, br, upstream, name, rep):
    """Content, not ancestry -- the squash discriminator, scoped to the branch's own paths.

    Two-dot `diff <upstream>..<branch>` alone answers "no" for every branch cut
    before the upstream moved on, since the upstream's later work reads as
    removals. So the comparison is restricted to the paths the branch itself
    touched, and what is left over is reported with its file count and how far
    behind the branch is -- a count the reader judges, not a verdict the script
    invents.

    With no merge base -- an orphan branch, a checkout whose upstream ref is
    gone -- there is nothing to scope the comparison to, and the count that came
    out was `0 files differ`: the campaign's own defect, a measurement never
    taken printed as a clean result. That goes to `unread`, which denies `clear`.
    """
    mb = git(repo, "merge-base", upstream, br, check=False)
    if not mb:
        rep.unread(f"REPORT: {name}: {br} and {upstream} share no merge base, so "
                   f"nothing of {br}'s content could be compared -- read it by hand")
        return f"could not be compared against {upstream}: no merge base", True
    paths = git(repo, "diff", "--name-only", mb, br, check=False).splitlines()
    if not paths:
        return f"landed: nothing of its own beyond {upstream}", False
    files = git(repo, "diff", "--name-only", f"{upstream}..{br}", "--", *paths,
                check=False).splitlines()
    if not files:
        return f"landed: its own paths carry nothing beyond {upstream}", False
    behind = git(repo, "rev-list", "--count", f"{br}..{upstream}", check=False)
    note = f"{len(files)} of its own file(s) differ from {upstream}"
    if behind and behind != "0":
        note += (f"; {behind} commit(s) behind {upstream}, so some of that is "
                 "the upstream's own")
    return note, True


def read_worktrees(repo, name, rep, prefix=None):
    """Worktrees other than the main one; scoped to this campaign in the base."""
    entries = run(repo, "git", "-C", repo, "worktree",
                  "list", "--porcelain").split("\n\n")
    for entry in entries[1:]:
        path = branch = None
        for line in entry.splitlines():
            if line.startswith("worktree "):
                path = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                branch = line.split(" ", 1)[1].removeprefix("refs/heads/")
        if not path or (prefix and not (branch or "").startswith(prefix)):
            continue
        # What a worktree puts at risk is its uncommitted edits. Commits it
        # holds are already the branch's own row, so a clean one is named for
        # the person who has to remove it and is not a blocker -- otherwise
        # every close is refused by the worktree the closer is standing in.
        dirty = git(path, "status", "--porcelain", check=False).splitlines()
        where = f"on {branch}" if branch else "detached"
        rep.add(name, "worktree", path, "git worktree list", "discard",
                note=(f"{where}; {len(dirty)} uncommitted path(s)" if dirty
                      else f"{where}; clean, so removing it loses nothing"),
                counted=bool(dirty))


def campaign_prefixes(n, rep):
    """Every branch prefix this campaign's claims can wear, newest first.

    Two for one window: `<slug>/`, cut since #181, and the `campaign-<N>/` every
    branch before it carries. The slug comes from `campaign-tracker.py slug`,
    the one reader of the `campaign:<slug>` label -- read as the WORD it prints,
    never the exit status. A slug that could not be read narrows the reading to
    the retired form and is REPORTED, because a narrower sweep that says nothing
    reads exactly like a machine holding less work than it does."""
    tracker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "campaign-tracker.py")
    try:
        out = subprocess.run([sys.executable, tracker, "slug", str(n)],
                             capture_output=True, text=True)
    except OSError as e:
        out = None
        why = f"campaign-tracker could not run ({e.__class__.__name__})"
    if out is not None:
        word = out.stdout.strip()
        if word and word != "none":
            why = None
        elif out.returncode == 1:
            # LOOKED AND FOUND NOTHING: the tracker read the campaign issue and
            # it carries no `campaign:` label.
            why = f"#{n} carries no `campaign:` label, so it has no slug"
        else:
            # COULD NOT LOOK. Kept apart from the line above, because the fix is
            # different: one is a label to add, the other a reading to retry.
            why = (f"campaign-tracker slug {n} exited {out.returncode} without "
                   f"a verdict: {out.stderr.strip()[:120] or 'no message'}")
    if why:
        rep.report(f"REPORT: {why}, so only campaign-{n}/ branches were read. "
                   f"A branch cut under a slug would not appear below.")
        return [f"campaign-{n}/"]
    return [f"{word}/", f"campaign-{n}/"]


def read_base(base, n, rep):
    name = slug(base)
    upstream = default_branch(base, name, rep)
    prefixes = campaign_prefixes(n, rep)
    read_branches(base, name, rep, upstream,
                  refspec=[f"refs/heads/{p}" for p in prefixes])
    read_worktrees(base, name, rep, prefix=tuple(prefixes))
    # The base's single working tree carries no campaign, so it cannot be
    # scoped and is not a blocker on this close -- but a person deciding to
    # delete wants to see it. No --ignored here: the base ignores every
    # campaign directory.
    dirty = git(base, "status", "--porcelain").splitlines()
    if dirty:
        rep.report(f"REPORT: {len(dirty)} uncommitted path(s) in {base}, "
                   "unattributed: the base has one working tree and an edit "
                   "in it carries no campaign, so it is not counted")


def read_runtime(campaign_dir, rep):
    """Anything under `runtime/` this script does not know the name of.

    GENERIC on purpose. This used to name `runtime/handover/` specifically, and
    when those briefs were retired the reading went with them -- so the files
    still on disk stopped being reported at all, one step before a close deletes
    the directory. The two entries the scaffold writes are known and stay quiet;
    anything else is named, because `runtime/` is the one place under the
    campaign directory that legitimately holds state and a close destroys it."""
    # `.gitkeep` is what the scaffold ships to keep `runtime/` a directory
    # at all, so leaving it out gave every fresh campaign a standing false
    # REPORT about a file the skill itself put there.
    known = {"repos", "campaign-issue-body-derived.md", ".gitkeep"}
    runtime = os.path.join(campaign_dir, "runtime")
    try:
        found = sorted(e for e in os.listdir(runtime)) if os.path.isdir(runtime) else []
    except OSError as e:
        refuse(f"{runtime} exists and did not enumerate ({e.strerror}); "
               "nothing was checked")
    extra = [e for e in found if e not in known]
    if extra:
        rep.report(f"REPORT: {len(extra)} entr(y/ies) under runtime/ this "
                   f"script does not know ({', '.join(extra)}): say what each "
                   f"is before the close deletes it")


def read_checkouts(campaign_dir, rep):
    read_runtime(campaign_dir, rep)
    repos = os.path.join(campaign_dir, "repos")
    if not os.path.isdir(repos):
        print(f"  -- no member checkout: {repos} does not exist")
        return
    try:
        found = sorted(e.path for e in os.scandir(repos) if e.is_dir())
    except OSError as e:
        refuse(f"{repos} exists and did not enumerate ({e.strerror}); "
               "nothing was checked")
    for repo in found:
        # Ask git, never stat `.git`: --separate-git-dir and every linked
        # worktree make `.git` a *file* holding a gitdir: pointer, so an
        # isdir() test would drop the whole checkout from the verdict.
        if not git(repo, "rev-parse", "--git-dir", check=False):
            rep.unread(f"REPORT: {repo} is not a checkout; read it by hand")
            continue
        name = slug(repo)
        for line in git(repo, "status", "--porcelain", "--ignored=matching").splitlines():
            state, path = line[:2].strip(), line[3:].strip().strip('"')
            # `CLAUDE.local.md` is the campaign's principles, written into each
            # delegate's clone and excluded in that clone's `.git/info/exclude`
            # -- and `--ignored=matching` reports an info/exclude'd file exactly
            # as it reports a build directory (probed 2026-09-04: it comes back
            # `!! CLAUDE.local.md`). It is not work: it is derived from the
            # campaign's own AGENTS.md and is rewritten at the next launch, so
            # counting it made every campaign that ever launched a delegate read
            # NOT clear for ever, which is a close gate that can never pass.
            if path == "CLAUDE.local.md" and state == "!!":
                continue
            kind = "ignored" if state == "!!" else "uncommitted"
            rep.add(name, kind, path.split("/")[0] if kind == "ignored" else path,
                    "git status --porcelain --ignored=matching", "discard")
        read_branches(repo, name, rep, default_branch(repo, name, rep))
        # A checkout left on a detached HEAD holds commits no branch names, so
        # the branch reading above cannot see them: `git log HEAD --not
        # --remotes` is the one that does.
        if not git(repo, "symbolic-ref", "--quiet", "HEAD", check=False):
            for line in git(repo, "log", "--oneline", "HEAD", "--not",
                            "--remotes").splitlines():
                rep.add(name, "unpushed commit", line.split(" ")[0],
                        "git log HEAD --not --remotes", "push",
                        note="on a detached HEAD, named by no branch")
        for line in git(repo, "stash", "list").splitlines():
            rep.add(name, "stash", line.split(":")[0], "git stash list", "discard")
        read_worktrees(repo, name, rep)

def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    n = sys.argv[1]
    campaign_dir = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else ""
    if campaign_dir and not os.path.isdir(campaign_dir):
        refuse(f"{campaign_dir} is not a directory; nothing was checked")
    if campaign_dir and not os.access(campaign_dir, os.R_OK | os.X_OK):
        refuse(f"{campaign_dir} cannot be read; nothing was checked")
    # Resolve it here, once, rather than asking every caller to. `git()` passes
    # the same path as both `cwd=` and `-C`, so git resolves it a second time
    # from inside the directory it just entered: a relative path doubles, the
    # command fails, and `check=False` turns that into "not a checkout". Every
    # member checkout then goes unread while the run still ends `clear`.
    # A documented precondition nothing enforces is a drift waiting to happen;
    # resolving here is the half that does not depend on the caller having
    # read the docstring.
    if campaign_dir:
        campaign_dir = os.path.realpath(campaign_dir)

    base = base_root()
    rep = Report()
    print(f"campaign #{n}  base {base}"
          + (f"  directory {campaign_dir}" if campaign_dir
             else "  (no directory on this machine)"))
    read_base(base, n, rep)
    if campaign_dir:
        read_checkouts(campaign_dir, rep)

    width = max((len(r) for r, _ in rep.rows), default=0)
    for (repo, ident), row in sorted(rep.rows.items()):
        mark = " " if row["counted"] else "~"
        print(f"  {mark} {repo:<{width}}  {row['kind']}  {ident}"
              + (f"  [{row['note']}]" if row["note"] else ""))
        print(f"      found by  {', '.join(row['checks'])}")
        print(f"      clears by {row['clears']}")
    for line in rep.notes:
        print(f"  -- {line}")

    count = len(rep.counted())
    if count or rep.skipped:
        unread = (f", and {rep.skipped} place(s) went unread"
                  if rep.skipped else "")
        fix = []
        if count:
            fix.append("clear every counted row, or say to discard it")
        if rep.skipped:
            fix.append("read every REPORT place by hand")
        print(f"  -- {count} item(s) exist only on this machine{unread}; "
              f"NOT clear: {', '.join(fix)}, then re-run")
    else:
        print("  -- 0 item(s) exist only on this machine; clear")


# Guarded, where it used to be a bare `main()`: importing this module ran the
# whole reading and then exited on the missing argv, so nothing could test its
# calculations. Every other script here is already shaped this way.
if __name__ == "__main__":
    main()
