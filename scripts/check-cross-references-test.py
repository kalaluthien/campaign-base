#!/usr/bin/env python3
"""Prove check-cross-references fires where it must and stays quiet where it must not.

The guard reads a git tree, so every case builds a throwaway repository and runs
the shipped script over it. Its measure is not how many cases pass but how many
ways of breaking the guard at least one case notices -- so each row that expects
a finding is aimed at ONE branch, and each row that expects quiet names a
boundary somebody would otherwise widen the guard straight past.

Two boundaries carry most of the weight, and both were found by watching a
throwaway version get them wrong:

  * where a citation's name ends. A `§` runs into ordinary prose, so the rows
    with a comma, a bracket, a full stop and a following word are what stop a
    delimiter-guessing rewrite; and `The bindings say` is what stops the word
    boundary being dropped from the prefix match.
  * dangling versus undecided. `bold prose` and `no rule for this shape` must
    come out of different branches with different exit statuses, because a guard
    that folds them reports a tree clean while a whole class of pointer is
    unchecked.

Usage: scripts/check-cross-references-test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "check-cross-references.py"

SKILL = ".claude/skills/demo"

# Every fixture repository gets this base, so a case only writes what it is
# about. AGENTS.md is the default target of an unqualified `§`.
BASE = {
    "AGENTS.md": (
        "# demo\n"
        "\n"
        "## The binding\n"
        "\n"
        "Text.\n"
        "\n"
        "## ID, directory, branch\n"
        "\n"
        "Text.\n"
        "\n"
        "## The campaign issue body\n"
        "\n"
        "**Compare then write the campaign issue body.** This is prose, not a\n"
        "heading, and citing it is a shape the guard has no rule for.\n"
        "\n"
        "```sh\n"
        "# Fenced heading\n"
        "echo hi\n"
        "```\n"
    ),
    "spec/campaign/orchestration/system.als": "sig S {}\n",
    f"{SKILL}/SKILL.md": "# demo skill\n",
    f"{SKILL}/references/gotchas.md": "# gotchas\n",
    f"{SKILL}/assets/sub-issue.md": "# sub-issue\n",
    # The two roots S5 asks: the tree's own, and the citing file's skill.
    "scripts/campaign-tracker.py": "#!/usr/bin/env python3\n",
    f"{SKILL}/scripts/demo-helper.sh": "#!/bin/sh\n",
}

# (name, {path: contents}, expected outcome)
#   None  -- exit 0 and no DANGLING/UNDECIDED line
#   ("DANGLING", substring)  -- exit 2 and that line present
#   ("UNDECIDED", substring) -- exit 3 and that line present
CASES = [
    # ---- S1: where the name ends. Each row is one shape of trailing prose.
    ("S1 a citation closed by a bracket",
     {"a.md": "See (`AGENTS.md` § The binding), so this step asks.\n"}, None),
    ("S1 a citation closed by a full stop",
     {"a.md": "It is `AGENTS.md` § The campaign issue body.\n"}, None),
    ("S1 a citation followed by a word",
     {"a.md": "File it as `AGENTS.md` § The binding says.\n"}, None),
    ("S1 a heading holding commas is not cut at the first one",
     {"a.md": "Nowhere to write (`AGENTS.md` § ID, directory, branch). Step 2.\n"},
     None),
    ("S1 an unqualified citation resolves against AGENTS.md",
     {"a.md": "Name it per § The binding, which says so.\n"}, None),
    # The qualifier must be a NON-default file, or the row passes on the
    # AGENTS.md fallback whether or not the previous line was read at all --
    # which is a row that pins nothing.
    ("S1 a qualifier on the previous line is still the qualifier",
     {"a.md": f"It is stated in `{SKILL}/references/gotchas.md`\n"
              "§ gotchas, which says so.\n"}, None),
    ("S1 a wrapped AGENTS.md qualifier, the shape the tree actually writes",
     {"a.md": "The holding session is retired (`AGENTS.md`\n"
              "§ The binding), so this step asks only what is live.\n"}, None),
    ("S1 a name wrapped across a line still resolves",
     {"a.md": "It is `AGENTS.md` § ID, directory,\nbranch. Step 2 follows.\n"},
     None),
    ("S1 a citation qualified by another file in the tree",
     {"a.md": f"See `{SKILL}/references/gotchas.md` § gotchas here.\n"}, None),

    # ---- S1 dangling. The name is read and the target does not hold it.
    ("S1 a name no heading prefixes",
     {"a.md": "See `AGENTS.md` § No Such Section here.\n"},
     ("DANGLING", "no heading this name prefixes")),
    ("S1 the word boundary: a longer word starting with a heading",
     {"a.md": "See `AGENTS.md` § The bindings say so.\n"},
     ("DANGLING", "no heading this name prefixes")),
    ("S1 a heading that exists only inside a fence is not a heading",
     {"a.md": "See `AGENTS.md` § Fenced heading here.\n"},
     ("DANGLING", "no heading this name prefixes")),

    # ---- S1 undecided. The two branches that must not read as dangling.
    ("U1 a citation naming bold prose, not a heading",
     {"a.md": "See `AGENTS.md` § Compare then write the campaign issue body.\n"},
     ("UNDECIDED", "U1")),
    ("U3 a citation whose target file is not there",
     {"a.md": "See `MISSING.md` § The binding here.\n"},
     ("UNDECIDED", "U3")),

    # ---- S2: a literal skill path, against the filesystem.
    ("S2 a skill path that is there",
     {"a.md": f"Fill it from `{SKILL}/assets/sub-issue.md`.\n"}, None),
    ("S2 a skill directory named with its trailing slash",
     {"a.md": f"Templates live in `{SKILL}/assets/`.\n"}, None),
    ("S2 a skill path that is not there",
     {"a.md": f"Fill it from `{SKILL}/assets/gone.md`.\n"},
     ("DANGLING", "S2: nothing at this path")),

    # ---- S3: a spec path.
    ("S3 a spec file that is there",
     {"a.md": "The contract is `spec/campaign/orchestration/system.als`.\n"}, None),
    ("S3 a spec file that is not there",
     {"a.md": "The contract is `spec/campaign/orchestration/gone.als`.\n"},
     ("DANGLING", "S3: nothing at this path")),

    # ---- S4: relative, and resolved against the SKILL ROOT rather than the
    # citing file's own directory. The second row is the one that fails when
    # the root is taken as the containing directory.
    ("S4 from a SKILL.md, against the skill root",
     {f"{SKILL}/SKILL.md": "# demo skill\n\nRead `references/gotchas.md`.\n"},
     None),
    ("S4 from a file one level down, still against the skill root",
     {f"{SKILL}/references/launching.md": "Read `assets/sub-issue.md`.\n"}, None),
    ("S4 a relative path that is not there",
     {f"{SKILL}/SKILL.md": "# demo skill\n\nRead `references/gone.md`.\n"},
     ("DANGLING", "S4: nothing at")),
    ("U2 the same shape in a file inside no skill",
     {"a.md": "Read `references/gotchas.md`.\n"},
     ("UNDECIDED", "U2")),

    # ---- Not a reference. Each row is a bucket that must not become a finding.
    ("a placeholder path names a form, not a file",
     {"a.md": "A delegate runs in `<campaign>/repos/<repo>/`.\n"}, None),
    ("a placeholder inside a real prefix is a template, not a truncated path",
     {"a.md": f"Copy `{SKILL}/assets/agents/<kind>.md` across.\n"}, None),
    ("a glob is a template",
     {"a.md": "Run it over `spec/campaign/*/*.als`.\n"}, None),
    ("a citation qualified by a path outside the repository is external",
     {"a.md": "The fast-forward `~/.claude/CLAUDE.md` § Git prescribes.\n"},
     None),
    ("a path shape the guard claims no rule over is left alone",
     {"a.md": "The workflow is `.github/workflows/check.yml` and no more.\n"},
     None),

    # ---- S5: a script path, resolved against EITHER root.
    ("S5 a script at the tree root resolves",
     {"a.md": "Run `scripts/campaign-tracker.py` for it.\n"}, None),
    ("S5 a skill's own script resolves from inside that skill",
     {f"{SKILL}/references/x.md": "Run `scripts/demo-helper.sh` first.\n"},
     None),
    # THE ROW THE TWO-ROOT RULE EXISTS FOR: prose inside a skill naming the
    # REPOSITORY's script. Asking only the skill root would flag this, and 13
    # references in the real tree have this shape.
    ("S5 a skill citing the repository's script resolves too",
     {f"{SKILL}/references/y.md": "Read `scripts/campaign-tracker.py` first.\n"},
     None),
    # THE `$BASE/` FORM, which is how a skill spells a command a session runs.
    # `RUN` cannot hold a `$`, so these arrived as `BASE/...` and matched no
    # shape at all: 17 script paths went unchecked, the one #227's own sweep
    # had just repaired among them.
    ("S5 reads a `$BASE/`-prefixed script path",
     {"a.md": "Run `\"$BASE/scripts/campaign-tracker.py\" bind 1` for it.\n"},
     None),
    ("S5 a `$BASE/`-prefixed script at neither root dangles",
     {"a.md": "Run `\"$BASE/scripts/gone.py\" bind 1` for it.\n"},
     ("DANGLING", "scripts/gone.py")),
    ("S2 reads a `$BASE/`-prefixed skill path too",
     {"a.md": f"Run `\"$BASE/{SKILL}/scripts/gone.sh\"` for it.\n"},
     ("DANGLING", f"{SKILL}/scripts/gone.sh")),

    ("S5 a script at neither root dangles",
     {"a.md": "Run `scripts/gone.py` for it.\n"},
     ("DANGLING", "scripts/gone.py")),
    ("S5 fires inside an .als file too, where the comments are the spec",
     {"spec/campaign/session/system.als": "/* `scripts/gone.py` owns it. */\n"},
     ("DANGLING", "scripts/gone.py")),

    # ---- Precedence: undecided outranks dangling, and both are printed.
    ("undecided and dangling together report both and exit 3",
     {"a.md": "See `AGENTS.md` § No Such Section here.\n"
              "\nAlso read `references/gotchas.md`.\n"},
     ("UNDECIDED", "U2")),
]


def build(tmp, files):
    root = Path(tmp)
    merged = dict(BASE)
    merged.update(files)
    for rel, text in merged.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                   capture_output=True)
    return root


def run_case(files, args=()):
    with tempfile.TemporaryDirectory() as tmp:
        root = build(tmp, files)
        return subprocess.run(
            [sys.executable, str(GUARD), *args],
            cwd=str(root), capture_output=True, text=True,
        )


def check(name, r, want):
    """One row's verdict, and the whole message when it is wrong."""
    out = r.stdout + r.stderr
    findings = [ln for ln in r.stdout.splitlines()
                if ln.startswith(("DANGLING", "UNDECIDED"))]
    if want is None:
        ok = r.returncode == 0 and not findings
        wanted = "exit 0 and no finding"
    else:
        kind, needle = want
        ok = (r.returncode == (2 if kind == "DANGLING" else 3)
              and any(ln.startswith(kind) and needle in ln for ln in findings))
        wanted = f"exit {2 if kind == 'DANGLING' else 3} and a {kind} line " \
                 f"holding {needle!r}"
    if ok:
        return 0
    print(f"FAIL  {name}\n      wanted {wanted}, got exit {r.returncode}:\n"
          f"      {out.strip()[:400] or '(nothing)'}")
    return 1


def main():
    if not GUARD.exists():
        print(f"the guard is not at {GUARD}")
        return 1
    failed = 0
    for name, files, want in CASES:
        failed += check(name, run_case(files), want)

    extra = 0

    # --staged reads the index, not the worktree. A violation staged and then
    # reverted on disk must still be refused, or a pre-commit hook judges a tree
    # that is not the one being committed.
    extra += 1
    with tempfile.TemporaryDirectory() as tmp:
        root = build(tmp, {"a.md": "See `AGENTS.md` § No Such Section here.\n"})
        (root / "a.md").write_text("Nothing to see.\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(GUARD), "--staged"],
                           cwd=str(root), capture_output=True, text=True)
        if r.returncode != 2 or "DANGLING" not in r.stdout:
            failed += 1
            print("FAIL  --staged judges the index, not the worktree\n"
                  f"      wanted exit 2, got {r.returncode}: "
                  f"{(r.stdout + r.stderr).strip()[:300]}")

    # The summary is the evidence that the guard ran at all: a bare verdict word
    # is the shape that gets trusted for months while enforcing nothing.
    extra += 1
    r = run_case({})
    if not ("file(s) under" in r.stdout
            and "reference(s):" in r.stdout
            and "read from the working tree" in r.stdout):
        failed += 1
        print("FAIL  a clean run still says what it read and from where\n"
              f"      got: {r.stdout.strip()[:300]}")

    # --list prints the buckets that are not verdicts, so the scope boundary is
    # readable rather than implied.
    extra += 1
    r = run_case({"a.md": "Run it over `spec/campaign/*/*.als`.\n"}, args=("--list",))
    if "template\t" not in r.stdout:
        failed += 1
        print("FAIL  --list shows the template bucket\n"
              f"      got: {r.stdout.strip()[:300]}")

    total = len(CASES) + extra
    print(f"{total - failed}/{total} cases pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
