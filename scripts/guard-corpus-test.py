#!/usr/bin/env python3
"""Prove guard-corpus keeps what the replay needs and drops the rest for a
reason it prints.

Its four filters decide what the guard suite can ever catch, and until a review
read them the fourth was CIRCULAR: it asked the current guard whether it could
split a command and dropped the ones it could not, so a splitter regression
removed its own witnesses from the corpus instead of reddening it. Four real
commands were hidden that way at 1a3138e. That filter is a case here now, and
so is every other.

Synthetic transcripts, written here: the real ones under `~/.claude/projects/`
move every minute, and a case keyed on them passes or fails by what somebody
typed this morning.

Usage: scripts/guard-corpus-test.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "guard-corpus.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


def call(cwd, name="Bash", uid="t1", **inp):
    return json.dumps({"type": "assistant", "cwd": cwd,
                       "timestamp": "2026-09-05T12:00:00Z",
                       "message": {"content": [
                           {"type": "tool_use", "id": uid, "name": name,
                            "input": inp}]}})


def refusal(uid):
    """The shape a blocked PreToolUse leaves in the transcript."""
    return json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": uid,
         "content": "PreToolUse:Bash hook error: [check-campaign-claim.py]: "
                    "check-campaign-claim: REFUSED.\n  no claim."}]}})


def extract(lines, base="/b", extra=()):
    """(rows, stderr) for one synthetic transcript."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "s.jsonl").write_text("".join(l + "\n" for l in lines))
        out = Path(d) / "corpus.jsonl"
        r = subprocess.run(
            [sys.executable, str(CORPUS), "--base", base, "--out", str(out),
             "--transcripts", str(Path(d) / "*.jsonl"), "--days", "3650",
             *extra], capture_output=True, text=True)
        rows = [json.loads(l) for l in out.read_text().splitlines()
                if l.strip()] if out.exists() else []
        return rows, r.stderr, r.returncode


def main():
    # THE FILTER THE REVIEW FOUND CIRCULAR. A command the guard cannot split
    # was ALLOWED when it ran, so a guard refusing it now is the regression the
    # corpus exists to show; dropping it deleted the witness.
    rows, err, _rc = extract([call("/b", command='echo "unterminated')])
    check("a command the guard cannot split is KEPT, not dropped as unread",
          len(rows) == 1 and rows[0]["command"] == 'echo "unterminated',
          f"{rows} {err}")

    # ...and the ordinary reading beside it: a command it CAN split and finds
    # no `gh` in is the 2.3 MB this filter exists to leave out.
    rows, err, _rc = extract([call("/b", command="ls -la /b")])
    check("a splittable command with no gh in it is dropped as allowed unread",
          rows == [] and "1 the guard allows unread" in err, f"{rows} {err}")
    rows, err, _rc = extract([call("/b", command="gh issue close 9")])
    check("...and one with a gh is kept", len(rows) == 1, f"{rows} {err}")
    rows, err, _rc = extract([call("/b", command="ls -la /b")], extra=("--all",))
    check("--all keeps the unread ones too", len(rows) == 1, f"{rows} {err}")

    # FILTER 2: place.
    rows, err, _rc = extract([call("/elsewhere", command="gh issue close 9")])
    check("a call from outside the base is dropped as outside",
          rows == [] and "1 outside the base" in err, f"{rows} {err}")

    # FILTER 3: the verdict at the time. This is what keeps a genuine refusal
    # out of an ALLOW corpus, and it is why filter 1 above can be generous.
    rows, err, _rc = extract([
        call("/b", command="gh issue close 9", uid="t9"), refusal("t9")])
    check("a call the guard refused at the time is dropped as refused",
          rows == [] and "1 the guard refused at the time" in err,
          f"{rows} {err}")

    # FILTER 1 AND THE SIZE AND SECRET CUTS, one case each.
    rows, err, _rc = extract([
        call("/b", command="gh issue close 9 # " + "x" * 300)],
        extra=("--max-bytes", "100"))
    check("a command over --max-bytes is dropped and counted",
          rows == [] and "1 over 100 bytes" in err, f"{rows} {err}")
    rows, err, _rc = extract([
        call("/b", command="gh auth login --with-token ghp_"
                           + "A" * 36)])
    check("a command carrying a token is dropped, not redacted",
          rows == [] and "1 matching a secret pattern" in err, f"{rows} {err}")

    # A FILE PATH IS A KIND AND A TAIL, so a fixture can rebuild it. One case
    # per kind, because the replay has a slot per kind and a wrong kind puts
    # the entry in the wrong checkout.
    # THE CAMPAIGN DIRECTORY IS READ BY EXCLUSION since #181: a slug is a word,
    # so `demo/` and `machinery/` are campaign directories exactly by not being
    # one of the base's own. Both the dated name and a bare slug appear below,
    # and `spec/` is the row that would turn green if the exclusion went.
    for path, kind, tail in (
            ("/b/scripts/x.py", "base", "scripts/x.py"),
            ("/b/spec/campaign/x.als", "base", "spec/campaign/x.als"),
            ("/b/.claude/skills/s/x.md", "base", ".claude/skills/s/x.md"),
            ("/b/runtime/guard.log", "base", "runtime/guard.log"),
            ("/b/README.md", "base", "README.md"),
            ("/b/machinery/notes.md", "campaign", "notes.md"),
            ("/b/machinery/worktrees/7/scripts/x.py", "worktree",
             "scripts/x.py"),
            ("/b/demo-260904/notes.md", "campaign", "notes.md"),
            ("/b/demo-260904/worktrees/7/scripts/x.py", "worktree",
             "scripts/x.py"),
            ("/b/demo-260904/repos/member/code.txt", "member", "code.txt")):
        rows, err, _rc = extract([call("/b", name="Write", file_path=path)])
        check(f"a file under {kind} is stored as that kind and its tail",
              len(rows) == 1 and rows[0].get("kind") == kind
              and rows[0].get("path") == tail, f"{rows} {err}")
    rows, err, _rc = extract([call("/b", name="Write", file_path="/elsewhere/x")])
    check("a file under no base is dropped", rows == [], f"{rows} {err}")

    # ONE ROW PER DISTINCT CALL, with a count: a re-run over a later window is
    # meant to be a diff, and two identical calls are one shape.
    rows, err, _rc = extract([call("/b", command="gh issue close 9", uid="a"),
                              call("/b", command="gh issue close 9", uid="b")])
    check("two identical calls are one row, counted",
          len(rows) == 1 and rows[0]["seen"] == 2, f"{rows} {err}")

    # NOTHING TO READ IS NOT AN EMPTY CORPUS. Writing one over a real corpus
    # would retire the whole replay in silence.
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(
            [sys.executable, str(CORPUS), "--base", "/b",
             "--out", str(Path(d) / "c.jsonl"),
             "--transcripts", str(Path(d) / "none" / "*.jsonl")],
            capture_output=True, text=True)
        check("no transcript matched is a refusal, not an empty corpus",
              r.returncode != 0 and "refusing to write an empty corpus"
              in r.stderr, r.stderr[:200])
        check("...and nothing was written",
              not (Path(d) / "c.jsonl").exists())

    if not RAN:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in FAILED:
        print(f"FAIL  {f}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
