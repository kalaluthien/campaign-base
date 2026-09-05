#!/usr/bin/env python3
"""Cases for campaign-assign.py, over a stubbed `herdr` on PATH.

AN ALLOW CASE BESIDE EVERY REFUSAL. A guard is only worth its refusals if the
thing it admits still gets through, and a refusing check with no allow case
reads identically to one that refuses everything.

The stub answers three subcommands -- `agent list`, `agent read`, `agent
prompt` -- and logs every prompt, so "the assignment was sent" is asserted on
what herdr was ASKED, never on an exit status: a run that refused and a run
that sent the prompt to the wrong pane both exit 0 or 1 for reasons this suite
has to separate.
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


MARKER = "Compacted (ctrl+o to see full summary)"
# The anchor as `campaign-claim.py` prints it. Spelled here rather than
# imported so that a case fails if the two ever disagree -- which is the one
# thing importing it on both sides would hide.
# The anchor as `campaign-claim.py` prints it, PANE AND ALL. Spelled here
# rather than imported so that a case fails if the two ever disagree.
RELEASED = "campaign-claim: released campaign-1/195-token-tally in w1:p2"
# The same release, printed in somebody else's pane. `herdr agent read` puts
# another session's output into the reader's own scrollback, which is the
# ordinary planner move -- so this string turns up in a pane that did not
# release, and must not answer for it.
ELSEWHERE = "campaign-claim: released campaign-1/177-commit-claim in w1:p1"


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
  "agent read")
    printf 'read %%s %%s\\n' "$3" "$5" >> "$log"
    %s ;;
  "agent prompt")
    printf 'HERDR_ENV=%%s pane=%%s prompt=%%s\\n' "${HERDR_ENV:-unset}" "$3" "$4" >> "$log"
    exit %s ;;
esac
echo "herdr shim: refusing $*" >&2
exit 1
"""


def shims(d, rows, screen="", read_exit=0, prompt_exit=0):
    """A PATH holding only the stub. PATH is this directory ALONE, so a call
    that escaped the stub would run nothing rather than silently reaching the
    real herdr and driving somebody's pane."""
    b = Path(d) / "bin"
    b.mkdir(parents=True, exist_ok=True)
    if read_exit == 0:
        read_arm = "cat <<'SCREEN'\n%s\nSCREEN\n    exit 0" % screen
    else:
        read_arm = ('echo \'{"error":{"code":"agent_not_idle"}}\' >&2; exit %d'
                    % read_exit)
    listing = json.dumps({"result": {"agents": rows}})
    (b / "herdr").write_text(
        HERDR % (str(Path(d) / "prompts.log"), listing, read_arm, prompt_exit))
    (b / "herdr").chmod(0o755)
    for tool in ("sh", "cat", "printf", "python3", "git"):
        found = shutil.which(tool)
        if found and not (b / tool).exists():
            (b / tool).symlink_to(found)
    return b


def calls(path_dir, kind):
    """Every `agent <kind>` the stub was asked to make, in order. One log for
    both, so a case can assert the window `agent read` was given as well as the
    prompt `agent prompt` carried -- the window was plumbed by nothing until a
    review mutated it away and the suite stayed green."""
    log = Path(path_dir).parent / "prompts.log"
    if not log.exists():
        return []
    return [ln for ln in log.read_text().splitlines()
            if ln.strip() and ln.startswith(kind)]


def prompts(path_dir):
    """Every prompt the stub was asked to send. An absent log is no calls."""
    return calls(path_dir, "HERDR_ENV=")


def reads(path_dir):
    """Every scrollback read, as `read <pane> <lines>`."""
    return calls(path_dir, "read ")


def assign(args, path_dir):
    env = dict(os.environ, PATH=str(path_dir))
    # The suite runs inside a herdr pane, so HERDR_ENV=1 is already here; left
    # in, a case asserting the script set the guard would pass while the script
    # set nothing.
    env.pop("HERDR_ENV", None)
    return subprocess.run([sys.executable, str(ASSIGN), *args],
                          capture_output=True, text=True, env=env)


def pure_cases(m):
    rows = {"S1": {"name": "campaign-1-worker-1", "status": "idle",
                   "cwd": "/tmp", "pane": "w1:p1"},
            "S2": {"name": "campaign-1-worker-2", "status": "working",
                   "cwd": "/tmp", "pane": "w1:p2"}}
    row, note = m.row_for(rows, "w1:p2")
    check("row_for finds the row by pane, not by position",
          row is not None and row["name"] == "campaign-1-worker-2", note)
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

    import importlib.machinery
    import importlib.util
    cspec = importlib.util.spec_from_loader(
        "campaign_claim", importlib.machinery.SourceFileLoader(
            "campaign_claim", str(HERE / "campaign-claim.py")))
    cm = importlib.util.module_from_spec(cspec)
    cspec.loader.exec_module(cm)
    check("the anchor this suite fixtures is the line campaign-claim prints",
          RELEASED.startswith(cm.RELEASED), f"{cm.RELEASED!r} vs {RELEASED!r}")

    def verdict(text, pane="w1:p2"):
        return m.compaction_verdict(text, cm.RELEASED, pane)

    # NO RELEASE LINE IS `unknown`, NOT `fresh`. It used to be `fresh`, which
    # ALLOWED, on the reasoning that a read shorter than its window is the
    # whole history. Measured 2026-09-05, that reasoning is false of the tool:
    # `herdr agent read` caps at 1000 lines and returns fewer than asked even
    # when more history exists (one 48-line pane answered `--lines 60` with 46
    # and `--lines 10` with nothing). So the absence refuses.
    v, why = verdict("nothing about a release here\nor here\n")
    check("no release line is unknown, not a pane that never released",
          v == "unknown" and "2 line(s)" in why
          and "not evidence" in why, f"{v} {why}")
    v, why = verdict(f"work\n{RELEASED}\n{MARKER}\n")
    check("a marker after the release line is compacted", v == "compacted", why)
    v, why = verdict(f"work\n{RELEASED}\nstill going\n")
    check("a release with no marker after it is stale",
          v == "stale" and "released at line 2" in why, why)
    # ORDER, NOT PRESENCE. This is the case the obvious implementation fails.
    v, why = verdict(f"{MARKER}\nwork\n{RELEASED}\nstill going\n")
    check("a marker BEFORE the release line does not count as compacted",
          v == "stale", f"{v} {why}")
    v, why = verdict("")
    check("an empty read is unknown with the count said, not a crash",
          v == "unknown" and "0 line(s)" in why, f"{v} {why}")
    # LAST RELEASE, NOT FIRST. A pane that released, compacted, worked and
    # released again holds a marker between the two releases. `min` here reads
    # that marker as coming after "the" release and admits the pane with its
    # SECOND release uncompacted. No fixture with two release lines existed, so
    # `max` -> `min` passed 33/33; found by review.
    v, why = verdict(f"{RELEASED}\n{MARKER}\nmore work\n{RELEASED}\nnow what\n")
    check("two releases: the LAST one decides, so this is stale",
          v == "stale" and "released at line 4" in why, f"{v} {why}")
    # ...and the allow beside it: a marker after the second release.
    v, why = verdict(f"{RELEASED}\n{MARKER}\nwork\n{RELEASED}\n{MARKER}\n")
    check("...and a marker after the last release is compacted",
          v == "compacted" and "line 4" in why, f"{v} {why}")
    # THE RELEASE THAT COULD NOT COMPACT is the single case this guard exists
    # for, and at 114e71a it read `fresh` and was assigned: the anchor was the
    # compaction's success line, which that release never printed.
    could_not = (f"work\n{RELEASED}\n"
                 f"not compacting: no herdr row names it (3 row(s) listed). "
                 f"The claim is released; only the compaction did not "
                 f"happen.\n")
    v, why = verdict(could_not)
    check("a release that could NOT compact reads stale, not unknown",
          v == "stale", f"{v} {why[:140]}")

    # THE FORGERY. `compacted` used to need only a line CONTAINING the marker,
    # and the marker's own definition is a line of campaign-assign.py -- so a
    # session that `cat`s or `grep`s this repository in its pane, which is what
    # working on this sub-issue looks like, read as compacted while holding the
    # whole previous sub-issue. Found by review at 2468517.
    forged = (f"{RELEASED}\n"
              f'MARKER = "Compacted (ctrl+o to see full summary)"\n')
    v, why = verdict(forged)
    check("this repository's own source does not forge a compaction",
          v == "stale", f"{v} {why[:140]}")
    # ...and the allow beside it: the marker as the transcript actually draws
    # it, behind a gutter, still counts.
    for gutter in ("  \u23bf  ", "\u2502 ", "   "):
        v, why = verdict(f"{RELEASED}\n{gutter}{MARKER}   \n")
        check(f"a marker behind the gutter {gutter!r} still counts",
              v == "compacted", f"{v} {why[:120]}")
    # A GUTTER GLYPH NOBODY MEASURED ONLY WIDENS THE ACCEPT SET. `|` and the
    # bullet sat in the set on plausibility, and the bullet made a quoted
    # marker in an issue body -- `gh issue view` output in a pane -- render to
    # the marker exactly.
    for forged in ("\u2022 ", "| ", "> ", "# "):
        v, why = verdict(f"{RELEASED}\n{forged}{MARKER}\n")
        check(f"a marker behind the unmeasured prefix {forged!r} does not count",
              v == "stale", f"{v} {why[:120]}")
    # ...and the harness appending to its own line must not cost a --force on
    # every honest compaction, which strict equality did.
    v, why = verdict(f"{RELEASED}\n  \u23bf  {MARKER}  (esc to interrupt)\n")
    check("a marker the harness appended to still counts",
          v == "compacted", f"{v} {why[:120]}")
    # MATCHING THE LINE'S START IS ONLY SAFE WHILE THE MARKER IS THE WHOLE
    # SENTENCE. Shortened to its first word it admits any line opening with it,
    # and nothing caught that until this case: strict equality had been holding
    # the marker's length by accident.
    v, why = verdict(f"{RELEASED}\n  \u23bf  Compacted 3 files into 1\n")
    check("a line merely opening with the marker's first word does not count",
          v == "stale", f"{v} {why[:120]}")
    # THE LAST MARKER NAMES ITSELF in the reason, which is what a reader
    # chases; `after[0]` reports the first and was held by nothing.
    v, why = verdict(f"{RELEASED}\n{MARKER}\nnoise\n{MARKER}\n")
    check("the reason names the LAST marker line, not the first",
          v == "compacted" and "compacted at line 4" in why, f"{v} {why}")
    # The anchor is matched the same way, so campaign-claim.py's own source
    # line does not manufacture a release.
    v, why = verdict('RELEASED = "campaign-claim: released"\nnoise\n')
    check("...and campaign-claim's source line does not forge a release",
          v == "unknown", f"{v} {why[:140]}")
    # ANOTHER PANE'S RELEASE IS NOT THIS PANE'S. A planner that reads a
    # delegate's pane has the delegate's release AND its compaction marker in
    # its own scrollback, in that order -- and read itself as compacted, which
    # ASSIGNS. The anchor names the pane it was printed in for this reason.
    # A LINE THAT MERELY CONTAINS THE ANCHOR is prose about a release, not a
    # release -- and prose about THIS pane's release ends with this pane's id,
    # so the pane tail alone does not separate the two. Only matching the
    # line's START does. This is what a pull request comment quoting the run,
    # read back in a pane, renders to.
    v, why = verdict(f"the run printed {RELEASED}\n{MARKER}\n")
    check("prose quoting a release mid-line is not a release",
          v == "unknown", f"{v} {why[:140]}")
    v, why = verdict(f"  \u23bf  {ELSEWHERE}\n  \u23bf  {MARKER}\n")
    check("a release read out of ANOTHER pane does not answer for this one",
          v == "unknown", f"{v} {why[:140]}")
    # ...and the allow beside it: this pane's own release still counts, and a
    # foreign one sitting after it does not move the answer.
    v, why = verdict(f"{RELEASED}\n  \u23bf  {ELSEWHERE}\n{MARKER}\n")
    check("...while this pane's own release still does",
          v == "compacted", f"{v} {why[:140]}")
    v, why = verdict(f"{RELEASED}\n{MARKER}\n", pane="w9:p9")
    check("...and reading for a different pane finds no release of its own",
          v == "unknown", f"{v} {why[:140]}")

    sentence = m.prompt_for("kalaluthien/campaign-base", "42")
    check("the prompt names the sub-issue and defers to its body",
          "kalaluthien/campaign-base#42" in sentence
          and "whole brief" in sentence, sentence)


def end_to_end_cases():
    rows = [agent("S1", "campaign-1-worker-1", "w1:p1"),
            agent("S2", "campaign-1-worker-2", "w1:p2")]

    with tempfile.TemporaryDirectory() as d:
        # ALLOW: idle, compacted since its last release.
        ok = shims(Path(d) / "ok", rows, screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198"], ok)
        out = r.stdout + r.stderr
        sent = prompts(ok)
        check("an idle, compacted pane is assigned",
              r.returncode == 0 and "assigned kalaluthien/campaign-base#198"
              in out, f"exit {r.returncode}: {out[:300]}")
        check("...by exactly one guarded prompt to the pane named",
              len(sent) == 1 and "pane=w1:p2" in sent[0]
              and "HERDR_ENV=1" in sent[0] and "#198" in sent[0], repr(sent))
        check("...and never to the other pane",
              not any("pane=w1:p1" in ln for ln in sent), repr(sent))
        # A CLEAN PATH SAYS NOTHING ABOUT OVERRIDING. Held by nothing until the
        # fifth review made the guard unconditional and the suite stayed green,
        # printing `assigning anyway, verdict was compacted`.
        check("...and says nothing about overriding anything",
              "assigning anyway" not in out and "--force" not in out
              and "--assume-fresh" not in out, out[:400])

        # THE REVERSAL. A pane with no release line USED to be assigned, on
        # the reasoning that a fresh session's context is small. Nothing here
        # can tell a fresh session from one whose release scrolled out of a
        # window that is capped and under-fills, so the two want opposite
        # answers from the same bytes and the absence now refuses. A first
        # assignment takes --force, which says what it overrode.
        fresh = shims(Path(d) / "fresh", rows, screen="a fresh session\n")
        r = assign(["w1:p2", "198"], fresh)
        check("a pane with no release line is NOT assigned on that alone",
              r.returncode == 1 and prompts(fresh) == [],
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:250]}")
        fresh_f = shims(Path(d) / "freshf", rows, screen="a fresh session\n")
        r = assign(["w1:p2", "198", "--force"], fresh_f)
        check("...and --force is how a genuinely fresh pane is assigned",
              r.returncode == 0 and len(prompts(fresh_f)) == 1,
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:250]}")
        # --lines REACHES herdr. The `unknown` refusal offers raising it as the
        # remedy, and nothing asserted the flag was plumbed at all: dropping it
        # from the call, and pinning the window to 1, both left 56/56 green.
        windowed = shims(Path(d) / "windowed", rows,
                         screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198", "--lines", "137"], windowed)
        check("the --lines window is what herdr is asked for",
              reads(windowed) == ["read w1:p2 137"], repr(reads(windowed)))
        defaulted = shims(Path(d) / "defaulted", rows,
                          screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198"], defaulted)
        check("...and the default window is the one the docstring names",
              reads(defaulted) == ["read w1:p2 400"], repr(reads(defaulted)))

        # REFUSE: released and not compacted since.
        stale = shims(Path(d) / "stale", rows, screen=f"{RELEASED}\nworking\n")
        r = assign(["w1:p2", "198"], stale)
        out = r.stdout + r.stderr
        check("a pane that has not compacted since its release is refused",
              r.returncode == 1 and "has not compacted since its last release"
              in out, f"exit {r.returncode}: {out[:300]}")
        check("...and nothing was sent",
              prompts(stale) == [], repr(prompts(stale)))
        # ...and --force is the way past, printing what it overrides.
        forced = shims(Path(d) / "forced", rows,
                       screen=f"{RELEASED}\nworking\n")
        r = assign(["w1:p2", "198", "--force"], forced)
        out = r.stdout + r.stderr
        check("--force assigns it and says what it is overriding",
              r.returncode == 0 and "verdict was stale" in out
              and len(prompts(forced)) == 1,
              f"exit {r.returncode}: {out[:300]}")

        # REFUSE: no release line anywhere in the read. Fails CLOSED now; at
        # 114e71a and at 1eb0d9b under a wide `--lines` this was `fresh` and
        # was assigned.
        full = shims(Path(d) / "full", rows,
                     screen="\n".join(["noise"] * 400))
        r = assign(["w1:p2", "198"], full)
        out = r.stdout + r.stderr
        check("a pane with no release line in the read is refused",
              r.returncode == 1 and "unknown" in out
              and prompts(full) == [], f"exit {r.returncode}: {out[:300]}")
        check("...and the refusal offers --lines and names the cap",
              "Raise --lines (at most 1000)" in out, out[:500])
        check("...and offers --assume-fresh, not --force, for this verdict",
              "--assume-fresh" in out and "pass --force" not in out, out[:500])
        # ...and --force is the door, naming the verdict it overrode rather
        # than one sentence for three different states.
        forced_unknown = shims(Path(d) / "fu", rows,
                               screen="\n".join(["noise"] * 400))
        r = assign(["w1:p2", "198", "--assume-fresh"], forced_unknown)
        out = r.stdout + r.stderr
        check("...and --assume-fresh assigns it, naming the verdict",
              r.returncode == 0 and "verdict was unknown" in out
              and len(prompts(forced_unknown)) == 1,
              f"exit {r.returncode}: {out[:300]}")
        # THE SPLIT. `--assume-fresh` reaches what a reading cannot; it must
        # NOT reach the one case the guard exists for.
        af_stale = shims(Path(d) / "afstale", rows,
                         screen=f"{RELEASED}\nworking\n")
        r = assign(["w1:p2", "198", "--assume-fresh"], af_stale)
        out = r.stdout + r.stderr
        check("--assume-fresh does NOT waive a pane read as stale",
              r.returncode == 1 and prompts(af_stale) == [],
              f"exit {r.returncode}: {out[:300]}")
        af_forced = shims(Path(d) / "afforced", rows,
                          screen=f"{RELEASED}\nworking\n")
        r = assign(["w1:p2", "198", "--force"], af_forced)
        out = r.stdout + r.stderr
        check("...and --force does, which is the whole difference",
              r.returncode == 0 and len(prompts(af_forced)) == 1,
              f"exit {r.returncode}: {out[:250]}")
        check("...naming --force, not the flag that would have refused",
              "--force: assigning anyway" in out
              and "--assume-fresh: assigning" not in out, out[:400])
        # AND --force ON A VERDICT --assume-fresh COULD ALSO HAVE WAIVED must
        # still name --force: it is what the caller typed, and a message naming
        # the narrower flag sends the next reader to the wrong scope.
        f_unknown = shims(Path(d) / "funknown", rows,
                          screen="\n".join(["noise"] * 20))
        r = assign(["w1:p2", "198", "--force"], f_unknown)
        out = r.stdout + r.stderr
        check("--force on an unknown pane is named --force, not --assume-fresh",
              r.returncode == 0 and "--force: assigning anyway" in out
              and "--assume-fresh:" not in out, out[:400])

        # A WINDOW ABOVE THE TOOL'S CAP reads no further, so asking for one is
        # refused rather than answered with less than it promises.
        over = shims(Path(d) / "over", rows, screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198", "--lines", "1500"], over)
        out = r.stdout + r.stderr
        check("a --lines above herdr's cap is refused, naming the cap",
              r.returncode == 1 and "above herdr's 1000-line cap" in out
              and prompts(over) == [], f"exit {r.returncode}: {out[:300]}")
        atcap = shims(Path(d) / "atcap", rows,
                      screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198", "--lines", "1000"], atcap)
        check("...and exactly the cap is admitted",
              r.returncode == 0 and len(prompts(atcap)) == 1,
              f"exit {r.returncode}: {(r.stdout + r.stderr)[:250]}")

        # REFUSE: not idle. Asserted on the pane's own status, and the read arm
        # is left working so a pass cannot come from an unreadable screen.
        busy = shims(Path(d) / "busy",
                     [agent("S1", "campaign-1-worker-1", "w1:p1"),
                      agent("S2", "campaign-1-worker-2", "w1:p2",
                            status="working")],
                     screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "198"], busy)
        out = r.stdout + r.stderr
        check("a working pane is refused before anything is sent",
              r.returncode == 1 and "not idle" in out
              and prompts(busy) == [], f"exit {r.returncode}: {out[:300]}")

        # REFUSE: no row names the pane.
        gone = shims(Path(d) / "gone", rows, screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w9:p9", "198"], gone)
        out = r.stdout + r.stderr
        check("a pane herdr does not list is refused, and the panes are named",
              r.returncode == 1 and "no herdr row names pane w9:p9" in out
              and "w1:p1" in out and prompts(gone) == [],
              f"exit {r.returncode}: {out[:300]}")

        # I COULD NOT LOOK is neither a yes nor a no.
        unread = shims(Path(d) / "unread", rows, read_exit=1)
        r = assign(["w1:p2", "198"], unread)
        out = r.stdout + r.stderr
        check("a scrollback that would not read refuses, saying it could not look",
              r.returncode == 1 and "an unknown is not" in out
              and "agent read" in out and prompts(unread) == [],
              f"exit {r.returncode}: {out[:300]}")
        forced_unread = shims(Path(d) / "forcedunread", rows, read_exit=1)
        r = assign(["w1:p2", "198", "--assume-fresh"], forced_unread)
        out = r.stdout + r.stderr
        check("...and --assume-fresh gets past it, saying what it did not read",
              r.returncode == 0 and "verdict was unread" in out
              and len(prompts(forced_unread)) == 1,
              f"exit {r.returncode}: {out[:300]}")
        # `--force` IMPLIES --assume-fresh, which its help promises and which
        # this branch implements separately from `waived`. Every case here
        # passed --assume-fresh, so dropping `args.force` from it survived.
        forced_unread2 = shims(Path(d) / "fu2", rows, read_exit=1)
        r2 = assign(["w1:p2", "198", "--force"], forced_unread2)
        check("--force alone also gets past a pane that would not read",
              r2.returncode == 0 and len(prompts(forced_unread2)) == 1,
              f"exit {r2.returncode}: {(r2.stdout + r2.stderr)[:250]}")
        check("...printing ONE --force line, not two about the same verdict",
              out.count("assigning anyway") == 1
              and "assigning without reading the pane" not in out, out[:400])

        # THE SEND ITSELF FAILING is not an assignment.
        broke = shims(Path(d) / "broke", rows, screen=f"{RELEASED}\n{MARKER}\n",
                      prompt_exit=4)
        r = assign(["w1:p2", "198"], broke)
        out = r.stdout + r.stderr
        check("a prompt that would not send reports it and is not an assignment",
              r.returncode == 1 and "exited 4" in out
              and "is not assigned" in out, f"exit {r.returncode}: {out[:300]}")

        # `#207` IS HOW AGENTS.md SPELLS A SUB-ISSUE, so it is what a caller
        # copying from an issue types; unstripped it prompts `<repo>##207`.
        hashed = shims(Path(d) / "hashed", rows,
                       screen=f"{RELEASED}\n{MARKER}\n")
        r = assign(["w1:p2", "#207"], hashed)
        check("a sub-issue typed as #N reaches the prompt as #N, not ##N",
              r.returncode == 0 and len(prompts(hashed)) == 1
              and "campaign-base#207" in prompts(hashed)[0]
              and "##207" not in prompts(hashed)[0], repr(prompts(hashed)))
        notnum = shims(Path(d) / "notnum", rows,
                       screen=f"{RELEASED}\n{MARKER}\n")
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
