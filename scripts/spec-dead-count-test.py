#!/usr/bin/env python3
# witnesses: S9_DeadElimination
"""Prove spec-dead-count.py lists a scenario no suite witnesses, and only that one.

`S9_DeadElimination` is the removal of a scenario nothing witnesses, beside a
code path that stays tied through another. Which scenario that is gets judged
outside the model, from the candidates this script prints; so the case is the
fixture S9 starts from: one code path, its suite declaring `S1_Live`, and
`S2_Dead` declared by nothing.

THE NAMED FAILING CASE is `the dead scenario is listed, the live one is not`:
it reddens a reader that drops the declaration filter (every command listed)
or reads declarations off no suite (both listed), which is the difference
between a candidate set and the whole snapshot.

Usage: scripts/spec-dead-count-test.py
"""
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "spec-dead-count.py"

harness = importlib.import_module("suite-harness-test")
check = harness.check

MODULE = "spec/demo/checks.als"
FIXTURE = {
    "spec/commands.snapshot.json": json.dumps({"commands": [
        [MODULE, "run", "S1_Live"], [MODULE, "run", "S2_Dead"]]}),
    MODULE: ("pred S1_Live { some univ }\npred S2_Dead { no univ }\n"
             "run S1_Live expect 1\nrun S2_Dead expect 1\n"),
    "scripts/demo.py": "print('demo')\n",
    "scripts/demo-test.py": "# witnesses: S1_Live\nprint('S1_Live')\n",
}


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args, str(root)],
                          capture_output=True, text=True)


def main() -> int:
    print(f"reading {SCRIPT}")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        harness.write_tree(root, FIXTURE)
        harness.git(root, "init", "-q", "-b", "main", check=True)
        harness.git(root, "add", "-A", check=True)

        r = run(root, "--mode", "unwitnessed")
        lines = r.stdout.splitlines()
        rows = [l.split("\t") for l in lines[1:]]
        check("unwitnessed exits 0", r.returncode == 0, f"exit {r.returncode}: {r.stderr[:300]}")
        check("the count line counts one of two snapshot commands",
              lines[:1] and lines[0].startswith("unwitnessed\t1\tof 2 snapshot commands"),
              repr(lines[:1]))
        check("the dead scenario is listed, the live one is not",
              [x[2] for x in rows] == ["S2_Dead"], repr(rows))
        check("its row carries the entity and the reason",
              rows[:1] and rows[0][1] == "demo" and "declared by no suite" in rows[0][3],
              repr(rows[:1]))

        r = run(root)
        modes = [l.split("\t")[0] for l in r.stdout.splitlines() if l.split("\t")[1:2] != ["-"]]
        check("every mode runs over the fixture and exits 0",
              r.returncode == 0 and {"defs", "unwitnessed", "unpaired", "duplicate",
                                     "undefined", "untied", "premise", "mismatch"} <= set(modes),
              f"exit {r.returncode}: {r.stderr[:300]}")
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
