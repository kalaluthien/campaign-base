#!/usr/bin/env python3
# witnesses: SR1_WholeReadOfALongFileIsSteered, SR1b_ARangeADiffOrAShortFilePasses
"""Prove check-read-range.py steers a whole Read of a long file, and nothing else.

The table runs `decide` against files written to a fixture directory, one
case per outcome: steered, a diff exempt by its name or its text, a notebook,
a ranged read, an offset near the end and one from the top, a short file at
the threshold, a last line with no newline, a binary file, a missing one, and
a tool that is not Read. Each is then broken in turn by a
mutation of the script's own text and must go red by its own assertion.
Three more cases run the script as the harness does -- a process, the payload
on stdin -- for the contract `decide` cannot show: exit 2 and stderr on a
denial, exit 0 and one stdout line on a pass, and a loud pass on a payload
that would not read.

Usage: scripts/check-read-range-test.py
"""
import importlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

SCRIPT = Path(__file__).resolve().parent / "check-read-range.py"
SOURCE = SCRIPT.read_text()
ROOT = Path(tempfile.mkdtemp(prefix="read-range-"))


def lines(n):
    return "".join(f"line {i}\n" for i in range(1, n + 1))


FILES = {"long.py": lines(351), "short.py": lines(350), "review.diff": lines(400),
         "blob.bin": b"\0" + b"x\n" * 400, "big.ipynb": lines(400),
         "saved.txt": "From github.com:o/r\ndiff --git a/x b/x\n" + lines(400),
         "open-end.py": lines(350) + "line 351"}
for name, body in FILES.items():
    (ROOT / name).write_bytes(body if isinstance(body, bytes) else body.encode())


def payload(name, tool="Read", **inp):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(ROOT),
            "tool_input": {"file_path": str(ROOT / name), **inp}}


def load(source):
    m = types.ModuleType("readrange")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


def decided(name, want_status, want_word, **inp):
    def case(m):
        status, line = m.decide(payload(name, **inp))
        return status == want_status and want_word in line, (status, line)
    return case


CASES = {
    "steered": decided("long.py", 2, "grep -n"),
    "steered names the count": decided("long.py", 2, "351 of 351 lines"),
    "an offset from the top is steered": decided("long.py", 2, "from line 1", offset=1),
    "diff exempt": decided("review.diff", 0, "a diff"),
    "a saved diff exempt by its text": decided("saved.txt", 0, "holds a diff"),
    "notebook": decided("big.ipynb", 0, "notebook"),
    "ranged": decided("long.py", 0, "ranged", offset=10, limit=40),
    "ranged by offset near the end": decided("long.py", 0, "52 of 351", offset=300),
    "short at the threshold": decided("short.py", 0, "350 of 350"),
    "no trailing newline still counts": decided("open-end.py", 2, "351 of 351"),
    "binary": decided("blob.bin", 0, "not text"),
    "missing": decided("gone.py", 0, "could not read"),
    "not a Read": decided("long.py", 0, "not a Read", tool="Bash"),
}

MUTATIONS = [
    ("the diff exemption dropped", "if path.endswith(DIFF_SUFFIXES):", "if False:", "diff exempt"),
    ("the diff text ignored", "if DIFF_LINE.search(data):", "if False:",
     "a saved diff exempt by its text"),
    ("the notebook exemption dropped", "if path.endswith(NOTEBOOK_SUFFIX):", "if False:", "notebook"),
    ("the range ignored", 'if inp.get("limit") is not None or inp.get("pages") is not None:',
     "if False:", "ranged"),
    ("the offset ignored", 'start = max(int(inp.get("offset") or 1), 1)', "start = 1",
     "ranged by offset near the end"),
    ("an offset read as a range", 'if inp.get("limit") is not None or inp.get("pages") is not None:',
     'if any(inp.get(k) is not None for k in ("offset", "limit", "pages")):',
     "an offset from the top is steered"),
    ("the threshold made inclusive", "if returned <= LONG_LINES:", "if returned < LONG_LINES:",
     "short at the threshold"),
    ("the last line without a newline dropped",
     '(1 if data and not data.endswith(b"\\n") else 0)', "0", "no trailing newline still counts"),
    ("the denial turned to a pass", "    return 2, (", "    return 0, (", "steered"),
    ("the binary test dropped", 'if b"\\0" in data:', "if False:", "binary"),
    ("the tool not read", 'if payload.get("tool_name") != "Read":', "if False:", "not a Read"),
]


def run(stdin):
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin,
                          capture_output=True, text=True)


def main():
    harness.mutate(SOURCE, load, CASES, MUTATIONS)
    p = run(json.dumps(payload("long.py")))
    check("process: a denial exits 2 on stderr", p.returncode == 2 and "grep -n" in p.stderr
          and not p.stdout, (p.returncode, p.stdout, p.stderr))
    p = run(json.dumps(payload("short.py")))
    check("process: a pass exits 0 with one stdout line", p.returncode == 0
          and p.stdout.count("\n") == 1 and "short.py" in p.stdout, (p.returncode, p.stdout, p.stderr))
    p = run("not json")
    check("process: a payload that would not read passes, loudly", p.returncode == 0
          and "could not judge" in p.stdout, (p.returncode, p.stdout, p.stderr))
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
