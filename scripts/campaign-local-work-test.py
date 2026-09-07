#!/usr/bin/env python3
"""Prove campaign-local-work names what it cannot account for under `runtime/`.

The script's other readings run git against real checkouts and are covered by
running it; this is the one calculation in it, and it had no suite at all --
which is how its `handover/` reading was deleted without anything going red.

No case may reach the network or a real campaign directory.

Usage: scripts/campaign-local-work-test.py
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import pathlib
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "campaign-local-work.py"

# THIS MACHINE'S GLOBAL GITIGNORE HOLDS `*.local.md` (#187, 2026-09-05), so
# `CLAUDE.local.md` is ignored here whether or not the fixture excludes it --
# and a case about what `.git/info/exclude` does could not tell the two apart.
# Every git command below runs with the global and system config emptied, so
# what is measured is the fixture and not the machine.
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull)
RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


class Rep:
    """The reporter's methods this reads, recorded rather than printed."""

    def __init__(self):
        self.lines = []
        self.rows = []

    def report(self, line):
        self.lines.append(line)

    def unread(self, line):
        self.lines.append(line)

    def add(self, repo, kind, ident, check, clears, note="", counted=True):
        self.rows.append((repo, kind, ident))


def a_clone(root, *files):
    """A member checkout under `<campaign>/repos/`, with `files` written into it
    and excluded in its own `.git/info/exclude` -- the shape a delegate launch
    leaves behind."""
    clone = pathlib.Path(root) / "repos" / "acme"
    clone.mkdir(parents=True)
    def g(*a):
        subprocess.run(["git", "-C", str(clone), *a], check=True,
                       capture_output=True, env=GIT_ENV)
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    (clone / "tracked").write_text("x")
    g("add", "tracked")
    g("commit", "-qm", "c")
    exclude = clone / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    for name in files:
        (clone / name).write_text("body\n")
        with exclude.open("a") as fh:
            fh.write(name + "\n")
    return clone


def main():
    spec = importlib.util.spec_from_loader(
        "clw", importlib.machinery.SourceFileLoader("clw", str(SCRIPT)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    # WHICH BRANCH PREFIXES ARE SWEPT, and why the reading narrowed when it
    # did. A slug that did not read means a `<slug>/` branch is invisible below,
    # so the two ways it can fail are kept apart: exit 1 is the tracker having
    # READ the campaign issue and found no `campaign:` label, and any other exit
    # is a reading that did not happen. One sentence for both sends the reader
    # to the wrong fix.
    with tempfile.TemporaryDirectory() as d:
        shim = Path(d) / "scripts"
        shim.mkdir()
        (shim / "campaign-local-work.py").write_text(SCRIPT.read_text())
        spec2 = importlib.util.spec_from_loader(
            "clw2", importlib.machinery.SourceFileLoader(
                "clw2", str(shim / "campaign-local-work.py")))
        m2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(m2)
        # ONE PREFIX SINCE #237, and an unreadable slug leaves NONE -- where it
        # used to fall back to `campaign-<N>/`. The empty list is the point:
        # the sweep read nothing, and says so, rather than reporting a machine
        # holding no work.
        for body, want, prefixes in (
                ("print('demo')\n", None, ["demo/"]),
                ("print('none')\nraise SystemExit(1)\n",
                 "carries no `campaign:` label", []),
                ("import sys\nprint('boom', file=sys.stderr)\n"
                 "raise SystemExit(2)\n",
                 "without a verdict", [])):
            (shim / "campaign-tracker.py").write_text(
                "#!/usr/bin/env python3\n" + body)
            rep = Rep()
            got = m2.campaign_prefixes("9", rep)
            check(f"campaign_prefixes sweeps {prefixes} when the tracker "
                  f"{'answers' if want is None else repr(want)}",
                  got == prefixes, f"{got} {rep.lines}")
            if want is None:
                check("...and a slug that read reports nothing",
                      not rep.lines, str(rep.lines))
            else:
                check(f"...and says {want!r} when it could not use one",
                      any(want in l for l in rep.lines), str(rep.lines))

        # THE CONSEQUENCE, not just the return value. An empty prefix list fed
        # through reached `git for-each-ref` with NO pattern and
        # `read_worktrees`'s `if prefix and` guard, so a slug that would not
        # read widened the sweep to every branch and worktree while the note
        # said no claim would appear. The case above pins the list; this pins
        # that nothing is read off it.
        (shim / "campaign-tracker.py").write_text(
            "#!/usr/bin/env python3\nprint('none')\nraise SystemExit(1)\n")
        seen = []
        m2.read_branches = lambda *a, **k: seen.append("branches")
        m2.read_worktrees = lambda *a, **k: seen.append("worktrees")
        m2.slug = lambda b: "base"
        m2.default_branch = lambda *a, **k: "main"
        m2.git = lambda *a, **k: ""
        rep = Rep()
        m2.read_base(str(shim.parent), "9", rep)
        check("with no prefix, neither the branches nor the worktrees are read",
              seen == [], f"read {seen}; {rep.lines}")

    with tempfile.TemporaryDirectory() as d:
        runtime = Path(d) / "runtime"
        runtime.mkdir()

        # What the scaffold ships and step 4 writes. A REPORT here is a false
        # one on every fresh campaign, which is how a real finding stops being
        # read.
        (runtime / ".gitkeep").touch()
        (runtime / "repos").write_text("owner/repo\n")
        (runtime / "campaign-issue-body-derived.md").write_text("body\n")
        rep = Rep()
        m.read_runtime(d, rep)
        check("a freshly scaffolded runtime/ reports nothing", not rep.lines)

        # ...and anything else is NAMED. Generic on purpose: this used to name
        # `handover/` specifically, so retiring that reading left the files on
        # disk unreported one step before a close destroys them.
        (runtime / "claims").mkdir()
        rep = Rep()
        m.read_runtime(d, rep)
        check("an entry the script cannot name is reported",
              len(rep.lines) == 1 and "claims" in rep.lines[0])
        check("...and the known entries are not named beside it",
              "repos" not in rep.lines[0]
              and ".gitkeep" not in rep.lines[0])

        # A campaign directory with no runtime/ at all is not a failure: the
        # reading simply has nothing to say.
        rep = Rep()
        m.read_runtime(str(Path(d) / "nothing-here"), rep)
        check("a campaign directory with no runtime/ reports nothing",
              not rep.lines)

    # THE DELEGATE'S PRINCIPLES ARE NOT LOCAL-ONLY WORK. `CLAUDE.local.md` is
    # written into each clone and excluded in that clone's `.git/info/exclude`,
    # and `git status --porcelain --ignored=matching` reports an info/exclude'd
    # file exactly as it reports a build directory -- probed 2026-09-04, it
    # comes back `!! CLAUDE.local.md`. Counting it made every campaign that ever
    # launched a delegate read NOT clear for ever: a close gate that cannot pass.
    #
    # `read_checkouts` and not the filter alone: the skip is a branch inside
    # that loop, and a case that re-implemented the condition would pass with
    # the branch deleted.
    with tempfile.TemporaryDirectory() as d:
        clone = a_clone(d, "CLAUDE.local.md", "build-output")
        rep = Rep()
        m.read_checkouts(d, rep)
        kinds = {(k, i) for _, k, i in rep.rows}
        check("the campaign's principles in a clone are not counted as work",
              ("ignored", "CLAUDE.local.md") not in kinds, str(kinds))
        # ...and the exemption is by name: every OTHER ignored file still counts,
        # or this would be a hole rather than a carve-out.
        check("...while any other ignored file still counts",
              ("ignored", "build-output") in kinds, str(kinds))

    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
