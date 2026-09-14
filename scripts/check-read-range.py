#!/usr/bin/env python3
"""Steer a whole Read of a long file to a grep and a bounded range.

A PreToolUse hook on `Read`, which install-hooks.sh registers in
~/.claude/settings.json, so it fires for every session on this machine and
every subagent of one, campaign work or not. The model is `steered` in
spec/campaign/session/system.als; the numbers below are this script's alone.

THE RULE, STATED HERE ONCE

  A Read naming `offset`, `limit` or `pages` is ranged and passes.
  A path ending in one of DIFF_SUFFIXES passes: a review reads its diff whole,
  and every line of it is the point.
  A file of more than LONG_LINES lines, read with no range, is denied, and the
  reason tells the session to find its lines with `grep -n` and read that part.
  Anything else passes: a short file, a file that is not text (a NUL byte in
  it: an image, a PDF), a path that is no readable file -- the Read reports
  that itself.

WHY THESE NUMBERS (rule-check#412 and #443)

  350 lines is #412's threshold. Over it, files not diffs took 10,528,650 of
  29,418,523 read bytes, and a whole Read 3,501,287 of those, against 1,065,366
  for an unranged `cat` or `sed`; `sed -n a,bp` paging took 4,061,216 and is
  not judged here. #429's experiments 4 and 5 answered every anchored question
  from a grep and a range at 2.3% to 9.1% of the bytes.

WHAT IT SAYS

  One line naming the file, what it read of it, and which branch it took:
  on stdout when it passes, which the harness does not put in the model's
  context, and on stderr with exit 2 when it denies, which it does. A failure
  of this script is a pass that says so -- a refusal here would turn a bug
  into a wall in front of every Read on the machine.

Usage: a PreToolUse hook; the payload arrives on stdin.
"""
import json
import os
import sys

LONG_LINES = 350
DIFF_SUFFIXES = (".diff", ".patch")
RANGE_KEYS = ("offset", "limit", "pages")


def decide(payload):
    """(exit status, the line to print) for one hook payload."""
    inp = payload.get("tool_input") or {}
    path = os.path.join(payload.get("cwd") or "", os.path.expanduser(str(inp.get("file_path") or "")))
    if payload.get("tool_name") != "Read":
        return 0, f"check-read-range: passed, {payload.get('tool_name')!r} is not a Read"
    if any(inp.get(k) is not None for k in RANGE_KEYS):
        return 0, f"check-read-range: passed {path}: ranged"
    if path.endswith(DIFF_SUFFIXES):
        return 0, f"check-read-range: passed {path}: a diff, read whole"
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as e:
        return 0, f"check-read-range: passed {path}: could not read it ({e.__class__.__name__})"
    if b"\0" in data:
        return 0, f"check-read-range: passed {path}: not text"
    count = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    if count <= LONG_LINES:
        return 0, f"check-read-range: passed {path}: {count} lines, at most {LONG_LINES}"
    return 2, (
        f"check-read-range: STEERED. {path}: {count} lines, over {LONG_LINES}, "
        f"read with no offset or limit.\n"
        f"  Find the lines you need first: grep -n '<pattern>' {path}\n"
        f"  then Read that part with offset and limit, or sed -n <a>,<b>p.")


def main():
    try:
        status, line = decide(json.load(sys.stdin))
    except Exception as e:  # noqa: BLE001 -- a bug here must not block every Read
        status, line = 0, f"check-read-range: could not judge this Read ({e.__class__.__name__}: {e}); passed"
    print(line, file=sys.stderr if status else sys.stdout)
    return status


if __name__ == "__main__":
    sys.exit(main())
