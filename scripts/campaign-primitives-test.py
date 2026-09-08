#!/usr/bin/env python3
"""Prove the inventory reports what is installed, and admits what it cannot read.

The announcement is what makes deleting a rule from the prose safe, so the way
it fails matters more than the way it succeeds. Two directions, not equally bad:
over-calling makes a reader look for a guard that is not there, while reporting
a deleted guard as installed makes a reader believe the tree is guarded when
nothing guards it.

Usage: scripts/campaign-primitives-test.py
"""
import importlib.machinery
import json
import os
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

PRIM = Path(__file__).resolve().parent / "campaign-primitives.py"

# Spelled with chr() so this file's own text holds no triple quote of its
# own: check-tree-shape reads one as a docstring opening.
SQ = chr(39) * 3

DECLARING = "#!/bin/sh\n# runs: check-rule-readers.py check-tree-shape.py\nfor g in $(sed ...); do :; done\n"
# The same hook after an ordinary refactor of its loop. Both readers use the
# declaration, so the loop's shape does not matter.
REFACTORED = "#!/bin/sh\n# runs: check-rule-readers.py check-tree-shape.py\nG=$(sed ...)\nfor g in $G; do :; done\n"
# A hook mentioning scripts in prose and declaring nothing. The classifier that
# matched a name anywhere reported these as installed guards.
PROSE_ONLY = "#!/bin/sh\n# see scripts/check-rule-readers.py and scripts/check-tree-shape.py\nexit 0\n"


def load():
    spec = importlib.util.spec_from_loader(
        "prim", importlib.machinery.SourceFileLoader("prim", str(PRIM)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    m = load()
    ran, fails = [], []

    def check(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)

    names = {"check-rule-readers.py", "check-tree-shape.py",
             "campaign-tracker.py", "install-hooks.sh",
             "push-campaign-branch.sh"}
    both = {"check-rule-readers.py", "check-tree-shape.py"}

    found, probs = m.hook_run({"pre-commit": DECLARING}, names)
    check("a hook's declaration names its guards", found == both and not probs)
    found, probs = m.hook_run({"pre-commit": REFACTORED}, names)
    check("...and a refactor of the loop changes nothing",
          found == both and not probs)

    found, probs = m.hook_run({"pre-commit": PROSE_ONLY}, names)
    check("a hook that only mentions guards in prose declares none",
          found == set())
    check("...and says so rather than reporting an unguarded tree as guarded",
          any("declares no" in p for p in probs))

    found, probs = m.hook_run({"pre-commit": "#!/bin/sh\n# runs: no-such\n"}, names)
    check("a declaration naming a script that is not here is reported",
          found == set() and any("not a script" in p for p in probs))

    found, probs = m.hook_run({}, names)
    check("no hook installed means no guard found", found == set() and not probs)

    with tempfile.TemporaryDirectory() as d:
        h = Path(d) / "hooks"
        h.mkdir()
        s = h / "pre-commit.sample"
        s.write_text(DECLARING)
        s.chmod(0o755)
        check("git's shipped .sample hooks are not installed hooks",
              m.installed_hooks(h) == {})
        p = h / "pre-commit"
        p.write_text(DECLARING)
        check("a hook without the execute bit is not one git runs",
              m.installed_hooks(h) == {})
        p.chmod(0o755)
        check("an executable hook is read", "pre-commit" in m.installed_hooks(h))
        check("a hooks directory that does not exist is empty, not a crash",
              m.installed_hooks(Path(d) / "absent") == {})
        check("and neither is None", m.installed_hooks(None) == {})

    with tempfile.TemporaryDirectory() as d:
        def wrote(body):
            q = Path(d) / "mystery"
            q.write_text(body)
            return q
        check("a comment under the shebang is the summary",
              m.summary(wrote("#!/bin/sh\n# what it does\n")) == "what it does")
        check("a docstring is too",
              m.summary(wrote('#!/usr/bin/env python3\n"""what it does."""\n'))
              == "what it does.")
        check("a single-quoted docstring is a docstring too",
              m.summary(wrote("#!/usr/bin/env python3\n" + SQ + "what it does."
                              + SQ + "\n")) == "what it does.")
        # The two halves of the same defect. Without an opener for it, a
        # single-quoted docstring did not report "no summary": the scan walked
        # past it and announced the next `#` line in the file, which is a wrong
        # answer wearing the shape of a right one.
        check("...and a stray comment below one is not mistaken for it",
              m.summary(wrote("#!/usr/bin/env python3\n" + SQ + "what it does."
                              + SQ + "\nimport sys\n# not the summary\n"))
              == "what it does.")
        check("a first line that opens no comment is named, not read past",
              m.summary(wrote("#!/bin/sh\nset -e\n# not the summary\necho hi\n"))
              == "<unrecognised comment opener: 'set -e'>")
        check("a file holding only a shebang has nothing to read",
              m.summary(wrote("#!/bin/sh\n")) is None)
        check("a file that cannot be read says so rather than returning none",
              str(m.summary(Path(d) / "absent")).startswith("<unreadable"))
        # End to end: what summary() names must reach the reader, and the
        # section that admits a script it could not classify is the one place
        # it can. A summary silently invented from a later line lands the
        # script in the reader list instead, where nothing says it was guessed.
        (Path(d) / "opaque").write_text("#!/bin/sh\nset -e\n# not the summary\n")
        (Path(d) / "opaque").chmod(0o755)
        r = subprocess.run([sys.executable, str(PRIM), "--scripts-dir", d],
                           capture_output=True, text=True)
        check("a script it could not classify is listed as such, and the run "
              "still exits 0",
              r.returncode == 0 and "could not be classified" in r.stdout
              and "unrecognised comment opener" in r.stdout)

    # This is the SessionStart hook's command, so it must deliver the listing
    # whatever it found: a non-zero exit there drops stdout entirely, which
    # suppressed the announcement in the one case the warning block is for.
    r = subprocess.run([sys.executable, str(PRIM), "--brief"],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    check("it exits 0 so SessionStart delivers the listing", r.returncode == 0)
    check("the push hook is announced, being a mechanism that acts unasked",
          "push-campaign-branch.sh" in out)
    check("the two guards are announced",
          "check-tree-shape.py" in out and "check-rule-readers.py" in out)
    check("it separates what runs unasked from what a flow calls",
          "run unasked, by git or by the harness" in out
          and "a flow calls these" in out)

    # The harness half. Its own section, because a settings.json that would not
    # parse and one with no hooks in it are different answers and only the
    # first denies the listing.
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Edit",
                            "hooks": [{"type": "command",
                                       "command": "/x/check-campaign-claim.py"}]}]}}))
        r = subprocess.run([sys.executable, str(PRIM)], cwd=PRIM.parent.parent,
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        out = r.stdout + r.stderr
        check("a harness-registered guard is announced as running unasked",
              "harness hooks in" in out and "check-campaign-claim.py" in out)
        # Read through harness_run and not the printed line: the line that
        # announces check-campaign-claim.py contains campaign-claim.py as text,
        # so a substring test on the output cannot see the defect.
        found, probs = m.harness_run(home / ".claude" / "settings.json",
                                     {"check-campaign-claim.py",
                                      "campaign-claim.py"})
        check("a basename inside another basename is not reported as installed",
              found == {"check-campaign-claim.py"} and not probs)
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text("{ not json")
        r = subprocess.run([sys.executable, str(PRIM)], cwd=PRIM.parent.parent,
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(home)))
        out = r.stdout + r.stderr
        check("settings that will not parse is reported, not read as no hooks",
              "would not read" in out and r.returncode == 0)
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, str(PRIM)], cwd=PRIM.parent.parent,
                           capture_output=True, text=True,
                           env=dict(os.environ, HOME=str(d)))
        out = r.stdout + r.stderr
        check("an absent settings file says so rather than announcing nothing",
              "does not exist" in out and r.returncode == 0)

    # TWO SETTINGS FILES AND EVERY SCRIPT ROOT. The machine's settings alone
    # named ONE harness hook where three run: this repository registers its own
    # SessionStart hook in .claude/settings.json, which was never read, and
    # campaign-role-brief.py lives in a skill and so was never even offered as a
    # name to match. A fixture tree, not the real one, because the real answer
    # moves whenever somebody edits either settings file.
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as h:
        root, home = Path(d), Path(h)
        (root / "scripts").mkdir()
        (root / ".claude" / "skills" / "s" / "scripts").mkdir(parents=True)

        def script(path, summ):
            path.write_text(f"#!/bin/sh\n# {summ}\nexit 0\n")
            path.chmod(0o755)

        script(root / "scripts" / "in-project.py", "Registered by the checkout.")
        script(root / "scripts" / "in-machine.py", "Registered by the machine.")
        script(root / "scripts" / "asked.py", "Registered nowhere.")
        script(root / ".claude" / "skills" / "s" / "scripts" / "briefer.py",
               "A skill's script the harness runs.")

        def settings(*commands):
            return json.dumps({"hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": c} for c in commands]}]}})

        (root / ".claude" / "settings.json").write_text(
            settings('"$CLAUDE_PROJECT_DIR"/scripts/in-project.py --brief'))
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text(
            settings("python3 /x/scripts/in-machine.py",
                     "python3 /x/.claude/skills/s/scripts/briefer.py"))

        r = subprocess.run(
            [sys.executable, str(PRIM), "--scripts-dir", str(root / "scripts")],
            capture_output=True, text=True, env=dict(os.environ, HOME=str(home)))
        # Section by section: a name anywhere in the output proves nothing --
        # every one of these appears in the reader list too if it is misfiled,
        # and that is exactly the defect.
        out = r.stdout
        unasked = out.split("run unasked, by git or by the harness")[-1]
        unasked = unasked.split("a flow calls these")[0]
        called = out.split("a flow calls these")[-1]
        check("a hook the checkout's own settings register is announced as "
              "running unasked",
              "in-project.py" in unasked and "in-project.py" not in called)
        check("...and so is one the machine's settings register",
              "in-machine.py" in unasked and "in-machine.py" not in called)
        check("a harness hook that is a skill's script is announced as running "
              "unasked, not as one a flow calls",
              "briefer.py" in unasked and "briefer.py" not in called)
        check("a script neither settings file names is still a script a flow "
              "calls",
              "asked.py" in called and "asked.py" not in unasked)
        check("each settings file is named beside what it registered",
              f"harness hooks in {root / '.claude' / 'settings.json'} (1)" in out
              and f"harness hooks in {home / '.claude' / 'settings.json'} (2)"
              in out)

    # core.hooksPath: git looks there and nowhere else, so resolving the hooks
    # directory by hand instead of asking git could report hooks as installed
    # that git never runs.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".git" / "hooks" / "pre-commit").write_text(DECLARING)
        (root / ".git" / "hooks" / "pre-commit").chmod(0o755)
        r = subprocess.run([sys.executable, str(PRIM)], cwd=root,
                           capture_output=True, text=True)
        check("a hook in the default place is found", "pre-commit" in r.stdout)
        subprocess.run(["git", "config", "core.hooksPath", str(root / "nowhere")],
                       cwd=root, check=True)
        r = subprocess.run([sys.executable, str(PRIM)], cwd=root,
                           capture_output=True, text=True)
        check("core.hooksPath sends git elsewhere, and the listing follows it",
              "NO git hook is installed" in r.stdout)

    # A hook with no marker and no declaration, in a real hooks directory: the
    # two-line shim acquire-repo wrote before #190, still on disk wherever a
    # clone was acquired then. The note is a true reading -- what the hook runs
    # is unknown to this reader -- and #178 fixed the clone, not the note, so it
    # must survive as written. The shim acquire-repo writes NOW carries a marker
    # comment, and this reader has no opinion about that either.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        h = root / ".git" / "hooks" / "pre-commit"
        h.write_text('#!/usr/bin/env sh\nexec "/h/.claude/git-hooks/no-main-commits" "$@"\n')
        h.chmod(0o755)
        r = subprocess.run([sys.executable, str(PRIM)], cwd=root,
                           capture_output=True, text=True)
        check("an unmarked hook with no `# runs:` line still yields the "
              "unknown note",
              "pre-commit declares no `# runs:` line" in r.stdout
              and r.returncode == 0)

    # The unclassifiable-script case the warning block above exists for.
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "mystery"
        q.write_text("#!/bin/sh\nset -e\necho hi\n")
        q.chmod(0o755)
        r = subprocess.run([sys.executable, str(PRIM), "--scripts-dir", d],
                           capture_output=True, text=True)
        out2 = r.stdout + r.stderr
    check("an unclassifiable script is reported", "could not be classified" in out2)
    check("...and does not suppress the listing by exiting non-zero",
          r.returncode == 0 and "Machine-decided here" in r.stdout)

    # Two roots. A script parked under the skill that owns it is still a script
    # a session must be told about, and a root this does not walk is a script it
    # does not announce -- the exact failure the inventory exists to prevent.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        top = root / "scripts"
        top.mkdir()
        (top / "in-scripts").write_text("#!/bin/sh\n# a shared reader\n")
        (top / "in-scripts").chmod(0o755)
        owned = root / ".claude" / "skills" / "some-skill" / "scripts"
        owned.mkdir(parents=True)
        (owned / "in-skill").write_text("#!/bin/sh\n# a reader one skill owns\n")
        (owned / "in-skill").chmod(0o755)
        # A skill directory with no scripts/ of its own is not a root.
        (root / ".claude" / "skills" / "bare-skill").mkdir(parents=True)
        # ...and a suite is not announced from either root.
        (owned / "in-skill-test").write_text("#!/bin/sh\n# a suite\n")
        (owned / "in-skill-test").chmod(0o755)

        roots = m.script_roots(top)
        check("the scripts directory is the first root",
              roots and roots[0] == ("", top))
        check("a skill with its own scripts/ is a second root",
              ("some-skill/", owned) in roots)
        check("a skill with no scripts/ is not a root",
              not any("bare-skill" in label for label, _ in roots))

        r = subprocess.run([sys.executable, str(PRIM), "--scripts-dir", str(top)],
                           capture_output=True, text=True)
        out3 = r.stdout + r.stderr
        check("a script under a skill is announced", "in-skill" in out3)
        check("...labelled by the skill that owns it, so it can be found",
              "some-skill/in-skill" in out3)
        check("...and the shared root is still listed", "in-scripts" in out3)
        check("a suite is announced from neither root",
              "in-skill-test" not in out3)

        # A git hook resolves its guard as <toplevel>/scripts/<name>, so a hook
        # declaring a skill's script names something git could never run. It is
        # reported, never quietly counted as an installed guard.
        found, probs = m.hook_run({"pre-commit": "#!/bin/sh\n# runs: in-skill\n"},
                                  {"in-scripts"})
        check("a hook declaring a skill's script is reported, not read as a guard",
              found == set() and any("not a script" in p for p in probs))

    # The real tree: the moved script must appear in the full listing, which is
    # the claim this two-root walk exists to keep true.
    r = subprocess.run([sys.executable, str(PRIM)], capture_output=True, text=True)
    check("the real listing announces the script that lives under a skill",
          "acquire-repo.sh" in r.stdout and r.returncode == 0)

    if not ran:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in fails:
        print(f"FAIL  {f}")
    print(f"{len(ran) - len(fails)}/{len(ran)} cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
