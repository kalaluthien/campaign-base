#!/usr/bin/env python3
"""Prove the commit gate refuses a commit on campaign work with no claim, through
the hook install-hooks actually writes.

Every case builds a real base with a real remote, runs the shipped installer
against it (HOME redirected, so the harness half touches nobody's settings),
and commits. Never a string fixture: the gate is a pre-commit hook, and what
is under test is whether a commit is refused, which only a commit can show.

The fixture reuses check-campaign-claim-test's `Fixture`, since the two halves
read one claim shape.

Usage: scripts/check-commit-claim-test.py
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
INSTALLER = HERE / "install-hooks.sh"


def _needed():
    """Every script the installed hooks run, read from the installer."""
    out = ["install-hooks.sh"]
    for line in INSTALLER.read_text().splitlines():
        for key in ("# runs: ", "# installs: ", "# imports: "):
            if line.startswith(key):
                for n in line[len(key):].split():
                    if n not in out:
                        out.append(n)
    return out


def load_fixture():
    path = HERE / "check-campaign-claim-test.py"
    spec = importlib.util.spec_from_loader(
        "guard_test", importlib.machinery.SourceFileLoader("guard_test", str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build(d, **kw):
    """A Fixture whose base holds every script the hooks run, with the hooks
    installed. Scripts land in a second commit so the fixture's remote and
    claim branches carry them too."""
    m = load_fixture()
    f = m.Fixture(d, claims=())
    for n in _needed():
        (f.base / "scripts" / n).write_text((HERE / n).read_text())
        (f.base / "scripts" / n).chmod(0o755)
    (f.base / "docs").mkdir()
    m.git(f.base, "add", "-A")
    m.git(f.base, "commit", "-qm", "scripts", "--no-verify")
    m.git(f.base, "push", "-q", "origin", "HEAD")
    # Every branch is cut AFTER the scripts landed, so each worktree holds
    # the guards the installed hook resolves under its own toplevel.
    for i, b in enumerate(kw.get("claims", ())):
        m.git(f.base, "branch", b)
        m.git(f.base, "push", "-q", "origin", b)
        f.trees[b] = f.worktree(f"wt-c{i}", b)
    for i, b in enumerate(kw.get("unpushed", ())):
        m.git(f.base, "branch", b)
        f.trees[b] = f.worktree(f"wt-u{i}", b)
    if kw.get("feature"):
        m.git(f.base, "branch", kw["feature"])
        f.trees[kw["feature"]] = f.worktree("wt-f", kw["feature"])
    home = Path(d) / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text("{}\n")
    r = subprocess.run([str(f.base / "scripts" / "install-hooks.sh"), "--git-only"],
                       cwd=f.base, capture_output=True, text=True,
                       env=dict(os.environ, HOME=str(home)))
    assert r.returncode == 0, r.stdout + r.stderr
    f.home = home
    f.git = m.git
    return f


def commit(f, tree, env=None):
    """A clean commit attempt in `tree`: one HTML page under docs/, which no
    other guard refuses, so the verdict is the claim gate's alone."""
    (tree / "docs").mkdir(exist_ok=True)
    p = tree / "docs" / "x.html"
    p.write_text("<p>x</p>\n")
    f.git(tree, "add", str(p))
    before = f.git(tree, "rev-parse", "HEAD").stdout.strip()
    e = dict(os.environ, HOME=str(f.home))
    e.pop("CLAUDE_CODE_SESSION_ID", None)
    e.update(env or {})
    r = subprocess.run(["git", "-C", str(tree), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "c"],
                       capture_output=True, text=True, env=e)
    after = f.git(tree, "rev-parse", "HEAD").stdout.strip()
    return r, before != after


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}\n      {detail}")

    def out(r):
        return r.stdout + r.stderr

    # THE GUARD'S OWN IMPORT, MISSING. `claim_match` reads the branch's campaign
    # token through `campaign-name-session.py`; a traceback there exits 1, and a
    # `pre-commit` that exits non-zero refuses -- but the PreToolUse half sharing
    # this code would have the call PROCEED. So the reading fails closed, and
    # names the cause rather than blaming the branch.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("campaign-1/7-x",))
        (f.trees["campaign-1/7-x"] / "scripts" / "campaign-name-session.py").unlink()
        r, moved = commit(f, f.trees["campaign-1/7-x"])
        check("a claim whose name rule will not load is refused, not admitted",
              r.returncode != 0 and not moved, f"exit {r.returncode}: {out(r)[:300]}")
        check("...naming the rule that would not load, not the branch",
              "would not load" in out(r), out(r)[:400])

    # THE SLUG FORM, IN ITS OWN WORKTREE -- the shape every claim takes after
    # #181, and the one no case reached: every other case here uses the retired
    # `campaign-<N>/` form, which needs no marker lookup at all. Finding 1 of
    # the #181 review shipped green underneath exactly this gap. A worktree
    # carries `scripts/` of its own and NO campaign directory, so asking the
    # base NEAREST the checkout finds no slugs and the claim reads as none.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("demo/7-x",))
        r, moved = commit(f, f.trees["demo/7-x"],
                          env={"CLAUDE_CODE_SESSION_ID": "sid-1"})
        check("a commit in a worktree on a SLUG claim goes through",
              r.returncode == 0 and moved, f"exit {r.returncode}: {out(r)[:400]}")
        check("...and the hook says that branch is a claim",
              "demo/7-x is a claim" in out(r).replace("its branch ", ""),
              out(r)[:400])

    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("campaign-1/7-x",), feature="feature")
        r, moved = commit(f, f.trees["campaign-1/7-x"],
                          env={"CLAUDE_CODE_SESSION_ID": "sid-1"})
        check("a commit in a worktree on a claimed branch goes through",
              r.returncode == 0 and moved, f"exit {r.returncode}: {out(r)[:300]}")
        check("...and the hook says the branch is a claim and where the ref was read",
              "is a claim" in out(r) and "refs/remotes/origin/campaign-1/7-x"
              in out(r), out(r)[:300])
        check("...naming the session it read from the environment",
              "session sid-1 (from CLAUDE_CODE_SESSION_ID)" in out(r), out(r)[:300])
        # A worktree at a sibling path runs the MAIN checkout's hooks, so a
        # commit there is judged: #180's `git commit` row, closed here.
        r, moved = commit(f, f.trees["feature"])
        check("#180 row 9: a commit in a sibling worktree on a plain branch is refused",
              r.returncode != 0 and not moved, f"exit {r.returncode}: {out(r)[:300]}")
        check("...saying the branch is not a campaign branch",
              "REFUSING the commit" in out(r) and "not a campaign branch" in out(r),
              out(r)[:300])
        check("...and, with no session id, that it judged a person's commit by "
              "the branch alone",
              "a person's commit, judged by the branch alone" in out(r), out(r)[:300])
        check("...and names the main checkout as the base",
              f"inside the base {f.base.resolve()}" in out(r), out(r)[:300])
        r, moved = commit(f, f.base, env={"CLAUDE_CODE_SESSION_ID": "sid-1"})
        check("a commit on main in the base is refused by the claim gate",
              r.returncode != 0 and not moved and "on main, not a campaign branch"
              in out(r), f"exit {r.returncode}: {out(r)[:300]}")
        r, moved = commit(f, f.base, env={"SKIP_REPO_GUARDS": "1"})
        check("SKIP_REPO_GUARDS=1 does not get past a refusal; it covers only a "
              "guard that cannot run",
              r.returncode != 0 and not moved, f"exit {r.returncode}: {out(r)[:300]}")

    with tempfile.TemporaryDirectory() as d:
        f = build(d, unpushed=("campaign-1/8-y",))
        wt8 = f.trees["campaign-1/8-y"]
        r, moved = commit(f, wt8)
        check("a campaign branch whose ref is on no remote is refused as no claim",
              r.returncode != 0 and not moved and "no such head" in out(r),
              f"exit {r.returncode}: {out(r)[:300]}")
        f.git(f.base, "remote", "set-url", "origin", str(Path(d) / "nowhere.git"))
        r, moved = commit(f, wt8)
        check("a remote that cannot be asked refuses saying it could not look",
              r.returncode != 0 and not moved and "could not be read" in out(r)
              and "Could not look" in out(r), f"exit {r.returncode}: {out(r)[:300]}")

    # A delegate's clone under the campaign directory, hooks installed there
    # too (#178), judged by its own branch.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("campaign-1/7-x",))
        clone = f.clone()
        r = subprocess.run([str(clone / "scripts" / "install-hooks.sh"),
                            "--git-only"], cwd=clone, capture_output=True,
                           text=True, env=dict(os.environ, HOME=str(f.home)))
        check("the installer installs into the clone", r.returncode == 0, out(r)[:200])
        r, moved = commit(f, clone)
        check("a commit in a clone on main is refused",
              r.returncode != 0 and not moved and "on main" in out(r),
              f"exit {r.returncode}: {out(r)[:300]}")
        f.git(clone, "switch", "-q", "--track", "origin/campaign-1/7-x")
        r, moved = commit(f, clone)
        check("...and on a claimed branch it goes through",
              r.returncode == 0 and moved and "is a claim" in out(r),
              f"exit {r.returncode}: {out(r)[:300]}")

    # Outside campaign work the gate is silent on the verdict: a plain
    # repository with the hooks installed commits as before.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "plain"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "scripts").mkdir()
        for n in _needed():
            (root / "scripts" / n).write_text((HERE / n).read_text())
            (root / "scripts" / n).chmod(0o755)
        (root / ".gitignore").write_text("/*\n!/.gitignore\n!/scripts/\n!/docs/\n")
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c",
                        "user.name=t", "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c",
                        "user.name=t", "commit", "-qm", "i", "--no-verify"], check=True)
        home = Path(d) / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "settings.json").write_text("{}\n")
        subprocess.run([str(root / "scripts" / "install-hooks.sh"), "--git-only"],
                       cwd=root, capture_output=True, text=True,
                       env=dict(os.environ, HOME=str(home)), check=True)
        (root / "docs").mkdir()
        (root / "docs" / "x.html").write_text("<p>x</p>\n")
        subprocess.run(["git", "-C", str(root), "add", "docs/x.html"], check=True)
        r = subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c",
                            "user.name=t", "commit", "-qm", "c"],
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        check("a repository that is not a base commits, the gate saying it is not "
              "campaign work",
              r.returncode == 0 and "not campaign work" in out(r),
              f"exit {r.returncode}: {out(r)[:300]}")

    # COULD NOT LOOK IS NOT A PASS. The claim reading lives in one script; when
    # that import fails the gate has read nothing, and the one branch that
    # turns "I could not look" into an allowed commit was asserted by nothing.
    with tempfile.TemporaryDirectory() as d:
        f = build(d)
        home = f.home
        (f.base / "scripts" / "check-campaign-claim.py").unlink()
        (f.base / "docs" / "y.html").write_text("<p>y</p>\n")
        m = load_fixture()
        m.git(f.base, "add", "-A")
        before = m.git(f.base, "rev-parse", "HEAD").stdout.strip()
        r = subprocess.run(["git", "-C", str(f.base), "-c", "user.email=t@t",
                            "-c", "user.name=t", "commit", "-qm", "c"],
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        after = m.git(f.base, "rev-parse", "HEAD").stdout.strip()
        check("the claim reading missing refuses the commit and says it could "
              "not import, rather than allowing it",
              r.returncode != 0 and "could not import" in out(r)
              and before == after,
              f"exit {r.returncode}; HEAD moved: {before != after}; "
              f"{out(r)[:300]}")

    # A remedy naming an option `take` does not accept sends the reader to a
    # command that fails. Read from `take --help`, so the next retired flag is
    # caught too.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, feature="feature")
        home = f.home
        wt = f.trees["feature"]
        (wt / "docs").mkdir(exist_ok=True)
        (wt / "docs" / "z.html").write_text("<p>z</p>\n")
        m = load_fixture()
        m.git(wt, "add", "-A")
        r = subprocess.run(["git", "-C", str(wt), "-c", "user.email=t@t", "-c",
                            "user.name=t", "commit", "-qm", "c"],
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        usage = subprocess.run(
            [sys.executable, str(HERE / "campaign-claim.py"), "take", "--help"],
            capture_output=True, text=True).stdout
        remedy = next((x for x in out(r).splitlines()
                       if "campaign-claim.py take" in x), "")
        unknown = [w.strip(",.") for w in remedy.split()
                   if w.startswith("--") and w.strip(",.") not in usage]
        check("the commit gate's remedy names only options `take` accepts",
              remedy and not unknown,
              f"not in `take --help`: {unknown}; remedy: {remedy!r}; "
              f"exit {r.returncode}: {out(r)[:300]}")

    if not ran:
        print("FAIL  the suite ran no case at all")
        return 1
    for x in fails:
        print(f"FAIL  {x}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
