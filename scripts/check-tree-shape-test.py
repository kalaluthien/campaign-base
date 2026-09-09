#!/usr/bin/env python3
"""Prove check-tree-shape fires where it must and stays quiet where it must not.

The guard reads a git tree, so every case builds a throwaway repository and runs
the shipped script over it. Its measure is not how many cases pass but how many
ways of breaking the guard at least one case notices -- so each row that expects
a hit is aimed at one branch, and each row that expects quiet names a boundary
somebody would otherwise widen the guard straight past.

Usage: scripts/check-tree-shape-test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "check-tree-shape.py"

IGNORE = "/*\n!/.gitignore\n!/spec/\n!/.claude/\n!/scripts/\n!/AGENTS.md\n"

# A fixture that spells a triple quote spells it with chr(), the way this
# file already spells the single-quoted one: written out, the guard reading
# *this* file takes it for a docstring opening and mis-reads what follows.
DQ = chr(34) * 3
SQ = chr(39) * 3

# (name, {path: contents}, expected_rule or None)
CASES = [
    # R1 -- misfiled markdown, and the two shapes that are not it.
    ("R1 markdown under spec/", {"spec/x.md": "hi\n"}, "R1"),
    ("R1 markdown at the root is where it belongs", {"AGENTS.md": "hi\n"}, None),
    ("R1 html under spec/ is the diagram beside a model",
     {"spec/x.html": "<p>hi</p>\n"}, None),

    # R2 -- the allowlist. The trailing slash is the shape every entry in the
    # real .gitignore has, so a guard that does not strip it passes nothing.
    ("R2 a tracked top-level name with no allowlist line",
     {"scratch/x.txt": "hi\n"}, "R2"),
    ("R2 an entry written with its trailing slash still matches",
     {".claude/skills/s/SKILL.md": "hi\n"}, None),

    # R3 markdown -- the split check-rule-readers already makes.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 md: a retired path in a fence",
     {"AGENTS.md": "t\n\n```sh\ncat runtime/holder\n```\n"}, "R3b"),
    ("R3 md: the same path named in prose is a mention",
     {"AGENTS.md": "t\n\n`runtime/holder` is retired with the role.\n"}, None),
    ("R3 md: an indented block is code too",
     {"AGENTS.md": "t\n\n    cat runtime/holder\n"}, "R3b"),
    ("R3 md: an exempted block is spent on the next block",
     {"AGENTS.md": "t\n\n<!-- unguarded: check-tree-shape -- the retired form, quoted -->\n```sh\ncat runtime/holder\n```\n"}, None),

    # R3 Alloy -- where the prose lives inside the comment.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 als: a retired name in a signature",
     {"spec/a.als": "sig S { holder: runtime/holder }\n"}, "R3b"),
    ("R3 als: the same name inside a block comment",
     {"spec/a.als": "/*\n * `runtime/holder` is retired with the role.\n */\nsig S {}\n"}, None),
    ("R3 als: after a // line comment",
     {"spec/a.als": "sig S {}  // runtime/holder went with #100\n"}, None),
    ("R3 als: after a -- line comment",
     {"spec/a.als": "sig S {}  -- runtime/holder went with #100\n"}, None),
    ("R3 als: the earliest line-comment marker wins, not the first in the table",
     {"spec/a.als": "sig S {} -- runtime/holder // x\n"}, None),
    ("R3 als: a one-line block comment does not swallow the rest of the file",
     {"spec/a.als": "/* a note */\nsig S { h: runtime/holder }\n"}, "R3b"),

    # R3 scripts -- docstring and hash prose.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a retired path in code",
     {"scripts/x.py": 'open("runtime/holder")\n'}, "R3b"),
    ("R3 py: the same path in the docstring",
     {"scripts/x.py": '"""Why runtime/holder went away."""\nx = 1\n'}, None),
    ("R3 py: after a hash",
     {"scripts/x.py": "x = 1  # runtime/holder is retired\n"}, None),
    ("R3 py: code before a trailing hash still counts",
     {"scripts/x.py": 'open("runtime/holder")  # a note\n'}, "R3b"),

    # The exemption itself, which is a branch and needs pinning both ways.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a marker exempts the run of code below it",
     {"scripts/x.py": '# unguarded: check-tree-shape -- fixture\nopen("runtime/holder")\n'}, None),
    ("R3 py: the exemption is spent at the next blank line",
     {"scripts/x.py": '# unguarded: check-tree-shape -- fixture\nx = 1\n\nopen("runtime/holder")\n'}, "R3b"),
    ("R3 als: the marker is read on a block comment's opening line",
     {"spec/a.als": "/* unguarded: check-tree-shape -- fixture */\nsig S { h: runtime/holder }\n"}, None),
    # A block comment runs many lines and the marker is usually not on the
    # first: that is a separate branch, and the one-line fixture above pins
    # nothing about it.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 als: the marker is read on a block comment's continuation line",
     {"spec/a.als": "/*\n * why this is here\n * unguarded: check-tree-shape -- fixture\n */\nsig S { h: runtime/holder }\n"}, None),

    # Who the exemption belongs to. Both halves were live: an unowned marker
    # exempted whatever followed it, so this guard's own header -- which spells
    # `unguarded:` while explaining the syntax -- exempted this guard's body;
    # and a marker naming a sibling guard's token silenced this one too.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a docstring explaining the marker is not a marker",
     {"scripts/x.py": DQ + "The `unguarded:` marker exempts the code below.\n"
                      + DQ + '\nopen("runtime/holder")\n'}, "R3b"),
    ("R3 py: a marker naming another guard's token exempts nothing here",
     {"scripts/x.py": "# unguarded: campaign-repos -- check-rule-readers' token\n"
                      'open("runtime/holder")\n'}, "R3b"),

    # The exemption reaches the code the comment sits on top of, and no
    # further back than the last thing that comment says. Without the second
    # of these the first passes with the marker buried anywhere in a docstring.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a marker on the comment's last line reaches the code below it",
     {"scripts/x.py": DQ + "Docs.\nunguarded: check-tree-shape -- fixture\n"
                      + DQ + '\nopen("runtime/holder")\n'}, None),
    ("R3 py: ...and prose after the marker spends it before the code",
     {"scripts/x.py": DQ + "Docs.\nunguarded: check-tree-shape -- fixture\n"
                      "More prose, and the marker is no longer what this says.\n"
                      + DQ + '\nopen("runtime/holder")\n'}, "R3b"),

    # A hash or a triple quote inside a string literal is indistinguishable
    # from a comment to this cut, so neither may spend an exemption granted
    # above it.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a hash inside a string literal does not spend an exemption",
     {"scripts/x.py": '# unguarded: check-tree-shape -- fixture\n'
                      'x = "a # b"\nopen("runtime/holder")\n'}, None),
    ("R3 py: nor does a quoted docstring delimiter with code in front of it",
     {"scripts/x.py": '# unguarded: check-tree-shape -- fixture\n'
                      "x = " + SQ + "y" + SQ + '\nopen("runtime/holder")\n'}, None),

    # R3 html -- the language a path grep in one syntax cannot see.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 html: a retired path in markup",
     {"spec/x.html": "<code>runtime/holder</code>\n"}, "R3b"),
    ("R3 html: the same path in an html comment",
     {"spec/x.html": "<!-- runtime/holder is retired -->\n<p>hi</p>\n"}, None),

    # The reading-versus-verdict rule: an unknown language is a file the sweep
    # cannot read, and an unread file must not come back as a clean tree.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R0 an unknown suffix is reported, not skipped",
     {"scripts/x.rb": 'puts "runtime/holder"\n'}, "R0"),
    ("R0 an unread file does not hide what the other rules found",
     {"scratch/x.rb": "hi\n"}, "R2"),
    ("R0 absent: a captured screen under a skill's scripts/fixtures/ is read",
     {".claude/skills/s/SKILL.md": "---\nname: s\n---\n",
      ".claude/skills/s/scripts/fixtures/banner.txt":
      "  \u23bf  You've hit your session limit \u00b7 resets 9pm (Asia/Seoul)\n"}, None),
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 stands down over a skill's scripts/fixtures/ as over the root's",
     {".claude/skills/s/SKILL.md": "---\nname: s\n---\n",
      ".claude/skills/s/scripts/fixtures/screen.txt": "cat $CAMPAIGN/runtime/holder\n"}, None),
    ("R3 still runs over a skill's scripts/ itself",
     {".claude/skills/s/SKILL.md": "---\nname: s\n---\n",
      ".claude/skills/s/scripts/screen.txt": "cat $CAMPAIGN/runtime/holder\n"}, "R3b"),
    ("R3 still runs over a scripts/fixtures/ under a skill's assets/",
     {".claude/skills/s/SKILL.md": "---\nname: s\n---\n",
      ".claude/skills/s/assets/scripts/fixtures/screen.txt": "cat $CAMPAIGN/runtime/holder\n"}, "R3b"),

    # A language with no comment syntax at all: every line is code, and the
    # empty marker lists must not make the whole file read as prose.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 json: a language with no comments is all code",
     {"scripts/x.json": '{"path": "runtime/holder"}\n'}, "R3b"),

    # RECORDED -- a corpus of calls that were really made. R3 stands down over
    # it and nothing else does, so the four cases below break the exemption
    # apart: remove it and the first two fail, widen it to the SUFFIX and the
    # third fails, widen it to the whole sweep and the fourth fails.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 stands down over a recorded corpus",
     {"scripts/fixtures/guard-allow-corpus.jsonl":
      '{"command": "ls runtime/claims", "tool": "Bash"}\n'}, None),
    ("R3 ...over any file in that directory, not one name",
     {"scripts/fixtures/older.jsonl":
      '{"command": "cat runtime/handover/7.md", "tool": "Bash"}\n'}, None),
    ("R3 ...but the exemption is the PATH and not the suffix",
     {"scripts/x.jsonl": '{"path": "runtime/holder"}\n'}, "R3b"),
    ("R4 still runs over a recorded path",
     {"scripts/fixtures/repos/member/x.jsonl": '{"a": 1}\n'}, "R4"),

    # R5 -- a skill directory holds SKILL.md and the three directories a skill
    # has. One refusal per branch, and one allow per shape somebody would
    # otherwise widen it past: `assets/` DOES nest (the campaign scaffold ships
    # `assets/agents/` and `assets/scripts/`), and `.claude/` holds directories
    # that are not skills at all.
    ("R5 a fourth name at a skill's root",
     {".claude/skills/s/notes.md": "hi\n"}, "R5"),
    ("R5 references/ two levels deep",
     {".claude/skills/s/references/deep/x.md": "hi\n"}, "R5"),
    ("R5 a loose file directly under .claude/skills/",
     {".claude/skills/loose.md": "hi\n"}, "R5"),
    ("R5 the SKILL.md itself is the point",
     {".claude/skills/s/SKILL.md": "hi\n"}, None),
    ("R5 a reference one level deep",
     {".claude/skills/s/references/x.md": "hi\n"}, None),
    ("R5 assets/ nests: it is a tree copied into a deliverable",
     {".claude/skills/s/assets/agents/x.md": "hi\n"}, None),
    ("R5 scripts/ beside a skill is not a reference",
     {".claude/skills/s/scripts/x.py": "x = 1\n"}, None),
    ("R5 a directory under .claude/ that is not a skill",
     {".claude/agents/x.md": "hi\n"}, None),
    ("R5 the skills root is anchored: one deeper in the tree is not it",
     {"scripts/fixtures/.claude/skills/s/notes.md": "hi\n"}, None),

    # R6 -- the extension. The refusal is the shape the retired deny list held
    # by name (`scripts/<name>` with no extension); the allows are the two
    # places a file may sit in a scripts/ tree without being a script.
    ("R6 a script with no extension",
     {"scripts/x": "hi\n"}, "R6"),
    ("R6 a script named for something that is not its language",
     {"scripts/x.html": "<p>hi</p>\n"}, "R6"),
    ("R6 a shell script is a script too",
     {"scripts/x.sh": "echo hi\n"}, None),
    ("R6 data nested below a scripts/ is not a script",
     {"scripts/fixtures/notes.html": "<p>hi</p>\n"}, None),
    ("R6 a template under an assets/ is some other tree's script",
     {".claude/skills/s/assets/scripts/x.html": "<p>hi</p>\n"}, None),

    # A file with no text in it at all -- a guard whose whole point is naming
    # which reading it could not make must not itself die in the decode.
    ("R0 a file that is not text is reported, not a traceback",
     {"spec/x.png": "\x89PNG\r\n\x1a\n\x00\x01\x02\x03"}, "R0"),

    # A known suffix whose bytes are not text: the decode branch, which the
    # PNG above does not reach because it is caught a step earlier by suffix.
    ("R0 a known suffix that will not decode is reported too",
     {"scripts/x.py": b"x = 1\n\xff\xfe not utf-8\n"}, "R0"),

    # The other two retired names. One case per pattern: without one, deleting
    # that pattern from RETIRED would leave the suite green.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 the runtime/executors path is retired too",
     {"scripts/x.py": 'open("runtime/executors/62")\n'}, "R3b"),
    ("R3 ...but the word in prose is a mention",
     {"AGENTS.md": "t\n\nThe `CLAIMED` message was retired by #59.\n"}, None),

    # The #105 merges, one case per name in each alternation: the #139 sweep
    # mangled `campaign-(anchors|...)` to `campaign-(campaign issues|...)` and
    # every suite stayed green, because nothing here spelled a name. Removing
    # any one name from its alternation now fails the case that spells it.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 scripts/campaign-anchors is retired",
     {"scripts/x.py": 'run("scripts/campaign-anchors")\n'}, "R3a"),
    ("R3 scripts/campaign-bound is retired",
     {"scripts/x.py": 'run("scripts/campaign-bound", "1")\n'}, "R3a"),
    ("R3 scripts/campaign-subtasks is retired",
     {"scripts/x.py": 'run("scripts/campaign-subtasks", "1")\n'}, "R3a"),
    ("R3 scripts/campaign-settlement is retired",
     {"scripts/x.py": 'run("scripts/campaign-settlement", "1")\n'}, "R3a"),
    ("R3 scripts/campaign-live is retired",
     {"scripts/x.py": 'run("scripts/campaign-live", "1")\n'}, "R3a"),
    ("R3 scripts/campaign-session-alive is retired",
     {"scripts/x.py": 'run("scripts/campaign-session-alive", "1")\n'}, "R3a"),
    ("R3 scripts/alloy-trace-digest is retired",
     {"scripts/x.py": 'run("scripts/alloy-trace-digest", "s.txt")\n'}, "R3a"),
    ("R3 a bare scripts/acquire-repo is the stale call",
     {"scripts/x.py": 'run("scripts/acquire-repo.sh", "o/r")\n'}, "R3a"),
    # THE ALLOW SIDE IS A FILE THAT IS THERE. R3a resolves against the tree it
    # is judging, so these fixtures carry the file they name -- which is the
    # rule stated from the other end: a call is fine exactly when its target
    # exists here.
    ("R3 ...and the moved path is the correct one",
     {"scripts/x.py": 'run(".claude/skills/opening-campaign/scripts/acquire-repo.sh", "o/r")\n',
      ".claude/skills/opening-campaign/scripts/acquire-repo.sh": "#!/bin/sh\n",
      # `.claude/` needs its allowlist line or R2 answers before R3a does.
      ".gitignore": IGNORE + "!/.claude/\n"}, None),
    ("R3 the live tracker subcommand is not a retired name",
     {"scripts/x.py": 'run("scripts/campaign-tracker.py", "campaign-issues")\n',
      "scripts/campaign-tracker.py": "x = 1\n"}, None),

    # The forms a quote-immediately-after-the-word pattern would miss. One
    # case each.

    # A single-quoted docstring is prose too; the table declared only the
    # double-quoted form, so a retired name mentioned in one read as code.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 py: a single-quoted docstring is prose",
     {"scripts/x.py": "#!/usr/bin/env python3\n" + SQ
      + "about runtime/holder" + SQ + "\nx = 1\n"}, None),

    # R2 could not read its input: reported, not raised, so R1's findings are
    # not discarded and R3, R4 still run.
    ("R0 a missing .gitignore is reported rather than raised",
     {"spec/x.md": "hi\n", ".gitignore": None}, "R0"),
    ("...and the rules that already ran still print what they found",
     {"spec/x.md": "hi\n", ".gitignore": None}, "R1"),

    # An extensionless script -- the "" entry in the prose table, which the
    # suffix cases never reach. It sits under an assets/, because R6 refuses an
    # extensionless file in a scripts/ of this tree's own.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 an extensionless script's docstring is prose",
     {".claude/skills/s/assets/scripts/x": "#!/usr/bin/env python3\n" + SQ
      + "about runtime/holder" + SQ + "\nx = 1\n"}, None),
    ("R3 ...and its code is still code",
     {".claude/skills/s/assets/scripts/x":
      "#!/usr/bin/env python3\nopen('runtime/holder')\n"}, "R3b"),

    # Shell, which #105 gave a suffix of its own. Before it, every shell script
    # was extensionless and reached PROSE through the "" entry; a `.sh` with no
    # rule of its own is R0, and R0 skips the file, so R3 would stop reading
    # the two hooks' installer entirely.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 sh: a # comment is prose",
     {"scripts/x.sh": "#!/usr/bin/env sh\n# about runtime/holder\n"}, None),
    ("R3 ...and a .sh file's code is still code",
     {"scripts/x.sh": "#!/usr/bin/env sh\ngrep runtime/holder .\n"}, "R3b"),

    # The extensionless-call ban, whose name list is read from the scripts
    # directory rather than written down. Three cases, because the lookahead
    # that lets the correct spellings through is the part that breaks silently:
    # drop it and the first two below still pass while the last two fail.
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("R3 a call to a script here that omits its extension",
     {"scripts/x.py": 'run("scripts/campaign-claim")\n'}, "R3a"),
    # THE THREE ALLOW-LISTS, from the allow side (#237). Each pair is one
    # thing the list admits and one it does not, so neither covers the other.
    ("R3b runtime/ may hold what is derived or a process artifact",
     {"scripts/x.py": 'open("runtime/repos"); open("runtime/guard.log")\n'
                      'open("runtime/agent.pid"); open("runtime/x.lock")\n'}, None),
    # PATH-QUALIFIED SITES, which is how every skill spells a call. The first
    # cut of these three patterns had a `(?<![\w./-])` lookbehind that blocked
    # a preceding slash, so `"$BASE/scripts/..."` was invisible and R3 was
    # NARROWER than the deny list it replaced. One case per pattern.
    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3a a $BASE-qualified call is read like any other",
     {"scripts/x.sh": 'test -x "$BASE/scripts/campaign-bound"\n'}, "R3a"),
    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3b a $CAMPAIGN-qualified runtime path is read too",
     {"scripts/x.sh": 'cat "$CAMPAIGN/runtime/holder"\n'}, "R3b"),
    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3b ...and a path built segment by segment, which no runtime/<name> sees",
     {"scripts/x.py": 'p = d / "runtime" / "claims"\n'}, "R3b"),
    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3c a verb followed by a QUOTED argument is still a call",
     {"scripts/x.sh": '"$BASE/scripts/campaign-claim.py" stood-down "$N"\n',
      "scripts/campaign-claim.py": 'sub.add_parser("take")\n'}, "R3c"),
    ("R3a ...while a token glued to a word is not one of ours",
     {"scripts/x.py": 'p = "myscripts/gone.py"\n'}, None),

    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3b ...but not a record of the work, whatever it is called",
     {"scripts/x.py": 'open("runtime/planner-state.md")\n'}, "R3b"),
    ("R3b ...and the message names the set rather than the retired word",
     {"scripts/x.py": 'open("runtime/holder")\n'}, "R3b"),
    ("R3c a subcommand argparse defines is a call",
     {"scripts/x.py": 'run("scripts/campaign-claim.py take 1 7 topic")\n',
      "scripts/campaign-claim.py": 'sub.add_parser("take")\n'}, None),
    # unguarded: check-tree-shape -- fixtures must spell the names it refuses
    ("R3c ...and one it does not define is not",
     {"scripts/x.py": 'run("scripts/campaign-claim.py stood-down 7")\n',
      "scripts/campaign-claim.py": 'sub.add_parser("take")\n'}, "R3c"),
    # THE SENTENCE THAT IS NOT A CALL. R3c reads code, and code quotes prose:
    # `scripts/campaign-claim.py in a checkout` is a sentence, and `in` is not
    # a subcommand. What tells them apart is what follows the verb.
    ("R3c prose naming the script is not a call",
     {"scripts/x.py": 'DOC = "scripts/campaign-claim.py in a checkout"\n',
      "scripts/campaign-claim.py": 'sub.add_parser("take")\n'}, None),
    # R3c SAYS WHEN IT DID NOT RUN. A `campaign-claim.py` that is here but
    # names no subcommand is `could not look`, not `nothing is allowed` -- and
    # it used to pass silently, printing `0 finding(s)` with the rule off.
    ("R3c a campaign-claim.py naming no subcommand is said, not assumed",
     {"scripts/x.py": 'run("scripts/campaign-claim.py take 1")\n',
      "scripts/campaign-claim.py": "x = 1\n"}, "R0"),

    ("R3a ...and a suite may name a path that is not there",
     {"scripts/x-test.py": 'CASES = [{"scripts/gone.py": "x"}]\n'}, None),

    ("R3 ...and the correct spelling is not a finding",
     {"scripts/x.py": 'run("scripts/campaign-claim.py")\n',
      "scripts/campaign-claim.py": 'sub.add_parser("take")\n'}, None),
    ("R3 ...nor is a suite, whose stem opens with a banned name",
     {"scripts/x.py": 'run("scripts/campaign-claim-test.py")\n',
      "scripts/campaign-claim-test.py": "x = 1\n"}, None),

    # R4
    ("R4 a member repository's file", {"repos/web/a.py": "x = 1\n"}, "R4"),
]


def run_staged_case(staged_files, worktree_files):
    """The hook runs `--staged`, and nothing pinned that it reads the index
    rather than the disk. Stage one tree, then overwrite the working tree with
    another: a guard reading the wrong one gives the opposite verdict."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".gitignore").write_text(IGNORE)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        for rel, body in staged_files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        subprocess.run(["git", "add", "-Af"], cwd=root, check=True)
        for rel, body in worktree_files.items():
            (root / rel).write_text(body)
        return subprocess.run([sys.executable, str(GUARD), "--staged"], cwd=root,
                              capture_output=True, text=True)


def run_case(files):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        if ".gitignore" not in files:
            (root / ".gitignore").write_text(IGNORE)
        for rel, body in files.items():
            if body is None:      # a file this case wants absent
                continue
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                p.write_bytes(body)
            else:
                p.write_text(body)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-Af"], cwd=root, check=True)
        return subprocess.run([sys.executable, str(GUARD)], cwd=root,
                              capture_output=True, text=True)


STAGED_CASES = [
    # unguarded: check-tree-shape -- fixtures must spell the names it bans
    ("--staged judges what is staged, not what is on disk",
     {"AGENTS.md": "t\n\n```sh\ncat runtime/holder\n```\n"},
     {"AGENTS.md": "t\n\nclean now\n"}, "R3b"),
    ("--staged does not fire on a violation only the working tree has",
     {"AGENTS.md": "t\n\nclean\n"},
     {"AGENTS.md": "t\n\n```sh\ncat runtime/holder\n```\n"}, None),
]


def committed_then_staged():
    """A violation already committed, and something clean staged on top.

    Every other fixture stages everything it creates, so the index and the
    file list always agree and never pin `tracked()` honouring its `staged`
    argument. This one leaves a prior violation unstaged, so a `tracked()`
    that ignored `staged` would scan it anyway."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".gitignore").write_text(IGNORE)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "spec").mkdir()
        (root / "spec" / "bad.md").write_text("already here\n")
        subprocess.run(["git", "add", "-Af"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "in", "--no-verify"], cwd=root, check=True)
        (root / "scripts").mkdir()
        (root / "scripts" / "ok.sh").write_text("#!/bin/sh\n")
        subprocess.run(["git", "add", "scripts/ok.sh"], cwd=root, check=True)
        return subprocess.run([sys.executable, str(GUARD), "--staged"], cwd=root,
                              capture_output=True, text=True)


def judge(r, rule):
    """(ok, what was wanted). A clean run is not silence: every run says how
    many paths it read and from where, so a clean verdict is `0 finding(s)`
    beside that reading and not an empty screen."""
    out = r.stdout + r.stderr
    said_what_it_read = "tracked path(s) under " in r.stdout
    if rule:
        return (r.returncode == 1 and f"{rule}\t" in out and said_what_it_read,
                f"a {rule} finding beside the reading")
    return (r.returncode == 0 and "refusing" not in out and said_what_it_read
            and "0 finding(s)" in r.stdout,
            "0 finding(s) beside the reading")


def says_what_it_read():
    """A clean run names its count and its root, and which of the two trees.

    Silence would read the same as a run that examined nothing, which is what a
    wrong checkout and an empty file list both look like -- and the count and
    the root are the two things that tell those apart from a clean tree.
    """
    files = {"spec/x.html": "<p>hi</p>\n"}          # plus the .gitignore: 2
    wrong = []
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        (root / ".gitignore").write_text(IGNORE)
        (root / "spec").mkdir()
        (root / "spec" / "x.html").write_text(files["spec/x.html"])
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-Af"], cwd=root, check=True)
        for args, where in ((["--staged"], "the index"), ([], "the working tree")):
            r = subprocess.run([sys.executable, str(GUARD), *args], cwd=root,
                               capture_output=True, text=True)
            want = f"2 tracked path(s) under {root}, read from {where}"
            if want not in r.stdout:
                wrong.append(f"wanted `{want}`, got: {r.stdout.strip()[:160]!r}")
    return wrong


def main():
    failed = 0
    for line in says_what_it_read():
        failed += 1
        print(f"FAIL  a run says how many paths it read and from where\n      {line}")
    r = committed_then_staged()
    ok, want = judge(r, None)
    if not ok:
        failed += 1
        print(f"FAIL  --staged does not judge a violation this commit does not "
              f"touch\n      wanted {want}, got exit {r.returncode}: "
              f"{(r.stdout + r.stderr).strip()[:160]}")
    for name, staged, worktree, rule in STAGED_CASES:
        r = run_staged_case(staged, worktree)
        ok, want = judge(r, rule)
        if not ok:
            failed += 1
            print(f"FAIL  {name}\n      wanted {want}, got exit {r.returncode}:\n"
                  f"      {(r.stdout + r.stderr).strip()[:200] or '(nothing)'}")
    for name, files, rule in CASES:
        r = run_case(files)
        ok, want = judge(r, rule)
        if not ok:
            failed += 1
            print(f"FAIL  {name}\n      wanted {want}, got exit {r.returncode}:\n"
                  f"      {(r.stdout + r.stderr).strip()[:200] or '(nothing)'}")
    total = len(CASES) + len(STAGED_CASES) + 2
    print(f"{total - failed}/{total} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
