#!/usr/bin/env python3
"""Prove the claim guard refuses for the reason it prints, and allows for one too.

Every case runs the shipped script against a fixture built here -- never the
real base -- and hands it a hook payload on stdin. The fixture is a real
repository with a real remote (a local bare one), because after #176 a claim
is a branch whose ref exists on the remote and the guard reads refs and
checkouts and nothing else. No case reaches the network.

WHAT EACH GROUP PINS

Allowing is as load-bearing as refusing. A guard installed machine-wide that
refused outside a campaign would stop every session on this machine, so the
"exits 0" cases are not filler: they are the ones whose failure is worst. And
an allow that prints WHY -- which clause admitted it, or that the command was
not read and the commit gate covers it -- is the whole of F1's closing, so the
sentence is asserted and not only the status.

The refusals are broken apart one at a time, because they share an exit status
and a stream. A case that only asserted `exit 2` would pass while any single
branch was deleted, so each asserts the sentence that branch alone prints.

#180's reproduction rows are the cases under "where the session sits", each
named for its row.

Usage: scripts/check-campaign-claim-test.py
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "check-campaign-claim.py"
CLAIM = HERE / "campaign-claim.py"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t",
                           "-c", "user.name=t", *args],
                          capture_output=True, text=True)


class Fixture:
    """A base with a remote, one campaign directory, and the checkouts asked
    for. `claims` are branches cut and pushed, each in a worktree at a SIBLING
    path (outside the base root, which is #180's shape); `unpushed` are
    campaign branches in worktrees whose ref exists nowhere on the remote;
    `feature` is a worktree on a plain branch."""

    def __init__(self, d, claims=("campaign-1/7-x",), unpushed=(), feature=None):
        self.d = Path(d)
        self.remote = self.d / "r.git"
        self.base = self.d / "base"
        # `main` pinned by hand: the cases assert the branch by name, and a
        # runner's init.defaultBranch is whatever its git ships (`master` on
        # the CI image).
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main",
                        str(self.remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.base)],
                       capture_output=True, check=True)
        git(self.base, "symbolic-ref", "HEAD", "refs/heads/main")
        (self.base / "scripts").mkdir()
        (self.base / "scripts" / "campaign-claim.py").write_text(CLAIM.read_text())
        self.camp = self.base / "demo-260904"
        self.camp.mkdir()
        # The allowlist shape check-tree-shape requires, which also ignores
        # the campaign directory: the commit gate's suite commits through the
        # installed hooks over this same fixture.
        (self.base / ".gitignore").write_text(
            "/*\n!/.gitignore\n!/scripts/\n!/spec/\n!/docs/\n")
        git(self.base, "add", "-A")
        git(self.base, "commit", "-qm", "init")
        git(self.base, "push", "-q", "origin", "HEAD")
        self.trees = {}
        for i, b in enumerate(claims):
            git(self.base, "branch", b)
            git(self.base, "push", "-q", "origin", b)
            self.trees[b] = self.worktree(f"wt-c{i}", b)
        for i, b in enumerate(unpushed):
            git(self.base, "branch", b)
            self.trees[b] = self.worktree(f"wt-u{i}", b)
        if feature:
            git(self.base, "branch", feature)
            self.trees[feature] = self.worktree("wt-f", feature)

    def worktree(self, name, branch, under=None):
        path = (under or self.d) / name
        r = git(self.base, "worktree", "add", "-q", str(path), branch)
        assert r.returncode == 0, r.stderr
        return path.resolve()

    def clone(self, branch=None):
        """A delegate's clone under the campaign directory."""
        dest = self.camp / "repos" / "campaign-base"
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(dest)],
                       capture_output=True, check=True)
        if branch:
            git(dest, "switch", "-q", "--track", f"origin/{branch}")
        return dest.resolve()

    def member(self, branch=None):
        """A MEMBER repository's clone under the campaign directory: its own
        remote, and no marker of its own. That last part is what makes it a
        different case from `clone()` above -- a clone of the base carries the
        marker and so answers as a base, while a member repository does not,
        and the guard has to resolve it through the base above it."""
        remote = self.d / "m.git"
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main",
                        str(remote)], check=True)
        seed = self.d / "m-seed"
        subprocess.run(["git", "clone", "-q", str(remote), str(seed)],
                       capture_output=True, check=True)
        (seed / "code.txt").write_text("x\n")
        git(seed, "add", "-A")
        git(seed, "commit", "-qm", "init")
        git(seed, "push", "-q", "origin", "HEAD")
        git(seed, "branch", "campaign-1/7-x")
        git(seed, "push", "-q", "origin", "campaign-1/7-x")
        dest = self.camp / "repos" / "member"
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", str(remote), str(dest)],
                       capture_output=True, check=True)
        if branch:
            git(dest, "switch", "-q", "--track", f"origin/{branch}")
        return dest.resolve()


def herdr_stub(d, sessions):
    """A directory to put first on PATH holding a `herdr` that prints the
    listing `sessions` describes: {session_id: name}. A stub on PATH rather
    than an environment variable the guard reads, because the guard's subject
    is what the CALLING session may do, and a seam that session can set is a
    bypass wearing a test's clothes."""
    listing = {"result": {"agents": [
        {"agent_session": {"value": sid}, "name": name, "pane_id": f"p{i}"}
        for i, (sid, name) in enumerate(sessions.items())]}}
    # One directory PER STUB: they used to share `d/stub`, so the last call
    # silently rewrote every earlier one and five cases were answered by a
    # listing they never asked for.
    tag = "-".join(sorted(sessions.values())) or "unnamed"
    bindir = Path(d) / f"stub-{abs(hash(tag)) % 10**8}"
    bindir.mkdir(exist_ok=True)
    body = json.dumps(listing).replace("'", "'\\''")
    (bindir / "herdr").write_text(f"#!/bin/sh\nprintf '%s' '{body}'\n")
    (bindir / "herdr").chmod(0o755)
    return {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}


def herdr_stub_raw(d, text):
    """A `herdr` printing exactly `text`, for the shapes a listing should not
    have and the guard must survive rather than traceback through."""
    bindir = Path(d) / f"stub-raw-{abs(hash(text)) % 10**8}"
    bindir.mkdir(exist_ok=True)
    body = text.replace("'", "'\\''")
    (bindir / "herdr").write_text(f"#!/bin/sh\nprintf '%s' '{body}'\n")
    (bindir / "herdr").chmod(0o755)
    return {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}


def no_herdr(d):
    """A PATH on which `herdr` exits non-zero: the COULD NOT LOOK case."""
    bindir = Path(d) / "nostub"
    bindir.mkdir(exist_ok=True)
    (bindir / "herdr").write_text("#!/bin/sh\necho 'herdr: gone' >&2\nexit 127\n")
    (bindir / "herdr").chmod(0o755)
    return {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}


def ask(cwd, tool="Edit", command=None, path=None, event=None, stdin=None,
        tool_input=None, env=None, session="sid-1", run_cwd=None):
    """`cwd` is what the PAYLOAD says; `run_cwd` is where the process runs.
    They are the same question everywhere except one case: a payload that will
    not parse carries no cwd, so the guard falls back to its own, and a case
    that did not set it would write that verdict into the REAL campaign log."""
    payload = {
        "session_id": session,
        "cwd": str(cwd),
        "tool_name": tool,
        "tool_input": tool_input if tool_input is not None else (
            {"command": command} if command is not None
            else {"file_path": path or str(Path(cwd) / "a.txt")}),
        "hook_event_name": event or "PreToolUse",
    }
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin if stdin is not None else json.dumps(payload),
        capture_output=True, text=True, cwd=str(run_cwd) if run_cwd else None,
        env=dict(os.environ, **(env or {})))


UNREAD = "was not read for a target"
GATE = "pre-commit claim gate"
CORPUS = HERE / "fixtures" / "guard-allow-corpus.jsonl"


def guard_module():
    """The guard, imported. The corpus replay calls it in-process and every
    other case runs the shipped script: 500 subprocesses at ~50 ms of
    interpreter start each is half a minute of nothing, and the replay is a
    sweep rather than a case. `corpus: in-process and subprocess agree` below
    is what keeps that from being a fixture standing in for the real thing."""
    src = HERE / "check-campaign-claim.py"
    spec = importlib.util.spec_from_loader(
        "ccc", importlib.machinery.SourceFileLoader("ccc", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ask_inproc(mod, payload, env):
    """(exit status, stdout, stderr) from the guard called in this process."""
    old = dict(os.environ)
    os.environ.update(env or {})
    o, e = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            rc = mod.pre(payload)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return rc, o.getvalue(), e.getvalue()


def corpus_rows():
    """The corpus, or None when it is not there. NOT AN EMPTY LIST: a replay
    over zero entries passes exactly like a replay over five hundred, and this
    file's whole reason for existing is that a check reporting nothing reads
    like a check that found nothing wrong."""
    if not CORPUS.is_file():
        return None
    return [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]


def row_posts_comment(mod, row):
    """Whether this corpus row posts a comment, read by the guard's own reader.

    Asked through `comment_body` and not by grepping the command for
    `gh issue comment`: a second reader of which calls post a comment would
    disagree with the one under test on exactly the forms this file exists to
    measure."""
    pairs, _why = mod.paired_segments(row["command"])
    for tokens, heredocs in pairs or []:
        word, rest = mod.head(tokens)
        if word != "gh":
            continue
        text, why, unjudged = mod.comment_body(rest, heredocs)
        if text is not None or why or unjudged:
            return True
    return False


def corpus_issues(mod, rows):
    """Every sub-issue number a corpus command names. The replay fixture holds
    a claim on each, because the corpus is the calls sessions made WHILE
    HOLDING one -- a fixture without them would replay the campaign's ordinary
    work against a session that had claimed nothing and call the refusals
    findings."""
    out = set()
    for r in rows:
        if r["tool"] != "Bash":
            continue
        segs, _why = mod.segments(r["command"])
        for seg in segs or []:
            word, rest = mod.head(seg)
            if word != "gh" or not mod.gh_write(rest)[0]:
                continue
            n = mod.issue_target(rest)
            if n:
                out.add(int(n))
    return sorted(out)


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}\n      {detail}")

    def out(r):
        return r.stdout + r.stderr

    # 1. Outside every base and campaign directory. The case that decides
    # whether a machine-wide registration is safe at all.
    with tempfile.TemporaryDirectory() as d:
        r = ask(d, path=str(Path(d) / "x.md"))
        check("a Write to a path in no base and no campaign is allowed",
              r.returncode == 0 and "not campaign work" in r.stdout, out(r)[:200])
        check("...and the allow names the path and says it looked",
              str(Path(d).resolve() / "x.md") in r.stdout
              and "no base tree and no campaign directory" in r.stdout, out(r)[:300])
        r = ask(d, tool="Bash", command="gh issue close 9")
        check("a gh write from a cwd in no repository and no base is allowed "
              "as not in a campaign",
              r.returncode == 0 and "in no campaign" in r.stdout, out(r)[:200])
        r = ask(d, tool="Bash", command="rm -rf x")
        check("a shell command outside is allowed unread",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:200])
        # A REPOSITORY IS NOT A BASE, and this guard is registered for every
        # session on the machine: gating the gh half on "has a repository root"
        # walled every campaign-plane write in every unrelated checkout. The
        # case above cannot catch it -- its cwd has no repository at all.
        plain = Path(d) / "plain"
        plain.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(plain)], check=True)
        for cmd in ("gh issue close 9", "gh pr merge 9 --merge",
                    "gh pr comment 9 --body 'NOTE campaign-1-worker-1: x'"):
            r = ask(plain, tool="Bash", command=cmd)
            check(f"`{cmd}` from an ordinary git repository that is no base is "
                  f"allowed, naming why",
                  r.returncode == 0 and "in no campaign" in r.stdout
                  and "not a base" in r.stdout, out(r)[:300])

    # 2. The two clauses, and the refusal when neither holds.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, feature="feature")
        wt7 = f.trees["campaign-1/7-x"]
        r = ask(d, path=str(wt7 / "a.md"))
        check("clause 1: a write into a checkout on a claimed branch is allowed "
              "from any cwd",
              r.returncode == 0 and "Clause 1" in r.stdout
              and "campaign-1/7-x, a claim" in r.stdout, out(r)[:300])
        check("...and says the ref was read from the local origin/ copy",
              "refs/remotes/origin/campaign-1/7-x" in r.stdout, out(r)[:300])
        r = ask(f.trees["feature"], path=str(f.base / "AGENTS.md"))
        check("clause 2: a write into the main checkout on main is allowed when "
              "the session's root has a worktree on a claim",
              r.returncode == 0 and "Clause 2" in r.stdout
              and str(wt7) in r.stdout, out(r)[:400])
        check("...and it says clause 1 did not hold and why",
              "Clause 1 does not hold" in r.stdout and "on main, not a campaign "
              "branch" in r.stdout, out(r)[:400])
        check("...and calls itself the weaker gate, naming the commit gate",
              "weaker gate" in r.stdout and "commit gate is what holds" in r.stdout,
              out(r)[:400])
        r = ask(f.base, path=str(f.camp / "notes.md"))
        check("a write under the campaign directory is campaign work, named as such",
              r.returncode == 0 and "inside the campaign directory" in r.stdout,
              out(r)[:300])
        r = ask(f.base, tool="Bash", command="perl -pi -e s/a/b/ AGENTS.md")
        check("a shell write inside is allowed unread, saying the commit gate "
              "covers it",
              r.returncode == 0 and UNREAD in r.stdout and GATE in r.stdout,
              out(r)[:300])

    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=(), feature="feature")
        r = ask(f.base, path=str(f.base / "AGENTS.md"))
        check("a write into the base with no claim anywhere is refused",
              r.returncode == 2, f"exit {r.returncode}: {out(r)[:300]}")
        check("...on stderr, where the model reads it", "REFUSED" in r.stderr)
        check("...saying neither clause held, and what it read",
              "Clause 1 does not hold" in r.stderr and "Clause 2 does not hold"
              in r.stderr and "no checkout under" in r.stderr, out(r)[:400])
        check("...and says how to take one", "campaign-claim.py take" in r.stderr)
        # A REMEDY THAT DOES NOT RUN IS NOT A REMEDY. `--dir` went with the
        # record in #176 and argparse now rejects it, so the refusal sent the
        # reader to a command that fails. Asserted against `take --help`
        # rather than against a literal, so the next retired flag is caught
        # too.
        usage = subprocess.run([sys.executable, str(CLAIM), "take", "--help"],
                               capture_output=True, text=True).stdout
        remedy = next(x for x in r.stderr.splitlines()
                      if "campaign-claim.py take" in x)
        unknown = [w.strip(",.") for w in remedy.split()
                   if w.startswith("--") and w.strip(",.") not in usage]
        check("...and every option the remedy prints is one `take` accepts",
              not unknown, f"not in `take --help`: {unknown}; remedy: {remedy}")
        r = ask(f.base, path=str(f.camp / "notes.md"))
        check("a write under the campaign directory with no claim is refused",
              r.returncode == 2 and "inside the campaign directory" in r.stderr,
              out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue close 9")
        check("a gh write with no claim is refused",
              r.returncode == 2 and "no claim covering a write to #9" in r.stderr,
              out(r)[:300])

    # 3. The ref is the claim, and a ref that cannot be read is not an absence.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=(), unpushed=("campaign-1/8-y",))
        wt8 = f.trees["campaign-1/8-y"]
        r = ask(wt8, path=str(wt8 / "a.md"))
        check("a campaign branch whose ref is on no remote is not a claim",
              r.returncode == 2 and "no such head" in r.stderr, out(r)[:400])
        check("...and says it asked the remote, having found no local copy",
              "ls-remote origin campaign-1/8-y" in r.stderr, out(r)[:400])
        git(f.base, "remote", "set-url", "origin", str(f.d / "nowhere.git"))
        r = ask(wt8, path=str(wt8 / "a.md"))
        check("a remote that cannot be asked is printed as unreadable, not absent",
              r.returncode == 2 and "could not be read" in r.stderr
              and "no such head" not in r.stderr, out(r)[:400])

    # 4. Where the session sits: #180's rows, on a worktree at a sibling path.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=(), feature="feature")
        wt1 = f.trees["feature"]
        r = ask(wt1, path=str(wt1 / "scripts" / "x.py"))
        check("#180 row 6: a Write into a sibling worktree, cwd inside it, no "
              "claim, is refused", r.returncode == 2, f"exit {r.returncode}: {out(r)[:300]}")
        check("...naming the MAIN checkout as the base it read",
              f"inside the base {f.base.resolve()}" in r.stderr, out(r)[:400])
        r = ask(wt1, path=str(f.base / "AGENTS.md"))
        check("#180 row 7: a Write from there into the main checkout is refused",
              r.returncode == 2, out(r)[:300])
        r = ask(wt1, path=str(f.camp / "notes.md"))
        check("#180 row 8: a Write from there into the campaign directory is refused",
              r.returncode == 2, out(r)[:300])
        r = ask(wt1, tool="Bash", command="gh issue close 999")
        check("#180 row 11: gh issue close from there with no claim is refused",
              r.returncode == 2 and "a write to #999" in r.stderr, out(r)[:300])
        r = ask(wt1, tool="Bash", command=f"rm -rf {f.camp}")
        check("#180 row 10: a shell delete of the campaign directory is allowed "
              "UNREAD -- the named cost -- and says the commit gate is the reader",
              r.returncode == 0 and UNREAD in r.stdout and GATE in r.stdout,
              out(r)[:300])
        r = ask(wt1, tool="Bash", command="git commit -m x")
        check("#180 row 9: git commit is not read here; it is the commit gate's",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, feature="feature")
        wt1 = f.trees["feature"]
        r = ask(wt1, path=str(wt1 / "scripts" / "x.py"))
        check("...and the same Write with a claim held under the root is allowed",
              r.returncode == 0 and "Clause 2" in r.stdout, out(r)[:300])
        git(f.base, "branch", "feature2")
        nested = f.worktree("x", "feature2", under=f.base / ".claude" / "worktrees")
        r = ask(nested, path=str(nested / "scripts" / "x.py"))
        check("a worktree nested under .claude/worktrees/ resolves to the base too",
              r.returncode == 0 and f"inside the base {f.base.resolve()}" in r.stdout,
              out(r)[:300])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "nogit"
        p.mkdir()
        r = ask(p, path=str(p / "x.md"))
        check("a directory with no marker and no git is allowed, printing that "
              "it looked and found no base",
              r.returncode == 0 and "not a git repository" in r.stdout
              and "not campaign work" in r.stdout, out(r)[:300])

    # 5. A delegate's clone under the campaign directory is a base tree of its
    # own, and its claim is its own branch.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x",))
        clone = f.clone()
        r = ask(clone, path=str(clone / "AGENTS.md"))
        check("a clone on main under the campaign directory, holding nothing, "
              "is refused", r.returncode == 2 and f"inside the base {clone}"
              in r.stderr, out(r)[:400])
        git(clone, "switch", "-q", "--track", "origin/campaign-1/7-x")
        r = ask(clone, path=str(clone / "AGENTS.md"))
        check("...and on a claimed branch it is allowed by clause 1",
              r.returncode == 0 and "Clause 1" in r.stdout, out(r)[:300])
    # 5b. THE ORDINARY DELEGATE SHAPE, which is NOT the clone above: a MEMBER
    # repository's clone carries no marker, so it resolves through the base,
    # and `held` then sweeps the BASE's worktrees -- which structurally cannot
    # see the member clone's own branch. A delegate standing on its own pushed
    # claim read as holding none, and every gh write it made was refused.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=())
        member = f.member(branch="campaign-1/7-x")
        r = ask(member, tool="Bash", command="gh issue close 7")
        check("a gh write from a member clone standing on its own claim is "
              "allowed, though no worktree of the base is on it",
              r.returncode == 0 and "campaign-1/7-x, a claim" in r.stdout,
              out(r)[:400])
        r = ask(member, tool="Bash", command="gh issue close 9")
        check("...and it is still narrowed: a write to another issue is refused",
              r.returncode == 2 and "a write to #9" in r.stderr, out(r)[:400])
        git(member, "switch", "-q", "main")
        r = ask(member, tool="Bash", command="gh issue close 7")
        check("...and the same clone off the claim holds none of its own",
              r.returncode == 2 and "a write to #7" in r.stderr, out(r)[:400])

    # 6. gh: the table, the exemption, the narrowing, the parse.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=())
        for cmd, what in [
            ("gh pr comment 5 --body hi", "gh pr comment"),
            ("gh pr review 5 --approve", "gh pr review"),
            ("gh pr edit 5 --title x", "gh pr edit"),
            ("gh pr merge 5 --merge", "gh pr merge"),
            ("gh pr create --title x --body y", "gh pr create"),
            ("gh issue reopen 5", "gh issue reopen"),
            ("gh issue develop 5", "gh issue develop"),
            ("gh issue transfer 5 o/r", "gh issue transfer"),
            ("gh issue delete 5 --yes", "gh issue delete"),
            ("gh issue edit 5 --body x", "gh issue edit"),
            ("gh issue comment 5 --body 'NOTE campaign-1-worker-1: x'", "gh issue comment"),
            ("gh api repos/o/r/issues -f title=x", "gh api with a field"),
            ("gh api -X PATCH repos/o/r/issues/5 --input body.json", "gh api PATCH"),
            ("gh api --method=DELETE repos/o/r/issues/5", "gh api DELETE"),
        ]:
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd}` is a campaign-plane write and is refused without a claim",
                  r.returncode == 2 and what in r.stderr,
                  f"exit {r.returncode}: {out(r)[:200]}")
        for cmd in ("gh issue create --title x --body 'git mv a b; gh issue close 3'",
                    "gh issue view 5", "gh pr view 5 --json state",
                    "gh api repos/o/r/issues/5", "gh repo clone o/r"):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd}` is not a write and is allowed",
                  r.returncode == 0, f"exit {r.returncode}: {out(r)[:200]}")
        r = ask(f.base, tool="Bash", command="gh issue create --title x")
        check("...and the issue-create allow names the exemption",
              "minted there" in r.stdout, out(r)[:200])
        r = ask(f.base, tool="Bash", command='gh pr comment 5 --body "unbalanced')
        check("a gh command shlex cannot split is refused, naming why",
              r.returncode == 2 and "would not split" in r.stderr
              and "No closing quotation" in r.stderr, out(r)[:200])
        r = ask(f.base, tool="Bash", command="echo ok && gh issue close 5")
        check("a gh write in a later segment is read",
              r.returncode == 2 and "a write to #5" in r.stderr, out(r)[:200])
        r = ask(f.base, tool="Bash", command="gh -R o/r issue close 5")
        check("a valued flag before the subcommand does not hide it",
              r.returncode == 2 and "a write to #5" in r.stderr, out(r)[:200])
        r = ask(f.base, tool="Bash",
                command="gh issue close https://github.com/o/r/issues/12 -R o/r")
        check("the closed issue is read from a URL too",
              r.returncode == 2 and "a write to #12" in r.stderr, out(r)[:200])
        # A PATH IS NOT AN ISSUE NUMBER. Reading the tail of any token holding
        # a slash made `--body-file /tmp/123` name #123 and refuse the write
        # for a claim nobody could hold.
        # The body file is REAL and kinded, so the comment check has nothing
        # to say and the diagnosis under test is the only one printed. Its
        # name still ends in digits after a slash, which is the whole shape.
        (f.base / "123").write_text("NOTE campaign-1-worker-1: x\n")
        r = ask(f.base, tool="Bash",
                command=f"gh issue comment --body-file {f.base}/123 7")
        check("a file path operand is not read as the issue number",
              r.returncode == 2 and "a write to #7" in r.stderr
              and "#123" not in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue close docs/2024/9")
        check("...nor is any other slashed word that is not an issue URL",
              "a write to #9" not in r.stderr, out(r)[:300])
        # And a flag's value that IS a bare number must not be read as the
        # issue either -- which the path rule alone cannot catch, since the
        # value has no slash. VALUED is what skips it.
        (f.base / "9").write_text("NOTE campaign-1-worker-1: x\n")
        r = ask(f.base, tool="Bash",
                command="gh issue comment --body-file 9 7")
        check("a valued flag's numeric value is not the issue the write names",
              r.returncode == 2 and "a write to #7" in r.stderr
              and "#9" not in r.stderr, out(r)[:300])
        # Position must not hide the call: every executing form the old
        # SERVICE_DOORS regex caught, the table catches too.
        for cmd in ("(gh issue close 5)",
                    "{ gh issue close 5; }", "/opt/homebrew/bin/gh issue close 5",
                    "env gh issue close 5", "GH_TOKEN=x gh issue close 5",
                    "command gh issue close 5", "time gh issue close 5",
                    "for i in 1; do gh issue close 5; done",
                    "if true; then gh issue close 5; fi",
                    "bash -c 'gh issue close 5'",
                    # The four the fix round's own spec-conformance audit found
                    # still open at 1918ce7: a backquoted call, eval's operand,
                    # and a -c spelled last in a short-option cluster.
                    "`gh issue close 5`", 'eval "gh issue close 5"',
                    "bash -lc 'gh issue close 5'", "sh -ec 'gh issue close 5'"):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd!r}` is read as the gh write it is",
                  r.returncode == 2 and "a write to #5" in r.stderr,
                  f"exit {r.returncode}: {out(r)[:200]}")
        # `cat <<EOF ... see gh ... EOF` used to be in this list and is not any
        # more: since #193 a heredoc body is data, and the cases for that are
        # the block at the end of this section.
        for cmd in ("xargs gh issue close", "echo gh issue close 5",
                    "echo hi\ngh issue close 5",
                    # The fourth: an assignment's VALUE names gh and the call
                    # itself is an expansion this cannot resolve.
                    "G=gh; $G issue close 5"):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd!r}`: a gh token this cannot read as the call is a "
                  f"write of unknown kind, refused without a claim",
                  r.returncode == 2 and "cannot read as a call" in r.stderr
                  and GATE not in r.stdout, f"exit {r.returncode}: {out(r)[:200]}")
        r = ask(f.base, tool="Bash", command="gh api -X GET search/issues -f q=x")
        check("gh api with an explicit GET is a read, fields or not",
              r.returncode == 0 and "gh api GET" in r.stdout, out(r)[:200])
        # `--method=X` carries its value, so it can be the LAST token where
        # `-X X` cannot. The method scan sliced the last token off and read the
        # attached spelling as absent, which allowed the write.
        r = ask(f.base, tool="Bash",
                command="gh api repos/o/r/issues/1 --method=DELETE")
        check("an attached --method= is read even as the last word",
              r.returncode == 2 and "gh api DELETE" in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh api repos/o/r/issues/1 --method=GET")
        check("...and an attached GET is still a read", r.returncode == 0
              and "gh api GET" in r.stdout, out(r)[:300])
        # A STRING HANDED TO A SHELL IS NOT READ, and these say so rather than
        # leaving it to the absence of a case. Reading them cost two blocking
        # findings -- a machine-wide over-refusal and a decoy that widened the
        # claim check -- so the boundary is here and is asserted here.
        for cmd in ('bash <<< "gh issue close 5"',
                    "echo 'gh issue close 5' | bash",
                    "echo hi | bash", "ls -la | wc -l"):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd}` is allowed unread: a string a shell is handed is a "
                  f"shell string",
                  r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        # The over-refusals that reading them produced, each an ordinary
        # command on a guard every session runs.
        for cmd in ('gh issue create --title t --body "then gh issue close 9"'
                    ' && bash run.sh',
                    'git commit -m "fix gh issue close parsing" && bash deploy.sh',
                    'echo "see gh docs" | bash'):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd[:44]}...` is allowed: a quoted string is data",
                  r.returncode == 0, out(r)[:300])
        # The list is a LIST, and the spec says so: a shell it does not name
        # has its -c string unread, like any other interpreter. Without this
        # case the sentence has no reader and drifts on the next name added.
        for sh in ("csh", "tcsh"):
            r = ask(f.base, tool="Bash", command=f"{sh} -c 'gh issue close 5'")
            check(f"{sh} is not in the named list, so its -c string is unread",
                  r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        for sh in ("ksh", "fish"):
            r = ask(f.base, tool="Bash", command=f"{sh} -c 'gh issue close 5'")
            check(f"{sh} runs a -c string like every other shell that does",
                  r.returncode == 2 and "a write to #5" in r.stderr, out(r)[:200])
        # `do` is a PREFIX, so a for-body is read as the call it is -- the
        # docstring used to name it as unreadable, which was the other way
        # round.
        r = ask(f.base, tool="Bash",
                command="for i in 1 2; do gh issue close 9; done")
        check("a loop body is read as the call it is, not as a stray token",
              r.returncode == 2 and "a write to #9" in r.stderr
              and "cannot read as a call" not in r.stderr, out(r)[:300])
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x",))
        # THE ORDINARY DELEGATE SHAPE. A member repository under a campaign
        # directory is a git repository with no marker, so resolving a cwd to
        # its own common dir read it as "in no campaign" and allowed every
        # campaign-plane write there, while file_call refused the same target.
        # Both halves are asserted, because the bug was that they disagreed.
        member = f.camp / "repos" / "member"
        member.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(member)], check=True)
        r = ask(member, tool="Bash", command="gh issue close 9")
        check("a gh write from inside a member clone is judged by the base "
              "above it, not by the clone",
              r.returncode == 2 and "no claim covering a write to #9" in r.stderr,
              out(r)[:400])
        r = ask(member, path=str(member / "a.txt"))
        check("...and the file half resolves the same target to the same "
              "campaign, which is what the two halves must agree on",
              str(f.camp) in out(r), out(r)[:400])
        r = ask(f.base, tool="Bash", command="gh issue close 7 -R a/b")
        check("closing the sub-issue a held claim names is allowed",
              r.returncode == 0 and "covers #7" in r.stdout, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue close 9 -R a/b")
        check("closing another sub-issue is refused, naming the issue",
              r.returncode == 2 and "a write to #9" in r.stderr
              and "not a claim on #9" in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue edit 9 --body x")
        check("every gh issue write naming a number is narrowed to it, not only close",
              r.returncode == 2 and "a write to #9" in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue comment 7 --body 'NOTE campaign-1-worker-1: x'")
        check("...and one naming the held claim's issue is allowed",
              r.returncode == 0 and "covers #7" in r.stdout, out(r)[:300])
        # EVERY ISSUE NAMED MUST BE COVERED. Collapsing two to "any claim at
        # all" let a claim on #7 admit a write to #9 standing beside it -- and
        # a decoy naming #7 was the shape a review turned into a bypass.
        r = ask(f.base, tool="Bash",
                command="gh issue close 9; gh issue close 7")
        check("a claim on one issue does not admit a write to another beside it",
              r.returncode == 2 and "a write to #9" in r.stderr, out(r)[:400])
        r = ask(f.base, tool="Bash",
                command="gh issue close 7; gh issue comment 7 --body 'NOTE campaign-1-worker-1: x'")
        check("...and two writes to the SAME claimed issue are allowed",
              r.returncode == 0 and "It covers #7" in r.stdout, out(r)[:400])
        r = ask(f.base, tool="Bash",
                command="gh pr comment 5 --body 'NOTE campaign-1-worker-1: hi'")
        check("a gh write that names no issue is covered by any held claim",
              r.returncode == 0 and "campaign-1/7-x, a claim" in r.stdout,
              out(r)[:300])

        # ------ #217: THE COMMENT'S SHAPE, read from all four spellings ------
        # A DIFFERENT QUESTION FROM THE CLAIM, so every case here runs on the
        # fixture that HOLDS the claim: a refusal below is the shape and can be
        # nothing else, and an allow is not the shape being skipped.
        ok = "NOTE campaign-1-worker-1: x"
        for kind in ("REPORT", "REVIEW", "BLOCKED", "DECISION", "NOTE"):
            r = ask(f.base, tool="Bash",
                    command=f"gh issue comment 7 --body '{kind} "
                            f"campaign-1-worker-1: x'")
            check(f"a comment kinded `{kind}` is allowed",
                  r.returncode == 0, out(r)[:300])
        # A SIXTH WORD IS NOT A KIND. Without this the kind list is decoration:
        # a check accepting any leading capitalised word passes all five above.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body 'SUMMARY "
                        "campaign-1-worker-1: x'")
        check("...and a word that is not one of the five is refused",
              r.returncode == 2 and "which is not `KIND" in r.stderr,
              out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body 'a review of the change'")
        check("an unkinded comment is refused, quoting its first line",
              r.returncode == 2 and "a review of the change" in r.stderr,
              out(r)[:300])
        # THE NAME IS THE ONLY ATTRIBUTION one `gh` account leaves, so it is
        # read against the session-name rule's own pattern and `owner` beside.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body 'DECISION owner: x'")
        check("`owner` is a name a comment may carry", r.returncode == 0,
              out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body 'NOTE somebody: x'")
        check("...and a name the session-name rule does not admit is refused",
              r.returncode == 2 and "which is not `KIND" in r.stderr,
              out(r)[:300])
        # THE CEILING, AT IT AND OVER IT. A case only over it passes with the
        # comparison written `>=`, which would refuse a comment at exactly the
        # number the rule names.
        at = ok + "y" * (2000 - len(ok))
        r = ask(f.base, tool="Bash", command=f"gh issue comment 7 --body '{at}'")
        check("a comment at exactly the ceiling is allowed",
              r.returncode == 0, out(r)[:300])
        r = ask(f.base, tool="Bash",
                command=f"gh issue comment 7 --body '{at}y'")
        check("...and one character over it is refused, with both numbers",
              r.returncode == 2 and "it is 2001 characters, over 2000" in r.stderr,
              out(r)[:300])
        # THE HEREDOC, which is the finding that overturned the writer-script
        # design: `strip_heredocs` returns the bodies and `paired_segments`
        # pairs them, so the text IS in hand. Without this case the check
        # refuses the `-b` spelling and passes the heredoc spelling of the
        # same comment, which is worse than no check.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body-file - <<'EOF'\n"
                        "a review of the change\nEOF\n")
        check("an unkinded heredoc comment is refused like the -b spelling",
              r.returncode == 2 and "a review of the change" in r.stderr,
              out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body-file - <<'EOF'\n"
                        f"{ok}\nEOF\n")
        check("...and a kinded heredoc comment is allowed", r.returncode == 0,
              out(r)[:300])
        # A HEREDOC THAT IS NOT A COMMENT'S is not read as one: the pairing is
        # per SEGMENT, and reading it per line would judge this commit message.
        r = ask(f.base, tool="Bash",
                command="git commit -F - <<'M'\nfix the parser\nM\n")
        check("a heredoc a commit message sits in is not a comment body",
              r.returncode == 0, out(r)[:300])
        # `--body-file`, READ FROM DISK and resolved against the PAYLOAD's cwd.
        (f.base / "c.md").write_text("a review of the change\n")
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body-file c.md")
        check("a relative --body-file is read against the payload's cwd",
              r.returncode == 2 and "a review of the change" in r.stderr,
              out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body-file no-such.md")
        check("...and one that will not read is refused as unread, naming the "
              "resolved path",
              r.returncode == 2 and "could not be read" in r.stderr
              and str(f.base / "no-such.md") in r.stderr, out(r)[:300])
        # `gh issue reopen --comment` IS THE FORM AGENTS.md PRESCRIBES for
        # appending a discovery, so it is checked and must stay usable.
        r = ask(f.base, tool="Bash",
                command=f"gh issue reopen 7 --comment '{ok}'")
        check("`gh issue reopen --comment` is checked and a kinded one passes",
              r.returncode == 0, out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh issue reopen 7 --comment 'found it again'")
        check("...and an unkinded one is refused", r.returncode == 2
              and "found it again" in r.stderr, out(r)[:300])
        # ...AND A CLOSE WITH NO `--comment` POSTS NONE, so it is untouched.
        r = ask(f.base, tool="Bash", command="gh issue close 7")
        check("a close with no --comment is not judged as a comment",
              r.returncode == 0 and "shape does not hold" not in r.stderr,
              out(r)[:300])
        # ...NOR IS AN ISSUE BODY. `gh issue edit --body` writes the brief,
        # whose shape is `campaign-tracker check`'s, not this one's.
        r = ask(f.base, tool="Bash",
                command="gh issue edit 7 --body 'a new brief'")
        check("an issue body is not judged by the comment rule",
              r.returncode == 0 and "shape does not hold" not in r.stderr,
              out(r)[:300])
        # ------ the fix round on e73ec4b's review ------
        # `--comment` IS THE REVIEW'S KIND ON `gh pr review`, not its body.
        # gh's own example is `gh pr review --comment -b "..."`; reading
        # `--comment` as valued swallowed the `-b` and judged the literal
        # `--body` as the first line, refusing a correctly kinded REVIEW -- the
        # one comment this vocabulary exists to make machine-readable.
        r = ask(f.base, tool="Bash",
                command=f"gh pr review 5 --comment -b '{ok}'")
        check("`gh pr review --comment -b` reads the -b, not the --comment",
              r.returncode == 0, out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh pr review 5 --comment -b 'a review of the change'")
        check("...and the same form unkinded is still refused",
              r.returncode == 2 and "a review of the change" in r.stderr,
              out(r)[:300])
        # ...AND `--comment` IS VALUED ON THE VERBS WHERE IT CARRIES THE TEXT.
        # The control for the line above: narrowing it must not stop reading
        # `gh issue close --comment "..."`.
        r = ask(f.base, tool="Bash",
                command="gh issue close 7 --comment 'closing it'")
        check("`gh issue close --comment` still reads its text",
              r.returncode == 2 and "closing it" in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash",
                command="gh pr close 5 --comment 'closing it'")
        check("...and so does `gh pr close --comment`",
              r.returncode == 2 and "closing it" in r.stderr, out(r)[:300])
        # ATTACHED SHORTHAND. pflag takes `-bTEXT` with no separator, and this
        # went through UNREAD and allowed -- the careless spelling passing while
        # the careful one was checked, which the header claims it does not.
        r = ask(f.base, tool="Bash", command="gh issue comment 7 -bunkinded")
        check("`-bTEXT` is read, not passed through as no comment at all",
              r.returncode == 2 and "unkinded" in r.stderr, out(r)[:300])
        r = ask(f.base, tool="Bash", command=f"gh issue comment 7 -b'{ok}'")
        check("...and a kinded `-bTEXT` passes", r.returncode == 0, out(r)[:300])
        # `--body=V` HAD NO CASE EITHER, so the branch could be deleted green.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 7 --body=unkinded")
        check("the `--body=V` spelling is read too", r.returncode == 2
              and "unkinded" in r.stderr, out(r)[:300])
        # A BODY THE SHELL COMPOSES IS NOT READ, AND THAT IS AN ALLOW. shlex
        # expands nothing, so the token arriving here is the SOURCE; judging it
        # refused a correctly kinded REPORT for a first line reading
        # `$(cat review.md)`, a form the allow corpus holds four times.
        r = ask(f.base, tool="Bash",
                command='gh pr comment 5 --body "$(cat review.md)"')
        check("a comment body the shell composes is allowed, not judged",
              r.returncode == 0, out(r)[:400])
        check("...and the allow SAYS it did not check the shape",
              "shape NOT checked" in r.stdout, out(r)[:400])
        # ...AND IT IS STILL A CAMPAIGN-PLANE WRITE. Unjudged is not exempt:
        # the claim reading below must still refuse it on an unclaimed issue.
        r = ask(f.base, tool="Bash",
                command='gh issue comment 9 --body "$(cat review.md)"')
        check("...while the claim reading still refuses it on another issue",
              r.returncode == 2 and "a write to #9" in r.stderr, out(r)[:400])

        # THE STATED CEILING, PINNED. `gh api ... -f body=` posts a comment and
        # is NOT read here. A ceiling nothing asserts is a ceiling that has
        # quietly closed or quietly widened; this says which it is today.
        r = ask(f.base, tool="Bash",
                command="gh api repos/o/r/issues/7/comments -f body=unkinded")
        check("the `gh api` comment route is not read, which is stated and "
              "not hidden", r.returncode == 0
              and "shape does not hold" not in r.stderr, out(r)[:300])
        # A worktree directory that is gone is a claim git itself calls
        # prunable, and clause 2 must not stand on it.
        shutil.rmtree(f.trees["campaign-1/7-x"])
        r = ask(f.base, path=str(f.base / "AGENTS.md"))
        check("a prunable worktree does not hold clause 2 open",
              r.returncode == 2 and "no checkout under" in r.stderr, out(r)[:300])

    # 7. F1/F2/F3: the probes the verb parser missed. Allowed, and the allow
    # says the command was not read and what covers it. That sentence is the
    # closing of F1: an allow that said nothing was the hole.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=())
        for cmd in ("git -C /x commit -m y", "git -c a=b push",
                    "git -C /x cherry-pick abc",
                    "python3 -c 'open(\"AGENTS.md\",\"w\")'",
                    "perl -pi -e s/a/b/ AGENTS.md", "npm run build",
                    "sed -i s/a/b/ AGENTS.md", "install-hooks.sh"):
            r = ask(f.base, tool="Bash", command=cmd)
            check(f"`{cmd}` is allowed printing that it was unread and the "
                  f"commit gate covers it",
                  r.returncode == 0 and UNREAD in r.stdout and GATE in r.stdout,
                  f"exit {r.returncode}: {out(r)[:200]}")

    # 8. The payload and the registration.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d)
        r = ask(f.base, stdin="{ not json")
        check("a payload that will not read refuses", r.returncode == 2
              and "permitted nothing" in r.stderr, out(r)[:200])
        r = ask(f.base, event="PostToolUse")
        check("invoked on any event but PreToolUse it refuses and says so",
              r.returncode == 2 and "PostToolUse" in r.stderr
              and "install-hooks" in r.stderr, out(r)[:200])
        r = ask(f.base, tool="Write", tool_input={})
        check("a file tool naming no path refuses",
              r.returncode == 2 and "names no path" in r.stderr, out(r)[:200])
        r = ask(f.base, tool="Read", tool_input={"file_path": str(f.base / "x")})
        check("a tool this guard has no opinion about exits 0",
              r.returncode == 0, out(r)[:200])


    # 9. #185's permission table, one case per cell. The role is read from the
    # session's name through `herdr agent list`, so each case stubs the listing
    # it needs; `campaign-name-session.py` owns the name pattern and the guard
    # imports it rather than restating it.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=())
        planner = herdr_stub(d, {"sid-1": "campaign-1-planner-3"})
        worker = herdr_stub(d, {"sid-1": "campaign-1-worker-4"})
        stranger = herdr_stub(d, {"sid-1": "campaign-9-worker-1"})
        unnamed = herdr_stub(d, {"sid-1": ""})
        gone = no_herdr(d)

        # THE CASE THAT PROMPTED #185, from a planner session that really was
        # refused this write on 2026-09-05: a comment on the campaign issue,
        # which no claim can ever cover because #1 is nobody's sub-issue.
        r = ask(f.base, tool="Bash", command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x'",
                env=planner)
        check("a planner comments on the campaign issue, which no claim covers",
              r.returncode == 0 and "planner writes the campaign plane" in r.stdout,
              out(r)[:400])
        # #207 decided the worker side of this row: a worker of THAT
        # campaign may comment on its campaign issue, which no claim can cover.
        # The contrast the planner row is here for is the CAMPAIGN, not the
        # claim -- so the refusal case is a worker of another one.
        r = ask(f.base, tool="Bash", command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x'",
                env=stranger)
        check("...and the same write from a worker of another campaign is "
              "refused", r.returncode == 2, out(r)[:400])

        # planner, campaign plane, ANOTHER campaign's issue
        r = ask(f.base, tool="Bash", command="gh issue close 116", env=planner)
        check("a planner closes an issue of a campaign it does not work",
              r.returncode == 0 and "any campaign" in r.stdout, out(r)[:300])

        # THE LICENCE IS THE CAMPAIGN PLANE, NOT EVERY gh WRITE. `gh pr create`
        # is OpenPullRequest and `gh pr merge` is MergePullRequest -- the code
        # plane and the three merge conditions respectively, neither a
        # planner's by role. Allowing every row of WRITES let a planner open
        # and merge pull requests and delete another worker's claim ref.
        for cmd in ("gh pr create --title t --body b",
                    "gh pr merge 9 --merge",
                    "gh pr edit 9 --title x",
                    "gh api -X DELETE repos/o/r/git/refs/heads/campaign-2/8-y"):
            r = ask(f.base, tool="Bash", command=cmd, env=planner)
            check(f"the planner licence does not cover `{cmd[:34]}`",
                  r.returncode == 2 and "not the campaign plane" in r.stderr,
                  out(r)[:400])
        # #213: `gh issue develop` IS the campaign plane -- `Claim` is in
        # `campaignPlaneEvents` -- and is still out of the licence, because it
        # is a SECOND ROUTE to the object `campaign-claim take` cuts and it
        # reads neither the binding nor the campaign's `## Repos`. Asserted on
        # the sentence and not on the exit status: a planner holds no claim, so
        # the claim reading below refuses it with rc=2 either way, and a case
        # keyed on rc=2 alone passes with the exception deleted.
        r = ask(f.base, tool="Bash", command="gh issue develop 9", env=planner)
        check("the planner licence does not cover `gh issue develop`",
              r.returncode == 2 and "cuts a branch in the sub-issue's "
              "own repository" in r.stderr
              and "not the campaign plane" not in r.stderr, out(r)[:400])
        # ...and one develop hidden among covered verbs sinks the whole call,
        # which is the shape a set-membership test on the SUBCOMMAND missed.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 9 --body 'NOTE campaign-1-worker-1: x' && gh issue develop 9",
                env=planner)
        check("...and a develop beside a covered verb is not carried by it",
              r.returncode == 2 and "cuts a branch in the sub-issue's "
              "own repository" in r.stderr, out(r)[:400])
        # THE REFUSAL IS A REFUSAL AND NOT A SENTENCE, which the first cut of
        # this got wrong and a review caught. Appending to `read_on` and
        # falling through left the claim reading to decide, and it ALLOWS a
        # planner `gh issue develop 9` outright whenever any worktree on this
        # machine sits on a claim for #9 -- the state the planner's own
        # `campaign-claim take` before a delegate launch creates. So the case
        # needs a fixture where that claim EXISTS, or it passes over the one
        # world the exception has to cover.
        with tempfile.TemporaryDirectory() as d9:
            f9 = Fixture(d9, claims=("campaign-1/9-topic",))
            p9 = herdr_stub(d9, {"sid-1": "campaign-1-planner-3"})
            r = ask(f9.base, tool="Bash", command="gh issue develop 9", env=p9)
            check("...and a live claim on the very issue does not carry it "
                  "either", r.returncode == 2
                  and "cuts a branch in the sub-issue's own repository" in r.stderr,
                  out(r)[:400])
            # ALLOW beside it: the same claim, the same planner, an ordinary
            # campaign-plane verb -- so the refusal is the verb and not the
            # fixture.
            r = ask(f9.base, tool="Bash", command="gh issue comment 9 --body 'NOTE campaign-1-worker-1: x'",
                    env=p9)
            check("...and the same planner still comments on that issue",
                  r.returncode == 0 and "any campaign" in r.stdout, out(r)[:400])

        # AND THE REFUSAL STILL SAYS WHAT ELSE IT READ. An early return is
        # where #191 item 1 gets broken: the first cut of it named the develop
        # and went silent about the other write in the same command and about
        # how the root was resolved.
        r = ask(f.base, tool="Bash",
                command="gh pr merge 5 --merge && gh issue develop 9",
                env=planner)
        check("...and the develop refusal still names the other write beside it",
              r.returncode == 2
              and "`gh pr` is not the campaign plane" in r.stderr
              and "cuts a branch in the sub-issue's own repository" in r.stderr
              # ...AND HOW THE ROOT WAS RESOLVED. `how` was the third thing
              # that early return dropped, and the two conjuncts above are both
              # satisfied without it -- so deleting `how,` from this refusal
              # left the suite green (#213's REPORT, item 1). One conjunct per
              # half, or the half with no conjunct is documentation.
              and "cwd " in r.stderr and "-> " in r.stderr,
              out(r)[:500])
        # THE ROLE READING, ONCE. It came out twice on exactly this shape: the
        # header printed `how_role` and every `read_on` entry opens with it
        # (#213's REPORT, item 2). Asserted as a COUNT, because a case
        # asserting presence passes on one copy and on five.
        check("...and the role reading is printed exactly once",
              r.stderr.count("is campaign-1-planner-") == 1,
              f"{r.stderr.count('is campaign-1-planner-')} copies: {out(r)[:500]}")
        # ...AND THE BARE develop STILL CARRIES IT. `read_on` is EMPTY there --
        # `issue` is a planner's subcommand and only the pair is excepted -- so
        # a header that simply dropped `how_role` would have lost the role
        # reading on the very command this branch exists for.
        r = ask(f.base, tool="Bash", command="gh issue develop 9", env=planner)
        check("a bare develop refusal still names the role it read",
              r.stderr.count("is campaign-1-planner-") == 1,
              f"{r.stderr.count('is campaign-1-planner-')} copies: {out(r)[:500]}")

        # THE FALLBACK SENTENCE, which had no case. `read_on` is empty when a
        # planner's command holds no gh WRITE the guard can read but does hold
        # a `gh` it cannot read as a call -- `stray`. Without it the refusal
        # printed the role line and then nothing about why the licence did not
        # apply.
        r = ask(f.base, tool="Bash", command="echo 9 | xargs gh issue close",
                env=planner)
        check("a planner's unreadable `gh` is refused saying the licence does "
              "not cover it", r.returncode == 2
              and "a gh call this cannot read is not covered by the planner "
                  "licence" in r.stderr, out(r)[:400])

        # THE COST, PINNED RATHER THAN LEFT TO BE FOUND. `-l` is `--list` for
        # `gh issue develop`, so this is a READ, and `WRITES` holds the verb
        # unconditionally -- so a planner is now over-refused on it. The
        # direction this guard fails in on purpose (see VALUED), and the price
        # of not putting a per-verb flag grammar in a PreToolUse hook.
        r = ask(f.base, tool="Bash", command="gh issue develop -l 11",
                env=planner)
        check("...and a planner's `gh issue develop --list` is over-refused "
              "with it, which is the cost", r.returncode == 2
              and "This reads no flags, so a `--list` is refused with it."
              in r.stderr, out(r)[:400])

        # ALLOW beside it: the campaign-plane verbs the licence is FOR.
        for cmd in ("gh issue edit 9 --body x", "gh issue comment 9 --body 'NOTE campaign-1-worker-1: x'",
                    "gh issue close 9", "gh issue reopen 9",
                    "gh label create x"):
            r = ask(f.base, tool="Bash", command=cmd, env=planner)
            check(f"ALLOW beside it: `{cmd[:30]}` is the campaign plane",
                  r.returncode == 0 and "any campaign" in r.stdout, out(r)[:400])
        # ...and a read stays a read for a planner too.
        r = ask(f.base, tool="Bash", command="gh pr view 9", env=planner)
        check("ALLOW beside it: a gh read is not a write for a planner either",
              r.returncode == 0, out(r)[:300])

        # planner, code plane: refused, and told which shape to use
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=planner)
        check("a planner may not change code in a checkout",
              r.returncode == 2 and "may not change code" in r.stderr
              and "Hand it to a worker" in r.stderr, out(r)[:400])
        # ...but its own campaign-directory scratch is campaign-plane
        r = ask(f.base, path=str(f.camp / "notes.md"), env=planner)
        check("...and a planner writes its campaign directory, which is no "
              "checkout",
              r.returncode == 0 and "campaign-plane scratch" in r.stdout,
              out(r)[:400])

        # the last row: a name the pattern does not admit, on BOTH planes
        r = ask(f.base, tool="Bash", command="gh issue close 9", env=unnamed)
        check("a session with no campaign name is refused on the campaign plane",
              r.returncode == 2 and "no role" in r.stderr, out(r)[:300])
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=unnamed)
        check("...and on the code plane too", r.returncode == 2
              and "no role" in r.stderr, out(r)[:300])

        # THE RETIRED ROLE WORD. `executor` was the word this guard read until
        # #185's rename; the pattern no longer admits it, so a session still
        # carrying it lands on that same last row and is refused on both
        # planes -- and the refusal quotes the name, so the reader is told
        # which of its two names is stale rather than that some name is. Put
        # `executor` back into the alternation in campaign-name-session.py and
        # these two go green: they are what pins the rename on this side.
        retired = herdr_stub(d, {"sid-1": "campaign-1-executor-5"})
        r = ask(f.base, tool="Bash", command="gh issue close 9", env=retired)
        check("the retired role word `executor` has no role on the campaign "
              "plane, and the refusal quotes the stale name",
              r.returncode == 2 and "no role" in r.stderr
              and "campaign-1-executor-5" in r.stderr, out(r)[:300])
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=retired)
        check("...and none on the code plane either", r.returncode == 2
              and "no role" in r.stderr
              and "campaign-1-executor-5" in r.stderr, out(r)[:300])

        # A CHECKOUT UNDER A CAMPAIGN DIRECTORY IS STILL CODE. A clone at
        # <campaign>/repos/<repo>/ reports the campaign directory as where it
        # is, so keying the planner refusal on that alone let a planner edit
        # every member clone and every worktree under a campaign directory.
        # A MEMBER repository's clone, not the base's: a clone of the base
        # carries the marker and answers as a base in its own right, so it
        # never reaches the scratch reading and the case could not see the
        # bug it was written for. Probed: with `f.clone()` here, reverting
        # `scratch` left the suite fully green.
        member = f.member(branch="campaign-1/7-x")
        r = ask(member, path=str(member / "code.txt"), env=planner)
        check("a planner may not edit a checkout under the campaign directory",
              r.returncode == 2 and "may not change code" in r.stderr,
              out(r)[:400])
        # ALLOW beside it: the campaign directory itself is still scratch.
        r = ask(f.camp, path=str(f.camp / "plan.md"), env=planner)
        check("ALLOW beside it: the campaign directory itself stays scratch",
              r.returncode == 0 and "campaign-plane scratch" in r.stdout,
              out(r)[:400])

        # COULD NOT LOOK is not the same as looked-and-found-nothing: with no
        # herdr the guard falls back to the claim reading and says so, which is
        # the pre-#185 behaviour and neither a wall nor a bypass.
        r = ask(f.base, tool="Bash", command="gh issue close 9", env=gone)
        check("herdr unreadable falls back to the claim reading, and SAYS both "
              "that it could not read the role and what it fell back to",
              r.returncode == 2 and "no claim covering" in r.stderr
              and "the role could not be read" in r.stderr
              and "falling back to the claim reading" in r.stderr, out(r)[:600])
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=gone)
        check("...and the file half says the same",
              r.returncode == 2
              and "falling back to the claim reading" in r.stderr, out(r)[:600])

    # AN ALLOW AFTER A FAILED READ MUST SAY SO TOO. They were silent, so an
    # allow that fell back looked exactly like one that read the role and found
    # it permitted -- the whole distinction this gate keeps, dropped on the one
    # path nobody asserts.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x",))
        gone = no_herdr(d)
        r = ask(f.base, tool="Bash", command="gh issue close 7", env=gone)
        check("an ALLOW that fell back says it fell back",
              r.returncode == 0
              and "falling back to the claim reading" in r.stdout, out(r)[:600])
        # ALLOW beside it: with herdr readable, the allow does NOT say it.
        fine = herdr_stub(d, {"sid-1": "campaign-1-worker-4"})
        r = ask(f.base, tool="Bash", command="gh issue close 7", env=fine)
        check("...and one that read the role does not claim to have fallen back",
              r.returncode == 0
              and "falling back" not in r.stdout, out(r)[:600])
        # A NAME THAT IS NOT A CAMPAIGN NAME IS NOT CAMPAIGN WORK'S PROBLEM
        # OUTSIDE A CAMPAIGN. Asked before "is this a base", it refused every
        # gh write anywhere on this machine from any session herdr lists.
        plain2 = Path(d) / "plain2"
        plain2.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(plain2)],
                       check=True)
        r = ask(plain2, tool="Bash", command="gh issue close 9", env=unnamed)
        check("a session with no campaign name still writes outside every base",
              r.returncode == 0, out(r)[:400])
        # A herdr row this cannot read is a reading, not a traceback: a hook
        # that exits 1 is its OWN error, and the call then proceeds.
        broken = herdr_stub_raw(
            d, '{"result": {"agents": [{"agent_session": "not-an-object", '
               '"name": "x"}]}}')
        r = ask(f.base, tool="Bash", command="gh issue close 9", env=broken)
        check("a malformed herdr row refuses rather than crashing",
              r.returncode == 2 and "not an object" in r.stderr, out(r)[:400])

        # ---- one ALLOW per refusal branch above, for the ordinary shape it
        # could catch by mistake. Five fix rounds stayed green while each
        # opened a false positive, because every case was named for a refusal.
        # A refusal branch with no allow beside it is half a test.
        r = ask(d, path=str(Path(d) / "elsewhere.md"), env=unnamed)
        check("ALLOW beside the nameless refusal: a file outside every base",
              r.returncode == 0 and "not campaign work" in r.stdout, out(r)[:300])
        r = ask(d, path=str(Path(d) / "elsewhere.md"), env=planner)
        check("ALLOW beside the planner code refusal: a file outside every base",
              r.returncode == 0 and "not campaign work" in r.stdout, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue list", env=unnamed)
        check("ALLOW beside the nameless refusal: a gh READ needs no role",
              r.returncode == 0, out(r)[:300])
        r = ask(f.base, tool="Bash", command="grep -rn 'gh issue close 9' .",
                env=unnamed)
        check("ALLOW beside the nameless refusal: a quoted string is data",
              r.returncode == 0, out(r)[:300])
        # A listing carrying other sessions and fields this does not read still
        # resolves the row it wants: the malformed-row refusal must not fire on
        # a shape that is merely unfamiliar.
        crowded = herdr_stub_raw(d, json.dumps({"result": {"agents": [
            {"agent_session": {"value": "sid-other"}, "name": "campaign-2-worker-1",
             "cwd": "/x", "unknown_field": 7},
            {"agent_session": {"value": "sid-1"}, "name": "campaign-1-planner-3",
             "revision": 12, "tab_id": "t1"},
        ]}}))
        r = ask(f.base, tool="Bash", command="gh issue close 116", env=crowded)
        check("ALLOW beside the malformed-row refusal: other rows and unknown "
              "fields are not malformed",
              r.returncode == 0 and "any campaign" in r.stdout, out(r)[:400])
        r = ask(d, tool="Bash", command="gh issue close 9", env=gone)
        check("...and outside every base it still allows, as it always did",
              r.returncode == 0, out(r)[:300])

    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x",))
        worker = herdr_stub(d, {"sid-1": "campaign-1-worker-4"})
        stranger = herdr_stub(d, {"sid-1": "campaign-9-worker-1"})
        # worker, its own campaign and the sub-issue it holds
        r = ask(f.base, tool="Bash", command="gh issue close 7", env=worker)
        check("a worker of campaign 1 closes the sub-issue it claimed",
              r.returncode == 0, out(r)[:300])
        # worker of ANOTHER campaign, standing at the same root
        r = ask(f.base, tool="Bash", command="gh issue close 7", env=stranger)
        check("a worker of another campaign may not stand on this "
              "campaign's claim",
              r.returncode == 2 and "another campaign" in r.stderr, out(r)[:400])
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=stranger)
        check("...and the file half says the same",
              r.returncode == 2 and "another campaign" in r.stderr, out(r)[:400])
        # #207: THE CAMPAIGN ISSUE IS NOBODY'S SUB-ISSUE, so no claim can ever
        # cover it and every worker was refused a comment on the campaign it
        # works. Its own campaign's number comes from its name.
        r = ask(f.base, tool="Bash", command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x'",
                env=worker)
        check("a worker comments on its OWN campaign's issue",
              r.returncode == 0 and "campaign issue of the campaign this "
              "session is of" in r.stdout, out(r)[:400])
        r = ask(f.base, tool="Bash", command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x'",
                env=stranger)
        check("...and a worker of another campaign may not",
              r.returncode == 2, out(r)[:400])
        # THE CARVE-OUT IS A VERB, NOT AN ISSUE NUMBER. Keyed on the number
        # alone it admitted every `gh issue` verb against the campaign issue --
        # `edit` is the charter body, `close` closes the campaign, `delete` and
        # `transfer` are irreversible, and a claim on some other sub-issue
        # makes none of them safer.
        for verb in ("close", "edit", "reopen", "delete", "transfer", "lock",
                     "pin", "develop"):
            cmd = f"gh issue {verb} 1" + (" --body x" if verb == "edit" else "")
            r = ask(f.base, tool="Bash", command=cmd, env=worker)
            check(f"the campaign-issue carve-out does not cover `{verb}`",
                  r.returncode == 2, out(r)[:400])
        # ...and it covers its own write and nothing standing beside it.
        r = ask(f.base, tool="Bash",
                command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x' && gh pr merge 12 --merge",
                env=worker)
        check("the carve-out carries no other write in the same command",
              r.returncode == 2 and "covers no other write" in r.stderr,
              out(r)[:400])
        # ALLOW beside all of it: the one verb the carve-out is for, and a read.
        r = ask(f.base, tool="Bash", command="gh issue comment 1 --body 'NOTE campaign-1-worker-1: x'",
                env=worker)
        check("ALLOW beside it: the comment the carve-out is for",
              r.returncode == 0, out(r)[:400])
        r = ask(f.base, tool="Bash", command="gh issue view 1", env=worker)
        check("ALLOW beside it: a read of the campaign issue",
              r.returncode == 0, out(r)[:400])
        # ALLOW beside it: a sub-issue of its own campaign still needs a claim,
        # so the carve-out did not become a general licence.
        r = ask(f.base, tool="Bash", command="gh issue close 99", env=worker)
        check("ALLOW beside it is a REFUSAL: a sub-issue it holds no claim on "
              "is still refused",
              r.returncode == 2 and "no claim covering a write to #99"
              in r.stderr, out(r)[:400])

        # CLAUSE 1 IS BOUND BY THE CAMPAIGN TOO. It asks only whether the
        # target's checkout is on SOME claim, so a worker of another
        # campaign -- role read correctly -- edited this campaign's worktree,
        # while the docstring said a worker writes its own campaign.
        wt = f.trees["campaign-1/7-x"]
        r = ask(wt, path=str(wt / "a.md"), env=stranger)
        check("clause 1 does not admit a worker of another campaign",
              r.returncode == 2 and "another campaign" in r.stderr, out(r)[:400])
        r = ask(wt, tool="Bash", command="gh pr merge 7 --merge", env=stranger)
        check("...nor does the session's own checkout, for the same session",
              r.returncode == 2, out(r)[:400])
        # ALLOW beside both: this campaign's own worker, same checkout.
        r = ask(wt, path=str(wt / "a.md"), env=worker)
        check("ALLOW beside it: clause 1 admits its own campaign's worker",
              r.returncode == 0 and "Clause 1" in r.stdout, out(r)[:400])
        r = ask(wt, tool="Bash", command="gh pr merge 7 --merge", env=worker)
        check("ALLOW beside it: and so does its own checkout",
              r.returncode == 0, out(r)[:400])
        # ALLOW beside the foreign-campaign refusal: this campaign's own
        # worker, standing at the same root, with the same claims present.
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=worker)
        check("ALLOW beside the foreign-campaign refusal: its own campaign's "
              "worker is admitted at the same root",
              r.returncode == 0, out(r)[:400])
        r = ask(f.base, tool="Bash", command="gh pr view 7", env=stranger)
        check("ALLOW beside the foreign-campaign refusal: a read is not a write",
              r.returncode == 0, out(r)[:400])

    # A ROOT HOLDING BOTH CAMPAIGNS' CLAIMS. The case above has only a foreign
    # claim under the root, and the gh half filtered once for the whole root --
    # so it refused only when EVERY claim was foreign, and a worker with any
    # claim of its own was admitted to write another campaign's sub-issue with
    # the foreign claim named as the cover. The filter is per issue now, and
    # this is the fixture that can tell the two apart.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x", "campaign-2/8-y"))
        worker = herdr_stub(d, {"sid-1": "campaign-1-worker-1"})
        r = ask(f.base, tool="Bash", command="gh issue close 8", env=worker)
        check("a worker may not write another campaign's sub-issue, even "
              "with a claim of its own under the same root",
              r.returncode == 2 and "no claim covering a write to #8" in r.stderr,
              out(r)[:500])
        check("...and the refusal names the foreign claim it declined to use",
              "a claim of another campaign" in r.stderr, out(r)[:500])
        # ALLOW beside it, on the same fixture: its own campaign's sub-issue.
        r = ask(f.base, tool="Bash", command="gh issue close 7", env=worker)
        check("ALLOW beside it: its own campaign's sub-issue on the same root",
              r.returncode == 0 and "It covers #7" in r.stdout, out(r)[:500])
        # ...and the file half, which filtered from the start, still agrees.
        r = ask(f.base, path=str(f.base / "AGENTS.md"), env=worker)
        check("ALLOW beside it: the file half admits the same session",
              r.returncode == 0, out(r)[:400])

    # ---------------------------------------------------------------- #193
    # A HEREDOC BODY IS DATA. Reproduced 2026-09-05 on
    # campaign-1/187-claim-identity: `git commit -F - <<'MSG'` whose message
    # said `machine's` was refused, and the refusal named a `gh` call that was
    # not in the command at all.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, claims=("campaign-1/7-x", "campaign-1/9-y"))
        wt7 = f.trees["campaign-1/7-x"]
        r = ask(wt7, tool="Bash",
                command="git commit -q -F - <<'MSG'\nRead the machine's "
                        "branch's name\nMSG")
        check("a commit message with an apostrophe in it is data, not a "
              "command that will not split",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        # ...and the body is not scanned for a `gh` either, because scanning
        # prose is what refused `git commit -m 'fix gh issue close parsing'`.
        r = ask(wt7, tool="Bash",
                command="git commit -F - <<'MSG'\nwhy gh issue close 9 was "
                        "wrong\nMSG")
        check("a heredoc body naming a gh call is prose, and is not read",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        # WHAT MAKES IT A COMMAND IS ITS CONSUMER. A shell reading a heredoc is
        # reading a script, and that IS read -- the same rule `-c` gets.
        r = ask(wt7, tool="Bash", command="bash <<EOF\ngh issue close 11\nEOF")
        check("a heredoc a SHELL reads is a script, and its gh write is read",
              r.returncode == 2 and "a write to #11" in r.stderr, out(r)[:300])
        # ...and the pairing is per SEGMENT, not per line: a line holding both
        # a shell and a prose heredoc must read only the shell's.
        r = ask(wt7, tool="Bash",
                command="bash deploy.sh && git commit -F - <<'M'\nit's fine\nM")
        check("a shell beside a prose heredoc does not make the prose a script",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        # ...and stripping the body does not blind the guard to the rest.
        r = ask(wt7, tool="Bash",
                command="gh issue close 11 && git commit -F - <<'M'\nit's "
                        "done\nM")
        check("a gh write beside a heredoc is still read",
              r.returncode == 2 and "a write to #11" in r.stderr, out(r)[:300])
        # A `<<` IS ONLY A HEREDOC WHERE IT IS SYNTAX. Found by the review at
        # 1a3138e: the opener was matched on the raw line, so a `<<` inside
        # quotes ate every line after it. One defect, two differentials against
        # `main`, and a case for each -- a REFUSAL that became an allow, and an
        # allow that became a refusal.
        r = ask(wt7, tool="Bash",
                command="git commit -m 'about the <<EOF form' &&\n"
                        "gh issue close 11")
        check("a quoted `<<` does not swallow the write on the next line",
              r.returncode == 2 and "a write to #11" in r.stderr, out(r)[:400])
        r = ask(wt7, tool="Bash",
                command='gh issue comment 7 --body "NOTE campaign-1-worker-1: line one\n'
                        'mentions <<EOF in passing\nline three"')
        check("...and a quote a `<<` sits inside is not eaten either, so a "
              "multi-line body still splits",
              r.returncode == 0 and "It covers #7" in r.stdout, out(r)[:400])
        # ...and the quote state is carried ACROSS lines, which is what the
        # second shape needs: the quote was opened on an earlier line.
        r = ask(wt7, tool="Bash",
                command='echo "opened here\nand a <<EOF inside it\nclosed here"'
                        '\ngh issue close 11')
        # Refused as a `gh` it cannot read as a call, not as a write to #11: a
        # NEWLINE is not a separator here (it never was -- `echo hi\ngh issue
        # close 5` is in the stray list above), so the two lines are one
        # segment whose command word is `echo`. What this pins is that the
        # quote CLOSED on line three, leaving the `gh` visible at all; without
        # the carry it was swallowed and the call exited 0.
        # ASSERTED ON THE `gh` BEING SEEN, not on the verdict. A NEWLINE is not
        # a separator here and never was (`echo hi` + `gh issue close 5` on two
        # lines is in the stray list above), so these two lines are one segment
        # whose command word is `echo` and whose `gh` is a stray token -- which
        # this session's claim then covers, exit 0. What the case pins is that
        # the quote CLOSED on line three and the `gh` survived to be read at
        # all; before the carry, the `<<EOF` on line two ate lines three and
        # four and the guard saw no `gh` anywhere.
        check("...tracked across lines, not restarted at each one",
              "cannot read as a call" in out(r) and "gh issue" in out(r),
              out(r)[:400])
        # ALLOW beside all three: the real heredoc still has its body removed.
        r = ask(wt7, tool="Bash",
                command="git commit -F - <<'M'\nthe machine's own\nM")
        check("ALLOW beside them: a real heredoc body is still data",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])

        # A `#` AT WORD START ENDS THE LINE. The carry above is what made this
        # load-bearing: without a comment branch the comment's stray quote was
        # handed to the next line and ate the real opener there. Both
        # directions, one case each, and an allow beside them.
        r = ask(wt7, tool="Bash",
                command="# it's fine\nbash <<'M'\ngh issue close 11\nM")
        check("a quote inside a comment does not hide the next line's heredoc",
              r.returncode == 2 and "a write to #11" in r.stderr, out(r)[:400])
        r = ask(wt7, tool="Bash",
                command="# don't do this\ngit commit -F - <<'M'\n"
                        "it's fine\nM")
        check("...and does not make the whole call unsplittable either (#193)",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:300])
        # ...AT WORD START, and that half is load-bearing for a reason a
        # first reading misses: this scanner runs BEFORE shlex, so breaking at
        # a mid-word `#` makes it miss a `<<` LATER ON THE SAME LINE and the
        # body is read as commands. `$#` is ordinary shell.
        r = ask(wt7, tool="Bash",
                command="test $# -eq 0 && cat <<EOF\ngh issue close 11\nEOF")
        # ASSERTED ON THE SENTENCE, not the exit status: this session holds a
        # claim, so a stray `gh` is covered and BOTH readings exit 0. What the
        # mid-word `#` changes is whether the body was stripped at all -- with
        # it, `cat`'s body is data and nothing is read; without it, the body's
        # lines join the segment and the `gh` shows up as a token.
        check("a `#` mid-word does not hide a heredoc opener later on its line",
              UNREAD in r.stdout and "cannot read as a call" not in out(r),
              out(r)[:400])
        r = ask(wt7, tool="Bash",
                command="cat > ${f#./} <<EOF\ngh issue close 11\nEOF")
        check("...and a `${var#prefix}` expansion is not a comment either",
              UNREAD in r.stdout and "cannot read as a call" not in out(r),
              out(r)[:400])
        # ...and `)` is NOT a boundary. `echo $(echo x)#c` prints `x#c`, so a
        # `#` after `)` is data; admitting `()` to the class made this refused
        # where it had been allowed.
        r = ask(wt7, tool="Bash",
                command="echo $(echo x)#c && cat <<EOF\ngh issue close 11\nEOF")
        check("a `#` after a closing paren is not a comment",
              r.returncode == 0 and UNREAD in r.stdout, out(r)[:400])

        # THE REFUSAL NAMES ONLY WHAT IT READ (#193 defect 2). Two branches,
        # one case each, asserted on the sentence: the exit status is the same.
        r = ask(wt7, tool="Bash", command='echo "unterminated')
        check("a command that will not split says so and names the text",
              r.returncode == 2 and "the text it could not split" in r.stderr,
              out(r)[:300])
        check("...and does not name a gh call nobody made",
              "no `gh` was seen in it" in r.stderr
              and "A gh call this cannot split" not in r.stderr, out(r)[:400])
        r = ask(wt7, tool="Bash", command='gh issue close 9 "unterminated')
        check("...and when a gh IS among its words, it says that instead",
              r.returncode == 2 and "a `gh` is among its words" in r.stderr
              and "no `gh` was seen" not in r.stderr, out(r)[:400])

        # ------------------------------------------------------------- #191
        # ITEM 1: a mixed command reaches two refusing branches, and the one
        # naming a NUMBER wins because it tells the reader which claim to take.
        no_claim = ask(f.base, tool="Bash",
                       command="gh issue close 11 && gh pr merge 5")
        check("a mixed command is refused by the issue it names, not by the "
              "unnarrowed fallback",
              no_claim.returncode == 2
              and "no claim covering a write to #11" in no_claim.stderr,
              out(no_claim)[:300])
        # ...and the fallback still decides once every named issue IS covered,
        # or the rule above would have swallowed it.
        r = ask(f.base, tool="Bash", command="gh issue close 9 && gh pr merge 5")
        check("...and the unnarrowed fallback decides when the named issue is "
              "covered",
              r.returncode == 0 and "gh pr merge" in r.stdout
              and "a claim (" in r.stdout, out(r)[:400])

        # ------------------------------------------------------------- #192
        # ITEM 3: `-l` is `--list` for `gh issue develop`, so treating it as
        # valued swallowed the issue number and dropped the call to the
        # unnarrowed gate, where a claim on any issue carried it.
        r = ask(f.base, tool="Bash", command="gh issue develop -l 11")
        check("`gh issue develop -l 11` is narrowed to #11, not swallowed",
              r.returncode == 2 and "no claim covering a write to #11"
              in r.stderr, out(r)[:300])
        # ALLOW beside it, twice: the label spellings that must go on working.
        r = ask(f.base, tool="Bash", command="gh issue edit 9 -l bug")
        check("ALLOW beside it: `-l bug` on a claimed issue is allowed",
              r.returncode == 0 and "It covers #9" in r.stdout, out(r)[:300])
        r = ask(f.base, tool="Bash", command="gh issue edit 9 --label 11")
        check("ALLOW beside it: `--label` is still a valued flag, so its "
              "value is not the issue",
              r.returncode == 0 and "It covers #9" in r.stdout, out(r)[:300])

    # #191 ITEM 2: `base_above` answers the NEAREST base, not the topmost.
    # Reached only where git resolves no marker-bearing repository, so the
    # fixture is deliberately not a git repository at all.
    with tempfile.TemporaryDirectory() as d:
        outer = (Path(d) / "outer").resolve()
        inner = outer / "demo-260904" / "inner"
        for root in (outer, inner):
            (root / "scripts").mkdir(parents=True)
            (root / "scripts" / "campaign-claim.py").write_text("x\n")
        target = inner / "demo-260905" / "note.md"
        target.parent.mkdir(parents=True)
        inner = inner.resolve()
        target.write_text("x\n")
        r = ask(d, path=str(target), env=no_herdr(d))
        check("base_above answers the nearest base, so the campaign directory "
              "is the inner one",
              f"campaign directory {inner / 'demo-260905'}" in out(r),
              out(r)[:400])
        # ASSERTED ON THE WHOLE PATH IT PRINTED, not on the outer path being
        # absent: the outer campaign directory is a PREFIX of the inner one, so
        # `not in` is true of nothing and the case would pass either way.
        named = re.search(r"campaign directory (\S+?)[.,]", out(r))
        check("...and not the outer base's, which the topmost reading gave",
              named is not None
              and named.group(1) == str(inner / "demo-260905"),
              f"{named and named.group(1)!r}")

    # #192 ITEM 1: `own_claim`'s reach, kept and named. An unrelated
    # repository on a claim-shaped branch with a local bare origin is
    # ADMITTED, which is #176's own property -- a claim is a branch name plus
    # a ref on whatever remote the checkout has. The two things it does ask
    # each have a case that fails when dropped.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d)
        sandbox = f.camp / "sandbox"
        sandbox.mkdir(parents=True)
        remote = Path(d) / "s.git"
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main",
                        str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(sandbox)],
                       check=True)
        git(sandbox, "remote", "add", "origin", str(remote))
        (sandbox / "f").write_text("x\n")
        git(sandbox, "add", "-A")
        git(sandbox, "commit", "-qm", "c")
        git(sandbox, "push", "-q", "origin", "HEAD")
        for branch, pushed in (("campaign-1/888-x", True),
                               ("campaign-1/889-x", False),
                               ("feature-888", True)):
            git(sandbox, "switch", "-qc", branch)
            if pushed:
                git(sandbox, "push", "-q", "origin", branch)
            git(sandbox, "fetch", "-q", "origin")
        git(sandbox, "switch", "-q", "campaign-1/888-x")
        r = ask(sandbox, tool="Bash", command="gh issue close 888")
        check("own_claim admits any checkout on a claim-shaped branch whose "
              "ref exists on ITS OWN remote -- the reach #192 names and keeps",
              r.returncode == 0 and "campaign-1/888-x" in r.stdout,
              out(r)[:400])
        git(sandbox, "switch", "-q", "campaign-1/889-x")
        r = ask(sandbox, tool="Bash", command="gh issue close 889")
        check("...but the ref must EXIST, so an unpushed branch is no claim",
              r.returncode == 2, out(r)[:400])
        git(sandbox, "switch", "-q", "feature-888")
        r = ask(sandbox, tool="Bash", command="gh issue close 888")
        check("...and the branch must be claim-SHAPED",
              r.returncode == 2, out(r)[:400])

    # ---------------------------------------------------------------- #196
    # EVERY VERDICT IS DURABLE. Asserted on the FILE, not on the sentence the
    # guard prints about it: a guard that says "logged to ..." and writes
    # nothing is the exact failure this closes.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d)
        # RESOLVED, because the guard prints the resolved path and a macOS
        # temporary directory is a symlink: `/var/...` and `/private/var/...`
        # are the same file and two different strings.
        camp_log = (f.camp / "runtime" / "guard.log").resolve()
        base_log = (f.base / "runtime" / "guard.log").resolve()
        r = ask(f.base, tool="Bash", command="gh issue close 7")
        check("an allowed verdict is written to the base's log",
              base_log.is_file(), out(r)[:300])
        check("...and the guard says where it wrote it",
              f"logged to {base_log}" in r.stdout, out(r)[:300])
        # READ DEFENSIVELY, so a mutation that stops the log being written
        # fails these cases instead of killing the suite in a traceback: a
        # crash is not a case failing, and it is not evidence either.
        def last(path):
            lines = path.read_text().splitlines() if path.is_file() else []
            return json.loads(lines[-1]) if lines else {}

        row = last(base_log)
        check("...and the line carries what guard-precision.py reads",
              row.get("verdict") == "allowed" and row.get("tool") == "Bash"
              and row.get("command") == "gh issue close 7"
              and row.get("session") and row.get("at") and "reason" in row,
              row)
        r = ask(f.base, tool="Bash", command="gh issue close 8")
        row = last(base_log)
        check("a refusal is written too, carrying the sentence it printed",
              row.get("verdict") == "REFUSED"
              and "no claim covering a write to #8" in row.get("reason", ""),
              row)
        check("...and the refusal says where the verdict went, on stderr",
              f"logged to {base_log}" in r.stderr, out(r)[:400])
        # THE CAMPAIGN IT WAS CLASSIFIED INTO, so one campaign's precision can
        # be read without separating it from every other session here.
        r = ask(f.base, path=str(f.camp / "notes.md"))
        check("a call inside a campaign directory is logged under THAT "
              "campaign, not under the base",
              camp_log.is_file()
              and last(camp_log).get("target")
              == str((f.camp / "notes.md").resolve()), out(r)[:300])
        # THE PAYLOAD THAT WOULD NOT READ IS A VERDICT TOO, and it used to
        # return past the log write -- so the one refusal meaning the guard was
        # handed something broken was the one nothing recorded and nothing said
        # was unrecorded. `run_cwd` because that payload carries no cwd.
        r = ask(f.base, stdin="{not json", run_cwd=f.base)
        check("a payload that would not read is logged like any other verdict",
              last(base_log).get("reason", "").startswith("the hook payload "
                                                          "would not read"),
              last(base_log))
        check("...and the guard says where that verdict went",
              r.returncode == 2 and f"logged to {base_log}" in r.stderr,
              out(r)[:300])

    with tempfile.TemporaryDirectory() as d:
        # A call under no base is not campaign work, and saying "logged" about
        # it would put every session on this machine in the measurement.
        r = ask(d, tool="Bash", command="rm -rf x")
        check("a call under no base is not logged, and the guard says why",
              r.returncode == 0 and "not logged: under no base" in r.stdout,
              out(r)[:300])
    with tempfile.TemporaryDirectory() as d:
        # A LOG THAT COULD NOT BE WRITTEN CHANGES NO VERDICT AND IS NOT
        # SILENT. `runtime` is a FILE here, so the mkdir fails.
        f = Fixture(d)
        (f.base / "runtime").write_text("not a directory\n")
        r = ask(f.base, tool="Bash", command="gh issue close 7")
        check("a log that could not be written leaves the verdict alone",
              r.returncode == 0, out(r)[:300])
        check("...and says it was not written, rather than nothing",
              "verdict not logged" in r.stdout, out(r)[:300])

    # THE ALLOW CORPUS (#196 step 4, #209 step 1). Every case above is a shape
    # somebody thought of; these are the shapes the campaign actually typed,
    # replayed against a fixture in which the session holds the claims it held
    # then. A refusal here is a false positive with a date on it.
    #
    # ONE ROLE, STATED: every entry is replayed as a WORKER of campaign 1,
    # whatever role the session that typed it had. A planner's campaign-plane
    # `gh` is admitted to a worker holding the claim too, so the corpus
    # stays green under the narrower of the two readings; replaying as a
    # planner instead would refuse every file write into a checkout, which is
    # the rule working and not a finding.
    rows = corpus_rows()
    check("the allow corpus is present", rows is not None,
          f"{CORPUS} is missing; scripts/guard-corpus.py writes it")
    if rows:
        mod = guard_module()
        issues = corpus_issues(mod, rows)
        check("the corpus names sub-issues to hold claims on", len(issues) > 1,
              f"issues={issues}")
        with tempfile.TemporaryDirectory() as d:
            # One claim per sub-issue the corpus names, plus one more for the
            # worktree UNDER the campaign directory: `worktree` entries came
            # from `<campaign>/worktrees/<n>/`, which is a checkout of its own
            # and cannot share a branch with the sibling worktrees above.
            f = Fixture(d, claims=tuple([f"campaign-1/{i}-x" for i in issues]
                                        + ["campaign-1/909-corpus"]))
            git(f.base, "worktree", "remove", "--force",
                str(f.trees["campaign-1/909-corpus"]))
            wt = f.worktree("209", "campaign-1/909-corpus",
                            under=f.camp / "worktrees")
            member = f.member(branch="campaign-1/7-x")
            env = herdr_stub(d, {"sid-1": "campaign-1-worker-1"})
            # FOUR SLOTS, AND TODAY'S CORPUS FILLS TWO. Every file entry in it
            # is `campaign` or `worktree`, because that is where this
            # campaign's sessions wrote; `base` and `member` are exercised by
            # the hand-written cases above and by nothing here. Kept anyway, so
            # a corpus extracted on a machine that works differently replays
            # without a change -- and said out loud, because a slot nothing
            # reaches reads exactly like a slot that passed.
            where = {"base": f.base, "campaign": f.camp, "worktree": wt,
                     "member": member}
            refused, refused_at, replayed = {}, [], 0
            for i, row in enumerate(rows):
                if row["tool"] == "Bash":
                    ti = {"command": row["command"]}
                    subject = row["command"]
                else:
                    root = where.get(row["kind"])
                    if root is None:
                        continue
                    ti = {"file_path": str(root / row["path"])}
                    subject = f'{row["tool"]} {row["kind"]}:{row["path"]}'
                payload = {"session_id": "sid-1", "cwd": str(f.base),
                           "tool_name": row["tool"], "tool_input": ti,
                           "hook_event_name": "PreToolUse"}
                rc, _o, err = ask_inproc(mod, payload, env)
                replayed += 1
                if rc != 0:
                    refused_at.append(i)
                    refused[i] = (f"{subject[:120]}\n         -> "
                                  f"{' '.join(err.split())[:200]}")
            # The count is asserted, not printed: a loop whose body never ran
            # prints the same clean line as one that replayed everything.
            check("the corpus replay ran over every entry",
                  replayed == len(rows), f"{replayed} of {len(rows)}")
            # THE ONE DELIBERATE BREAK IN THE RECORD (#217). The corpus is the
            # calls this campaign actually made, and every comment among them
            # predates the five kinds -- so the comment check refuses them, and
            # that is the rule working rather than a false positive. The
            # assertion is therefore not "nothing is refused" but "the refusals
            # are EXACTLY the comment writes": a comment row that slipped
            # through and any other row that started failing are both findings,
            # and a blanket exemption would have hidden the second.
            posts = {i for i, row in enumerate(rows)
                     if row["tool"] == "Bash" and row_posts_comment(mod, row)}
            # THE EXEMPT SET IS FROZEN TO A NUMBER, because it is computed by
            # the reader under test: any row the comment check MISCLASSIFIES as
            # a comment has its refusal excused by the very mistake that caused
            # it, and the `already` control below cannot see a narrow false
            # positive. Frozen, a row newly entering the set is itself a
            # failure. 611 rows, 64 of them comment writes, at the corpus as
            # `guard-corpus.py` last wrote it; re-bless both numbers when the
            # corpus is regenerated, and read a change here as a question about
            # `comment_body` before reading it as a question about the corpus.
            check("the corpus's comment rows are the 64 last blessed",
                  len(rows) == 611 and len(posts) == 64,
                  f"{len(posts)} of {len(rows)}")
            other = sorted(set(refused_at) - posts)
            check(f"of the {replayed} recorded allows the guard refuses only "
                  f"comment writes, whose shape #217 changed",
                  not other, "\n      ".join(refused[i] for i in other[:8]))
            check("...and it does refuse some of them, so the rule bites on "
                  "the record rather than passing it",
                  len(refused_at) > 5, f"{len(refused_at)} refused")
            # THE CONTROL, and it is not decoration: without it the two above
            # are equally satisfied by a check that refuses EVERY comment. A
            # handful of this campaign's own `REPORT campaign-1-worker-3: ...`
            # comments already carry a kind and a name, and they must still
            # pass -- which is what says this reads the SHAPE and not the verb.
            already = sorted(posts - set(refused_at))
            check("...while the comments that already carry a kind still pass",
                  len(already) > 1, f"{len(already)} of {len(posts)} passed")

            # THE REPLAY IS IN-PROCESS, so something must show that the
            # in-process reading is the shipped script's. A sample of the
            # corpus goes through the real subprocess and the two verdicts are
            # compared; without this the whole sweep could be measuring a
            # module the hook never runs.
            sample = rows[::max(1, len(rows) // 12)][:12]
            disagreed = []
            for row in sample:
                if row["tool"] != "Bash":
                    continue
                rc1, _o, _e = ask_inproc(
                    mod, {"session_id": "sid-1", "cwd": str(f.base),
                          "tool_name": "Bash",
                          "tool_input": {"command": row["command"]},
                          "hook_event_name": "PreToolUse"}, env)
                r2 = ask(f.base, tool="Bash", command=row["command"], env=env)
                if rc1 != r2.returncode:
                    disagreed.append(f"{row['command'][:80]}: in-process "
                                     f"{rc1}, subprocess {r2.returncode}")
            check("corpus: in-process and subprocess agree on the sample",
                  not disagreed, "; ".join(disagreed))

    if not ran:
        print("FAIL  the suite ran no case at all")
        return 1
    for x in fails:
        print(f"FAIL  {x}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
