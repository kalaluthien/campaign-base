#!/usr/bin/env python3
"""Assign a sub-issue to a session, by prompting its pane.

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
  (launch)          `sessionLaunch`'s preconditions, read before anything is
                    sent: the sub-issue is open, its campaign is bound to this
                    machine, the pane's session is named for that campaign,
                    and the pane's checkout, when it is on `main`, is not
                    behind `origin/main` -- a session launched behind obeys
                    an AGENTS.md already superseded, and nothing reports it.
                    A checkout on any other branch, or a cwd that is a
                    directory and no git work tree, is said and skipped, since
                    a claim behind `main` is normal; a cwd that is no
                    directory refuses. A sub-issue of no campaign refuses
                    too, although `take` allows one (the 100-sub-issue cap,
                    #213): no binding or name can be read for it, so relink
                    it first. Neither flag reaches
                    these: each is a fact about the launch, not about the
                    transcript. A raw `herdr agent prompt` is read by nothing,
                    so they hold only on this path.
  (not idle)        a pane mid-turn queues the prompt behind work whose outcome
                    nobody has read, and the assignment lands on a session that
                    may be about to report something that changes it.
  `unknown`         no time the claim of the pane's last assigned sub-issue
                    went: no assignment prompt in its transcript (a first
                    assignment, or one in an earlier file a resume left
                    behind), its ref still standing, or GitHub not read.
                    --assume-fresh assigns anyway and says what it overrode.
  `stale`           that claim went and the pane has not compacted since, so
                    the next sub-issue would re-read the last one's whole
                    transcript on every turn. `campaign-claim.py release`
                    enqueues that compaction in a worker's own pane, and
                    sends none from a planner's, which on the base is often
                    the releasing one; this is the reader that says whether
                    this pane's happened. --force is the way
                    past, and it prints what it is overriding.
  (unread)          the transcript could not be found or read. Either flag
                    gets past it, since it is a reading not made rather than
                    one that came back bad.
  (input box)       the pane's input box holds text, or no box was found in
                    what `herdr pane read` returned. A prompt typed after
                    text there is submitted WITH it as one line: `/compact`
                    left unsent and this sentence went in as `/compactWork
                    ...`, an unknown command, and neither happened
                    (rule-check#370 issuecomment-5648017196). No flag
                    reaches it, either way: joining two prompts is never what
                    was meant, and a screen with no box is no chat's -- a
                    `claude remote-control` pane reads so (2026-09-13), and
                    there a typed space or `w` is a keystroke.

  TWO DOORS, NOT ONE, BOTH ON THE TRANSCRIPT'S READING. `--assume-fresh` is
  for what that reading cannot reach, a first assignment included; `--force`
  is for a pane that WAS read and has not compacted. One flag for both made
  bypassing the single case this guard exists for the same keystroke as the
  routine first assignment. The input box has no door.

IT READS THE TRANSCRIPT AND GITHUB, AND OF THE PANE ONLY ITS INPUT BOX, which
is the one thing a transcript cannot show: text typed and not yet sent.
The last assignment prompt
and the compaction come from the session's own transcript, through
`campaign-heartbeat.py`'s `transcript_reading`; when the claim went comes from
GitHub, through the heartbeat's `ref_went`, which its `retire` asks too. The
pane's scrollback was the source until kalaluthien/campaign-base#296, and it
failed both ways (#293, #220). The release line in the releasing pane's
transcript was the source until rule-check#349, and on the base the planner
releases, so a worker read `unknown` for good.

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
import re
import subprocess
import sys


def load(path, alias):
    """The script at `path` as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def claim_module():
    """campaign-claim.py, imported for its reader of herdr's listing and of a
    sub-issue's campaign.

    `herdr_sessions` is campaign-name-session.py's, bound there, and a second
    copy here would drift from it -- AGENTS.md, "Do not write a second reader
    of a rule a script owns".
    The listing's shape is one such rule: which key holds the session id, and
    that a row herdr cannot identify is counted rather than dropped."""
    return load(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "campaign-claim.py"), "campaign_claim")


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError,
            subprocess.TimeoutExpired) as e:
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


# THE INPUT BOX, as `herdr pane read --source detection` shows Claude Code's:
# the last two rule lines of the screen, the first line between them opening
# with the prompt mark. Read 2026-09-13 off six panes: an empty box is the
# mark alone, text typed and not sent follows it after a no-break space, and
# the top rule can carry the session's name (`───── rule-check-planner-10 ─`),
# so a rule is a line OPENING with the rule character: `RULE.match`, which
# anchors at the line's start.
RULE = re.compile(r"\u2500{10,}")
PROMPT_MARK = "\u276f"


def input_line(screen):
    """(text, None) -- what sits in the pane's input box, "" when it is empty
    -- or (None, why) when no box is found. Pure, over the screen's text."""
    lines = screen.splitlines()
    rules = [i for i, line in enumerate(lines) if RULE.match(line)]
    if len(rules) < 2:
        return None, (f"no input box: {len(rules)} rule line(s) in the "
                      f"{len(lines)} line(s) read")
    inside = lines[rules[-2] + 1:rules[-1]]
    if not inside or not inside[0].startswith(PROMPT_MARK):
        first = inside[0].strip()[:60] if inside else "nothing"
        return None, (f"no input box: the last two rule lines hold {first!r}, "
                      f"not a line opening with {PROMPT_MARK}")
    return " ".join(" ".join([inside[0][len(PROMPT_MARK):], *inside[1:]])
                    .split()), None


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
    transcript and of when a claim went, which its `retire` asks too. Loaded
    by path from the `assuming-role` skill."""
    return load(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), ".claude", "skills", "assuming-role", "scripts",
        "campaign-heartbeat.py"), "campaign_heartbeat")


def refs_of(m, hb, parent, slug):
    """The heartbeat's reader of claim refs and their deletion, over the
    campaign the sub-issue being assigned hangs from: the pane's last
    sub-issue is of that campaign too, since a worker is named for one, which
    `launch_refusal` has already read."""
    return hb.refs_reader(hb.claim_reading(parent, slug, m), slug)


def behind_main(cwd):
    """(refusal or None, note) -- is the checkout at `cwd` on `main` and
    behind `origin/main`, after a fetch? Only `main` is read: a claim branch
    behind `main` is normal, and whether it contains `main` is merge
    condition 3's."""
    if not os.path.isdir(cwd):
        return (f"pane cwd {cwd!r} is no directory, so its checkout is "
                f"unread"), None
    r = run("git", "-C", cwd, "branch", "--show-current")
    if r.returncode != 0:
        return None, f"{cwd} is not a git work tree; no checkout to be behind"
    branch = r.stdout.strip()
    if branch != "main":
        return None, (f"{cwd} is on {branch or 'a detached HEAD'}, not main; "
                      f"skipped")
    r = run("git", "-C", cwd, "fetch", "-q", "origin", "main", timeout=60)
    if r.returncode != 0:
        return (f"`git -C {cwd} fetch origin main` exited {r.returncode}: "
                f"{r.stderr.strip()[:160]}; whether it is behind is unread"), None
    r = run("git", "-C", cwd, "rev-list", "--count", "HEAD..origin/main")
    count = r.stdout.strip()
    if r.returncode != 0 or not count.isdigit():
        return (f"`git -C {cwd} rev-list --count HEAD..origin/main` exited "
                f"{r.returncode}: {r.stderr.strip()[:160]}"), None
    note = f"{cwd} is {count} commit(s) behind origin/main"
    if count != "0":
        return (f"{note}. Bring it level, then retry: an install by "
                f"`scripts/campaign-installed.py reach` (AGENTS.md, Installed "
                f"repositories), a clone by `git -C {cwd} pull --ff-only`"), None
    return None, note


def launch_refusal(m, row, issue):
    """(refusal, None) or (None, (parent, slug)) -- `sessionLaunch`'s
    preconditions over the sub-issue and the pane, each printed as it is read.
    Every GitHub reading here that did not happen refuses: a state, a
    binding or a parent that could not be read is not one that admits."""
    settled, note = m.issue_settled(issue)
    if settled is not False:
        return note, None
    print(note)
    parent, note, _ = m.issue_parent(issue)
    if parent is None:
        return f"{note}, so no campaign's binding or name can be read", None
    why = m.binding_refusal(parent)
    if why:
        return f"#{parent}: {why}", None
    print(f"{note}, bound here")
    slug, note = m.campaign_slug(parent)
    if slug is None:
        return note, None
    named = m.NAMES.campaign_of(row["name"])
    if named != slug:
        said = f"`{named}`" if named else "no campaign"
        return (f"pane {row['pane']}'s session {row['name']} is of {said}, "
                f"and #{issue} is of `{slug}`. Name the pane for `{slug}` "
                f"first, or assign a pane of it"), None
    print(f"{row['name']} is of `{slug}`")
    why, note = behind_main(row["cwd"])
    if why:
        return why, None
    print(note)
    return None, (parent, slug)


# THE ONE HOME OF THE ASSIGNMENT SENTENCE'S SHAPE, written by `prompt_for`
# below and read back by `campaign-role-brief.py`, which imports this pattern
# from here by path rather than spelling a second copy of it: the brief hook
# delivers the kind's reference to whichever sub-issue a prompt assigns, so a
# regex of its own there would drift the moment the sentence is reworded. A
# planner typing the opening by hand is read by the same pattern, which is why
# it matches the OPENING and not the whole sentence.
ASSIGNMENT = re.compile(r"Work sub-issue (?P<repo>[\w.-]+/[\w.-]+)#(?P<issue>\d+)")


def prompt_for(repo, issue):
    """The one sentence. THE BRIEF IS THE SUB-ISSUE (AGENTS.md § Delegate
    launch), so this names it and says nothing else: anything restated here is
    a second copy of the body that goes stale the moment the body is edited.
    campaign-context.py is named because it reads what the body cannot hold,
    the comments on it and on what it cites (rule-check#416). Its path is
    absolute, this script's own directory, because a delegate sits in a member
    clone where `scripts/` is not the base's."""
    context = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           "campaign-context.py")
    return (f"Work sub-issue {repo}#{issue} now: run "
            f"`{context} {issue} {repo}` first, then read its "
            f"body, which is the whole brief, including how to claim, land and "
            f"report it.")


def main():
    m = claim_module()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pane")
    ap.add_argument("issue")
    ap.add_argument("--repo", default=m.DEFAULT_REPO)
    # TWO DOORS, NOT ONE, because the states behind them are not alike.
    # `--assume-fresh` covers what an honest reading CANNOT REACH: no time the
    # last sub-issue's claim went, or a transcript that would not read.
    # `--force` covers what it read and found wanting. Neither reaches the
    # input box.
    ap.add_argument("--assume-fresh", action="store_true",
                    help="assign a pane for which no time its last "
                         "sub-issue's claim went was read, or whose transcript "
                         "could not be. Does NOT waive a pane that was read "
                         "and has not compacted.")
    ap.add_argument("--force", action="store_true",
                    help="assign a pane that was READ and has not compacted "
                         "since its last sub-issue's claim went. Implies "
                         "--assume-fresh.")
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

    why, campaign = launch_refusal(m, row, issue)
    if why:
        print(f"refusing: {why}\n  The sub-issue is not assigned.",
              file=sys.stderr)
        return 1

    r = run("herdr", "pane", "read", args.pane, "--source", "detection")
    text, why = (input_line(r.stdout) if r.returncode == 0 else
                 (None, f"`herdr pane read` exited {r.returncode}: "
                        f"{r.stderr.strip()[:160]}"))
    if text is None:
        print(f"refusing: {why}.\n  What waits in {args.pane}'s input box is "
              f"unknown, and a prompt typed after text there\n  goes in as one "
              f"line with it.", file=sys.stderr)
        return 1
    if text:
        print(f"refusing: {args.pane}'s input box holds {text[:120]!r}, and a "
              f"prompt typed now joins it as one line.\n  Send it with "
              f"`herdr pane send-keys {args.pane} enter` -- a /compact then "
              f"runs, so wait for it -- or clear it,\n  then retry.",
              file=sys.stderr)
        return 1
    print(f"input box empty (herdr pane read {args.pane} --source detection)")

    hb = heartbeat_module()
    reading, where, why_unread = hb.read_transcript(row["sid"])
    if reading is None:
        # I COULD NOT LOOK, which is neither a yes nor a no. It refuses, and
        # `--assume-fresh` is the way past: an unreadable transcript is a
        # reading this cannot make, not a reading that came back bad.
        # `--force` reaches it too, because it implies --assume-fresh.
        if not (args.assume_fresh or args.force):
            print(f"refusing: {where}: {why_unread}\n  Whether {args.pane} "
                  f"compacted since its last sub-issue ended is unknown, and "
                  f"an unknown is not\n  a compaction. Pass --assume-fresh to "
                  f"assign anyway.", file=sys.stderr)
            return 1
        verdict, why = "unread", f"{where}: {why_unread}"
    else:
        verdict, why = hb.compacted_since_ref(reading,
                                              refs_of(m, hb, *campaign))
        print(f"{verdict}: {why} (read {where})")
    # ONE REMEDY LIST PER VERDICT: `/compact and retry` changes nothing for
    # `unknown`, and --assume-fresh does not reach `stale`.
    waived = args.force or (verdict != "stale" and args.assume_fresh)
    if verdict != "compacted" and not waived:
        if verdict == "stale":
            print(f"refusing: {args.pane} has not compacted since the claim "
                  f"of its last sub-issue went.\n  {why}\n  Every turn of "
                  f"{args.repo}#{issue} would re-read the sub-issue before "
                  f"it. Prompt the pane with\n  /compact and retry, or pass "
                  f"--force.", file=sys.stderr)
        else:
            print(f"refusing: nothing read says when {args.pane}'s last "
                  f"sub-issue ended, which is not evidence\n  it never "
                  f"worked one: {why}.\n  Pass --assume-fresh if this "
                  f"session genuinely has not worked a sub-issue yet.",
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
