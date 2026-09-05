#!/usr/bin/env python3
"""Prove guard-precision pairs a refusal with the allow that followed it, and
says what it could not read.

Every case runs the shipped script over a SYNTHETIC log written here, never
over a real one: a real log is a moving artifact and a case keyed on it would
pass or fail by what somebody typed this morning.

The pairing is a heuristic on purpose -- a session may be refused, take a
claim, and be allowed, which reads identically -- so what these pin is that the
heuristic does what its docstring says, not that a pair is a defect.

Usage: scripts/guard-precision-test.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRECISION = HERE / "guard-precision.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{(' -- ' + detail) if detail else ''}")


# A REAL SESSION'S ID IS A UUID and the shipped script now counts only those
# by default, so a case's rows have to look like a real session's or they are
# dropped before anything is paired. `S1` and `S2` are two of them; `PROBE` is
# what a hand probe or a suite run leaves behind, and is what the filter is for.
S1 = "7496e7c9-3f96-4a54-8c18-92eb858a36e7"
S2 = "d184e76d-fb49-439d-ac2f-c24cf186af2b"
PROBE = "s1"


def row(at, session, verdict, reason, command="", target="", tool="Bash"):
    return json.dumps({"at": f"2026-09-05T12:{at}:00+00:00", "session": session,
                       "verdict": verdict, "reason": reason, "tool": tool,
                       "command": command, "target": target, "status":
                       2 if verdict == "REFUSED" else 0}, sort_keys=True)


def run(lines, *args, path=None):
    """(exit status, output) for one synthetic log."""
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "guard.log"
        if lines is not None:
            log.write_text("".join(l + "\n" for l in lines))
        r = subprocess.run([sys.executable, str(PRECISION),
                            str(path or log), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


NO_CLAIM = ("gh issue close: a campaign-plane write, and this session holds no "
            "claim covering a write to #9.")
NO_CLAIM_11 = NO_CLAIM.replace("#9", "#11")
COVERED = "gh issue close: cwd /x -> /x; /x/wt is on campaign-1/9-y, a claim."


def main():
    # THE PAIR THE WHOLE FILE IS FOR: refused, then allowed, same session,
    # same issue, inside the window.
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("05", S1, "allowed", COVERED, "gh issue close 9")])
    check("a refusal followed by an allow on the same issue is a suspected "
          "false positive",
          rc == 0 and "1 suspected false positive" in out, out[:400])
    check("...and the pair is printed verbatim, both lines",
          "REFUSED 2026-09-05T12:00" in out and "allowed 2026-09-05T12:05" in out,
          out[:600])

    # ...and each of the three ways it could fail to be one.
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("55", S1, "allowed", COVERED, "gh issue close 9")],
                  "--minutes", "30")
    check("an allow outside the window is not paired; the refusal is held",
          "0 suspected false positive" in out and "1 refusal(s) held" in out,
          out[:400])
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("05", S2, "allowed", COVERED, "gh issue close 9")])
    check("another session's allow is not this session's second try",
          "0 suspected false positive" in out and "1 refusal(s) held" in out,
          out[:400])
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("05", S1, "allowed", COVERED, "gh issue close 12")])
    check("an allow naming another issue is not the same target",
          "0 suspected false positive" in out and "1 refusal(s) held" in out,
          out[:400])

    # THE OTHER TWO TARGET READINGS, one case each: without them the pairing
    # would only ever see `gh issue` calls, and #193's false positive was a
    # `git commit`.
    rc, out = run([row("00", S1, "REFUSED", "Write changes a file.",
                       target="/b/a.md", tool="Write"),
                   row("05", S1, "allowed", "Clause 1.",
                       target="/b/a.md", tool="Write")])
    check("a file tool is paired on its path",
          "1 suspected false positive" in out, out[:400])
    rc, out = run([row("00", S1, "REFUSED", "the command would not split.",
                       "git commit -F - <<M"),
                   row("05", S1, "allowed", "not read for a target.",
                       "git commit -F /tmp/m")])
    check("a shell call is paired on its command's basename",
          "1 suspected false positive" in out, out[:400])

    # A REFUSAL WITH NOTHING TO MATCH ON is neither a pair nor held: folding it
    # into held would report a rule as holding when nothing could have shown
    # otherwise.
    rc, out = run([row("00", S1, "REFUSED", "the hook payload would not read"),
                   row("05", S1, "allowed", COVERED, "gh issue close 9")])
    check("a refusal with no target is counted apart from the held ones",
          "1 with nothing to match on" in out and "0 refusal(s) held" in out,
          out[:400])

    # GROUPED BY THE SENTENCE, numbers replaced: two refusals differing only in
    # the issue number are one row, or the table is one row per call.
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("01", S1, "REFUSED", NO_CLAIM_11, "gh issue close 11")])
    check("two refusals differing only in a number are one row",
          out.count("no claim covering a write to N") == 1
          and "2 refusal(s), 0 allow(s)" in out, out[:600])

    # WHAT IT COULD NOT READ IS NAMED. Three readings kept apart: a log that is
    # not there, a line that will not parse, and a log with nothing in it.
    with tempfile.TemporaryDirectory() as d:
        rc, out = run(None, path=Path(d) / "nope.log")
        check("a log that is not there is named, not skipped",
              "absent, so nothing was read from it" in out, out[:400])
        check("...and a run over no verdicts is not a clean report",
              rc == 1 and "nothing to measure" in out, out[:400])
    rc, out = run(["{not json", row("00", S1, "allowed", COVERED, "gh pr view 1")])
    check("a line that will not parse is counted, not silently dropped",
          "1 line(s) that would not parse" in out, out[:400])

    # The verdict counts themselves, so a table over the wrong rows is visible.
    rc, out = run([row("00", S1, "REFUSED", NO_CLAIM, "gh issue close 9"),
                   row("01", S1, "allowed", COVERED, "gh pr view 1"),
                   row("02", S1, "allowed", COVERED, "gh pr view 2")])
    check("the counts name how many of each verdict were read",
          "1 refusal(s), 2 allow(s)" in out, out[:400])

    # ---- #213: the session filter. A rate over probe rows is not a blurred
    # measurement, it is a measurement of the wrong population, and it reads
    # exactly like the right one.
    #
    # ASSERTED ON THE PAIR COUNT, which is the number the filter is there to
    # protect. A case keyed on the "dropped" line alone would pass with the
    # filter reporting a drop it never made.
    mixed = [row("00", PROBE, "REFUSED", NO_CLAIM, "gh issue close 9"),
             row("05", PROBE, "allowed", COVERED, "gh issue close 9"),
             row("10", S1, "REFUSED", NO_CLAIM, "gh issue close 9")]
    rc, out = run(mixed)
    check("a probe session's refused/allowed pair is not counted",
          "0 suspected false positive" in out and "1 refusal(s)" in out,
          out[:600])
    check("...and the rows it dropped are counted and named by id",
          "2 dropped" in out and f"session {PROBE}" in out, out[:600])
    rc, out = run(mixed, "--all")
    check("...and --all counts them, which is what produced the 100% table",
          "1 suspected false positive" in out and "3 row(s) kept" in out,
          out[:600])
    rc, out = run(mixed, "--sessions", PROBE)
    check("...and --sessions counts the named id and nothing else",
          "1 suspected false positive" in out and "1 dropped" in out,
          out[:600])

    # A suite run leaves an EMPTY session id, which is a third shape and must
    # not read as a real session.
    rc, out = run([row("00", "", "REFUSED", "the hook payload would not read"),
                   row("05", "", "allowed", COVERED, "gh issue close 9")])
    check("a suite run's rows, whose session id is empty, are dropped",
          "0 row(s) kept" in out and "<no session id>" in out, out[:600])
    # ...AND THE TWO ABSENCES ARE KEPT APART. "I read nothing" and "I read 2
    # rows and none was real" are different findings, and the second is the one
    # that says the measurement window has not opened.
    check("...and a log of only foreign rows is not reported as an empty log",
          rc == 1 and "all 2 verdict(s) were dropped" in out
          and "no verdict has been logged yet" not in out, out[:600])

    if not RAN:
        print("FAIL  the suite ran no case at all")
        return 1
    for f in FAILED:
        print(f"FAIL  {f}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
