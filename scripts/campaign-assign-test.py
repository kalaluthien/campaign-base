#!/usr/bin/env python3
# witnesses: SessionCompactsBetweenSubIssues
"""Cases for campaign-assign.py, over a stubbed `herdr` on PATH and a fake
HOME holding the session's transcript.

AN ALLOW CASE BESIDE EVERY REFUSAL. A guard is only worth its refusals if the
thing it admits still gets through, and a refusing check with no allow case
reads identically to one that refuses everything.

The stub answers `agent list` and `agent prompt`, logs every prompt, and
refuses everything else -- so a case passes only if the reading came from
the transcript and never from the pane. "The assignment was sent" is
asserted on what herdr was ASKED, never on an exit status. How the
transcript is read -- order, forgery, another pane's release -- is
campaign-heartbeat-test.py's, since that reader is the heartbeat's.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGN = HERE / "campaign-assign.py"

RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}" + (f" -- {detail}" if detail else ""))


# The anchor as `campaign-claim.py` prints it, PANE AND ALL. Spelled here
# rather than imported so that a case fails if the two ever disagree.
RELEASED = "campaign-claim: released machinery/195-token-tally in w1:p2"


def released(ts):
    """A tool result carrying this session's release, as the transcript
    records the Bash call that ran `campaign-claim.py release`."""
    return {"type": "user", "timestamp": ts, "message": {"content": [
        {"type": "tool_result", "content": f"sent /compact\n{RELEASED}"}]}}


def compacted(ts):
    return {"type": "system", "subtype": "compact_boundary", "timestamp": ts,
            "compactMetadata": {"postTokens": 9000}}


T1, T2 = "2026-09-10T10:00:00.000Z", "2026-09-10T10:01:00.000Z"
COMPACTED = [released(T1), compacted(T2)]
STALE = [released(T1)]
FRESH = [{"type": "user", "timestamp": T1, "message": {"content": "hello"}}]


def agent(sid, name, pane, status="idle"):
    return {"agent_session": {"value": sid}, "name": name, "cwd": "/tmp",
            "pane_id": pane, "agent_status": status}


HERDR = """#!/bin/sh
log="%s"
case "$1 $2" in
  "agent list")
    cat <<'JSON'
%s
JSON
    exit 0 ;;
  "agent prompt")
    printf 'HERDR_ENV=%%s pane=%%s prompt=%%s\\n' "${HERDR_ENV:-unset}" "$3" "$4" >> "$log"
    exit %s ;;
esac
echo "herdr shim: refusing $*" >&2
exit 1
"""


def shims(d, rows, records=None, prompt_exit=0, sid="S2"):
    """A PATH holding only the stub, and a HOME whose transcript for `sid`
    holds `records` (no file at all when None). PATH is this directory ALONE,
    so a call that escaped the stub would run nothing rather than silently
    reaching the real herdr and driving somebody's pane."""
    d = Path(d)
    b = d / "bin"
    b.mkdir(parents=True, exist_ok=True)
    listing = json.dumps({"result": {"agents": rows}})
    (b / "herdr").write_text(
        HERDR % (str(d / "prompts.log"), listing, prompt_exit))
    (b / "herdr").chmod(0o755)
    for tool in ("sh", "cat", "printf", "python3", "git"):
        found = shutil.which(tool)
        if found and not (b / tool).exists():
            (b / tool).symlink_to(found)
    if records is not None:
        proj = d / "home" / ".claude" / "projects" / "-tmp"
        proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{sid}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records))
    return b


def prompts(path_dir):
    """Every prompt the stub was asked to send. An absent log is no calls."""
    log = Path(path_dir).parent / "prompts.log"
    if not log.exists():
        return []
    return [ln for ln in log.read_text().splitlines() if ln.strip()]


def assign(args, path_dir):
    env = dict(os.environ, PATH=str(path_dir),
               HOME=str(Path(path_dir).parent / "home"))
    # The suite runs inside a herdr pane, so HERDR_ENV=1 is already here; left
    # in, a case asserting the script set the guard would pass while the script
    # set nothing.
    env.pop("HERDR_ENV", None)
    return subprocess.run([sys.executable, str(ASSIGN), *args],
                          capture_output=True, text=True, env=env)


def pure_cases(m):
    rows = {"S1": {"name": "machinery-worker-1", "status": "idle",
                   "cwd": "/tmp", "pane": "w1:p1"},
            "S2": {"name": "machinery-worker-2", "status": "working",
                   "cwd": "/tmp", "pane": "w1:p2"}}
    row, note = m.row_for(rows, "w1:p2")
    check("row_for finds the row by pane, not by position",
          row is not None and row["name"] == "machinery-worker-2", note)
    check("...and carries its session id, which names the transcript",
          row is not None and row["sid"] == "S2", repr(row))
    row, note = m.row_for(rows, "w9:p9")
    check("a pane no row names lists the panes that were there",
          row is None and "w1:p1" in note and "w1:p2" in note, note)
    two = {"A": dict(rows["S1"]), "B": dict(rows["S1"])}
    row, note = m.row_for(two, "w1:p1")
    check("two rows on one pane refuse rather than pick one",
          row is None and "2 herdr rows" in note, note)

    ok, why = m.idle_verdict({"status": "idle"})
    check("idle is assignable", ok and why is None)
    ok, why = m.idle_verdict({"status": "done"})
    check("...and so is done, which is also a finished turn", ok)
    ok, why = m.idle_verdict({"status": "working"})
    check("working is refused, and the refusal says why it matters",
          not ok and "queues behind work" in why, why)
    ok, why = m.idle_verdict({"status": "unheard-of"})
    check("a status this does not recognise is not evidence of rest",
          not ok and "unheard-of" in why, why)

    cm = m.claim_module()
    check("the anchor this suite fixtures is the line campaign-claim prints",
          RELEASED.startswith(cm.RELEASED), f"{cm.RELEASED!r} vs {RELEASED!r}")

    sentence = m.prompt_for("kalaluthien/campaign-base", "42")
    check("the prompt names the sub-issue and defers to its body",
          "kalaluthien/campaign-base#42" in sentence
          and "whole brief" in sentence, sentence)

    # THE WRITER AND THE READER OF THE SENTENCE CANNOT DRIFT. `campaign-role-
    # brief.py` imports `ASSIGNMENT` from this script to find the sub-issue a
    # prompt assigns; this case is what fails if `prompt_for`'s wording moves
    # out from under the pattern, on either side.
    hit = m.ASSIGNMENT.search(sentence)
    check("the sentence `prompt_for` writes is matched by ASSIGNMENT, which "
          "the brief hook reads it back with",
          hit is not None, sentence)
    check("...and yields the same repository and sub-issue it was given",
          hit is not None and hit.group("repo") == "kalaluthien/campaign-base"
          and hit.group("issue") == "42",
          repr(hit.groupdict()) if hit else sentence)


def end_to_end_cases():
    rows = [agent("S1", "machinery-worker-1", "w1:p1"),
            agent("S2", "machinery-worker-2", "w1:p2")]

    with tempfile.TemporaryDirectory() as d:
        # ALLOW: idle, compacted since its last release. This is #293's first
        # item: the pane's scrollback lost the release line to the
        # compaction and read `unknown`; the transcript keeps both.
        ok = shims(Path(d) / "ok", rows, COMPACTED)
        r = assign(["w1:p2", "198"], ok)
        out = r.stdout + r.stderr
        sent = prompts(ok)
        check("a session that released and then compacted is assigned",
              r.returncode == 0 and "assigned kalaluthien/campaign-base#198"
              in out, f"exit {r.returncode}: {out[:300]}")
        check("...by exactly one guarded prompt to the pane named",
              len(sent) == 1 and "pane=w1:p2" in sent[0]
              and "HERDR_ENV=1" in sent[0] and "#198" in sent[0], repr(sent))
        check("...and never to the other pane",
              not any("pane=w1:p1" in ln for ln in sent), repr(sent))
        check("...saying what it read and from where",
              "compacted: released" in out and "S2.jsonl" in out, out[:400])
        # A CLEAN PATH SAYS NOTHING ABOUT OVERRIDING.
        check("...and says nothing about overriding anything",
              "assigning anyway" not in out and "--force" not in out
              and "--assume-fresh" not in out, out[:400])

        # THE TRANSCRIPT READ IS THIS ROW'S. The other session's transcript
        # is compacted and this one's is stale, so a reader that took the
        # wrong session id assigns.
        other = shims(Path(d) / "other", rows, STALE)
        shims(Path(d) / "other", rows, COMPACTED, sid="S1")
        r = assign(["w1:p2", "198"], other)
        check("the transcript read is the named pane's session's, not another's",
              r.returncode == 1 and prompts(other) == [],
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:250]}")

        # REFUSE: no release in the transcript. A first assignment takes
        # --assume-fresh, which says what it overrode.
        fresh = shims(Path(d) / "fresh", rows, FRESH)
        r = assign(["w1:p2", "198"], fresh)
        out = r.stdout + r.stderr
        check("a transcript with no release is refused",
              r.returncode == 1 and "unknown" in out
              and prompts(fresh) == [], f"exit {r.returncode}: {out[:300]}")
        check("...and the refusal offers --assume-fresh, not --force",
              "--assume-fresh" in out and "pass --force" not in out, out[:500])
        fresh_a = shims(Path(d) / "fresha", rows, FRESH)
        r = assign(["w1:p2", "198", "--assume-fresh"], fresh_a)
        out = r.stdout + r.stderr
        check("...and --assume-fresh assigns it, naming the verdict",
              r.returncode == 0 and "verdict was unknown" in out
              and len(prompts(fresh_a)) == 1, f"exit {r.returncode}: {out[:300]}")
        fresh_f = shims(Path(d) / "freshf", rows, FRESH)
        r = assign(["w1:p2", "198", "--force"], fresh_f)
        out = r.stdout + r.stderr
        check("--force on an unknown pane is named --force, not --assume-fresh",
              r.returncode == 0 and "--force: assigning anyway" in out
              and "--assume-fresh:" not in out, out[:400])

        # REFUSE: released and not compacted since.
        stale = shims(Path(d) / "stale", rows, STALE)
        r = assign(["w1:p2", "198"], stale)
        out = r.stdout + r.stderr
        check("a pane that has not compacted since its release is refused",
              r.returncode == 1 and "has not compacted since its last release"
              in out and prompts(stale) == [], f"exit {r.returncode}: {out[:300]}")
        # THE SPLIT. `--assume-fresh` reaches what a reading cannot; it must
        # NOT reach the one case the guard exists for.
        af_stale = shims(Path(d) / "afstale", rows, STALE)
        r = assign(["w1:p2", "198", "--assume-fresh"], af_stale)
        check("--assume-fresh does NOT waive a pane read as stale",
              r.returncode == 1 and prompts(af_stale) == [],
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:300]}")
        forced = shims(Path(d) / "forced", rows, STALE)
        r = assign(["w1:p2", "198", "--force"], forced)
        out = r.stdout + r.stderr
        check("...and --force does, naming itself and the verdict",
              r.returncode == 0 and "--force: assigning anyway" in out
              and "verdict was stale" in out and len(prompts(forced)) == 1,
              f"exit {r.returncode}: {out[:300]}")

        # I COULD NOT LOOK is neither a yes nor a no.
        unread = shims(Path(d) / "unread", rows, None)
        r = assign(["w1:p2", "198"], unread)
        out = r.stdout + r.stderr
        check("a transcript that is not there refuses, saying it could not look",
              r.returncode == 1 and "an unknown is not" in out
              and "S2.jsonl" in out and prompts(unread) == [],
              f"exit {r.returncode}: {out[:300]}")
        forced_unread = shims(Path(d) / "forcedunread", rows, None)
        r = assign(["w1:p2", "198", "--assume-fresh"], forced_unread)
        out = r.stdout + r.stderr
        check("...and --assume-fresh gets past it, saying what it did not read",
              r.returncode == 0 and "verdict was unread" in out
              and len(prompts(forced_unread)) == 1,
              f"exit {r.returncode}: {out[:300]}")
        forced_unread2 = shims(Path(d) / "fu2", rows, None)
        r = assign(["w1:p2", "198", "--force"], forced_unread2)
        out = r.stdout + r.stderr
        check("--force alone also gets past a transcript that is not there",
              r.returncode == 0 and len(prompts(forced_unread2)) == 1
              and out.count("assigning anyway") == 1,
              f"exit {r.returncode}: {out[:250]}")

        # REFUSE: not idle, with a transcript that would have admitted it.
        busy = shims(Path(d) / "busy",
                     [agent("S1", "machinery-worker-1", "w1:p1"),
                      agent("S2", "machinery-worker-2", "w1:p2",
                            status="working")], COMPACTED)
        r = assign(["w1:p2", "198"], busy)
        out = r.stdout + r.stderr
        check("a working pane is refused before anything is sent",
              r.returncode == 1 and "not idle" in out
              and prompts(busy) == [], f"exit {r.returncode}: {out[:300]}")

        # REFUSE: no row names the pane.
        gone = shims(Path(d) / "gone", rows, COMPACTED)
        r = assign(["w9:p9", "198"], gone)
        out = r.stdout + r.stderr
        check("a pane herdr does not list is refused, and the panes are named",
              r.returncode == 1 and "no herdr row names pane w9:p9" in out
              and "w1:p1" in out and prompts(gone) == [],
              f"exit {r.returncode}: {out[:300]}")

        # THE SEND ITSELF FAILING is not an assignment.
        broke = shims(Path(d) / "broke", rows, COMPACTED, prompt_exit=4)
        r = assign(["w1:p2", "198"], broke)
        out = r.stdout + r.stderr
        check("a prompt that would not send reports it and is not an assignment",
              r.returncode == 1 and "exited 4" in out
              and "is not assigned" in out, f"exit {r.returncode}: {out[:300]}")

        # `#207` IS HOW AGENTS.md SPELLS A SUB-ISSUE, so it is what a caller
        # copying from an issue types; unstripped it prompts `<repo>##207`.
        hashed = shims(Path(d) / "hashed", rows, COMPACTED)
        r = assign(["w1:p2", "#207"], hashed)
        check("a sub-issue typed as #N reaches the prompt as #N, not ##N",
              r.returncode == 0 and len(prompts(hashed)) == 1
              and "campaign-base#207" in prompts(hashed)[0]
              and "##207" not in prompts(hashed)[0], repr(prompts(hashed)))
        notnum = shims(Path(d) / "notnum", rows, COMPACTED)
        r = assign(["w1:p2", "not-a-number"], notnum)
        check("...and something that is not an issue number is refused",
              r.returncode == 1 and prompts(notnum) == [],
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:200]}")

        # herdr absent: a listing that did not happen is not an empty machine.
        nowhere = Path(d) / "nowhere" / "bin"
        nowhere.mkdir(parents=True)
        r = assign(["w1:p2", "198"], nowhere)
        out = r.stdout + r.stderr
        check("herdr that cannot be run is a failed reading, not an absent pane",
              r.returncode == 1 and "did not happen" in out,
              f"exit {r.returncode}: {out[:300]}")


def main():
    import importlib.machinery
    import importlib.util
    spec = importlib.util.spec_from_loader(
        "campaign_assign",
        importlib.machinery.SourceFileLoader("campaign_assign", str(ASSIGN)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    pure_cases(m)
    end_to_end_cases()
    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
