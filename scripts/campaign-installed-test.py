#!/usr/bin/env python3
"""Prove campaign-installed reads an install for what it is, names the
merge-not-reached case, and reaches one.

Every fixture is a real git repository under a temporary directory: a bare
origin at `<tmp>/example/thing.git` so the URL's last two components name the
repository, an install cloned from it, and a second clone that plays the merge
by pushing to origin. The base row is exercised through `list` alone, because
`check` on it fetches the real base's origin, which a suite does not do.

THE NAMED FAILING CASE is "marker present, step skipped": a merge has landed
on origin and nobody ran `reach`, so the install reads `behind 1` and the
verdict is NOT clear. Every other refusal is asserted on the sentence it
prints, never on the exit status, which they all share.

Usage: scripts/campaign-installed-test.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
INSTALLED = HERE / "campaign-installed.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


def sh(*args, cwd=None):
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def git(path, *args):
    rc, out, err = sh("git", "-C", path, *args)
    assert rc == 0, f"git {' '.join(args)} in {path}: {err}"
    return out.strip()


def run(*args):
    """(exit status, stdout, stderr) for one invocation."""
    return sh(sys.executable, str(INSTALLED), *args)


def commit(path, name):
    Path(path, name).write_text(name + "\n")
    git(path, "add", name)
    git(path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
        "-m", name)
    return git(path, "rev-parse", "HEAD")


def body(tmp, *entries):
    p = Path(tmp, "body.md")
    p.write_text("## Repos\n\n" + "".join(f"- {e}\n" for e in entries)
                 + "\n## Intent\n- x\n")
    return str(p)


def fixture(tmp):
    """origin, install, work -- install and work both clones of origin at one
    commit on main."""
    origin = Path(tmp, "example", "thing.git")
    origin.parent.mkdir(parents=True)
    git(tmp, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = Path(tmp, "seed")
    git(tmp, "clone", "-q", str(origin), str(seed))
    git(str(seed), "checkout", "-q", "-b", "main")
    commit(str(seed), "first")
    git(str(seed), "push", "-q", "origin", "main")
    git(str(origin), "symbolic-ref", "HEAD", "refs/heads/main")
    install, work = Path(tmp, "install"), Path(tmp, "work")
    git(tmp, "clone", "-q", str(origin), str(install))
    git(tmp, "clone", "-q", str(origin), str(work))
    return str(origin), str(install), str(work)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        origin, install, work = fixture(tmp)
        marker = f"example/thing (installed: {install}, apply: touch applied.txt)"

        # ---- list
        rc, out, err = run("list", body(tmp, marker, "other/plain"))
        lines = out.splitlines()
        check("list puts the base first, at the base root, with install-hooks as apply",
              rc == 0 and lines and lines[0].startswith("kalaluthien/campaign-base  ")
              and lines[0].endswith("  scripts/install-hooks.sh"), out + err)
        check("list shows the marker row and drops the unmarked one",
              f"example/thing  {install}  touch applied.txt" in lines
              and not any(l.startswith("other/plain") for l in lines), out)
        check("list says how many rows and where it read them",
              "2 installed row(s)" in out and "body.md" in out, out)
        rc, out, err = run("list", body(tmp, "example/thing (installed: ~/x)"))
        check("a `~` path is expanded and a missing apply prints as `-`",
              rc == 0 and f"example/thing  {os.path.expanduser('~/x')}  -" in out, out + err)
        rc, out, err = run("list", body(tmp, "example/thing (apply: make)"))
        check("a body campaign-repos refuses is refused in its words",
              rc == 1 and "campaign-repos refused" in err
              and "`apply` with no `installed`" in err, err)
        rc, out, err = run("list", str(Path(tmp, "absent.md")))
        check("an unreadable body is named, not read as empty",
              rc == 1 and "cannot read" in err, err)

        # ---- check
        rc, out, err = run("check", body(tmp, marker), "example/thing")
        check("an install at origin's default branch reads current and clear",
              rc == 0 and "-- current" in out and "1 row(s) read, 0 behind, 0 unread -- clear" in out,
              out + err)
        check("check prints what it read: HEAD and origin's tip",
              "HEAD " in out and "origin/main " in out, out)

        merged = commit(work, "second")
        git(work, "push", "-q", "origin", "main")
        rc, out, err = run("check", body(tmp, marker), "example/thing")
        check("MARKER PRESENT, STEP SKIPPED: a merge nobody reached reads behind 1, NOT clear",
              rc == 1 and "-- behind 1" in out and "1 behind, 0 unread -- NOT clear" in out,
              out + err)

        rc, out, err = run("check", body(tmp, f"example/thing (installed: {tmp}/nowhere)"),
                           "example/thing")
        check("an absent install is unread and NOT clear, never current",
              rc == 1 and "-- absent" in out and "1 unread -- NOT clear" in out, out + err)
        plain = Path(tmp, "plain"); plain.mkdir()
        rc, out, err = run("check", body(tmp, f"example/thing (installed: {plain})"),
                           "example/thing")
        check("a directory that is not a checkout is named as such",
              rc == 1 and "-- not a checkout" in out, out + err)
        rc, out, err = run("check", body(tmp, f"other/name (installed: {install})"),
                           "other/name")
        check("an install of another repository says which",
              rc == 1 and "-- a checkout of example/thing" in out, out + err)
        rc, out, err = run("check", body(tmp, marker), "nobody/here")
        check("a filter naming no installed row is refused, not read as clear",
              rc == 1 and "has no installed row" in err and "clear" not in out, out + err)
        rc, out, err = run("check", body(tmp, marker), "exampl-thing")
        check("a filter that is not an owner/repo is refused, nothing compared",
              rc == 1 and "is not an owner/repo" in err, out + err)
        sub = Path(install, "sub"); sub.mkdir(exist_ok=True)
        rc, out, err = run("check", body(tmp, f"example/thing (installed: {sub})"),
                           "example/thing")
        check("a path inside a checkout is refused as inside it, naming the root",
              rc == 1 and f"-- inside the checkout {os.path.realpath(install)}" in out,
              out + err)

        # ---- reach
        rc, out, err = run("reach", body(tmp, marker), "other/plain", merged)
        check("reach on a repository with no row is nothing to reach, exit 0",
              rc == 0 and "nothing to reach" in out, out + err)
        rc, out, err = run("reach", body(tmp, marker), "exampl-thing", merged)
        check("reach on a word that is not an owner/repo is refused, as check refuses it",
              rc == 1 and "is not an owner/repo" in err and "nothing to reach" not in out,
              out + err)
        unmerged = commit(work, "third-unpushed")
        rc, out, err = run("reach", body(tmp, marker), "example/thing", unmerged)
        check("a sha not on origin's default branch is refused: merge first",
              rc == 1 and "is not on origin/main" in err and "merge first" in err, err)
        git(install, "checkout", "-q", "-b", "elsewhere")
        rc, out, err = run("reach", body(tmp, marker), "example/thing", merged)
        check("an install on another branch is refused, and the branch is named",
              rc == 1 and "is on elsewhere, not main" in err, err)
        git(install, "checkout", "-q", "main")

        rc, out, err = run("reach", body(tmp, marker), "example/thing", merged)
        check("reach fast-forwards the install to the merged sha and runs apply",
              rc == 0 and git(install, "rev-parse", "HEAD") == merged
              and Path(install, "applied.txt").exists()
              and f"reached example/thing at {install}: HEAD {merged} contains {merged}; apply `touch applied.txt` ran" in out,
              out + err)
        rc, out, err = run("check", body(tmp, marker), "example/thing")
        check("...and check reads current afterwards",
              rc == 0 and "-- current" in out and "-- clear" in out, out + err)

        git(work, "push", "-q", "origin", "main")
        rc, out, err = run("reach", body(tmp, f"example/thing (installed: {install}, apply: false)"),
                           "example/thing", unmerged)
        check("a failing apply is reported with its exit status after the fast-forward",
              rc == 1 and "apply `false` exited 1" in err
              and git(install, "rev-parse", "HEAD") == unmerged, err)
        rc, out, err = run("check", body(tmp, marker), "example/thing")
        check("APPLY FAILED IS DURABLE: check reads it after the fast-forward, NOT clear",
              rc == 1 and "-- apply failed" in out and "apply `false` exited 1" in out
              and "1 unread -- NOT clear" in out, out + err)
        rc, out, err = run("reach", body(tmp, marker), "example/thing", unmerged)
        check("a reach whose apply runs through clears the mark",
              rc == 0 and "apply `touch applied.txt` ran" in out
              and run("check", body(tmp, marker), "example/thing")[0] == 0, out + err)

        local = commit(install, "local-only")
        fourth = commit(work, "fourth")
        git(work, "push", "-q", "origin", "main")
        rc, out, err = run("reach", body(tmp, marker), "example/thing", fourth)
        check("a diverged install cannot be fast-forwarded, and git's words are quoted",
              rc == 1 and "could not fast-forward" in err
              and git(install, "rev-parse", "HEAD") == local, err)

        rc, out, err = run("reach", body(tmp, marker), "example/thing")
        check("reach without a sha prints the usage", rc == 2 and "reach <body>" in err, err)
        rc, out, err = run("nonsense", body(tmp, marker))
        check("an unknown subcommand prints the usage", rc == 2 and "check <body>" in err, err)

    if not RAN:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in FAILED:
        print(f"FAIL  {f}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
