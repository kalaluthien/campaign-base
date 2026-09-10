#!/usr/bin/env python3
# witnesses: Cov_CreateDir, S15_NoLocalDirectory
"""Prove the campaign directory is found by its marker under either name form.

The name form has moved twice -- `campaign-<slug>-<date>`, then bare `<slug>`,
then dated again -- and each move broke a caller that composed the path out of
the slug. So the cases are one per form, plus the two answers that are not a
path: a directory with no marker, and two directories naming one campaign.

THE NAMED FAILING CASE is `a dated directory is the only one carrying the
marker`: the fixture holds `campaign-demo-260910/` and no `demo/`, so a line
spelling `$BASE/$SLUG` resolves to nothing while the reader answers the path.
It reddens exactly the resolution kalaluthien/campaign-base#181 round 2 replaced.

Usage: scripts/campaign-directory-test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = HERE / "campaign-directory.py"
GUARD = HERE / "check-campaign-claim.py"
CLAIM = HERE / "campaign-claim.py"

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        FAILURES.append(name)
        if detail:
            print("      " + detail)


class Fixture:
    """A base root -- a git repository carrying `scripts/campaign-claim.py`,
    which is what `base_above` reads a base by -- with the campaign directories
    asked for. `dirs` maps a directory name to its marker text, or to None for
    a directory carrying no marker at all."""

    def __init__(self, d, dirs):
        self.base = Path(d).resolve() / "base"
        (self.base / "scripts").mkdir(parents=True)
        # THE READER AND THE RULE'S OWNER, copied together: the script imports
        # the guard beside it, so a fixture holding one and not the other would
        # test the import path rather than the reading.
        for src in (READER, GUARD, CLAIM):
            (self.base / "scripts" / src.name).write_text(src.read_text())
            (self.base / "scripts" / src.name).chmod(0o755)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.base)],
                       check=True)
        for name, marker in dirs.items():
            (self.base / name).mkdir()
            if marker is not None:
                (self.base / name / ".campaign").write_text(marker)

    def ask(self, token):
        r = subprocess.run([str(self.base / "scripts" / "campaign-directory.py"),
                            token, str(self.base)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout.splitlines()[0] if r.stdout else "", r


def main() -> int:
    print(f"reading {READER}")

    # ONE CASE PER NAME FORM, each read by its marker and not by its name.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, {"campaign-demo-260910": "1 demo\n"})
        rc, word, r = f.ask("1")
        check("a dated directory is found by the campaign's number",
              rc == 0 and word == str(f.base / "campaign-demo-260910"),
              f"exit {rc}: {word} / {r.stderr[:200]}")
        rc, word, r = f.ask("demo")
        check("...and by its slug, which is the marker's other field",
              rc == 0 and word == str(f.base / "campaign-demo-260910"),
              f"exit {rc}: {word} / {r.stderr[:200]}")
        # THE NAMED FAILING CASE. `$BASE/$SLUG` is a path that does not exist
        # here, so the retired resolution cannot reach the directory this
        # answers with, and no assertion about it passes by coincidence.
        check("...where the retired `$BASE/$SLUG` resolves to nothing",
              not (f.base / "demo").exists())

    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, {"demo": "1 demo\n"})
        rc, word, r = f.ask("1")
        check("the bare slug is the accepted older form and is found too",
              rc == 0 and word == str(f.base / "demo"),
              f"exit {rc}: {word} / {r.stderr[:200]}")

    # A DIRECTORY WITH NO MARKER IS NO CAMPAIGN, which is `none` and not a
    # failure: a campaign this machine holds no directory for is the ordinary
    # state off the bound machine (S15_NoLocalDirectory).
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, {"campaign-demo-260910": None, "scripts-like": None})
        rc, word, r = f.ask("1")
        check("a directory carrying no marker is not a campaign directory",
              rc == 1 and word == "none", f"exit {rc}: {word} / {r.stderr[:200]}")

    # TWO NAMING ONE CAMPAIGN IS NOT AN ANSWER. Sorted order is not a tiebreak,
    # and a close that picked one would delete a directory nobody named.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, {"campaign-demo-260910": "1 demo\n", "demo": "1 demo\n"})
        rc, word, r = f.ask("demo")
        check("two directories naming one campaign is unknown, not a pick",
              rc == 2 and word == "unknown",
              f"exit {rc}: {word} / {r.stderr[:200]}")

    # COULD NOT LOOK IS NOT AN EMPTY ANSWER. A guard that will not import is the
    # reading failing, and answering `none` there would send a close on to
    # scaffold a directory that already exists.
    with tempfile.TemporaryDirectory() as d:
        f = Fixture(d, {"campaign-demo-260910": "1 demo\n"})
        (f.base / "scripts" / "check-campaign-claim.py").write_text(
            "raise RuntimeError('broken')\n")
        rc, word, r = f.ask("1")
        check("a marker reader that will not load answers unknown, not none",
              rc == 2 and word == "unknown",
              f"exit {rc}: {word} / {r.stderr[:200]}")

    print(f"{len(FAILURES)} failing" if FAILURES else "all cases pass")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
