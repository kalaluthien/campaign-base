#!/usr/bin/env python3
"""Assign a sub-issue to a session already running, by prompting its pane.

    campaign-assign.py <pane> <sub-issue> [--repo owner/repo]
                       [--assume-fresh] [--force]

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
  `unknown`         the session's transcript holds no release of this pane.
                    That is a session that never released -- or one whose
                    release sits in an earlier file a resume left behind, and
                    nothing here tells the two apart. --assume-fresh assigns
                    anyway and says what it overrode.
  `stale`           the pane released a sub-issue and has not compacted since,
                    so the next sub-issue would re-read the last one's whole
                    transcript on every turn. `campaign-claim.py release`
                    enqueues that compaction; this is the reader that says
                    whether it happened. --force is the way past, and it prints
                    what it is overriding.
  (unread)          the transcript could not be found or read. Either flag
                    gets past it, since it is a reading not made rather than
                    one that came back bad.

  TWO DOORS, NOT ONE. `--assume-fresh` is for what the reading cannot reach, a
  first assignment included; `--force` is for a pane that WAS read and has
  not compacted. One flag for both made bypassing the single case this guard
  exists for the same keystroke as the routine first assignment.

IT READS THE TRANSCRIPT, NOT THE PANE. The release and the compaction come from
the session's own transcript, through `campaign-heartbeat.py`'s
`transcript_reading`, the one reader of them. The pane's scrollback was the
source until kalaluthien/campaign-base#296, and it failed both ways: `herdr
pane read` caps at 1000 lines and a compaction clears the release line, so a
pane that released and compacted read `unknown` (#293, twice on 2026-09-10);
and a compaction marker is harness text with no pane in it, so one read out of
another pane could answer for this one (#220). In the transcript the release is
a tool result of this session's own, naming its pane, and the compaction is a
`compact_boundary` record that no printed text can forge.

WHAT IT CANNOT DO IS SAID, NEVER SKIPPED

Every reading here can come back absent for a reason that is not an answer: the
listing may not run, the transcript may not be found. Each prints what was
read, from where, and which branch was taken, and none of them silently
assigns.

PROBED ON THIS MACHINE 2026-09-05

  * `herdr agent prompt <pane> "/compact"` runs the command; it is not typed as
    text.
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
    """(row, note) -- the herdr row whose `pane_id` is this pane, with its
    session id under `sid`, which names the transcript. Pure.

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
    return dict(row, sid=sid), (f"pane {pane} is {row['name']} ({sid}), "
                                f"status {row['status']}")


def idle_verdict(row):
    """(ok, why). Pure. `idle` and `done` are both a finished turn; every other
    word herdr prints is a turn in flight, and an unknown word is treated as
    one, because a status this does not recognise is not evidence of rest."""
    if row["status"] in ("idle", "done"):
        return True, None
    return False, (f"status is {row['status']}, not idle. A prompt to a pane "
                   f"mid-turn queues behind work nobody has read the outcome "
                   f"of.")


def heartbeat_module():
    """campaign-heartbeat.py, imported for its reader of a session's
    transcript -- the one reader of the release and the compaction, which the
    heartbeat asks too. Loaded by path from the `assuming-role` skill."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), ".claude", "skills", "assuming-role", "scripts",
        "campaign-heartbeat.py")
    spec = importlib.util.spec_from_file_location("campaign_heartbeat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    # TWO DOORS, NOT ONE, because the states behind them are not alike.
    # `--assume-fresh` covers what an honest reading CANNOT REACH: no release
    # in the transcript, or a transcript that would not read. `--force` covers
    # what it read and found wanting.
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

    hb = heartbeat_module()
    reading, where, why_unread = hb.read_transcript(row["sid"], m.RELEASED,
                                                    args.pane)
    if reading is None:
        # I COULD NOT LOOK, which is neither a yes nor a no. It refuses, and
        # `--assume-fresh` is the way past: an unreadable transcript is a
        # reading this cannot make, not a reading that came back bad.
        # `--force` reaches it too, because it implies --assume-fresh.
        if not (args.assume_fresh or args.force):
            print(f"refusing: {where}: {why_unread}\n  Whether {args.pane} "
                  f"compacted since its last release is unknown, and an "
                  f"unknown is not\n  a compaction. Pass --assume-fresh to "
                  f"assign anyway.", file=sys.stderr)
            return 1
        verdict, why = "unread", f"{where}: {why_unread}"
    else:
        verdict, why = hb.compacted_since_release(reading)
        print(f"{verdict}: {why} (read {where})")
    # ONE REMEDY LIST PER VERDICT: `/compact and retry` changes nothing for
    # `unknown`, and --assume-fresh does not reach `stale`.
    waived = args.force or (verdict != "stale" and args.assume_fresh)
    if verdict != "compacted" and not waived:
        if verdict == "stale":
            print(f"refusing: {args.pane} has not compacted since its last "
                  f"release.\n  {why}\n  Every turn of {args.repo}#{issue} "
                  f"would re-read the sub-issue before it. Prompt the pane "
                  f"with\n  /compact and retry, or pass --force.",
                  file=sys.stderr)
        else:
            print(f"refusing: {args.pane} shows no release in its transcript, "
                  f"which is not evidence\n  it never released: {why}.\n"
                  f"  Pass --assume-fresh if this session genuinely has not "
                  f"worked a sub-issue yet.", file=sys.stderr)
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
