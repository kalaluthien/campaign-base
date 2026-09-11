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
    """Every script the installed hooks run, read from the installer.

    An `# installs:` entry is `<repo-relative path>:<Event>[,<Event>]` since
    #227; the events are the installer's business and the path is this
    suite's. A `# runs:` entry is still a bare name under `scripts/`."""
    out = ["install-hooks.sh"]
    for line in INSTALLER.read_text().splitlines():
        for key in ("# runs: ", "# installs: ", "# imports: "):
            if line.startswith(key):
                for n in line[len(key):].split():
                    n = n.split(":", 1)[0]
                    if n not in out:
                        out.append(n)
    return out


def place(n, root):
    """Copy one `_needed()` entry into a fixture tree at the path the installer
    looks for it: repo-relative when it holds a slash, under `scripts/`
    otherwise."""
    rel = n if "/" in n else f"scripts/{n}"
    src = HERE.parent / rel
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text())
    dst.chmod(0o755)


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
        place(n, f.base)
    (f.base / "spec").mkdir()
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
    """A clean commit attempt in `tree`: one Alloy file under spec/, which no
    other guard refuses, so the verdict is the claim gate's alone."""
    (tree / "spec").mkdir(exist_ok=True)
    p = tree / "spec" / "x.als"
    p.write_text("sig X {}\n")
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

    # BEFORE ANY FIXTURE, because every case below copies these files and a
    # path that does not resolve comes out as a FileNotFoundError from
    # whichever case ran first -- which is how #227's change to the
    # `# installs:` line was found: as a crash naming a doubled `scripts/`
    # prefix, not as a case named for the list.
    for n in _needed():
        rel = n if "/" in n else f"scripts/{n}"
        check(f"the installer's entry {n} resolves to a file in this tree",
              (HERE.parent / rel).is_file(), f"no {HERE.parent / rel}")
    if fails:
        # TERMINAL, because every case below copies these files: without this
        # the finding is appended and then buried by the FileNotFoundError the
        # first fixture raises, and the summary that would have named it never
        # prints.
        for f in fails:
            print(f"FAIL  {f}")
        print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
        return 1

    # THE GUARD'S OWN IMPORT, MISSING. `claim_match` reads the branch's campaign
    # token through `campaign-name-session.py`; a traceback there exits 1, and a
    # `pre-commit` that exits non-zero refuses -- but the PreToolUse half sharing
    # this code would have the call PROCEED. So the reading fails closed, and
    # names the cause rather than blaming the branch.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("demo/7-x",))
        (f.trees["demo/7-x"] / ".claude" / "skills" / "assuming-role" / "scripts" / "campaign-name-session.py").unlink()
        r, moved = commit(f, f.trees["demo/7-x"])
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
        f = build(d, claims=("demo/7-x",), feature="feature")
        r, moved = commit(f, f.trees["demo/7-x"],
                          env={"CLAUDE_CODE_SESSION_ID": "sid-1"})
        check("a commit in a worktree on a claimed branch goes through",
              r.returncode == 0 and moved, f"exit {r.returncode}: {out(r)[:300]}")
        check("...and the hook says the branch is a claim and where the ref was read",
              "is a claim" in out(r) and "refs/remotes/origin/demo/7-x"
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
        f = build(d, unpushed=("demo/8-y",))
        wt8 = f.trees["demo/8-y"]
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
        f = build(d, claims=("demo/7-x",))
        clone = f.clone()
        r = subprocess.run([str(clone / "scripts" / "install-hooks.sh"),
                            "--git-only"], cwd=clone, capture_output=True,
                           text=True, env=dict(os.environ, HOME=str(f.home)))
        check("the installer installs into the clone", r.returncode == 0, out(r)[:200])
        r, moved = commit(f, clone)
        check("a commit in a clone on main is refused",
              r.returncode != 0 and not moved and "on main" in out(r),
              f"exit {r.returncode}: {out(r)[:300]}")
        f.git(clone, "switch", "-q", "--track", "origin/demo/7-x")
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
            place(n, root)
        (root / ".gitignore").write_text(
            "/*\n!/.gitignore\n!/.claude/\n!/scripts/\n!/spec/\n")
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
        (root / "spec").mkdir()
        (root / "spec" / "x.als").write_text("sig X {}\n")
        subprocess.run(["git", "-C", str(root), "add", "spec/x.als"], check=True)
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
        (f.base / "spec" / "y.als").write_text("sig Y {}\n")
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
        (wt / "spec").mkdir(exist_ok=True)
        (wt / "spec" / "z.als").write_text("sig Z {}\n")
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

    # THE PUSH HALF. `push-campaign-branch.sh` used to match the branch name
    # itself, with `campaign-*/*`, which is a second reader of `claim_match` --
    # and it drifted: after #181 cut claims as `<slug>/<issue>-<topic>` the
    # glob matched the retired form alone, so a commit on a live claim fell
    # through to `exit 0` and was never pushed. Nothing said so. These cases
    # assert on the REMOTE, which is the only place the difference shows.
    with tempfile.TemporaryDirectory() as d:
        f = build(d, claims=("demo/9-topic",), feature="feature/9-topic",
                  unpushed=("campaign-1/9-topic",))
        for branch, want, why in (
                ("demo/9-topic", True, "a slug claim, the only form minted"),
                ("campaign-1/9-topic", False,
                 "the retired form, no longer a claim: `campaign` is a barred "
                 "slug segment, so the pre-commit half refuses first"),
                ("feature/9-topic", False,
                 "no claim, so the pre-commit half refuses and there is "
                 "nothing for the push half to reach")):
            tree = f.trees[branch]
            r, moved = commit(f, tree)
            remote = f.git(tree, "ls-remote", "origin", branch).stdout.split()
            local = f.git(tree, "rev-parse", "HEAD").stdout.strip()
            pushed = bool(remote) and remote[0] == local
            check(f"post-commit pushes {branch} -- {why}" if want else
                  f"{branch} never reaches the remote -- {why}",
                  (moved and pushed) if want else (not moved and not pushed),
                  f"committed={moved} pushed={pushed} remote={remote[:1]} "
                  f"local={local} :: {out(r)[:300]}")

        # WHAT THE HOOK DOES WITH EACH ANSWER, which the cases above do not
        # reach: they are satisfied by the pre-commit half refusing first. The
        # reader is stubbed, so this pins the hook's own branches and nothing
        # else -- and the word is what it reads, because python exits 1 on an
        # uncaught exception and a bare 1 read as `no` would strand a claim.
        # THE COPY THE HOOK ACTUALLY RUNS is the worktree's own, resolved under
        # its toplevel -- not the base's. Stubbing the base's left the real
        # reader answering and the case passed on the wrong thing.
        tree = f.trees["demo/9-topic"]
        gate = tree / "scripts" / "check-commit-claim.py"
        real = gate.read_text()
        for word, status, pushes, why in (
                ("no-claim", 1, False, "answered no: not this hook's branch"),
                ("unknown", 2, True,
                 "could not look: an unread question is not a no"),
                ("claim", 1, True,
                 "the word and the status disagree, which is itself unread")):
            # The third round pushes like the second, so `pushed` alone cannot
            # tell them apart -- deleting the disagreement branch kept 40/40.
            # What separates them is what the hook SAID.
            # `--is-claim` ONLY. The same file is the pre-commit gate, and a
            # stub that refused there would stop the commit before the push
            # half ran -- which is the branch these cases exist to reach.
            gate.write_text("#!/usr/bin/env python3\n"
                            "import sys\n"
                            "if '--is-claim' not in sys.argv[1:]:\n"
                            "    print('stub: pre-commit half not judged')\n"
                            "    sys.exit(0)\n"
                            f"print({word + ' stub'!r})\n"
                            f"sys.exit({status})\n")
            gate.chmod(0o755)
            before = f.git(tree, "ls-remote", "origin",
                           "demo/9-topic").stdout.split()
            # A DISTINCT FILE PER ROUND: `commit` writes one fixed page, so a
            # second round had nothing to commit and every branch looked the
            # same as the last.
            (tree / "spec").mkdir(exist_ok=True)
            (tree / "spec" / f"{word}.als").write_text("sig W {}\n")
            f.git(tree, "add", str(tree / "spec" / f"{word}.als"))
            r, moved = commit(f, tree)
            after = f.git(tree, "ls-remote", "origin",
                          "demo/9-topic").stdout.split()
            local = f.git(tree, "rev-parse", "HEAD").stdout.strip()
            pushed = bool(after) and after[0] == local
            said = "could not tell whether" in out(r)
            check(f"the hook {'pushes' if pushes else 'stands down'} on "
                  f"`{word}` -- {why}",
                  moved and pushed == pushes
                  and said == (word != "no-claim" and status != 0),
                  f"committed={moved} pushed={pushed} said={said} "
                  f"before={before[:1]} after={after[:1]} :: {out(r)[:200]}")
        gate.write_text(real)
        gate.chmod(0o755)

        # The reading the hook asks for, on its own. Three outcomes, and `2`
        # is not folded into `1`: the hook pushes on 2, because an unread
        # question is not a no.
        gate = f.base / "scripts" / "check-commit-claim.py"
        e = dict(os.environ, HOME=str(f.home))
        e.pop("CLAUDE_CODE_SESSION_ID", None)
        for cwd, want, why in (
                (f.trees["demo/9-topic"], 0, "a claim"),
                (f.trees["feature/9-topic"], 1, "answered: not a claim"),
                (Path(d), 2, "could not look -- no git repository here")):
            r = subprocess.run([str(gate), "--is-claim"], cwd=str(cwd),
                               capture_output=True, text=True, env=e)
            check(f"--is-claim exits {want} when {why}", r.returncode == want,
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
