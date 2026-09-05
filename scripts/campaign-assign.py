#!/usr/bin/env python3
"""Assign a sub-issue to a session already running, by prompting its pane.

    campaign-assign.py <pane> <sub-issue> [--repo owner/repo]
                       [--lines N] [--assume-fresh] [--force]

THE CHANNEL RULE, AND WHY IT NEEDS A SCRIPT

AGENTS.md § The four messages states it: an instruction to a session is a
prompt into its pane; information between sessions is one of the four messages.
A prompt is the session's own user turn, so its hooks run and no relay caveat
applies; a message is a peer's word, which AGENTS.md says is never the
authority -- which is exactly why an instruction must not travel as one.

Stated in prose alone it had already drifted: the rule appeared in two sections
with no criterion between them, and a later assignment to a reused worker,
the answer to a BLOCKED, and a slash command fell between them and were sent
whichever way the sender guessed. This is that rule with a machine behind it.

WHAT IT REFUSES, AND WHY EACH IS A REFUSAL AND NOT A WARNING

  (no row)          no herdr row names this pane, so there is nothing to
                    prompt and the pane string is probably stale.
  (not idle)        a pane mid-turn queues the prompt behind work whose outcome
                    nobody has read, and the assignment lands on a session that
                    may be about to report something that changes it.
  `unknown`         nothing in what was read says THIS PANE ever released.
                    That is NOT evidence it never did -- see the window note
                    below -- so it refuses. --lines reads further back,
                    --assume-fresh assigns anyway and says what it overrode.
  `stale`           the pane released a sub-issue and has not compacted since,
                    so the next sub-issue would re-read the last one's whole
                    transcript on every turn. `campaign-claim.py release`
                    enqueues that compaction; this is the reader that says
                    whether it happened. --force is the way past, and it prints
                    what it is overriding.

  A PANE WHOSE RELEASE THIS DID NOT SEE IS REFUSED, and that is a reversal
  measured into place rather than a preference. `orchestrationInit`'s
  `Compacted = Session` does say a fresh session is assignable, and the first
  cut allowed on that reading -- but NOTHING HERE CAN TELL a fresh session from
  one whose release scrolled out of the window, and the two want opposite
  answers. Three measurements, 2026-09-05, all against `herdr agent read`:

    * it caps at 1000 lines however large `--lines` is (900->900, 1000->1000,
      1500->1000, 3000->1000), so a bigger window silently reads no further;
    * it returns FEWER lines than both the window and the history -- one pane
      with 48 lines answered `--lines 60` with 46, and `--lines 10` with
      nothing at all -- so "shorter than the window" is not evidence the whole
      history was seen;
    * a shell command's output does reach the pane text at 40 lines with its
      middle intact, but whether an OLDER turn's output survives the
      transcript's `... +N lines` collapse is unmeasured, and a session cannot
      read its own pane to find out.

  Any of the three turns an absent anchor into a false "never released", which
  ALLOWS. So the absence refuses, and `--assume-fresh` is the door for the case
  the reading cannot reach -- a first assignment included. `--force` is a
  DIFFERENT door, for a pane that WAS read and has not compacted; one flag for
  both made bypassing the single case this guard exists for the same keystroke
  as the routine first assignment. Either prints what it overrode, where the
  old allow printed a sentence that was sometimes false.

WHAT IT CANNOT DO IS SAID, NEVER SKIPPED

Every reading here can come back absent for a reason that is not an answer: the
listing may not run, the pane's scrollback may not be readable, the marker text
may have scrolled out of the window this reads. Each prints what was read, from
where, and which branch was taken, and none of them silently assigns.

PROBED ON THIS MACHINE 2026-09-05

  * `herdr agent prompt <pane> "/compact"` runs the command; it is not typed as
    text. The pane showed `Compacting conversation... (41s)`.
  * A compacted pane's scrollback holds `Compacted (ctrl+o to see full
    summary)`, which is MARKER below.
  * `herdr agent read <pane> --lines N` refuses a pane that is working
    (`agent_not_idle`: "its alternate-screen history can only be captured by
    scrolling while idle"), so the idle check is not merely polite -- the
    scrollback cannot be read without it. `--source visible` reads a working
    pane but only the visible screen, which is too little for this.
  * A session that compacted came back idle holding no plan it had named
    before compacting. That is why an assignment is a fresh prompt carrying the
    sub-issue number, and why nothing here relies on the session remembering.
"""
import argparse
import importlib.util
import os
import subprocess
import sys

DEFAULT_REPO = "kalaluthien/campaign-base"

# What a compacted pane says, read off a live pane 2026-09-05. Held here as one
# string because it is the harness's wording and will change with it; when it
# does, this line is the whole edit and `read_pane`'s could-not-look branch is
# what a reader hits in the meantime.
MARKER = "Compacted (ctrl+o to see full summary)"

# What the transcript draws to the left of a rendered line. Stripped before a
# line is compared, so the comparison can be against the line's START rather
# than against anything it merely contains -- see `rendered`.
# MEASURED ONLY. Every character here has been seen drawn to the left of a
# transcript line on this machine; `|`, `\u2022` and four box-drawing glyphs
# were here on plausibility alone, and each of them only ever WIDENS what is
# accepted -- `\u2022` in particular made a bulleted quote of the marker in an
# issue body render to the marker. A gutter this does not know makes an honest
# compaction read `stale`, which refuses; a gutter it wrongly knows makes a
# quotation read as a compaction, which assigns. Add one only with a pane read
# beside it.
GUTTER = " \t" + "\u23bf\u2502"


def rendered(line):
    """A pane line with the transcript's gutter taken off, so a marker or an
    anchor can be matched against what the line IS rather than what it holds.

    CONTAINMENT WAS FORGEABLE, and by the most ordinary thing a worker does.
    `compacted` needed only some line CONTAINING MARKER after the last release;
    MARKER's own definition is a line of this file, so a session that `cat`s or
    `grep`s `campaign-assign.py` in its pane -- which is what working on this
    sub-issue looks like -- was read as compacted while holding the whole
    previous sub-issue. Found by review at 2468517, reproduced.

    Matching the rendered line's START is what closes it, and it is not the
    laxer choice it looks: `MARKER = "Compacted (...)"` does not begin with the
    marker, and neither does a `> ` quotation, because `>` is not a gutter this
    knows. Equality was the first cut and was too strict in the one direction
    that costs a `--force` on every honest compaction -- a pane that appends to
    the line, or one narrow enough to wrap it, read `stale` for ever."""
    # No `.rstrip()`: GUTTER holds space and tab, so both ends are already
    # stripped of whitespace by the call above.
    return line.strip(GUTTER)

# THE ANCHOR IS THE RELEASE, NOT THE COMPACTION'S SUCCESS, and it is
# `campaign_claim.RELEASED` -- taken from the script that prints it, never
# copied. Keyed on the compaction's own success line, which is how this shipped
# at 114e71a, a release that could NOT compact printed no such line, read as a
# pane that never released, and was assigned: the single case this guard exists
# for. Found by review and reproduced end to end before this was written.
#
# The marker alone cannot answer the question either: a pane that compacted,
# then worked and released again holds an older marker that says nothing about
# now. Hence the ordering in `compaction_verdict`.

# How much scrollback to ask for. A release turn and the compaction after it
# are a few dozen lines; this is wide enough for several and small enough that
# an unreadable pane fails fast.
#
# IT IS A BUDGET, NOT A PROOF. Nothing about how many lines came back says
# whether the whole history was seen -- see the measurements in the docstring.
# So no verdict here is derived from the count; an absent anchor is `unknown`
# whatever the length, and raising this only ever adds earlier lines.
LINES = 400

# What `herdr agent read` will return however large `--lines` is, measured
# 2026-09-05: 900->900, 1000->1000, 1001->1000, 1200->1000, 1500->1000,
# 3000->1000, with the three large reads sharing a tail and differing at the
# head. Asking past it reads no further, so a `--lines` above it is refused
# rather than silently answered with less.
READ_CAP = 1000


def claim_module():
    """campaign-claim.py, imported for its reader of herdr's listing.

    `parse_agents` is that script's, and a second copy here would drift from
    it -- AGENTS.md, "Do not write a second reader of a rule a script owns".
    The listing's shape is one such rule: which key holds the session id, and
    that a row herdr cannot identify is counted rather than dropped."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "campaign-claim.py")
    spec = importlib.util.spec_from_file_location("campaign_claim", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


def row_for(sessions, pane):
    """(row, note) -- the herdr row whose `pane_id` is this pane. Pure.

    Keyed by pane rather than by session id because the caller names a pane:
    a planner reads `herdr agent list` and types what it saw there, and the
    session id is not in that reading."""
    matches = [(sid, row) for sid, row in sorted(sessions.items())
               if row["pane"] == pane]
    if not matches:
        panes = ", ".join(sorted(r["pane"] for r in sessions.values())) or "none"
        return None, (f"no herdr row names pane {pane}. Listed: {panes}")
    if len(matches) > 1:
        return None, (f"{len(matches)} herdr rows name pane {pane}; nothing "
                      f"here can tell which session is in it")
    sid, row = matches[0]
    return row, f"pane {pane} is {row['name']} ({sid}), status {row['status']}"


def idle_verdict(row):
    """(ok, why). Pure. `idle` and `done` are both a finished turn; every other
    word herdr prints is a turn in flight, and an unknown word is treated as
    one, because a status this does not recognise is not evidence of rest."""
    if row["status"] in ("idle", "done"):
        return True, None
    return False, (f"status is {row['status']}, not idle. A prompt to a pane "
                   f"mid-turn queues behind work nobody has read the outcome "
                   f"of.")


def compaction_verdict(text, anchor, pane):
    """Has this pane compacted since its last release? Pure, over the pane's
    scrollback. Returns (verdict, why) with verdict one of:

      `compacted`   the marker appears after the last release line. The one
                    verdict that admits a pane on its own.
      `stale`       a release line with no marker after it.
      `unknown`     no release line NAMING THIS PANE in what was read. NOT
                    "it never released":
                    `herdr agent read` caps at 1000 lines and returns fewer
                    than asked even when more history exists, so an absent
                    anchor and a pane that never released are the same bytes.
                    Refuses like `stale`.

    ORDER, NOT PRESENCE, is the whole reading: a pane that compacted, worked,
    and released again holds a marker that is older than its release and says
    nothing about now. Both are searched by LAST occurrence for that reason --
    `min` here instead of `max` would call that pane `compacted` and assign it
    with its second release uncompacted."""
    lines = [rendered(ln) for ln in (text or "").splitlines()]
    # STARTSWITH for both, against the rendered line, so this file's own
    # source answers neither. The anchor must also END with this pane's id: a
    # pane's text holds what it DISPLAYED as well as what it printed, and
    # `herdr agent read` puts another session's release into the reader's own
    # scrollback, which AGENTS.md makes the ordinary planner move.
    #
    # THE MARKER CANNOT BE QUALIFIED THAT WAY -- it is harness UI text with
    # nothing in it that says whose pane it is -- so one direction is still
    # open: this pane's own release followed by somebody else's marker read
    # into this pane assigns. Bounded (this pane's own compaction must have
    # failed first, or its own marker would be there), and its fix is to stop
    # reading the pane at all and read the session's transcript, which no
    # other pane can write into. That is kalaluthien/campaign-base#220.
    tail = f" in {pane}"
    last_release = max((i for i, ln in enumerate(lines)
                        if ln.startswith(anchor) and ln.endswith(tail)),
                       default=None)
    if last_release is None:
        return "unknown", (f"no release line in the {len(lines)} line(s) read. "
                           f"That is not evidence this pane never released: "
                           f"the read is capped and returns fewer lines than "
                           f"asked, so an absent anchor and a pane that never "
                           f"released look identical.")
    after = [i for i, ln in enumerate(lines)
             if ln.startswith(MARKER) and i > last_release]
    if after:
        return "compacted", (f"released at line {last_release + 1}, compacted "
                             f"at line {after[-1] + 1}")
    return "stale", (f"released at line {last_release + 1} and no {MARKER!r} "
                     f"after it in the {len(lines)} line(s) read")


def read_pane(pane, limit):
    """(text, why_unread). The scrollback, or the reason there is none.

    NO DEFAULT for `limit`: `main` always passes `--lines`, so a default here
    is unreachable, and an unreachable value is one a mutation cannot redden --
    the fifth review pinned `limit=1` and the suite stayed green.

    Not guarded by HERDR_ENV: that guard is against ACTING on somebody else's
    session, never against reading -- the same reading `campaign-claim.py`
    makes of `agent list`."""
    r = run("herdr", "agent", "read", pane, "--lines", str(limit))
    if r.returncode != 0:
        return None, (f"`herdr agent read {pane} --lines {limit}` exited "
                      f"{r.returncode}: {r.stderr.strip()[:200] or r.stdout.strip()[:200]}")
    return r.stdout, None


def prompt_for(repo, issue):
    """The one sentence. THE BRIEF IS THE SUB-ISSUE (AGENTS.md § Delegate
    launch), so this names it and says nothing else: anything restated here is
    a second copy of the body that goes stale the moment the body is edited."""
    return (f"Work sub-issue {repo}#{issue} now: its body is the whole brief, "
            f"including how to claim, land and report it.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pane")
    ap.add_argument("issue")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--lines", type=int, default=LINES,
                    help=f"how much scrollback to read (default {LINES}, "
                         f"capped by herdr at {READ_CAP})")
    # TWO DOORS, NOT ONE, because the states behind them are not alike.
    # `--assume-fresh` covers what an honest reading CANNOT REACH: no anchor in
    # the window, or a pane that would not read. `--force` covers what it read
    # and found wanting. One flag for both made the bypass of the single case
    # this guard exists for the same keystroke as the routine first assignment
    # -- and with no pane yet carrying an anchor, that keystroke is routine.
    ap.add_argument("--assume-fresh", action="store_true",
                    help="assign a pane whose release this did not see, or "
                         "could not read for. Does NOT waive a pane that was "
                         "read and has not compacted.")
    ap.add_argument("--force", action="store_true",
                    help="assign a pane that was READ and has not compacted "
                         "since its last release. Implies --assume-fresh.")
    args = ap.parse_args()
    # AGENTS.md types a sub-issue as `#N`, so the hash is what a caller
    # copying from an issue or a listing will type. Stripped here, or the
    # prompt names `<repo>##207` and nothing downstream notices.
    issue = args.issue.lstrip("#")
    if not issue.isdigit():
        print(f"refusing: {args.issue!r} is not a sub-issue number. This "
              f"prompts a session to work one,\n  and a prompt naming "
              f"something that is not an issue reads as an instruction all "
              f"the same.", file=sys.stderr)
        return 1
    if args.lines > READ_CAP:
        print(f"refusing: --lines {args.lines} is above herdr's {READ_CAP}-line "
              f"cap, which would read\n  no further while reporting a wider "
              f"window than it had. Pass --lines {READ_CAP} or less, and "
              f"--assume-fresh\n  if the release is further back than that -- "
              f"a release past the cap is exactly what a reading\n  cannot "
              f"reach, which is that flag's whole scope.",
              file=sys.stderr)
        return 1

    m = claim_module()
    sessions, why = m.herdr_sessions()
    if sessions is None:
        print(f"refusing: {why}\n  A listing that did not happen is not a pane "
              f"that is not there.", file=sys.stderr)
        return 1
    print(f"read {len(sessions)} session(s) from herdr agent list")

    row, note = row_for(sessions, args.pane)
    if row is None:
        print(f"refusing: {note}", file=sys.stderr)
        return 1
    print(note)

    ok, why = idle_verdict(row)
    if not ok:
        print(f"refusing: {why}", file=sys.stderr)
        return 1

    screen, why_unread = read_pane(args.pane, args.lines)
    if screen is None:
        # I COULD NOT LOOK, which is neither a yes nor a no. It refuses, and
        # `--assume-fresh` is the way past: an unreadable pane is a reading
        # this cannot make, not a reading that came back bad. `--force`
        # reaches it too, because it implies --assume-fresh.
        if not (args.assume_fresh or args.force):
            print(f"refusing: {why_unread}\n  Whether {args.pane} compacted "
                  f"since its last release is unknown, and an unknown is not"
                  f"\n  a compaction. Pass --assume-fresh to assign anyway.",
                  file=sys.stderr)
            return 1
        # ONE `--force:` LINE PER RUN. This used to print here and again below,
        # twice about the same verdict with the same reason.
        verdict, why = "unread", why_unread
    else:
        verdict, why = compaction_verdict(screen, m.RELEASED, args.pane)
        print(f"{verdict}: {why}")
    # ONE REMEDY LIST PER VERDICT. Shared, it offered `/compact and retry` to
    # `unknown`, which changes nothing when no anchor is in the window, and
    # `raise --lines` to `stale`, where the release was already found and a
    # wider window can only add earlier lines. Neither could work for the
    # verdict it was printed under.
    waived = args.force or (verdict != "stale" and args.assume_fresh)
    if verdict != "compacted" and not waived:
        if verdict == "stale":
            print(f"refusing: {args.pane} has not compacted since its last "
                  f"release.\n  {why}\n  Every turn of {args.repo}#{issue} "
                  f"would re-read the sub-issue before it. Prompt the pane "
                  f"with\n  /compact and retry, or pass --force.",
                  file=sys.stderr)
        else:
            print(f"refusing: {args.pane} shows no release in what this read, "
                  f"which is not evidence\n  it never released. {why}\n"
                  f"  Raise --lines (at most {READ_CAP}) if the release is "
                  f"further back, or pass\n  --assume-fresh if this session "
                  f"genuinely has not worked a sub-issue yet.",
                  file=sys.stderr)
        return 1
    if verdict != "compacted":
        # `--force` names itself whenever it was passed, and it is the ONLY
        # flag that reaches `stale` -- so the `stale` disjunct that used to sit
        # here was dead, and its deadness was itself unobservable.
        flag = "--force" if args.force else "--assume-fresh"
        print(f"{flag}: assigning anyway, verdict was {verdict} -- {why}")

    sentence = prompt_for(args.repo, issue)
    # The one call here that DRIVES a pane, so it carries the guard and names
    # its target explicitly -- which is the pane the caller typed, never one
    # this resolved for itself.
    r = run("herdr", "agent", "prompt", args.pane, sentence,
            env=dict(os.environ, HERDR_ENV="1"))
    if r.returncode != 0:
        print(f"refusing: `herdr agent prompt` exited {r.returncode}: "
              f"{r.stderr.strip()[:200]}\n  The sub-issue is not assigned.",
              file=sys.stderr)
        return 1
    print(f"assigned {args.repo}#{issue} to {args.pane}: {sentence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
