#!/usr/bin/env python3
"""Print what this repository can decide by machine, so a session knows it exists.

Moving a rule out of AGENTS.md and into a hook or script only works if a session
can still find it: a rule deleted from the prose and buried in a script nobody
knows about is not mechanised, it is lost. This is the announcement, and a
SessionStart hook runs it.

It is derived, never a hand-kept list -- a second copy of the inventory would
drift exactly the way the prose copies this campaign is deleting drifted. Three
facts already on this machine carry it: every script states its purpose on the
line under its shebang, install-hooks names which of them git runs on its own,
and the settings files name which of them the HARNESS runs on its own. So
adding a script changes this output with no second edit anywhere.

The harness half is read from the settings files rather than from install-hooks,
for the same reason the git half is read from the installed hooks: what an
installer writes can drift from what is installed, and what actually runs is the
question a session is asking. There are two such files, and reading one of them
omits as silently as reading none: ~/.claude/settings.json is the machine's,
holds the guard install-hooks registers, and is true of no checkout at all -- so
a session in a worktree sees that guard running over a script the worktree also
holds -- while this checkout's own .claude/settings.json is where the repository
registers hooks of its own, this announcement being one of them. A reading of
the machine's alone named one harness hook where three run.

The harness half is also the half that can name a script from any root. git
resolves a hook's guard as <toplevel>/scripts/<name>, so only that root can
answer a `# runs:` line; the harness is given an absolute path and runs a
skill's script as readily as scripts/'s -- which is why the two halves are
offered different name sets, and why a guard here is one whose name either half
found rather than one that sits in scripts/.

A script it cannot read, or one whose kind it cannot tell, is printed as such.
An inventory that silently omits a primitive is worse than none: it reads as a
complete list, and the reader concludes the thing is not there.

WHAT IS LOCAL TO THIS REPOSITORY

How a script is named and where it lives are AGENTS.md's, under "Authoring a
script or a skill". It states the rule this listing's two sections are the
consequence of -- a reader is asked a question by a flow, and a guard acts
without being asked -- which is why the output has two sections rather than one
alphabetical list. Two facts are this repository's own and are stated only here.

A reader's subject is one of AGENTS.md's three planes, so `campaign-` prefixes a
reading of the campaign plane and nothing else. By that, `campaign-primitives`
is misnamed: it reads the base plane. It stays, because renaming it means
editing the SessionStart hook path in .claude/settings.json, whose failure mode
is silent -- the announcement simply stops appearing and nothing says so.

Scripts here sit in two roots, and this walks both. A script in a root it did
not walk is a script it does not announce, which is the precise failure it
exists to prevent, so adding a root is the same edit here as anywhere.

Usage: scripts/campaign-primitives.py [--brief] [--scripts-dir DIR]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# How each language in this tree opens a comment. A summary must be one. Python
# and sh are the two, and Python spells a docstring two ways.
#
# The list being short is exactly why an opener missing from it must not fail
# quietly. Dropping `'''` as dead -- no file in the tree used it -- did not make
# a `'''` script report "no summary"; the scan walked past the docstring and
# returned whatever `#` comment came next, announcing that line as what the
# script answers. So the scan stops at the first non-blank line under the
# shebang and names an opener it does not recognise, and a language arriving
# tomorrow is reported here rather than mis-summarised.
MARKERS = ('"""', "'''", "#")


def summary(path):
    """The line under the shebang, however the language spells a comment.

    It must *be* a comment or a docstring: a script with no summary must not be
    announced by a line of its own code -- `echo hi` presented to a reader as
    what the script answers. A wrong description is worse than a missing one,
    because the missing one is reported.

    None when there is nothing to read, an `<unreadable: ...>` marker when the
    file could not be opened, and an `<unrecognised comment opener: ...>` marker
    when the first line under the shebang opens no comment this script knows.
    All three are reported by the caller; none is silently dropped."""
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return f"<unreadable: {e.__class__.__name__}>"
    for line in lines[1:8]:
        stripped = line.strip()
        if not stripped:
            continue
        for marker in MARKERS:
            if stripped.startswith(marker):
                # A one-line docstring closes on the same line, so the opener's
                # own quote character comes off both ends.
                text = stripped[len(marker):].strip().strip(marker[0]).strip()
                return text or None
        # The first thing under the shebang is not a comment. Reading on would
        # find some later `#` and present it as the summary, which is the wrong
        # answer given in the shape of a right one.
        return f"<unrecognised comment opener: {stripped[:40]!r}>"
    return None


def hooks_dir():
    """Where git actually looks for hooks in this checkout. Returns
    (path, why_unreadable)."""
    # --git-path hooks, not --git-common-dir + "/hooks": the former is what git
    # itself resolves, so it honours core.hooksPath. The latter can name a
    # directory git is not actually looking at, which would have the inventory
    # report hooks as installed while git runs none -- the announcement lying
    # in the direction that matters.
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                        "--git-path", "hooks"], capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"git rev-parse failed: {r.stderr.strip()[:100]}"
    return Path(r.stdout.strip()), None


def installed_hooks(hdir):
    """The hook files git will run, with their text. Reality, not intent: what
    install-hooks writes can drift from what git actually executes, and what
    git will run is the question a session is actually asking.
    """
    out = {}
    if hdir is None or not hdir.is_dir():
        return out
    for p in sorted(hdir.iterdir()):
        if p.suffix == ".sample" or not p.is_file():
            continue
        if not p.stat().st_mode & 0o111:
            continue
        try:
            out[p.name] = p.read_text()
        except (OSError, UnicodeDecodeError) as e:
            out[p.name] = f"<unreadable: {e.__class__.__name__}>"
    return out


def hook_run(hook_texts, names):
    """Which scripts the installed hooks declare they run.

    Read from each hook's own `# runs:` line, which is also the list the hook
    loops over -- one list, two readers, and no parsing of shell on this side.
    A declaration the hook itself consumes cannot say something the hook does
    not do.

    Returns (found, problems). A hook with no `# runs:` line is named, not
    passed over: a hook this cannot read is not a hook that runs nothing.
    """
    found, problems = set(), []
    for name, text in sorted(hook_texts.items()):
        declared = re.findall(r"^# runs: (.+)$", text, re.M)
        if not declared:
            problems.append(f"{name} declares no `# runs:` line, so what it "
                            f"runs is unknown")
            continue
        for word in " ".join(declared).split():
            if word in names:
                found.add(word)
            else:
                problems.append(f"{name} declares {word}, which is not a "
                                f"script in this checkout")
    return found, problems


HARNESS_SETTINGS = Path.home() / ".claude" / "settings.json"


def harness_run(settings_path, names):
    """Which of these scripts the harness runs unasked, from its settings.

    Returns (found, problems). Every failure to read is a problem rather than
    an empty set: a settings file that would not parse is not a machine with no
    hooks, and the difference decides whether a session is told the guard is
    there.

    The match is on the script's basename as a whole token of a hook's
    `command` -- no word character, dot or hyphen touching it -- because a
    command is a shell line, a path, quoting and flags around it, and parsing
    it would be a second reader of how install-hooks writes one. A whole
    token and not a substring:
    `campaign-claim.py` is inside `check-campaign-claim.py`, and a substring
    match announced the first as installed when only the second was."""
    found, problems = set(), []
    try:
        settings = json.loads(settings_path.read_text())
    except FileNotFoundError:
        return found, [f"{settings_path} does not exist, so no harness hook "
                       f"is registered there"]
    except (OSError, ValueError) as e:
        return found, [f"{settings_path} would not read "
                       f"({e.__class__.__name__}), so what the harness runs is "
                       f"unknown"]
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return found, [f"{settings_path} has no `hooks` object this can read"]
    for event, entries in sorted(hooks.items()):
        if not isinstance(entries, list):
            problems.append(f"{settings_path} {event} is not a list of entries")
            continue
        for entry in entries:
            for h in (entry or {}).get("hooks") or []:
                command = (h or {}).get("command") or ""
                for name in names:
                    if re.search(r"(?<![\w.-])" + re.escape(name)
                                 + r"(?![\w.-])", command):
                        found.add(name)
    return found, problems


def script_roots(scripts_dir):
    """Every directory this repository parks a script in, newest-found last.

    Returns (label, directory) pairs; the label prefixes a script's name in the
    listing so a reader can find the file. The skills root is derived from
    `scripts_dir` rather than from HERE, so --scripts-dir moves both roots
    together and a fixture tree can exercise the walk.
    """
    roots = [("", scripts_dir)]
    skills = scripts_dir.parent / ".claude" / "skills"
    if skills.is_dir():
        for skill in sorted(skills.iterdir()):
            d = skill / "scripts"
            if d.is_dir():
                roots.append((f"{skill.name}/", d))
    return roots


def executables(root):
    """The scripts in one root. A suite is not one: it is run by CI and by a
    person, never by a flow that needs to be told it exists.

    A suite is recognised by its `-test` element, on the stem and not the name:
    the extension names the language, so `-test.py` and a later `-test.sh` are
    both suites and neither is announced."""
    return [p for p in sorted(root.iterdir())
            if not p.is_dir() and not p.stem.endswith("-test")
            and p.stat().st_mode & 0o111]


def main():
    brief = "--brief" in sys.argv
    # Which tree to describe. Defaults to this script's own directory; named so
    # another checkout can be listed, and so the unclassifiable case has a case
    # at all -- it cannot be reached by planting a broken script in the real
    # scripts/.
    here = HERE
    if "--scripts-dir" in sys.argv:
        here = Path(sys.argv[sys.argv.index("--scripts-dir") + 1])
    hdir, why = hooks_dir()
    hook_texts = installed_hooks(hdir)
    # (display name, path, is it in scripts/). A git hook resolves its guard as
    # <toplevel>/scripts/<name>, so only that root can answer a `# runs:` line;
    # offering a skill's script to hook_run would let a hook declare a guard git
    # could never find and have it read as installed.
    scripts = [(label + p.name, p, label == "")
               for label, root in script_roots(here)
               for p in executables(root)]
    top_names = {p.name for _, p, top in scripts if top}
    # The harness names a hook by absolute path, so it runs a skill's script as
    # readily as scripts/'s: campaign-role-brief.py is registered in the
    # machine's settings and was listed as a script a flow calls, because only
    # scripts/ names were offered to this half.
    all_names = {p.name for _, p, _ in scripts}
    runs, problems = hook_run(hook_texts, top_names)
    # Both files the harness reads, in the order it merges them. The second is
    # the described checkout's rather than HERE's, so --scripts-dir moves it the
    # way it moves the script roots and a fixture tree can exercise the reading.
    settings_files = [HARNESS_SETTINGS, here.parent / ".claude" / "settings.json"]
    harness, harness_problems = {}, []
    for sp in settings_files:
        found, probs = harness_run(sp, all_names)
        harness[sp] = found
        harness_problems += probs
        runs |= found
    guards, readers, unknown = [], [], []
    for name, p, top in scripts:
        summ = summary(p)
        if summ is None or summ.startswith("<"):
            # `<unreadable: ...>` and `<unrecognised comment opener: ...>` are
            # both readings this inventory could not make, and the section that
            # says so is the one place a reader learns a script went unnamed.
            unknown.append((name, summ or "<no comment under the shebang>"))
        elif p.name in runs:
            guards.append((name, summ))
        else:
            readers.append((name, summ))

    print("Machine-decided here. Ask these before writing a check by hand.")

    if why:
        print(f"\n  !! could not find this checkout's hooks ({why}), so nothing "
              f"below is\n     known to run on its own.")
    elif not hook_texts:
        print(f"\n  !! NO git hook is installed in {hdir}. Nothing in this "
              f"checkout is guarded.\n     Run scripts/install-hooks.sh.")
    else:
        print(f"\n  git hooks installed ({len(hook_texts)}): "
              f"{', '.join(sorted(hook_texts))}")
        for w in problems:
            print(f"     !! {w}")
        if not runs:
            print("     !! no hook declares a script named below, so nothing "
                  "in this checkout is\n        known to be guarded.")

    for sp, found in harness.items():
        if found:
            print(f"\n  harness hooks in {sp} ({len(found)}): "
                  f"{', '.join(sorted(found))}")
    for w in harness_problems:
        print(f"     !! {w}")

    print(f"\n  run unasked, by git or by the harness ({len(guards)}):")
    for n, summ in guards:
        print(f"    {n:30} {summ}")
    print(f"\n  a flow calls these ({len(readers)}):")
    if brief:
        # Every session start pays for this, so the brief form spends its lines
        # on what acts unasked and names the rest -- a name is enough to go and
        # read one.
        line, out = "   ", []
        for n, _ in readers:
            if len(line) + len(n) > 76:
                out.append(line)
                line = "   "
            line += " " + n
        out.append(line)
        print("\n".join(out))
        print("\n  scripts/campaign-primitives.py says what each one answers.")
    else:
        for n, summ in readers:
            print(f"    {n:30} {summ}")
    if unknown:
        print(f"\n  !! {len(unknown)} could not be classified:")
        for n, w in unknown:
            print(f"    {n:30} {w}")

    # Always 0. This is the SessionStart hook's command, and a non-zero exit
    # there is a non-blocking error: stderr surfaces and stdout is dropped. So
    # exiting 1 on an unclassifiable script suppressed the entire announcement
    # -- the one case the `!!` block exists for. The block is the report; the
    # status is not.
    return 0


if __name__ == "__main__":
    sys.exit(main())
