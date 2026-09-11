#!/usr/bin/env python3
"""Prove the hooks install-hooks writes actually refuse.

Every other suite here tests a script in isolation. This one builds a
repository with the hooks installed and commits against it, because a script
correct in isolation says nothing about whether the pre-commit body it writes
actually stops a violation.

These cases build a throwaway repository, run the shipped installer, and commit.
The remote is a local bare repo; nothing here reaches the network.

Usage: scripts/install-hooks-test.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _needed():
    """The scripts a fixture repository must hold, read from the installer.

    Derived, never listed. The hook install-hooks writes REFUSES every commit
    when a guard on its `# runs:` line is missing, so a hand-kept list here goes
    stale the moment a guard is added -- and it fails as an unrelated crash far
    downstream (nothing commits, so nothing is pushed, so a later ls-remote
    reads empty) rather than as a case named for the list.

    Both `# runs:` lines in the installer are read: the pre-commit one inside
    its heredoc and the post-commit one, which is where push-campaign-branch
    comes from. `# installs:` is read for the same reason one line down: the
    installer refuses when a harness hook it is registering is not there, so a
    fixture missing it fails every case with one unrelated message. `# imports:`
    is read for the third time for the same reason: the installer refuses when a
    file the guards IMPORT is absent, because a guard that tracebacks where it
    meant to refuse is a hole and not a refusal.
    """
    out = ["install-hooks.sh"]
    for line in (SCRIPTS / "install-hooks.sh").read_text().splitlines():
        for key in ("# runs: ", "# installs: ", "# imports: "):
            if line.startswith(key):
                for n in line[len(key):].split():
                    # An `# installs:` entry carries its events after a colon
                    # (#227); only the path names a file to place.
                    n = n.split(":", 1)[0]
                    if n not in out:
                        out.append(n)
    return out


def place(n, root):
    """Copy one `NEEDED` entry into a fixture tree at the path the installer
    will look for it. An entry is repo-relative since #227 (a harness hook may
    live under `.claude/skills/<skill>/scripts/`) or a bare name from the older
    `# runs:` lines, which belongs in `scripts/`."""
    rel = n if "/" in n else f"scripts/{n}"
    src = SCRIPTS.parent / rel
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)


NEEDED = _needed()
IGNORE = "/*\n!/.gitignore\n!/.claude/\n!/scripts/\n!/spec/\n"


def git(root, *args, **kw):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                           *args], cwd=root, capture_output=True, text=True, **kw)


class Repo:
    def __init__(self, d):
        self.root = Path(d) / "w"
        self.remote = Path(d) / "r.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.root)],
                       capture_output=True, check=True)
        (self.root / "scripts").mkdir()
        for n in NEEDED:
            place(n, self.root)
        (self.root / ".gitignore").write_text(IGNORE)
        git(self.root, "add", "-Af")
        git(self.root, "commit", "-qm", "init", "--no-verify")
        git(self.root, "switch", "-qc", "topic")

    def hook(self, name):
        return self.root / ".git" / "hooks" / name

    def violate(self, name="spec/bad.md"):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("misfiled\n")
        git(self.root, "add", str(name))

    def commit(self, msg="c", env=None):
        e = dict(os.environ, **(env or {}))
        return git(self.root, "commit", "-qm", msg, env=e)

    def commit_amend_push(self):
        """Run the push hook by hand after an amend: the post-commit hook has
        already fired, and what is under test is the rejection path."""
        r = subprocess.run([str(self.root / "scripts" / "push-campaign-branch.sh")],
                           cwd=self.root, capture_output=True, text=True)
        return r.stdout + r.stderr

    def head(self):
        return git(self.root, "log", "--oneline", "-1").stdout.strip()


def installer(root):
    """Run the installer against a HOME of its own.

    Load-bearing, not tidiness: the installer now writes the harness hooks into
    $HOME/.claude/settings.json, and a suite that let it see the real one would
    edit the person running it -- a case whose damage is outside the temporary
    directory everything else here is confined to."""
    home = root.parent / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    settings = home / ".claude" / "settings.json"
    if not settings.exists():
        settings.write_text("{}\n")
    return subprocess.run([str(root / "scripts" / "install-hooks.sh")], cwd=root,
                          capture_output=True, text=True,
                          env=dict(os.environ, HOME=str(home)))


def legacy_guard_shim(guard):
    """The two lines acquire-repo wrote BEFORE #190, spelled from its printf.

    Kept because clones acquired then still hold it on disk, and `is_guard_shim`
    still has to adopt it. What acquire-repo writes now carries the claim gate
    too and is not spelled here, nor is its length: the cases for it run the
    shipped script and read the bytes back."""
    return f'#!/usr/bin/env sh\nexec "{guard}" "$@"\n'


def fake_guard(home):
    """A no-main-commits at the place acquire-repo and the hook look, which
    refuses every commit in its own words so chaining is observed, not read."""
    g = home / ".claude" / "git-hooks" / "no-main-commits"
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text("#!/bin/sh\necho 'FAKE GUARD RAN' >&2\nexit 1\n")
    g.chmod(0o755)
    return g


def main():
    ran, fails = [], []

    def check(name, cond, detail=""):
        ran.append(name)
        if not cond:
            fails.append(f"{name}\n      {detail}")

    # 1. The whole point: an installed hook stops a real violation.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        before = r.head()
        r.violate()
        c = r.commit()
        check("an installed pre-commit refuses a real violation",
              c.returncode != 0 and r.head() == before,
              f"exit {c.returncode}; {(c.stdout + c.stderr).strip()[:160]}")
        check("...and names the rule it refused on",
              "R1" in c.stdout + c.stderr, (c.stdout + c.stderr)[:160])

    # 2. A clean commit still goes through.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        (r.root / "spec").mkdir()
        (r.root / "spec" / "x.als").write_text("sig X {}\n")
        git(r.root, "add", "spec/x.als")
        c = r.commit()
        check("a clean commit is not blocked", c.returncode == 0,
              (c.stdout + c.stderr)[:160])

    # 3. The declaration is what drives the loop, so removing it must stop the
    # commit rather than silently run nothing.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        h = r.hook("pre-commit")
        h.write_text("\n".join(l for l in h.read_text().splitlines()
                               if not l.startswith("# runs: ")) + "\n")
        before = r.head()
        r.violate()
        c = r.commit()
        check("a hook with no `# runs:` line refuses instead of running nothing",
              c.returncode != 0 and r.head() == before
              and "carries no '# runs:' line" in c.stdout + c.stderr,
              f"exit {c.returncode}; {(c.stdout + c.stderr).strip()[:200]}")

    # 3b. A declaration that is present but names nothing. `[ -z "$guards" ]`
    # is false for a line of whitespace, so the loop would run zero times and
    # a violation would commit with no output at all -- the same silent skip.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        h = r.hook("pre-commit")
        # Rewrite the line by its PREFIX, never by a copy of its contents. The
        # guard list is install-hooks' to change, and a literal of it here is a
        # second reader: adding a guard made this replace silently match
        # nothing, so the hook kept a working declaration and the case passed
        # its own name while testing the opposite branch.
        h.write_text("\n".join(
            "# runs:   " if l.startswith("# runs: ") else l
            for l in h.read_text().splitlines()) + "\n")
        before = r.head()
        r.violate()
        c = r.commit()
        # The message, not only the status: a hook with a syntax error also
        # exits non-zero and leaves HEAD alone, so a status-only assertion
        # passes for a reason that has nothing to do with the declaration.
        check("a declaration naming nothing refuses too",
              c.returncode != 0 and r.head() == before
              and "carries no '# runs:' line" in c.stdout + c.stderr,
              f"exit {c.returncode}; {(c.stdout + c.stderr).strip()[:200]}")

    # The installed hook is what a person reads: an unescaped backtick in the
    # heredoc runs as command substitution and eats the comment around it.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        body = r.hook("pre-commit").read_text()
        # Assert on text that sits AFTER the backticks. Command substitution
        # eats from the first backtick to the second, so a phrase before them
        # would survive the very corruption this case is named for.
        check("the installed hook keeps the comments the source writes",
              "followed by a space leaves" in body
              and "EMPTY declaration refuses" in body,
              body[:300])
        check("...including the backticked words inside them",
              "`# runs:`" in body, body[:300])

    # 4. A guard that cannot run refuses, and the escape hatch is the only way past.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        (r.root / "scripts" / "check-tree-shape.py").chmod(0o644)
        before = r.head()
        r.violate()
        c = r.commit()
        check("a guard without its execute bit refuses",
              c.returncode != 0 and r.head() == before,
              f"exit {c.returncode}")
        c = r.commit(env={"SKIP_REPO_GUARDS": "1"})
        check("SKIP_REPO_GUARDS=1 is the only way past, and it announces itself",
              c.returncode == 0 and "SKIP_REPO_GUARDS=1" in c.stdout + c.stderr,
              (c.stdout + c.stderr)[:160])

    # A GUARD'S IMPORT IS NOT INSTALLED, so nothing used to read the line that
    # declares it -- and a guard whose import is absent tracebacks where it
    # meant to refuse, which a PreToolUse hook reads as its own error and lets
    # the call PROCEED. The refusal is the installer's, so the case is here.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        imported = [n.split(":", 1)[0] for line in
                    (SCRIPTS / "install-hooks.sh").read_text().splitlines()
                    if line.startswith("# imports: ")
                    for n in line[len("# imports: "):].split()]
        check("the installer declares at least one import to check",
              len(imported) > 0, f"imports {imported}")
        (r.root / imported[0]).unlink()
        out = installer(r.root)
        check("the installer refuses when a file its guards IMPORT is missing",
              out.returncode != 0 and imported[0] in out.stderr,
              (out.stdout + out.stderr)[:200])
        check("...and it names why: a traceback where a refusal was meant",
              "traceback" in (out.stdout + out.stderr).lower(),
              (out.stdout + out.stderr)[:200])

    # 5. The installer refuses where git would not look.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        git(r.root, "config", "core.hooksPath", str(r.root / "elsewhere"))
        out = installer(r.root)
        check("the installer refuses when core.hooksPath sends git elsewhere",
              out.returncode != 0 and "hooksPath" in out.stderr,
              (out.stdout + out.stderr)[:160])

    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        r.hook("pre-commit").write_text("#!/bin/sh\n# somebody else's\n")
        out = installer(r.root)
        check("the installer refuses a hook it did not write",
              out.returncode != 0 and "refusing" in out.stderr,
              (out.stdout + out.stderr)[:160])

    # 5b. The one hook it adopts: a shim acquire-repo wrote into a clone.
    # Before #178 this refused, so no delegate clone held either hook. This case
    # is the PRE-#190 two-line form, which is still on disk wherever a clone was
    # acquired then; the current form is adopted in 5d, against the real bytes.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        home = r.root.parent / "home"
        guard = fake_guard(home)
        r.hook("pre-commit").write_text(legacy_guard_shim(guard))
        r.hook("pre-commit").chmod(0o755)
        out = installer(r.root)
        check("the installer adopts the no-main-commits shim and says so",
              out.returncode == 0 and "adopting" in out.stderr
              and r.hook("post-commit").exists(),
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")
        # Chaining, exercised and not read: the fake guard refuses every commit
        # with its own words, so a clean commit going through would mean the
        # adopted slot lost the guard the shim carried.
        (r.root / "spec").mkdir()
        (r.root / "spec" / "x.als").write_text("sig X {}\n")
        git(r.root, "add", "spec/x.als")
        c = r.commit(env={"HOME": str(home)})
        # Pinned to the hook install-hooks wrote: the un-adopted shim also
        # prints the fake guard's words, so the `# runs:` line is what
        # separates "adopted and chained" from "left the shim alone".
        check("...and the hook it writes still chains no-main-commits",
              c.returncode != 0 and "FAKE GUARD RAN" in c.stdout + c.stderr
              and "# runs:" in r.hook("pre-commit").read_text(),
              f"exit {c.returncode}; {(c.stdout + c.stderr)[:160]}")
    # A near miss is not the legacy shim. One line more than it is somebody's
    # decision, and matching on "mentions no-main-commits" would adopt it. Nor
    # does it become the CURRENT shim by being three lines: that one is
    # recognised by the marker on line 2 and by nothing else.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        guard = fake_guard(r.root.parent / "home")
        r.hook("pre-commit").write_text(legacy_guard_shim(guard) + "echo also this\n")
        out = installer(r.root)
        check("a shim with one line added is still refused",
              out.returncode != 0 and "refusing" in out.stderr
              and "adopting" not in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:160]}")

    # ...AND THE OTHER CONJUNCT OF THAT BRANCH, which nothing pinned until a
    # review of #214 deleted the line-2 pattern and watched both suites stay
    # green: two lines and the right shebang, with a line 2 that is not the
    # exec. Somebody's own two-line hook, adopted and replaced.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        r.hook("pre-commit").write_text("#!/usr/bin/env sh\nexec /usr/bin/true\n")
        r.hook("pre-commit").chmod(0o755)
        out = installer(r.root)
        check("a two-line hook with the right shebang but no guard call is "
              "refused, not adopted",
              out.returncode != 0 and "refusing" in out.stderr
              and "adopting" not in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:160]}")

    # THE MARKER IS NOT ENOUGH ON ITS OWN, and each of the other two conjuncts
    # gets a case of its own -- three near misses, one per conjunct, or the
    # branch is pinned by whichever of them happens to be tested. What licenses
    # replacing a hook here is that the one written below carries everything
    # read out of this one, and a comment somebody pasted proves nothing.
    GUARD_CALL = ('"/x/.claude/git-hooks/no-main-commits" "$@" || exit 1\n')
    MARKER = "# Written by acquire-repo.sh. Re-run it after changing this file.\n"
    for name, body in (
            ("but not the guard at all",
             "#!/usr/bin/env sh\n" + MARKER + "exec /usr/bin/true\n"),
            # The one that was actually broken: `grep -q no-main-commits` over
            # the whole file cannot tell a CALL from a mention, so a foreign
            # hook naming the guard in a comment was adopted and announced as
            # chaining it.
            ("but naming the guard only in a comment",
             "#!/usr/bin/env sh\n" + MARKER
             + "# nothing here calls no-main-commits\nexec /usr/bin/true\n"),
            # And the shebang, which nothing pinned until this line: deleting
            # that conjunct left the suite fully green.
            ("but not opening with the shebang",
             "#!/bin/sh\n" + MARKER + GUARD_CALL),
            # And the marker itself, which the other three cases cannot pin:
            # deleting that conjunct left the suite green, because every hook
            # they build carries the marker. Somebody else's hook that happens
            # to chain the guard is still somebody else's decision.
            ("replaced by somebody else's comment",
             "#!/usr/bin/env sh\n# our team's pre-commit\n" + GUARD_CALL)):
        with tempfile.TemporaryDirectory() as d:
            r = Repo(d)
            r.hook("pre-commit").write_text(body)
            r.hook("pre-commit").chmod(0o755)
            out = installer(r.root)
            check(f"a hook carrying the marker {name} is refused, not adopted",
                  out.returncode != 0 and "refusing" in out.stderr
                  and "adopting" not in out.stderr,
                  f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")

    # 5c. --git-only. The harness half is machine-wide and points at one
    # checkout; a clone running it would repoint every session's guard.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        home = r.root.parent / "home"
        (home / ".claude").mkdir(parents=True)
        settings = home / ".claude" / "settings.json"
        settings.write_text('{"untouched": true}\n')
        out = subprocess.run([str(r.root / "scripts" / "install-hooks.sh"),
                              "--git-only"], cwd=r.root, capture_output=True,
                             text=True, env=dict(os.environ, HOME=str(home)))
        check("--git-only installs both git hooks and says the harness half "
              "was skipped",
              out.returncode == 0 and r.hook("pre-commit").exists()
              and r.hook("post-commit").exists() and "skipped" in out.stdout,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")
        check("...and leaves settings.json byte for byte",
              settings.read_text() == '{"untouched": true}\n',
              settings.read_text()[:120])

    # 5d. acquire-repo, which is where a clone gets its hooks. Over a checkout
    # already present (its clone strategy needs gh and the network; the shared
    # path after it does not), a repository shipping this installer ends up
    # with both hooks; one without it gets the shim; a re-run converges.
    with tempfile.TemporaryDirectory() as d:
        home = Path(d) / "home"
        guard = fake_guard(home)
        (home / ".claude" / "settings.json").write_text('{"untouched": true}\n')
        env = dict(os.environ, HOME=str(home))
        acq = SCRIPTS.parent / ".claude" / "skills" / "opening-campaign" \
            / "scripts" / "acquire-repo.sh"

        def checkout(name, with_installer):
            remote = Path(d) / name / "owner" / "repo.git"
            remote.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", "--bare", str(remote)],
                           check=True)
            w = Path(d) / name / "w"
            subprocess.run(["git", "clone", "-q", str(remote), str(w)],
                           capture_output=True, check=True)
            (w / "scripts").mkdir()
            for n in NEEDED:
                if with_installer or n != "install-hooks.sh":
                    place(n, w)
            git(w, "add", "-Af")
            git(w, "commit", "-qm", "init", "--no-verify")
            git(w, "push", "-q", "origin", "HEAD")
            dest = Path(d) / name / "repos" / "repo"
            subprocess.run(["git", "clone", "-q", str(remote), str(dest)],
                           capture_output=True, check=True)
            return dest

        dest = checkout("ships", True)
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        pre = dest / ".git" / "hooks" / "pre-commit"
        post = dest / ".git" / "hooks" / "post-commit"
        check("acquire-repo runs the repository's installer when it ships one",
              out.returncode == 0 and "own installer" in out.stderr
              and post.exists() and "install-hooks" in pre.read_text(),
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")
        check("...with --git-only, so the person's settings are untouched",
              (home / ".claude" / "settings.json").read_text()
              == '{"untouched": true}\n')
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("...and a re-run converges rather than refusing",
              out.returncode == 0 and post.exists()
              and "install-hooks" in pre.read_text(),
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")

        # An installer the repository ships that writes a hook without the
        # guard: success here would be the unguarded checkout the header says
        # a caller must never read success over.
        dest = checkout("foreign", False)
        bad = dest / "scripts" / "install-hooks.sh"
        bad.write_text("#!/bin/sh\nprintf '#!/bin/sh\\necho lint\\n' >| "
                       ".git/hooks/pre-commit\nchmod +x .git/hooks/pre-commit\n")
        bad.chmod(0o755)
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("an installer whose hook omits the guard is refused, not trusted",
              out.returncode != 0 and "without the no-main-commits guard"
              in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")

        # ...AND ONE WHOSE HOOK ONLY MENTIONS IT (#214). That verification was
        # `grep -q 'no-main-commits'` over the whole file until then, three
        # lines from the overwrite test with the same defect, so a hook naming
        # the guard in a COMMENT passed as one chaining it -- acquire returning
        # 0 over a clone whose commits nothing stops. The allow control is the
        # "ships" case above, which runs the REAL install-hooks.sh: if the
        # whole-line pattern stops matching what this repository writes, that
        # case reddens rather than this one.
        dest = checkout("mentions", False)
        bad = dest / "scripts" / "install-hooks.sh"
        bad.write_text(
            "#!/bin/sh\nprintf '#!/bin/sh\\n"
            "# we deliberately do not run no-main-commits\\necho lint\\n' >| "
            ".git/hooks/pre-commit\nchmod +x .git/hooks/pre-commit\n")
        bad.chmod(0o755)
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("an installer whose hook names the guard only in a comment is "
              "refused too",
              out.returncode != 0 and "without the no-main-commits guard"
              in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")
        # An installer that fails: the status it gave is what is reported.
        # `$?` read inside an `if !` branch is 0, which is the false answer in
        # the direction that reads as success.
        bad.write_text("#!/bin/sh\necho unhappy >&2\nexit 7\n")
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("an installer that fails is reported with the status it gave",
              out.returncode != 0 and "exited 7" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")
        bad.chmod(0o644)
        bad.write_text("#!/bin/sh\nexit 0\n")
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("an installer present but not executable is named, not skipped",
              out.returncode != 0 and "not executable" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")

        # THE ALLOW CASE BESIDE IT, and the one that says how far the tightening
        # went. The first spelling of that check matched a whole-line CALL, and
        # refused a hook that reaches the guard through a variable -- which the
        # substring test accepted and which is a perfectly guarded hook. A
        # refusal here is fatal, so the pattern discriminates a comment-only
        # mention and nothing more.
        dest = checkout("indirect", False)
        ok = dest / "scripts" / "install-hooks.sh"
        ok.write_text(
            "#!/bin/sh\nprintf '%s\\n' '#!/bin/sh' "
            "'g=\"$HOME/.claude/git-hooks/no-main-commits\"' "
            "'\"$g\" \"$@\"' >| .git/hooks/pre-commit\n"
            "chmod +x .git/hooks/pre-commit\n")
        ok.chmod(0o755)
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        check("an installer whose hook reaches the guard through a variable is "
              "accepted, not refused",
              out.returncode == 0 and "chain the no-main-commits guard"
              in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")

        # A repository with no installer of its own gets the shim, and since
        # #190 that shim carries the claim gate as well as the guard. Asserted
        # on the two things it must name rather than on the whole text: a copy
        # of the body here would be the second reader this repository refuses,
        # and scripts/acquire-repo-test.py is where the installed hook is RUN.
        dest = checkout("bare", False)
        out = subprocess.run([str(acq), "owner/repo", str(dest)], env=env,
                             capture_output=True, text=True)
        pre = dest / ".git" / "hooks" / "pre-commit"
        gate = SCRIPTS / "check-commit-claim.py"
        body = pre.read_text() if pre.exists() else ""
        check("a repository with no installer gets the shim, and no post-commit",
              out.returncode == 0 and str(guard) in body
              and not (dest / ".git" / "hooks" / "post-commit").exists(),
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")
        check("...carrying the claim gate by its absolute path in the base",
              f'"{gate}" --staged' in body, repr(body[-160:]))
        # "Only the shim" used to be pinned by comparing the whole text, which
        # went with #190. This is what that comparison was actually for: acquire
        # must not install THIS repository's hook into a member clone, whose
        # `# runs:` guards it does not have and whose post-commit would push its
        # branches.
        check("...and not this repository's own hook, which the clone could not "
              "run",
              "# runs:" not in body, repr(body[:160]))

        # 5e. AND THIS INSTALLER ADOPTS THAT SHIM. #178's fix, which #190 would
        # have undone in silence: the shim stopped being the two lines
        # `is_guard_shim` knew, so a clone that later gained this repository's
        # hooks would have been refused as holding somebody else's.
        for n in NEEDED:
            place(n, dest)
        out = installer(dest)
        check("the installer adopts the shim acquire-repo writes NOW, not only "
              "the one it used to",
              out.returncode == 0 and "adopting" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:240]}")
        check("...replacing it with its own hook, which runs the same gate",
              "# runs:" in pre.read_text()
              and "check-commit-claim.py" in pre.read_text(),
              repr(pre.read_text()[:160]))

    # 6. post-commit, on the real thing.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        installer(r.root)
        (r.root / "spec").mkdir()
        (r.root / "spec" / "a.als").write_text("sig A {}\n")
        git(r.root, "add", "spec/a.als")
        c = r.commit()
        # The hook's own verdict line, not its name: a pre-commit guard may
        # NAME the script in its reading (check-sdlc-tie lists it among the
        # untied code paths), and a name is not a push.
        check("an ordinary branch is not pushed", "push-campaign-branch:" not in
              c.stdout + c.stderr, (c.stdout + c.stderr)[:160])
        # THE REF IS THE CLAIM, so the branch is on the remote before the
        # commit -- which is what `campaign-claim take` does, server-side,
        # before a worker ever checks it out. The hook used to push on the
        # branch NAME alone; it now asks whether the branch is a claim, and a
        # name with no ref behind it is not one.
        git(r.root, "switch", "-qc", "demo/1-x")
        git(r.root, "push", "-q", "origin", "demo/1-x")
        (r.root / "spec" / "b.als").write_text("sig B {}\n")
        git(r.root, "add", "spec/b.als")
        c = r.commit()
        check("a campaign branch is pushed by the hook",
              "pushed demo/1-x" in c.stdout + c.stderr,
              (c.stdout + c.stderr)[:200])
        ls = subprocess.run(["git", "ls-remote", "--heads", str(r.remote)],
                            capture_output=True, text=True)
        check("...and the remote really has it", "demo/1-x" in ls.stdout,
              ls.stdout[:160])
        remote_sha = subprocess.run(["git", "ls-remote", "--heads",
                                     str(r.remote), "demo/1-x"],
                                    capture_output=True, text=True).stdout.split()[0]
        # A rejected push. The commit is durable nowhere, and silence here is
        # exactly the loss push-early exists to prevent.
        git(r.root, "commit", "-q", "--amend", "-m", "amended", "--no-verify")
        c = r.commit_amend_push()
        check("a rejected push is reported, and nothing is forced",
              "could NOT push" in c and "non-fast-forward" in c, c[:200])
        # The sha, not the ref name: the name survives a force-push, so
        # asserting on it passed with the remote rewritten and the case pinned
        # nothing it was named for.
        after = subprocess.run(["git", "ls-remote", "--heads", str(r.remote),
                                "demo/1-x"], capture_output=True,
                               text=True).stdout.split()[0]
        check("...and the remote still holds the exact commit it had",
              after == remote_sha, f"{remote_sha} -> {after}")

        # A branch SHAPED like a claim with no ref behind it. The old glob
        # pushed it -- it matched `campaign-*/*` and asked nothing else -- so
        # any branch a person happened to name that way was published by a
        # commit. Nothing here is a claim, so nothing is pushed.
        git(r.root, "switch", "-qc", "demo/2-unclaimed")
        (r.root / "spec" / "d.als").write_text("sig D {}\n")
        git(r.root, "add", "spec/d.als")
        c = r.commit()
        ls2 = subprocess.run(["git", "ls-remote", "--heads", str(r.remote),
                              "demo/2-unclaimed"],
                             capture_output=True, text=True)
        check("a claim-SHAPED branch with no ref behind it is not pushed",
              not ls2.stdout.strip()
              and "pushed demo/2-unclaimed" not in c.stdout + c.stderr,
              f"ls-remote={ls2.stdout!r}; {(c.stdout + c.stderr)[:200]}")
        git(r.root, "switch", "-q", "demo/1-x")

        # mktemp failing: TMPDIR pointed at nothing does not make mktemp fail,
        # so a failing mktemp shimmed ahead of it on PATH is what actually
        # reaches the branch.
        shim = Path(d) / "shim"
        shim.mkdir()
        (shim / "mktemp").write_text("#!/bin/sh\nexit 1\n")
        (shim / "mktemp").chmod(0o755)
        p = subprocess.run([str(r.root / "scripts" / "push-campaign-branch.sh")],
                           cwd=r.root, capture_output=True, text=True,
                           env=dict(os.environ,
                                    PATH=f"{shim}:{os.environ['PATH']}"))
        check("mktemp failing says the commit was not pushed",
              "mktemp failed" in p.stdout + p.stderr, (p.stdout + p.stderr)[:160])

        (r.root / "scripts" / "push-campaign-branch.sh").chmod(0o644)
        (r.root / "spec" / "c.als").write_text("sig C {}\n")
        git(r.root, "add", "spec/c.als")
        c = r.commit()
        check("a missing push script says the commit was not pushed",
              "NOT pushed" in c.stdout + c.stderr, (c.stdout + c.stderr)[:200])

    # 10. The harness half. A git hook and a settings.json entry fail in
    # opposite directions -- git refuses loudly, a hook nobody registered is
    # silent -- so the registration gets its own cases.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        out = installer(r.root)
        settings = json.loads((r.root.parent / "home" / ".claude"
                               / "settings.json").read_text())
        def commands(event):
            return [h["command"]
                    for e in settings.get("hooks", {}).get(event, [])
                    for h in e["hooks"]]
        check("the guard is registered on PreToolUse",
              any("check-campaign-claim.py" in c for c in commands("PreToolUse")),
              str(settings)[:200])
        # Nothing on PostToolUse: the --released half went with #176's
        # records, and a guard left there would run and enforce nothing.
        check("...and nothing of it is registered on PostToolUse",
              not any("check-campaign-claim.py" in c for c in commands("PostToolUse")),
              str(commands("PostToolUse"))[:200])
        check("...and the installer says where it wrote them",
              "settings.json PreToolUse" in out.stdout, out.stdout[:200])
        # THE BRIEF HOOK, on both its events and on neither of the guard's.
        # It lives under `.claude/skills/`, so the registered command is the
        # case that catches an installer that still assumes `scripts/`: a
        # prefixed path would name a file that is not there, and the harness
        # would run a hook that cannot start.
        BRIEF = ".claude/skills/assuming-role/scripts/campaign-role-brief.py"
        for event in ("SessionStart", "UserPromptSubmit"):
            check(f"the brief hook is registered on {event} by its whole path",
                  any(BRIEF in c for c in commands(event)),
                  str(commands(event))[:200])
        check("...and the brief hook is not on the guard's event",
              not any("campaign-role-brief.py" in c
                      for c in commands("PreToolUse")),
              str(commands("PreToolUse"))[:200])
        # A matcher on SessionStart matches nothing, so an entry carrying one
        # would register a hook that never fires.
        check("...and its entries carry no matcher",
              all("matcher" not in e
                  for ev in ("SessionStart", "UserPromptSubmit")
                  for e in settings.get("hooks", {}).get(ev, [])),
              str(settings.get("hooks", {}).get("SessionStart"))[:200])
        # The pane stamp every role and liveness reading keys on. Its readers
        # are all here, so a registration that missed an event would leave a
        # pane unstamped exactly when that event was its only chance.
        LINK = ".claude/skills/herdr/scripts/herdr-session-link.py"
        for event in ("SessionStart", "UserPromptSubmit"):
            check(f"the session-link hook is registered on {event} by its "
                  f"whole path",
                  any(LINK in c for c in commands(event)),
                  str(commands(event))[:200])
        # The registered command must fail CLOSED when its script is gone. Run
        # each one the way the harness does -- through a shell -- after
        # deleting the guard: a bare path exits 127, which the harness reads as
        # not-a-refusal, so a moved checkout would silently un-enforce the
        # rule. Exit 2 is the one code that refuses. Asserted on the exit the
        # harness reads, not on the text of the command.
        (r.root / "scripts" / "check-campaign-claim.py").unlink()
        for event in ("PreToolUse", "PostToolUse"):
            for cmd in commands(event):
                if "check-campaign-claim.py" not in cmd:
                    continue
                run = subprocess.run(["sh", "-c", cmd], input="{}",
                                     capture_output=True, text=True)
                check(f"{event}: a missing guard refuses (exit 2) instead of "
                      f"failing open",
                      run.returncode == 2,
                      f"exit {run.returncode} from `{cmd}`; "
                      f"{run.stderr.strip()[:120]}")

        # Idempotent: a second clone must not leave the guard running twice,
        # and an entry an earlier install left on the retired event is swept.
        shutil.copy(SCRIPTS / "check-campaign-claim.py",
                    r.root / "scripts" / "check-campaign-claim.py")
        settings["hooks"].setdefault("PostToolUse", []).append(
            {"matcher": "Bash", "hooks": [{"type": "command",
             "command": 'python3 "/old/check-campaign-claim.py" --released'}]})
        # An entry is a group, and a person's own hook may share one with an
        # earlier registration of ours -- as a hand-written `echo` shared one
        # with the old herdr-session-link.py. Only our command may go.
        MINE = "echo 'a person wrote this'"
        settings["hooks"].setdefault("UserPromptSubmit", []).append(
            {"hooks": [{"type": "command", "command": MINE},
                       {"type": "command", "command":
                        '/usr/bin/python3 "$HOME/.claude/hooks/herdr-session-link.py"'}]})
        (r.root.parent / "home" / ".claude" / "settings.json").write_text(
            json.dumps(settings))
        out = installer(r.root)
        settings = json.loads((r.root.parent / "home" / ".claude"
                               / "settings.json").read_text())
        check("a retired PostToolUse registration is removed on re-install, and "
              "the installer says so",
              not any("check-campaign-claim.py" in c for c in commands("PostToolUse"))
              and "removed:" in out.stdout and "PostToolUse" in out.stdout,
              out.stdout[:300] + str(commands("PostToolUse"))[:200])
        settings = json.loads((r.root.parent / "home" / ".claude"
                               / "settings.json").read_text())
        check("re-running replaces the entry rather than stacking one",
              len([c for c in commands("PreToolUse")
                   if "check-campaign-claim.py" in c]) == 1,
              str(commands("PreToolUse"))[:200])
        check("a person's hook sharing an entry with an earlier registration "
              "survives the re-install",
              MINE in commands("UserPromptSubmit"),
              str(commands("UserPromptSubmit"))[:300])
        linked = [c for c in commands("UserPromptSubmit")
                  if "herdr-session-link.py" in c]
        check("...while the earlier registration beside it is replaced",
              len(linked) == 1 and linked[0].endswith(f'/{LINK}"'),
              str(commands("UserPromptSubmit"))[:300])

    # 11. Registering a command that cannot run reads to every session like a
    # rule being enforced, so it refuses instead.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        (r.root / "scripts" / "check-campaign-claim.py").chmod(0o644)
        out = installer(r.root)
        check("a guard that is not executable refuses the install",
              out.returncode != 0 and "not executable" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")

    # 12. This writes INTO a person's settings. Neither an absent file nor an
    # unparseable one may be answered by writing a fresh one over it.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        home = r.root.parent / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "settings.json").write_text("{ not json")
        out = installer(r.root)
        check("settings.json that will not parse refuses rather than overwrites",
              out.returncode != 0 and "would not read" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")
        check("...and the file is left exactly as it was",
              (home / ".claude" / "settings.json").read_text() == "{ not json")

    # The absent case is its own branch and not the unparseable one: creating a
    # settings.json would be this script deciding a person's harness config for
    # them, on a machine where the absence may be deliberate.
    with tempfile.TemporaryDirectory() as d:
        r = Repo(d)
        empty = r.root.parent / "nohome"
        empty.mkdir()
        out = subprocess.run([str(r.root / "scripts" / "install-hooks.sh")],
                             cwd=r.root, capture_output=True, text=True,
                             env=dict(os.environ, HOME=str(empty)))
        check("an absent settings.json refuses rather than creating one",
              out.returncode != 0 and "does not exist" in out.stderr,
              f"exit {out.returncode}; {(out.stdout + out.stderr)[:200]}")
        check("...and none was created",
              not (empty / ".claude" / "settings.json").exists())

    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
