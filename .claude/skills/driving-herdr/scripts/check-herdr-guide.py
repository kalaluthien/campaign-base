#!/usr/bin/env python3
"""Say whether references/guide.md still equals what the installed herdr prints.

    check-herdr-guide.py          exit 0 identical, 1 differs, 2 could not tell
    check-herdr-guide.py write    replace guide.md with `herdr --skill`, whole

guide.md is herdr's own text, byte for byte, so that an upgrade replaces it and
nothing of ours is lost in the replacement. That identity is the one thing this
reads. It has no caller in a commit hook on purpose: the guide goes stale when
herdr is upgraded, which no commit here causes, and a guard that judged the
machine's herdr would refuse commits that touched nothing of it.

Every answer says what was read and from where: the herdr on PATH and its
version, the guide's path and the commit that last wrote it. `2` is for a
question that could not be read -- no `herdr`, a `--skill` that fails -- and is
never folded into `1`, since "differs" licenses a rewrite and "unknown" does not.
"""
import difflib
import shutil
import subprocess
import sys
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1] / "references" / "guide.md"


def out(*argv):
    r = subprocess.run(argv, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main(argv):
    if argv not in ([], ["write"]):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    herdr = shutil.which("herdr")
    if herdr is None:
        print("unknown: no `herdr` on PATH, so there is nothing to compare "
              f"{GUIDE} with")
        return 2
    version = (out(herdr, "--version") or "herdr ?").strip()
    theirs = out(herdr, "--skill")
    if not theirs:
        print(f"unknown: `{herdr} --skill` ({version}) printed nothing or failed")
        return 2
    ours = GUIDE.read_text() if GUIDE.exists() else ""
    wrote = (out("git", "-C", str(GUIDE.parent), "log", "-1",
                 "--format=%h %cs", "--", GUIDE.name) or "").strip() or "uncommitted"
    if ours == theirs:
        print(f"identical: {GUIDE} (last written {wrote}) equals "
              f"`{herdr} --skill` ({version})")
        return 0
    changed = [l for l in difflib.unified_diff(
        ours.splitlines(), theirs.splitlines(), "guide.md", version, lineterm="", n=0)
        if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    if argv == ["write"]:
        GUIDE.write_text(theirs)
        print(f"wrote: {GUIDE} from `{herdr} --skill` ({version}), "
              f"{len(changed)} changed line(s) against {wrote}. Each one is a "
              f"references/facts.md entry to re-probe or remove.")
        return 0
    print(f"differs: {GUIDE} (last written {wrote}) against `{herdr} --skill` "
          f"({version}), {len(changed)} changed line(s):")
    for l in changed:
        print("  " + l[:160])
    print(f"`{Path(__file__).name} write` replaces it whole.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
