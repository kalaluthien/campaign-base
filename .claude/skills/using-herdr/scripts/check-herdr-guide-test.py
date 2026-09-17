#!/usr/bin/env python3
# witnesses: HG1_AGuideUnlikeHerdrsTextDiffers, HG1b_AnUnreadableHerdrLicensesNoRewrite
"""Prove check-herdr-guide.py tells identical, differs and unknown apart.

Each case copies the script into a throwaway skill tree, since it finds
guide.md from its own path, and runs it as a process against a fake `herdr`
on PATH. The differing guide is the one this repository held at v0.8.2,
`fixtures/guide-v0.8.2.md`, against a fake printing other text.

Usage: .claude/skills/using-herdr/scripts/check-herdr-guide-test.py
"""
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4] / "scripts"))
harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-herdr-guide.py"
OLD = (HERE / "fixtures" / "guide-v0.8.2.md").read_text()
NEW = OLD.replace("within five seconds", "within FIVE seconds") + "- a new rule\n"
FAKE = """#!/bin/sh
case "$1" in
  --version) echo "herdr 9.9.9" ;;
  --skill) cat "$(dirname "$0")/skill.txt" ;;
esac
"""
BROKEN = "#!/bin/sh\nexit 3\n"


def run(guide, fake_body=FAKE, skill=NEW, argv=(), herdr=True, commits=False):
    root = Path(tempfile.mkdtemp(prefix="herdr-guide-"))
    try:
        (root / "skill/scripts").mkdir(parents=True)
        (root / "skill/references").mkdir()
        shutil.copy(SCRIPT, root / "skill/scripts")
        if guide is not None:
            (root / "skill/references/guide.md").write_text(guide)
        stamp = None
        if commits:
            # The guide is committed first and a sibling after it, so a `git
            # log` that forgot to name the guide reports the sibling's commit.
            refs = root / "skill/references"
            harness.git(root, "init", "-q")
            for name in ("guide.md", "facts.md"):
                (refs / name).touch()
                harness.git(root, "add", str(refs / name))
                harness.git(root, "-c", "user.name=t", "-c", "user.email=t@t",
                            "commit", "-q", "-m", name)
                if name == "guide.md":
                    stamp = harness.git(root, "log", "-1", "--format=%h").stdout.strip()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        if herdr:
            (bin_dir / "herdr").write_text(fake_body)
            (bin_dir / "herdr").chmod(0o755)
            (bin_dir / "skill.txt").write_text(skill)
        # git stays reachable for the "last written" line; herdr is only ours.
        path = os.pathsep.join([str(bin_dir), "/usr/bin", "/bin"])
        r = subprocess.run([sys.executable, str(root / "skill/scripts" / SCRIPT.name), *argv],
                           capture_output=True, text=True, env={**os.environ, "PATH": path})
        g = root / "skill/references/guide.md"
        said = r.stdout + r.stderr
        return r.returncode, (said, stamp) if commits else said, g.read_text() if g.exists() else None
    finally:
        shutil.rmtree(root, True)


def main():
    code, said, _ = run(NEW)
    check("identical is 0", code == 0 and said.startswith("identical:"), said)
    check("identical names the version read", "herdr 9.9.9" in said, said)

    code, said, after = run(OLD)
    check("the v0.8.2 guide differs, 1", code == 1 and said.startswith("differs:"), said)
    check("differs names the version and the count", "herdr 9.9.9" in said and "3 changed line(s)" in said, said)
    check("differs shows the changed text", "within FIVE seconds" in said, said)
    check("a check never writes", after == OLD)

    code, said, after = run(OLD, argv=["write"])
    check("write replaces the guide whole, 0", code == 0 and after == NEW, said)
    check("write names what to re-probe", "facts.md" in said, said)

    code, said, after = run(None, argv=["write"])
    check("write creates a missing guide", code == 0 and after == NEW, said)

    code, (said, stamp), _ = run(OLD, commits=True)
    check("differs names the commit that last wrote the guide, not a sibling's",
          bool(stamp) and f"last written {stamp} " in said, f"{stamp!r}: {said[:200]}")
    code, said, _ = run(OLD)
    check("a guide no commit holds says so", "last written uncommitted" in said, said[:200])

    code, said, _ = run(OLD, herdr=False)
    check("no herdr is unknown, 2, never differs", code == 2 and said.startswith("unknown:"), said)

    code, said, after = run(OLD, fake_body=BROKEN, argv=["write"])
    check("a failing --skill is unknown and writes nothing", code == 2 and after == OLD, said)

    code, said, after = run(OLD, skill="", argv=["write"])
    check("an empty --skill never empties the guide", code == 2 and after == OLD, said)

    code, said, _ = run(OLD, argv=["refresh"])
    check("an unknown verb is 2", code == 2, said)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
