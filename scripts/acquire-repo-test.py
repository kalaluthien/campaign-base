#!/usr/bin/env python3
"""Prove `acquire-repo.sh` leaves a clone with what a delegate needs: the principles, and a commit gate.

Two defects, one shape. #187 question 5: #176 wrote the principles channel down
as prose and no command wrote the file, so a delegate launched by the documented
procedure got nothing and nothing recorded it. #190: `install_commit_guard` ran
a clone's own `scripts/install-hooks.sh` only when the clone shipped one, and a
member repository ships none, so every member clone got the machine-wide
no-main-commits guard and NO claim gate -- while check-campaign-claim.py went on
calling that clone campaign work whose shell writes "land at the commit".
#214: the two decisions about an existing pre-commit -- may this one be
overwritten, and did the repository's own installer leave one chaining the
guard -- were both `grep -q 'no-main-commits'` over the whole file, so a hook
naming the guard in a COMMENT read as one calling it, and the first of those
two decisions is the destructive one.

A case made of strings would have caught neither, because both defects were the
absence of a command. So every case here runs SHIPPED code against a real git
checkout and reads the bytes back, and the gate cases go further and run a real
`git commit` through the hook that was installed.

No case reaches the network. The principles cases make their clone with `git
init`; the gate cases clone from a LOCAL BARE REPOSITORY at
`<dir>/acme/widget.git`, which `remote_slug` reads as `acme/widget` because it
takes the last two path segments and strips `.git` -- so a local bare repo is a
member repository as far as `acquire` is concerned, and the whole entry point
runs offline.

Usage: scripts/acquire-repo-test.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# THIS MACHINE'S GLOBAL GITIGNORE HOLDS `*.local.md`, so `CLAUDE.local.md` is
# ignored here whether or not the script writes anything -- and the first shape
# of this suite passed its "the clone stays clean" case on that ambient rule,
# with the per-clone exclude deleted. Every git command below runs with the
# global and system config emptied, so what is measured is the exclude the
# script writes and nothing the machine happens to carry.
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull)

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SCRIPT = (BASE / ".claude" / "skills" / "opening-campaign" / "scripts"
          / "acquire-repo.sh")
# What the installed hook must name. Derived from this file's own location, the
# same way `install_commit_guard` derives it from the script's -- so a case
# asserting on it fails when the two stop agreeing, rather than when a copy kept
# here goes stale.
GATE = BASE / "scripts" / "check-commit-claim.py"

# READ OUT OF THE SCRIPT, not spelled here. A fixture carrying a marker that is
# no longer the one `is_guard_shim` looks for would still be "refused", for the
# wrong reason, and every near-miss case below would pass while pinning nothing.
_M = [l for l in SCRIPT.read_text().splitlines() if l.startswith("SHIM_MARKER=")]
SHIM_MARKER = _M[0].split("=", 1)[1].strip("'") if len(_M) == 1 else None

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


def install_principles(dest):
    """Run the shipped function, extracted from the shipped file.

    Extracted rather than copied: a fixture holding its own copy would pass
    while the real one was deleted, which is the exact defect this suite is
    about. `acquire-repo.sh` runs `acquire` at import, so the function is
    sliced out instead of the file being sourced."""
    src = SCRIPT.read_text()
    body = src[src.index("install_principles() {"):
               src.index("install_commit_guard() {")]
    harness = ('log() { printf "%s\\n" "$*"; }\n'
               'die() { printf "die: %s\\n" "$*" >&2; exit 1; }\n'
               + body + f'\ninstall_principles "{dest}"\n')
    return subprocess.run(["bash", "-c", harness], capture_output=True,
                          text=True, env=GIT_ENV)


def a_campaign(d, principles=True):
    """A campaign directory with a clone under `repos/`, the shape a launch
    finds. Returns the clone."""
    camp = Path(d) / "demo-260905"
    clone = camp / "repos" / "acme"
    clone.mkdir(parents=True)
    if principles:
        (camp / "AGENTS.md").write_text("# Campaign principles\nBe careful.\n")
    def g(*a):
        subprocess.run(["git", "-C", str(clone), *a], check=True,
                       capture_output=True, env=GIT_ENV)
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    (clone / "tracked").write_text("x")
    g("add", "tracked")
    g("commit", "-qm", "c")
    return clone


def text_of(path):
    """The file's bytes, or None when it is not there.

    A bare `read_text()` raises, and an exception ABORTS THE SUITE: the first
    mutation run against this file deleted the write and every case after it
    went unreported, so the run looked like a crash rather than like a named
    failure. A case has to be able to say "the file is missing"."""
    try:
        return path.read_text()
    except OSError:
        return None


def status(clone, *flags):
    r = subprocess.run(["git", "-C", str(clone), "status", "--porcelain",
                        *flags], capture_output=True, text=True, env=GIT_ENV)
    return r.stdout



# ------------------------------------------------------------ the gate fixture
#
# Everything below builds the shape `check-commit-claim.py` actually reads, so
# the refusals and the admissions come from the shipped gate and not from a
# stand-in: a base root marked by `scripts/campaign-claim.py`, a
# campaign directory under it, and a clone of a member
# repository under that directory's `repos/`.


def a_base_with_campaign(d):
    """A base root and a campaign directory under it. Only the MARKER files are
    built -- `classify` reads the tree's shape, and nothing here runs the base's
    scripts, so a stub is the honest fixture for the marker and the real script
    is what runs against it."""
    base = Path(d) / "base"
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "campaign-claim.py").write_text("# the base marker\n")
    camp = base / "demo-260905"
    camp.mkdir()
    # THE MARKER IS WHAT MAKES `demo` A CAMPAIGN HERE, and since #237 it is the
    # only thing that can: the retired `campaign-<N>/` branch carried its
    # campaign in the name and needed no directory behind it, so a clone under
    # this base was read as claimed with no marker anywhere.
    (camp / ".campaign").write_text("1 demo\n")
    return base, camp


def a_member_repo(d, camp, slug="acme/widget"):
    """A bare repository and a clone of it under the campaign, offline.

    The bare repo sits at `<d>/remotes/acme/widget.git`, which `remote_slug`
    reads as `acme/widget` -- last two path segments, `.git` stripped -- so
    `acquire` treats it as the member repository `acme/widget` and takes its
    already-present branch, which needs no network. Two branches are pushed:
    `main`, which is not a claim, and `demo/190-fixture`, which is one,
    because `ref_exists` reads the clone's `refs/remotes/origin/` copy first."""
    owner, name = slug.split("/")
    remote = Path(d) / "remotes" / owner / f"{name}.git"
    remote.parent.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(list(a), check=True, capture_output=True,
                                    env=GIT_ENV)
    run("git", "init", "-q", "--bare", "-b", "main", str(remote))
    seed = Path(d) / f"seed-{name}"
    run("git", "clone", "-q", str(remote), str(seed))
    def g(*a):
        run("git", "-C", str(seed), *a)
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    (seed / "tracked").write_text("x")
    g("add", "tracked")
    g("commit", "-qm", "init")
    g("push", "-q", "origin", "HEAD:refs/heads/main")
    g("push", "-q", "origin", "HEAD:refs/heads/demo/190-fixture")
    dest = camp / "repos" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", "-q", str(remote), str(dest))
    run("git", "-C", str(dest), "config", "user.email", "t@example.invalid")
    run("git", "-C", str(dest), "config", "user.name", "t")
    return slug, dest


def a_home(d, name="home", refuses=False):
    """A HOME holding the machine-wide guard where acquire-repo looks for it.

    It says its own name, so the two halves of the installed hook are told
    apart: a commit that reaches the gate has run the guard first, and a
    refusal carrying only one of the two words names which half spoke.

    `refuses=True` is the real guard's answer on `main`, and it is the only way
    to ask whether the hook HONOURS that answer rather than merely running it.
    """
    home = Path(d) / name
    g = home / ".claude" / "git-hooks" / "no-main-commits"
    g.parent.mkdir(parents=True)
    g.write_text("#!/bin/sh\necho 'NO-MAIN-COMMITS RAN' >&2\n"
                 + ("echo 'GUARD REFUSED' >&2\nexit 1\n" if refuses
                    else "exit 0\n"))
    g.chmod(0o755)
    return home


def run_acquire(slug, dest, home, script=SCRIPT):
    """The whole shipped entry point, run offline. Not an extracted function:
    what #190 broke was a branch of `install_commit_guard`, and what a caller
    gets is whatever `acquire` calls, so the call site is exercised here rather
    than asserted about."""
    return subprocess.run([str(script), slug, str(dest)], capture_output=True,
                          text=True, env=dict(GIT_ENV, HOME=str(home)))


def a_base_copy(d, gate=True, name="otherbase"):
    """A second base tree holding its own copy of acquire-repo.sh, and its
    scripts/ with or without the gate. `install_commit_guard` resolves the base
    from BASH_SOURCE, so running THIS copy is how the missing-gate branch is
    reached without touching the real checkout."""
    root = Path(d) / name
    (root / ".claude" / "skills" / "opening-campaign" / "scripts").mkdir(parents=True)
    copy = (root / ".claude" / "skills" / "opening-campaign" / "scripts"
            / "acquire-repo.sh")
    shutil.copy(SCRIPT, copy)
    (root / "scripts").mkdir()
    if gate:
        shutil.copy(GATE, root / "scripts" / GATE.name)
        # The gate imports the claim reading from beside itself: one script owns
        # it, and a copy without its neighbour would refuse for the wrong reason.
        shutil.copy(HERE / "check-campaign-claim.py",
                    root / "scripts" / "check-campaign-claim.py")
    return root, copy


def commit_in(clone, home, name, text):
    (clone / name).write_text(text)
    subprocess.run(["git", "-C", str(clone), "add", name], check=True,
                   capture_output=True, env=GIT_ENV)
    r = subprocess.run(["git", "-C", str(clone), "commit", "-m", "x"],
                       capture_output=True, text=True,
                       env=dict(GIT_ENV, HOME=str(home)))
    return r, r.stdout + r.stderr


def on_branch(clone, branch, track=False):
    args = (["switch", "-q", "--track", f"origin/{branch}"] if track
            else ["switch", "-q", "-c", branch])
    subprocess.run(["git", "-C", str(clone), *args], check=True,
                   capture_output=True, env=GIT_ENV)


def main():
    with tempfile.TemporaryDirectory() as d:
        clone = a_campaign(d)
        r = install_principles(clone)
        out = r.stdout + r.stderr
        check("the campaign's AGENTS.md lands as CLAUDE.local.md in the clone",
              (clone / "CLAUDE.local.md").exists(), out[:200])
        check("...with the campaign's own bytes, not a stand-in",
              "Be careful." in (text_of(clone / "CLAUDE.local.md") or ""))
        # THE HALF THAT KEEPS IT OUT OF THE MEMBER REPOSITORY'S HISTORY. Asserted
        # on `git status` and not on the exclude file's text: a line in
        # info/exclude that git does not honour reads identically.
        check("...and the clone is clean, so it is not the delegate's to commit",
              status(clone) == "", repr(status(clone)))
        check("...while `--ignored=matching` still names it, which is what "
              "campaign-local-work reads",
              "CLAUDE.local.md" in status(clone, "--ignored=matching"),
              repr(status(clone, "--ignored=matching")))
        check("...and it says what it wrote and where",
              "principles:" in out and "CLAUDE.local.md" in out, out[:200])

        # Idempotent: a second acquire over the same clone converges, and does
        # not stack a second exclude line.
        install_principles(clone)
        exclude = text_of(clone / ".git" / "info" / "exclude") or ""
        check("a second run does not stack a second exclude line",
              exclude.count("CLAUDE.local.md") == 1, repr(exclude[-80:]))

    # A campaign that adds no principles is a real answer, and it is SAID: a
    # silent skip here is indistinguishable from the defect this closes.
    with tempfile.TemporaryDirectory() as d:
        clone = a_campaign(d, principles=False)
        r = install_principles(clone)
        out = r.stdout + r.stderr
        check("a campaign with no AGENTS.md is reported, not skipped silently",
              "adds no principles" in out, out[:200])
        check("...and nothing is written",
              not (clone / "CLAUDE.local.md").exists())


    # ---- #190. A MEMBER CLONE GETS THE CLAIM GATE, and it is the gate that
    # runs. Every case here is on the deployed path: the shipped `acquire`, a
    # real clone, and a real `git commit` going through the hook it installed.
    with tempfile.TemporaryDirectory() as d:
        base, camp = a_base_with_campaign(d)
        home = a_home(d)
        slug, clone = a_member_repo(d, camp)
        r = run_acquire(slug, clone, home)
        out = r.stdout + r.stderr
        hook = clone / ".git" / "hooks" / "pre-commit"
        body = text_of(hook) or ""
        check("a member clone -- one shipping no installer of its own -- gets a "
              "pre-commit that runs the claim gate",
              r.returncode == 0 and str(GATE) in body,
              f"exit {r.returncode}; {out[:240]}")
        # THE PATH, not merely the name. A member clone has no scripts/ of its
        # own, so a hook reaching the gate the way this repository's own hook
        # does -- through `git rev-parse --show-toplevel` -- would resolve to the
        # clone and find nothing. "Installed" and "runnable" drift apart exactly
        # here.
        check("...by its absolute path in the base, which is the only way the "
              "clone can reach it",
              f'"{GATE}" --staged' in body, repr(body[-160:]))
        check("...and it says which gate it installed, so a wrong base is "
              "readable at acquire time and not at commit time",
              str(GATE) in out, out[-240:])

        # The refusal, exercised. Asserted on WHAT IT SAID and not on the exit
        # status: a crash and a refusal share a status, and a hook that silently
        # did nothing shares a status with one that passed the commit honestly.
        on_branch(clone, "not-a-claim")
        c, both = commit_in(clone, home, "a", "1")
        check("...and that clone refuses a real commit whose branch is not a claim",
              c.returncode != 0 and "check-commit-claim: REFUSING" in both,
              f"exit {c.returncode}; {both[:240]}")
        check("...naming the reading it made, not just failing",
              "not a campaign branch" in both, both[:240])
        check("...with the machine-wide guard still running beside it, which is "
              "the half that was there before",
              "NO-MAIN-COMMITS RAN" in both, both[:240])

        # ...AND ADMITS ONE, or the gate is a wall rather than a gate. This is
        # the case a rule that refused everything would fail, and the one the
        # refusals above cannot distinguish themselves from without it.
        on_branch(clone, "demo/190-fixture", track=True)
        c, both = commit_in(clone, home, "b", "2")
        check("...and admits a commit on a claimed branch",
              c.returncode == 0, f"exit {c.returncode}; {both[:240]}")
        check("...saying so, and not merely staying quiet",
              "is a claim" in both, both[:240])

    # ---- THE GUARD'S REFUSAL IS THE HOOK'S ANSWER, not a line it printed on
    # the way to the gate. Before #190 the shim was `exec "$guard"`, so its
    # status was the hook's by construction; now something runs after it. For
    # one revision the only thing making the refusal fatal was a `set -e` no
    # case pinned, and deleting that line left both suites fully green while a
    # commit the guard had refused LANDED.
    with tempfile.TemporaryDirectory() as d:
        home = a_home(d, refuses=True)
        # OUTSIDE every base tree and every campaign directory ON PURPOSE: there
        # `classify` says "not campaign work", so the claim gate admits and the
        # guard is the only half that can refuse. In a campaign clone the gate
        # refuses too and the case would pass without testing anything.
        loose = Path(d) / "loose"
        loose.mkdir()
        slug, clone = a_member_repo(d, loose)
        r = run_acquire(slug, clone, home)
        c, both = commit_in(clone, home, "a", "1")
        check("a commit the machine-wide guard refuses does not land, even where "
              "the claim gate admits it",
              r.returncode == 0 and c.returncode != 0,
              f"acquire {r.returncode}, commit {c.returncode}; {both[:240]}")
        # The gate NEVER RUNS, and that is the assertion. Without `|| exit 1`
        # it runs, prints "no claim needed", and the commit lands -- so its
        # silence here is what separates a refusal honoured from one printed.
        check("...and the gate never got to speak, which is what honouring the "
              "refusal means",
              "GUARD REFUSED" in both and "no claim needed" not in both,
              both[:400])

    # ---- The gate that is named but cannot run, at both moments it can be
    # read. A hook naming a script that is not there is worse than no hook: it
    # reads to every session like a rule being enforced.
    with tempfile.TemporaryDirectory() as d:
        base, camp = a_base_with_campaign(d)
        home = a_home(d)
        slug, clone = a_member_repo(d, camp)
        _, copy = a_base_copy(d, gate=False)
        r = run_acquire(slug, clone, home, script=copy)
        check("a base with no check-commit-claim.py refuses to install rather "
              "than leaving a hook that cannot run",
              r.returncode != 0 and "gate it cannot run" in r.stderr,
              f"exit {r.returncode}; {(r.stdout + r.stderr)[-240:]}")
        check("...and writes no hook at all",
              not (clone / ".git" / "hooks" / "pre-commit").exists())

        # The second reading: installed from a base that HAD the gate, and the
        # gate is gone by the time a commit is made -- a base checkout moved or
        # deleted months later. The hook re-reads the path rather than trusting
        # the one baked in at acquire time.
        other, copy = a_base_copy(d, gate=True, name="gatedbase")
        r = run_acquire(slug, clone, home, script=copy)
        check("a base that has the gate installs the hook that names it",
              r.returncode == 0 and str(other / "scripts" / GATE.name)
              in (text_of(clone / ".git" / "hooks" / "pre-commit") or ""),
              f"exit {r.returncode}; {(r.stdout + r.stderr)[-240:]}")
        (other / "scripts" / GATE.name).unlink()
        on_branch(clone, "not-a-claim-either")
        c, both = commit_in(clone, home, "c", "3")
        check("...and once that gate is gone the hook REFUSES, rather than "
              "passing the commit it can no longer judge",
              c.returncode != 0 and "is missing or not executable" in both,
              f"exit {c.returncode}; {both[:240]}")
        check("...naming the path it looked for",
              str(other / "scripts" / GATE.name) in both, both[:240])

    # ---- #214. WHICH PRE-COMMIT MAY BE OVERWRITTEN. `install_commit_guard`
    # decided that with `grep -q 'no-main-commits'` over the whole file, so a
    # foreign hook naming the guard in a COMMENT was silently overwritten --
    # #190 round two fixed the same substring test one file over, in
    # install-hooks.sh, and the two were fixed apart because only one was in
    # that round's diff. This is the direction that destroys.
    #
    # The fixtures below carry the marker read out of the script rather than a
    # copy, and every case asserts on WHAT ACQUIRE SAID plus the hook's bytes:
    # "refused" and "overwrote and then failed later" share an exit status.
    check("the shim marker was found in acquire-repo.sh, so the fixtures below "
          "carry the real one", SHIM_MARKER is not None)
    # ...and if it was not, the loop below still RUNS. A failed check that then
    # raises aborts the suite, and every case after it goes unreported -- the
    # thing `text_of` above exists to prevent, met again one screen down.
    marker = SHIM_MARKER or "# SHIM_MARKER WAS NOT FOUND IN acquire-repo.sh"

    # The two shapes that MUST still be overwritten, or a re-run stops
    # converging and clones acquired before #190 never gain the claim gate.
    with tempfile.TemporaryDirectory() as d:
        base, camp = a_base_with_campaign(d)
        home = a_home(d)
        slug, clone = a_member_repo(d, camp)
        guard = home / ".claude" / "git-hooks" / "no-main-commits"

        r = run_acquire(slug, clone, home)
        first = text_of(clone / ".git" / "hooks" / "pre-commit") or ""
        r2 = run_acquire(slug, clone, home)
        second = text_of(clone / ".git" / "hooks" / "pre-commit") or ""
        check("a second acquire over the shim it just wrote converges rather "
              "than refusing",
              r.returncode == 0 and r2.returncode == 0 and second == first
              and str(GATE) in second,
              f"exit {r.returncode}/{r2.returncode}; "
              f"{(r2.stdout + r2.stderr)[-240:]}")

        # The pre-#190 two-liner, still on disk in clones acquired then. It has
        # no marker to name itself by, so it is matched whole -- and it has to
        # keep being overwritten, because it is exactly the hook that carries
        # the guard and NOT the claim gate.
        hook = clone / ".git" / "hooks" / "pre-commit"
        hook.write_text(f'#!/usr/bin/env sh\nexec "{guard}" "$@"\n')
        r = run_acquire(slug, clone, home)
        body = text_of(hook) or ""
        check("the pre-#190 two-line shim is upgraded, not refused",
              r.returncode == 0 and str(GATE) in body,
              f"exit {r.returncode}; {(r.stdout + r.stderr)[-240:]}")

    # ...and the near misses, one per conjunct of `is_guard_shim`. A row of
    # refusals needs one case per branch or it is pinned by whichever conjunct
    # happens to be exercised: deleting any one conjunct must redden the case
    # named for it and no other. NO COUNT IS WRITTEN HERE -- the first spelling
    # said "these five" over six entries, which is the staleness three comments
    # in install-hooks.sh hit with "ten lines".
    GUARD_CALL = '"/x/.claude/git-hooks/no-main-commits" "$@" || exit 1\n'
    for name, body in (
            # THE ONE #214 IS ABOUT: the guard named in a comment and called
            # nowhere. Under the substring test this was overwritten.
            ("naming the guard only in a comment",
             "#!/usr/bin/env sh\n" + marker + "\n"
             + "# nothing here calls no-main-commits\nexec /usr/bin/true\n"),
            # ...and the case the substring test got RIGHT, which must not
            # regress: a hook that never mentions the guard at all.
            ("not naming the guard at all",
             "#!/usr/bin/env sh\n# our team's pre-commit\nexec /usr/bin/true\n"),
            ("carrying the marker and the call but not the shebang",
             "#!/bin/sh\n" + marker + "\n" + GUARD_CALL),
            ("carrying the shebang and the call but somebody else's line 2",
             "#!/usr/bin/env sh\n# our team's pre-commit\n" + GUARD_CALL),
            # Two lines is the legacy branch, matched WHOLE; three is not it,
            # and without the marker it is not the current shape either.
            ("that is a legacy shim with one line added",
             '#!/usr/bin/env sh\nexec "/x/.claude/git-hooks/no-main-commits" "$@"\n'
             "echo also this\n"),
            ("that is a legacy shim whose shebang is not the one written",
             '#!/bin/sh\nexec "/x/.claude/git-hooks/no-main-commits" "$@"\n'),
            # THE LEGACY BRANCH'S OTHER CONJUNCT, and nothing pinned it until a
            # review of #214 deleted the pattern and watched the suite stay
            # green: two lines, the right shebang, and a line 2 that is not the
            # exec. Somebody's own two-line hook, overwritten.
            ("two lines and the right shebang but no guard call on line 2",
             "#!/usr/bin/env sh\nexec /usr/bin/true\n")):
        with tempfile.TemporaryDirectory() as d:
            base, camp = a_base_with_campaign(d)
            home = a_home(d)
            slug, clone = a_member_repo(d, camp)
            hook = clone / ".git" / "hooks" / "pre-commit"
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(body)
            hook.chmod(0o755)
            r = run_acquire(slug, clone, home)
            out = r.stdout + r.stderr
            check(f"a pre-commit {name} is refused, not overwritten",
                  r.returncode != 0 and "refusing to overwrite" in out,
                  f"exit {r.returncode}; {out[-240:]}")
            # The assertion that separates a refusal from a crash after the
            # write: the bytes are still somebody else's.
            check(f"...and the hook {name} is left byte for byte alone",
                  text_of(hook) == body, repr((text_of(hook) or "")[:120]))

    # The MILDER direction of the same defect -- `install_commit_guard`
    # verifying that a repository's OWN installer left a hook chaining the
    # guard, which was the same substring test three lines away -- is covered
    # in scripts/install-hooks-test.py, beside the case for an installer that
    # omits the guard entirely and beside the allow control that runs the real
    # install-hooks.sh. One home per branch, and that one already had it.

    # THE ORDER OF THE CALL, and this one is TEXTUAL rather than executed --
    # said plainly because a reader is owed the difference. The cases above run
    # `acquire` for real, so the CALL is covered now; what they cannot cover is
    # the order, because they reach the already-present branch and `clone_into`
    # never fires. Until #190 the whole call site was textual on the premise
    # that `acquire` clones from GitHub and so cannot run offline; a local bare
    # repository is a member repository as far as `remote_slug` is concerned,
    # which is what retired that premise. Without the case below the function
    # would be covered and its position not: deleting `install_principles
    # "$dest"` from `acquire` left all eight cases green, which is the fifth
    # time that shape has appeared in this repository.
    body = SCRIPT.read_text()
    acquire = body[body.index("acquire() {"):]
    check("acquire calls install_principles on every checkout it leaves",
          'install_principles "$dest"' in acquire,
          "the function is covered above; nothing runs it")
    # ...and it runs after the clone exists, or it would write into nothing.
    # Guarded on the call being present at all: `.index` RAISES when the case
    # above has already failed, and an exception aborts the suite instead of
    # reporting -- the same way a bare `read_text()` on the missing file did.
    check("...after the checkout is made, not before",
          'install_principles "$dest"' in acquire
          and acquire.index('install_principles "$dest"')
              > acquire.index("clone_into"))

    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
