#!/usr/bin/env python3
"""Close one piece of a campaign, or the whole of it, behind the gates every close shares.

    scripts/campaign-close.py [<target>] [--not-planned "<why>"] [--close] [--delete]
    scripts/campaign-close.py sub-issue <N> <issue> --not-planned "<why>"
    scripts/campaign-close.py worker <N> <pane>
    scripts/campaign-close.py repo <N> <owner/repo> [--delete]
    scripts/campaign-close.py here <N> [--delete]
    scripts/campaign-close.py campaign <N> [--close] [--delete]

Every close used to restate the same gates in prose: drop a sub-issue, retire
a worker, drop a repository, let a directory go, close the campaign. This is
where they are defined ONCE, each read off the script that owns it, by the
WORD it prints and never by its exit status -- a reader that crashed exits
non-zero too, so a status reads a bug as a verdict.

THE GATES, and why each exists (printed beside every refusal)

  bound        `campaign-tracker.py bound <N>`: here | elsewhere | unbound.
               A close and a scope change are the bound machine's; letting a
               directory go is every machine's but the bound one.
  directory    `campaign-directory.py <N>`: a path, or `none`. Never composed
               from the slug: the `.campaign` marker says which it is.
  standing     `campaign-tracker.py standing <N>`. A person keeps the
               campaign open, and only they take the label off.
  settlement   `campaign-tracker.py settlement <N>`. The one reader of
               whether a sub-issue is open, and whether the campaign closes.
  live         `campaign-claim.py live <N>`, after `git worktree prune` on
               the base root, since a worktree deleted by hand stays listed
               and would read as an occupied claim: the claim refs, where
               each is checked out, herdr's sessions. A claim somebody is standing
               in, or may be, is asked about and never closed out from under
               them. A listed session is printed by name, "ask it which claim
               it holds"; nothing here writes into a pane but `worker`'s
               `/exit`.
  local-work   `campaign-local-work.py <N> [dir]`. Work that exists only on
               this machine has no other copy.
  installed    `campaign-installed.py check <README>`. A merge that has not
               reached its install is a merge nobody installed.
  retire       `campaign-heartbeat.py <N>` without --apply, one pane's line.
               Only a worker the heartbeat reads as released, compacted and
               idle since holds nothing an `/exit` could lose; that reading is
               the heartbeat's, and nothing here restates it.

THE PERSON'S ANSWERS are flags, and a run without one halts before the write
it would license (exit 3): an open sub-issue's disposition (`sub-issue`'s
--not-planned, or finish it, or reparent it), the close (`--close`), and the
delete (`--delete`). Every run re-reads every gate, so a run that stopped
halfway is run again, never resumed from memory.

A RELEASE ENQUEUES `/compact` ON THE PANE THAT RUNS THIS -- every
`campaign-claim release` does, and `sub-issue` and `campaign` both call it;
a run says so once, beside its first release.

THE FRONT DOOR -- `/close <target>` -- reads the scope off the one target and
prints which it read and from where, then runs that scope as below. The five
scopes stay callable by name; the front door only chooses among them.

  a number        `campaign-tracker.py check <n>`'s kind line: a campaign
                  issue is scope campaign; a sub-issue is scope sub-issue of
                  the parent the line names, and halts without --not-planned.
                  Any other kind refuses.
  owner/repo      scope repo, of the campaign read as for no target.
  a session name  one `herdr agent list` names: scope worker, of the campaign
                  its name's slug names, on the pane herdr gives it.
  no target       scope here, of the campaign whose directory this runs in
                  (its `.campaign` marker), else the one this session's name
                  names (`campaign-tracker.py issue <slug>`).
  anything else   refuses, saying what it tried. A flag the scope read does
                  not take refuses too, rather than being dropped.

SCOPE sub-issue <N> <issue> --not-planned "<why>"

  1. settlement   Holds when: the row for <issue> reads `open` (close, then
                  release) or `dropped` (a run that closed and did not
                  release: skip the close, release). `complete`, `unread`, no
                  row, or a reading that did not finish refuses.
  2. live         Holds when: `live` made all three readings, no claim naming
                  <issue> is checked out on this machine, and either no claim
                  naming <issue> stands or no session of the campaign is
                  listed. A `landed` claim blocks nothing.
  3. local-work   Holds when: the reading finished, no place went unread, and
                  no counted row names a claim branch of <issue>.
  4. author       Holds when: the comment's first line can name who wrote it
                  -- this session's herdr name, which must be of THIS
                  campaign's slug, or `owner` with no session id.
  5. close        `gh issue close --reason "not planned"` with the comment
                  `DECISION <author>: closed not planned -- <why>`.
                  Holds when: gh exited 0 (skipped on a `dropped` row).
  6. release      `campaign-claim.py release <N> <issue>`, only when a claim
                  ref names <issue>. Holds when: it printed `deleted` or `no
                  ref to delete` and no `refusing:`.

SCOPE worker <N> <pane>

  1. retire       Holds when: the heartbeat's line for <pane> opens `retire`.
  2. herdr        Holds when: HERDR_ENV is 1, the guard on every herdr
                  command that drives a pane.
  3. exit         `herdr agent prompt <pane> /exit`, the heartbeat's own
                  action text. Holds when: herdr exited 0.
  4. gone         `herdr agent list`, WAIT_POLLS polls WAIT_EVERY seconds
                  apart. Holds when: no row names <pane>. Still listed is
                  reported with the time measured, and never killed.

SCOPE repo <N> <owner/repo> [--delete] -- drop a member repository

  1. bound        Holds when: `here`.
  2. directory    Holds when: a path; the README there is what is synced.
  3. repos        Holds when: the README's `## Repos` no longer lists it. The
                  person removes that line by hand, as adding one is; no
                  script writes that list.
  4. settlement   Holds when: no open or unread sub-issue lands in it, read
                  from each open sub-issue's own `## Lands in`.
  5. live         Holds when: no claim is checked out in its clone and no
                  session of the campaign was started there.
  6. local-work   Holds when: the reading finished, nothing went unread, and
                  no counted row is that repository's.
  7. sync         The README becomes the campaign issue body, as in
                  `campaign` step 9.
  8. delete       With --delete: its clone under `repos/`, confirmed by the
                  clone's own origin, as in `campaign` step 12.

SCOPE here <N> [--delete] -- this machine lets its directory go, the campaign stays open

  1. bound        Holds when: `elsewhere` or `unbound`. Bound here, the
                  directory is the campaign's working copy: bind the machine
                  taking it first (a person's word), or close the campaign.
  2. directory    `none` finishes: nothing here to let go.
  3. live         Holds when: all three readings were made, no claim is
                  checked out on this machine, no session of it is listed.
  4. local-work   Holds when: the last line reads `clear`.
  5. installed    Holds when: the last line reads `clear`.
  6. delete       With --delete, as in `campaign` step 12. Nothing on GitHub
                  is written.

SCOPE campaign <N> [--close] [--delete]

  1. bound        Holds when: `here`.
  2. directory    A path, or `none`: with none, the sync and the delete are
                  not applicable, and the installed check reads the body.
  3. standing     Holds when: `not-standing`.
  4. live         Holds when: all three readings were made, no claim is
                  checked out, every claim checked out nowhere reads `landed`,
                  and no session of the campaign is listed.
  5. local-work   Holds when: the last line reads `clear`.
  6. installed    Holds when: the last line reads `clear`.
  7. settlement   Holds when: <N> is a campaign issue -- no REPORT that it
                  lacks the label or is itself a sub-issue -- and it ends
                  `; closable` or the index is empty. An open row halts,
                  listed: its disposition is the person's.
  8. author       As in `sub-issue` step 4.
     -- without --close, halt: the close is the person's word.
  9. sync         Holds when: `runtime/campaign-issue-body-derived.md` equals
                  the body now, and after the write the body GitHub stored is
                  the README, `## Repos` read back equal; README and derived
                  copy then take the stored body.
 10. announce     `NOTE <author>: closing campaign #<N>` on the campaign
                  issue, listing what the delete destroys outside `runtime/`
                  and `repos/`. Holds when: gh exited 0.
 11. release      Every claim ref checked out nowhere in `live` read AGAIN
                  here, after the writes, `campaign-claim release --branch`. Holds when: each printed `deleted` or
                  `no ref to delete`. Then `gh issue close` with `NOTE
                  <author>: campaign closed.`; a CLOSED issue skips 9-11's
                  writes and still releases.
     -- without --delete, halt: the delete is the person's word.
 12. delete       Holds when: the path is a direct child of the base root
                  holding `.campaign` and `runtime/`, `lsof +D` lists nothing
                  open under it, and after `rm -rf` it is gone; then `git
                  worktree prune`.

WHAT IT NEVER DOES: kill a session, touch the `standing` label, write the
`## Repos` list, skip a gate, or take a --force.

    exit 0   every step held
    exit 1   a gate refused or a step failed; the lines above say which, why,
             and what was already changed
    exit 3   halted for a person's answer, named with the flag that gives it
"""
import argparse
import importlib.util
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SKILL_SCRIPTS = BASE / ".claude" / "skills" / "assuming-role" / "scripts"
TRACKER_SCRIPT = HERE / "campaign-tracker.py"
CLAIM_SCRIPT = HERE / "campaign-claim.py"
LOCAL_WORK_SCRIPT = HERE / "campaign-local-work.py"
DIRECTORY_SCRIPT = HERE / "campaign-directory.py"
INSTALLED_SCRIPT = HERE / "campaign-installed.py"
HEARTBEAT_SCRIPT = SKILL_SCRIPTS / "campaign-heartbeat.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The owners, imported: the claim-branch shape, the herdr reading, a
# sub-issue's landing repository and the tracker's name are campaign-claim's,
# and the `## Repos` list is campaign-repos' through it; which campaign a
# session name is of is campaign-name-session's; the retire verdict and its
# action are the heartbeat's.
CLAIM = load(CLAIM_SCRIPT, "campaign_claim")
REPOS = CLAIM.REPOS
NAMES = load(SKILL_SCRIPTS / "campaign-name-session.py", "cns")
HEARTBEAT = load(HEARTBEAT_SCRIPT, "campaign_heartbeat")
RETIRE = "retire"
EXIT_TEXT = HEARTBEAT.ACTIONS[RETIRE]

WAIT_EVERY = 5
WAIT_POLLS = 12

WHY = {
    "slug": "every claim branch and session name of the campaign is read "
            "under its slug, and an unread one is not an empty campaign",
    "bound": "a close and a scope change are the bound machine's, and letting "
             "a directory go is every other machine's",
    "directory": "only the `.campaign` marker says which directory is the "
                 "campaign's, and a word that is not a path is not one",
    "standing": "a person keeps the campaign open, and only they take the "
                "label off",
    "settlement": "settlement is the one reader of whether a sub-issue is "
                  "open and whether the campaign closes",
    "live": "a claim somebody is standing in, or may be, is asked about and "
            "never closed out from under them",
    "local-work": "work that exists only on this machine has no other copy",
    "installed": "a merge that has not reached its install is a merge nobody "
                 "installed",
    "repos": "`## Repos` is edited by hand, as adding a repository is; this "
             "script syncs it and never writes it",
    "author": "every comment carries its kind and its writer on its first line",
    "sync": "one write of the campaign issue body must not silently discard "
            "another",
    "announce": "a machine working the campaign against its label can only "
                "answer on the campaign issue",
    "close": "a close is a GitHub fact or it is nothing",
    "release": "a claim ref is residue only once it is deleted",
    "delete": "the delete is the one step nothing recovers",
    "retire": "only a worker the heartbeat reads as released, compacted and "
              "idle since holds nothing an /exit could lose",
    "herdr": "a herdr command that drives a pane runs only inside herdr "
             "(HERDR_ENV=1), so it cannot act on somebody else's session",
    "exit": "a session leaves by fact, and the fact is its pane stopping",
    "gone": "a session still listed is asked, never killed",
    "target": "the scope is read off the target, and a target read as nothing "
              "closes nothing",
}


class Refused(Exception):
    def __init__(self, gate, reason, changed="nothing was changed"):
        super().__init__(reason)
        self.gate, self.reason, self.changed = gate, reason, changed


class Halt(Exception):
    """Every gate up to here held, and the next step is a person's answer."""
    def __init__(self, question, flag):
        super().__init__(question)
        self.question, self.flag = question, flag


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


def script(path, *args):
    r = run(sys.executable, str(path), *args)
    return (r.stdout or "") + (r.stderr or "")


def word_of(path, *args):
    """(the first line of stdout, stderr) of a reader that answers one word."""
    r = run(sys.executable, str(path), *args)
    return (r.stdout or "").strip(), (r.stderr or "").strip()[:160]


def holds(step, evidence):
    print(f"{step:<11} holds -- {evidence}")


# ------------------------------------------------------------- the readings
# Pure: each takes what its owner printed and returns what the gate needs.


SETTLED = re.compile(r"-- \d+/\d+ settled")
SETTLEMENT_HEAD = re.compile(r"^campaign issue \S+#\d+\s+\[(\w+)\]")
SETTLEMENT_ROW = re.compile(r"^  (\S+/\S+#\d+)\s+(\S+)")
# campaign-tracker's two REPORTs that the number is no campaign issue: no
# `campaign` label, or a parent of its own. Closing either closes the wrong
# thing, so both refuse.
NOT_A_CAMPAIGN = ("may be a sub-issue read as a campaign issue",
                  "is itself a sub-issue of")


def settlement_word(text, issue):
    """(word, line) for <issue>'s row, or (None, why)."""
    ref = f"{CLAIM.TRACKER}#{issue}"
    finished = False
    for line in text.splitlines():
        t = line.split()
        if len(t) >= 2 and t[0] == ref:
            return t[1], line.strip()
        finished |= bool(SETTLED.search(line)) or "the index is empty" in line
    if finished:
        return None, f"{ref} is not in the campaign's sub-issue index"
    last = text.strip().splitlines()[-1:] or ["<no output>"]
    return None, f"settlement did not finish reading: {last[0].strip()[:200]}"


def settlement_rows(text):
    """The campaign issue's state, every row as (ref, word, line), and whether
    the reader finished and called the campaign closable."""
    out = {"state": None, "rows": [], "finished": False, "closable": False,
           "not_campaign": []}
    for line in text.splitlines():
        if any(x in line for x in NOT_A_CAMPAIGN):
            out["not_campaign"].append(line.strip())
        head = SETTLEMENT_HEAD.match(line)
        if head:
            out["state"] = head.group(1)
        row = SETTLEMENT_ROW.match(line)
        if row:
            out["rows"].append((row.group(1), row.group(2), line.strip()))
        if SETTLED.search(line):
            out["finished"] = True
            out["closable"] = line.rstrip().endswith("; closable")
        if "the index is empty" in line:
            out["finished"] = out["closable"] = True
    return out


LIVE_GROUPS = (("claims checked out on this machine", "occupied"),
               ("claims checked out nowhere on this machine", "vacant"),
               ("live sessions of ", "sessions"),
               ("sessions named for no campaign", None))


def live_reading(text, n, slug):
    """`campaign-claim live`'s groups: claim rows as (branch, issue, rest),
    session rows as (name, status, pane, cwd). A row is a row only if its
    first word is a claim branch or a session name of this campaign, so the
    notes printed under each group are never read as one."""
    out = {"read": False, "occupied": [], "vacant": [], "sessions": [],
           "unread": []}
    group = None
    for line in text.splitlines():
        if line.startswith("all three readings were made."):
            out["read"] = True
        # What `live` could not read, named by its own `!!` and `FAILED:`
        # lines; the `!!` ones print twice, so they are kept once.
        said = line.strip()
        if (said.startswith("!!") or "-- FAILED:" in said) \
                and said not in out["unread"]:
            out["unread"].append(said)
        head = next((k for h, k in LIVE_GROUPS if line.startswith(h)), False)
        if head is not False:
            group = head
            continue
        if not line.startswith("  "):
            group = None
            continue
        t = line.split()
        if not t or group is None:
            continue
        if group == "sessions":
            if len(t) >= 3 and NAMES.campaign_of(t[0]) == slug:
                out["sessions"].append((t[0], t[1], t[2], " ".join(t[3:])))
            continue
        issue = CLAIM.issue_of_branch(t[0], n, slug)
        if issue is not None:
            out[group].append((t[0], issue, " ".join(t[1:])))
    return out


def claims_of(reading, issue):
    """(checked out here, standing elsewhere) for <issue>. `landed` is work on
    main whose ref outlived it, and stands in nobody's way."""
    here = [(b, rest) for b, i, rest in reading["occupied"] if i == issue]
    away = [(b, rest) for b, i, rest in reading["vacant"]
            if i == issue and not rest.startswith("landed as")]
    return here, away


LOCAL_ROW = re.compile(r"^  ([ ~]) (\S+)\s")
LOCAL_VERDICT = re.compile(r"-- \d+ item\(s\) exist only on this machine")


def local_reading(text):
    """(finished, unread, counted rows as (repository, line), last line). A
    counted row opens with a blank mark, an uncounted one with `~`."""
    lines = text.strip().splitlines()
    last = lines[-1].strip() if lines else ""
    finished = bool(LOCAL_VERDICT.search(last))
    rows = [(m.group(2), line.strip()) for line in lines
            for m in [LOCAL_ROW.match(line)] if m and m.group(1) == " "]
    return finished, finished and "went unread" in last, rows, last


def local_rows(text, n, slug, issue):
    """`local_reading`, its rows narrowed to those naming <issue>'s claims."""
    finished, unread, rows, last = local_reading(text)
    mine = [line for _, line in rows
            if any(CLAIM.issue_of_branch(tok.strip("[];,"), n, slug) == issue
                   for tok in line.split())]
    return finished, unread, mine, last


HEARTBEAT_LINE = r"^(\S+) {pane} (\S+): (.*)$"


def heartbeat_line(text, pane):
    """(word, name, reason) of the heartbeat's verdict line for <pane>."""
    m = re.search(HEARTBEAT_LINE.format(pane=re.escape(pane)), text, re.M)
    return m.groups() if m else None


def status_text(slug, issue, name):
    return (f"STATUS to {name}: {slug}#{issue} is about to be closed not "
            f"planned. Are you working it? Say what you are doing, what exists "
            f"only on this machine, and whether it is safe to stop.")


def leftovers(directory):
    """Every entry the delete destroys outside `runtime/` and `repos/`, files,
    directories and symlinks alike, relative and sorted. A git checkout -- a
    worktree -- is one line and not its files: local-work has read it, and
    its files would outgrow the comment the list goes into."""
    skip = {directory / "runtime", directory / "repos"}
    out = []
    for dirpath, dirnames, filenames in os.walk(directory):
        d = Path(dirpath)
        dirnames[:] = [x for x in dirnames if d / x not in skip]
        checkouts = [x for x in dirnames if (d / x / ".git").exists()]
        dirnames[:] = [x for x in dirnames if x not in checkouts]
        out += [str((d / x).relative_to(directory)) for x in dirnames + filenames
                if d / x not in skip]
        out += [f"{(d / x).relative_to(directory)}/ (a git checkout)"
                for x in checkouts]
    return sorted(out)


# ------------------------------------------------------------- the gates


def slug_of(n):
    slug, note = CLAIM.campaign_slug(n)
    if slug is None:
        raise Refused("slug", f"the campaign's slug did not read: {note}")
    return slug


def gate_bound(n, want_here):
    said, err = word_of(TRACKER_SCRIPT, "bound", n)
    word = said.split(" ")[0]
    if word not in ("here", "elsewhere", "unbound"):
        raise Refused("bound", f"campaign-tracker bound {n} answered "
                               f"{said or err or '<nothing>'!r}")
    if (word == "here") != want_here:
        raise Refused("bound", f"#{n} reads `{said}`" + (
            "; close it, or change its scope, from the machine it is bound to"
            if want_here else "; bind the machine taking it first (a person's "
            "word), or close the campaign"))
    holds("bound", said)


def base_root(gate):
    root, why = CLAIM.base_root()
    if root is None:
        raise Refused(gate, f"the base root did not resolve: {why}")
    return Path(root)


def read_directory(n, need=False):
    # THE BASE IS PASSED, never left to the cwd: the delete below resolves it
    # from this script, and the two must name one base.
    said, err = word_of(DIRECTORY_SCRIPT, n, str(base_root("directory")))
    if said == "none" and not need:
        holds("directory", "none on this machine")
        return None
    if not said.startswith("/"):
        raise Refused("directory", f"campaign-directory {n} answered "
                                   f"{said or '<nothing>'!r}: {err}")
    holds("directory", said)
    return Path(said)


def gate_standing(n):
    said, err = word_of(TRACKER_SCRIPT, "standing", n)
    if said == "not-standing":
        holds("standing", said)
        return
    raise Refused("standing", f"#{n} carries the `standing` label"
                  if said == "standing" else
                  f"campaign-tracker standing {n} answered "
                  f"{said or err or '<nothing>'!r}")


def read_live(n, slug):
    root = base_root("live")
    r = run("git", "-C", str(root), "worktree", "prune")
    print(f"  pruned stale worktree entries under {root}" if r.returncode == 0
          else f"  git worktree prune exited {r.returncode}: a worktree deleted "
               f"by hand may read below as an occupied claim")
    reading = live_reading(script(CLAIM_SCRIPT, "live", n), n, slug)
    if not reading["read"]:
        raise Refused("live", "`campaign-claim live` did not make all three "
                              "readings, so no count from it is safe: "
                              + (" | ".join(reading["unread"])
                                 or "it named nothing it could not read"))
    return reading


def gate_live(n, slug, issue):
    reading = read_live(n, slug)
    here, away = claims_of(reading, issue)
    who = reading["sessions"]
    if here or (away and who):
        for name, status, pane, _ in who:
            print(f"  ask {name} ({status}, {pane}): "
                  f"{status_text(slug, issue, name)}")
        what = ([f"{b} is checked out at {p}" for b, p in here]
                + [f"{b} ({m}) stands and {len(who)} session(s) of {slug} "
                   f"are listed" for b, m in away])
        raise Refused("live", "; ".join(what))
    holds("live", f"{len(here) + len(away)} open claim(s) of #{issue}, "
                  f"{len(who)} session(s) of {slug} listed")
    return [b for b, i, _ in reading["occupied"] + reading["vacant"]
            if i == issue]


def gate_live_whole(n, slug, vacant_blocks, under=None):
    """The live gate over a whole campaign, or over what stands `under` one
    clone. Sessions are printed by name to be asked, and nothing is sent."""
    reading = read_live(n, slug)

    def inside(path):
        return under is None or Path(path).is_relative_to(under)
    here = [(b, p) for b, _, p in reading["occupied"] if inside(p)]
    away = [(b, m) for b, _, m in reading["vacant"]
            if vacant_blocks and not m.startswith("landed as")]
    who = [s for s in reading["sessions"] if inside(s[3])]
    for name, status, pane, _cwd in who:
        print(f"  ask {name} ({status}, {pane}): which claim do you hold?")
    what = ([f"{b} is checked out at {p}" for b, p in here]
            + [f"{b} is checked out nowhere here and reads `{m}`"
               for b, m in away]
            + [f"{len(who)} session(s) of {slug} are listed"] * bool(who))
    if what:
        raise Refused("live", "; ".join(what))
    holds("live", f"{len(reading['vacant'])} claim ref(s) checked out nowhere, "
                  f"none occupied, no session listed")
    return reading


def gate_local_work(n, slug, issue):
    directory = read_directory(n)
    args = [n, str(directory)] if directory else [n]
    finished, unread, rows, last = local_rows(
        script(LOCAL_WORK_SCRIPT, *args), n, slug, issue)
    if not finished:
        raise Refused("local-work", f"the reading did not finish: {last[:200]}")
    if unread:
        raise Refused("local-work", f"places went unread, and one may hold "
                                    f"#{issue}'s branch: {last}")
    if rows:
        raise Refused("local-work", "work on #%s's branch exists only on this "
                                    "machine: %s" % (issue, " | ".join(rows)))
    holds("local-work", f"no counted row names #{issue}'s branch ({last})")


def gate_local_whole(n, directory, repo=None):
    args = [n, str(directory)] if directory else [n]
    done, gaps, rows, last = local_reading(script(LOCAL_WORK_SCRIPT, *args))
    if not done:
        raise Refused("local-work", f"the whole reading did not finish: {last[:200]}")
    if gaps:
        raise Refused("local-work", f"places went unread: {last}")
    kept = [ln for r, ln in rows if not repo or REPOS.key(r) == REPOS.key(repo)]
    if kept:
        raise Refused("local-work", f"{len(kept)} item(s) exist only on this "
                                    f"machine: " + " | ".join(kept))
    holds("local-work", last if not repo else f"no counted row is {repo}'s")


def body_of(n):
    r = run("gh", "issue", "view", n, "-R", CLAIM.TRACKER, "--json", "body",
            "-q", ".body")
    return r.stdout if r.returncode == 0 else None


def gate_installed(n, directory):
    if directory:
        lines = script(INSTALLED_SCRIPT, "check",
                       str(directory / "README.md")).strip().splitlines()
    else:
        body = body_of(n)
        if body is None:
            raise Refused("installed", f"the body of #{n} did not read, and "
                                       f"with no directory it is the list")
        with tempfile.NamedTemporaryFile("w", suffix=".md") as f:
            f.write(body)
            f.flush()
            lines = script(INSTALLED_SCRIPT, "check", f.name).strip().splitlines()
    last = lines[-1].strip() if lines else "<no output>"
    if not last.endswith("-- clear"):
        raise Refused("installed", " | ".join(ln.strip() for ln in lines[-4:]))
    holds("installed", last)


def gate_settlement(n, issue):
    word, line = settlement_word(script(TRACKER_SCRIPT, "settlement", n), issue)
    if word == "open":
        holds("settlement", line)
        return "open"
    if word == "dropped":
        holds("settlement", f"{line} -- already closed, so release only")
        return "dropped"
    if word is None:
        raise Refused("settlement", line)
    raise Refused("settlement", f"the row reads `{word}`, not `open`: {line}")


def read_settlement(n):
    s = settlement_rows(script(TRACKER_SCRIPT, "settlement", n))
    if not s["finished"]:
        raise Refused("settlement", "the reading did not finish")
    if s["not_campaign"]:
        raise Refused("settlement", f"#{n} is not a campaign issue: "
                                    + " | ".join(s["not_campaign"]))
    unread_rows = [ln for _, w, ln in s["rows"] if w == "unread"]
    if unread_rows:
        raise Refused("settlement", "rows that did not read settle nothing: "
                                    + " | ".join(unread_rows))
    return s


def gate_closable(n):
    s = read_settlement(n)
    if not s["closable"]:
        rows = [ln for _, w, ln in s["rows"] if w == "open"]
        for ln in rows:
            print(f"  open  {ln}")
        raise Halt(f"{len(rows)} open sub-issue(s) need a disposition, the "
                   f"person's: finish it, drop it with `campaign-close.py "
                   f"sub-issue {n} <issue> --not-planned <why>`, or reparent "
                   f"it", None)
    holds("settlement", f"closable, #{n} is {s['state']}")
    return s["state"]


def gate_landing(n, repo):
    hits = []
    for ref, word, line in read_settlement(n)["rows"]:
        if word != "open":
            continue
        subject, _named, note = CLAIM.issue_repo(ref.rsplit("#", 1)[1],
                                                 CLAIM.DEFAULT_REPO)
        if subject is None:
            raise Refused("settlement", f"where {ref} lands did not read: {note}")
        if REPOS.key(subject) == REPOS.key(repo):
            hits.append(line)
    if hits:
        raise Refused("settlement", f"open sub-issue(s) land in {repo}: finish, "
                                    f"drop or reparent them first: "
                                    + " | ".join(hits))
    holds("settlement", f"no open sub-issue lands in {repo}")


def gate_unlisted(directory, repo):
    rows, why = REPOS.read_repos((directory / "README.md").read_text())
    if rows is None:
        raise Refused("repos", f"the README's ## Repos did not read: {why}")
    if any(REPOS.key(r) == REPOS.key(repo) for r, _, _ in rows):
        raise Refused("repos", f"the README still lists {repo}: remove its "
                               f"line from ## Repos first")
    holds("repos", f"the README does not list {repo}")


def gate_author(slug):
    sid = os.environ.get(CLAIM.SESSION_ID_VAR)
    if not sid:
        holds("author", "no session id, so a person: owner")
        return "owner"
    sessions, why = CLAIM.herdr_sessions()
    name = ((sessions or {}).get(sid) or {}).get("name")
    if not name or NAMES.campaign_of(name) != slug:
        raise Refused("author", f"session {sid} has no name of {slug} in herdr "
                                f"({why or name or 'no row'})")
    holds("author", name)
    return name


# ------------------------------------------------------------- the writes


def step_close(issue, author, why):
    body = f"DECISION {author}: closed not planned -- {why}"
    r = run("gh", "issue", "close", issue, "-R", CLAIM.TRACKER,
            "--reason", "not planned", "--comment", body)
    if r.returncode != 0:
        raise Refused("close", f"gh exited {r.returncode}: "
                               f"{(r.stderr or '').strip()[:200]}")
    holds("close", f"{CLAIM.TRACKER}#{issue} closed not planned")


def release_refusal(text):
    """Why a `campaign-claim release` did not release, or None. Its words:
    `refusing:` refuses, and `deleted` or `no ref to delete` is done."""
    print("\n".join(f"  | {line}" for line in text.rstrip().splitlines()))
    lines = text.splitlines()
    refusal = next((ln for ln in lines if ln.startswith("refusing:")), None)
    done = any(ln.startswith("deleted ") or "no ref to delete" in ln
               for ln in lines)
    if refusal or not done:
        return refusal or "release printed neither `deleted` nor `no ref to delete`"
    return None


COMPACT_NOTE = ("  each `campaign-claim release` enqueues /compact on the "
                "pane that runs this")


def step_release(n, issue):
    print(COMPACT_NOTE)
    why = release_refusal(script(CLAIM_SCRIPT, "release", n, issue))
    if why:
        raise Refused("release", why,
                      changed=f"#{issue} is closed not planned; its claim "
                              f"still stands -- re-run once the cause is fixed")
    holds("release", "the claim ref is gone")


def step_release_all(n, reading, changed):
    rows = reading["vacant"]
    if not rows:
        holds("release", "no claim ref of the campaign is left")
        return
    print(COMPACT_NOTE)
    failed = []
    for branch, issue, _ in rows:
        why = release_refusal(script(CLAIM_SCRIPT, "release", n, issue,
                                     "--branch", branch))
        if why:
            failed.append(f"{branch}: {why}")
    if failed:
        raise Refused("release", " | ".join(failed), changed=changed)
    holds("release", f"{len(rows)} claim ref(s) released")


def step_sync(n, directory):
    readme = directory / "README.md"
    derived = directory / "runtime" / "campaign-issue-body-derived.md"
    text = readme.read_text()
    before, why = REPOS.read_repos(text)
    if before is None:
        raise Refused("sync", f"the README's ## Repos did not read: {why}")
    if not derived.is_file():
        raise Refused("sync", f"no {derived} to compare the body against")
    now = body_of(n)
    if now is None:
        raise Refused("sync", f"the body of #{n} did not read")
    if now.rstrip("\n") != derived.read_text().rstrip("\n"):
        raise Refused("sync", "the body moved since the README was derived "
                              "from it: read what the other writer did, fold "
                              "it into the README, refresh the derived copy, "
                              "re-run")
    if now.rstrip("\n") == text.rstrip("\n"):
        holds("sync", "the body already is the README")
        return False
    r = run("gh", "issue", "edit", n, "-R", CLAIM.TRACKER, "--body-file",
            str(readme))
    if r.returncode != 0:
        raise Refused("sync", f"gh exited {r.returncode}: "
                              f"{(r.stderr or '').strip()[:200]}")
    after = body_of(n)
    rows, _ = REPOS.read_repos(after or "")
    if after is None or rows != before or after.rstrip("\n") != text.rstrip("\n"):
        raise Refused("sync", "the body GitHub stored is not the README; the "
                              "README and the derived copy are left as they "
                              "were", changed="the body was written")
    readme.write_text(after)
    derived.write_text(after)
    holds("sync", f"the body is the README, {len(before)} ## Repos entr(ies) "
                  f"read back")
    return True


def step_announce(n, author, directory, changed):
    where = socket.gethostname().split(".")[0]
    listing = "\n".join(leftovers(directory)) if directory else ""
    body = (f"NOTE {author}: closing campaign #{n} from {where}. Say so here "
            f"if you are still in it.\n\n"
            + (f"The delete destroys these entries under the campaign "
               f"directory, `runtime/` and `repos/` excluded:\n\n```\n"
               f"{listing or 'no entries outside runtime/ and repos/'}\n```\n"
               if directory else "No directory of it on this machine.\n"))
    with tempfile.NamedTemporaryFile("w", suffix=".md") as f:
        f.write(body)
        f.flush()
        r = run("gh", "issue", "comment", n, "-R", CLAIM.TRACKER,
                "--body-file", f.name)
    if r.returncode != 0:
        raise Refused("announce", f"gh exited {r.returncode}: "
                                  f"{(r.stderr or '').strip()[:200]}",
                      changed=changed)
    holds("announce", f"NOTE posted on #{n}")


def step_close_campaign(n, author):
    r = run("gh", "issue", "close", n, "-R", CLAIM.TRACKER, "--comment",
            f"NOTE {author}: campaign closed.")
    if r.returncode:
        raise Refused("close", f"gh exited {r.returncode}: "
                               f"{(r.stderr or '').strip()[:200]}",
                      changed="announced, and its claim refs released")
    holds("close", f"#{n} closed")


def campaign_dir_shape(path):
    root = base_root("delete")
    if path.parent != root or not (
            (path / ".campaign").is_file() and (path / "runtime").is_dir()):
        raise Refused("delete", f"{path} is not a campaign directory directly "
                                f"under the base root {root}")
    return path


def clone_of(directory, repo):
    """Its clone under `repos/`, confirmed by the clone's own origin, or None
    when there is none. The folder is the entry's last segment, the name
    campaign-repos refuses two entries for sharing."""
    path = directory / "repos" / REPOS.slug(repo).rsplit("/", 1)[-1]
    if not path.exists():
        return None
    where = CLAIM.remote_of(str(path))
    if where is None or REPOS.key(where) != REPOS.key(repo):
        raise Refused("delete", f"{path} is not a clone of {repo}: its origin "
                                f"reads {where or 'nothing git could read'}")
    return path


def step_delete(path):
    r = run("lsof", "+D", str(path))
    if r.returncode == 127:
        raise Refused("delete", f"lsof did not run, so what is open under "
                                f"{path} is unknown")
    open_rows = (r.stdout or "").splitlines()[1:]
    if open_rows:
        raise Refused("delete", f"{len(open_rows)} file(s) open under {path}: "
                                + " | ".join(ln[:80] for ln in open_rows[:5]))
    shutil.rmtree(path)
    if path.exists():
        raise Refused("delete", f"{path} is still there after the delete")
    root, _ = CLAIM.base_root()
    if root:
        run("git", "-C", str(root), "worktree", "prune")
    holds("delete", f"{path} is gone")


def wait_gone(pane, read=None, sleep=None, polls=WAIT_POLLS,
              every=WAIT_EVERY):
    """(gone, what the last poll read). A listing that did not read is not an
    absence, so it is one more poll and never the answer."""
    read, sleep = read or CLAIM.herdr_sessions, sleep or time.sleep
    note = "no poll ran"
    for k in range(polls):
        sessions, why = read()
        if sessions is None:
            note = f"poll {k + 1}: {why}"
        elif not any(row["pane"] == pane for row in sessions.values()):
            return True, f"poll {k + 1}: {pane} is not listed"
        else:
            note = f"poll {k + 1}: {pane} is still listed"
        if k + 1 < polls:
            sleep(every)
    return False, note


# ------------------------------------------------------------- the scopes


def sub_issue(args):
    n, issue = args.campaign_issue, args.issue
    slug = slug_of(n)
    word = gate_settlement(n, issue)
    branches = gate_live(n, slug, issue)
    gate_local_work(n, slug, issue)
    author = gate_author(slug)
    if word == "open":
        step_close(issue, author, args.not_planned)
    if branches:
        step_release(n, issue)
    else:
        holds("release", f"no claim ref names #{issue}; nothing to release")


def worker(args):
    n, pane = args.campaign_issue, args.pane
    text = script(HEARTBEAT_SCRIPT, n)
    line = heartbeat_line(text, pane)
    if line is None:
        first = (text.strip().splitlines() or ["<no output>"])[0]
        raise Refused("retire", f"the heartbeat gave {pane} no verdict -- not "
                                f"a session of #{n}, or it could not read: "
                                f"{first[:200]}")
    word, name, reason = line
    if word != RETIRE:
        raise Refused("retire", f"the heartbeat reads {name} as `{word}`: "
                                f"{reason}")
    holds("retire", f"{name}: {reason}")
    if os.environ.get("HERDR_ENV") != "1":
        raise Refused("herdr", "HERDR_ENV is not 1")
    holds("herdr", "HERDR_ENV=1")
    r = run("herdr", "agent", "prompt", pane, EXIT_TEXT)
    if r.returncode != 0:
        raise Refused("exit", f"herdr exited {r.returncode}: "
                              f"{(r.stderr or '').strip()[:200]}")
    holds("exit", f"sent {EXIT_TEXT} to {pane}")
    began = time.monotonic()
    gone, note = wait_gone(pane)
    if not gone:
        raise Refused("gone", f"{note} after {time.monotonic() - began:.0f}s: "
                              f"say so on the sub-issue it worked, and ask",
                      changed=f"{EXIT_TEXT} was sent to {pane}")
    holds("gone", note)


def drop_repo(args):
    n, repo = args.campaign_issue, REPOS.slug(args.repo)
    if repo is None or REPOS.is_base(repo):
        raise Refused("repos", f"{args.repo!r} is not a member repository")
    slug = slug_of(n)
    gate_bound(n, want_here=True)
    directory = read_directory(n, need=True)
    gate_unlisted(directory, repo)
    gate_landing(n, repo)
    clone = clone_of(directory, repo)
    gate_live_whole(n, slug, vacant_blocks=False,
                    under=clone or directory / "repos" / repo.rsplit("/", 1)[-1])
    gate_local_whole(n, directory, repo=repo)
    step_sync(n, directory)
    if clone is None:
        holds("delete", f"no clone of {repo} on this machine")
        return
    if not args.delete:
        raise Halt(f"deleting {clone} is the person's word", "--delete")
    step_delete(clone)


def here(args):
    n = args.campaign_issue
    slug = slug_of(n)
    gate_bound(n, want_here=False)
    directory = read_directory(n)
    if directory is None:
        holds("delete", "nothing on this machine to let go")
        return
    gate_live_whole(n, slug, vacant_blocks=False)
    gate_local_whole(n, directory)
    gate_installed(n, directory)
    if not args.delete:
        raise Halt(f"deleting {directory} is the person's word", "--delete")
    step_delete(campaign_dir_shape(directory))


def campaign(args):
    n = args.campaign_issue
    slug = slug_of(n)
    gate_bound(n, want_here=True)
    directory = read_directory(n)
    gate_standing(n)
    reading = gate_live_whole(n, slug, vacant_blocks=True)
    gate_local_whole(n, directory)
    gate_installed(n, directory)
    state = gate_closable(n)
    author = gate_author(slug)
    if state == "CLOSED":
        holds("close", f"#{n} is already closed")
        step_release_all(n, reading, changed="nothing new; the issue was "
                                             "already closed")
    else:
        if not args.close:
            raise Halt(f"every gate held; closing #{n} is the person's word",
                       "--close")
        wrote = bool(directory) and step_sync(n, directory)
        step_announce(n, author, directory, changed="the body was written"
                      if wrote else "nothing was changed")
        step_release_all(n, read_live(n, slug),
                         changed="the body synced and the close announced; "
                                 "#%s is still open" % n)
        step_close_campaign(n, author)
    if directory is None:
        holds("delete", "no directory on this machine")
        return
    if not args.delete:
        raise Halt(f"#{n} is closed; deleting {directory} is the person's word",
                   "--delete")
    step_delete(campaign_dir_shape(directory))


# ------------------------------------------------------------- the front door


SCOPES = ("sub-issue", "worker", "repo", "here", "campaign")
NUMBER = re.compile(r"^#?(\d+)$")
CHECK_LINE = re.compile(r"^read \S+#(\d+): (campaign issue|sub-issue|stray|"
                        r"third kind) \(label `[^`]+`: (?:yes|no), parent: "
                        r"(#\d+|no)\)", re.M)
# The flags each scope takes. Any other one refuses: a flag dropped in silence
# is an answer the person gave and nobody read.
FLAGS = {"campaign": ("close", "delete"), "here": ("delete",),
         "repo": ("delete",), "sub-issue": ("not_planned",), "worker": ()}


def campaign_named(slug, whose):
    n, err = word_of(TRACKER_SCRIPT, "issue", slug)
    if not n.isdigit():
        raise Refused("target", f"{whose} names slug {slug}, and "
                                f"campaign-tracker issue {slug} answered "
                                f"{n or err or '<nothing>'!r}")
    return n


def own_campaign():
    """(N, where it was read): the campaign directory this runs in, by its
    marker, else the campaign this session's herdr name names."""
    guard = load(HERE / "check-campaign-claim.py", "guard")
    here_dir = guard.campaign_dir_of(Path.cwd().resolve(),
                                     base_root("target").resolve())
    fields = guard.marker_fields(here_dir) if here_dir else None
    if fields:
        return fields[0], f"the marker {here_dir / '.campaign'}"
    sid = os.environ.get(CLAIM.SESSION_ID_VAR)
    sessions, why = CLAIM.herdr_sessions() if sid else (None, "no session id")
    name = ((sessions or {}).get(sid) or {}).get("name")
    slug = NAMES.campaign_of(name) if name else None
    if slug is None:
        raise Refused("target", f"no campaign directory holds {Path.cwd()}, "
                                f"and this session has no campaign name "
                                f"({why or name or 'no row'})")
    return campaign_named(slug, f"this session's name {name}"), \
        f"this session's name {name}"


def front_door(args):
    """The scope's own argv, read off the one target, with what was read and
    from where printed first."""
    t = args.target
    if t is None:
        n, where = own_campaign()
        scope, argv, how = "here", ["here", n], f"no target; #{n} from {where}"
    elif NUMBER.match(t):
        n = NUMBER.match(t).group(1)
        text = script(TRACKER_SCRIPT, "check", n)
        m = CHECK_LINE.search(text)
        if m is None:
            raise Refused("target", f"campaign-tracker check {n} printed no kind "
                                    f"line: {(text.strip().splitlines() or ['<nothing>'])[0][:160]}")
        kind, parent = m.group(2), m.group(3)
        if kind == "campaign issue":
            scope, argv = "campaign", ["campaign", n]
        elif kind == "sub-issue":
            scope, argv = "sub-issue", ["sub-issue", parent.lstrip("#"), n]
        else:
            raise Refused("target", f"#{n} reads as a {kind} (campaign-tracker "
                                    f"check), neither a campaign issue nor a "
                                    f"sub-issue")
        how = (f"#{n} is a {kind}" + (f" of {parent}" if kind == "sub-issue"
                                      else "") + ", by campaign-tracker check")
    elif "/" in t:
        repo = REPOS.slug(t)
        if repo is None:
            raise Refused("target", f"{t!r} has a slash and names no owner/repo")
        n, where = own_campaign()
        scope, argv = "repo", ["repo", n, repo]
        how = f"{repo} is a repository; #{n} from {where}"
    else:
        sessions, why = CLAIM.herdr_sessions()
        if sessions is None:
            raise Refused("target", f"{t!r} is not a number or owner/repo, and "
                                    f"herdr agent list did not read: {why}")
        panes = [r["pane"] for r in sessions.values() if r["name"] == t]
        if len(panes) != 1:
            raise Refused("target", f"{t!r} is not a number, not owner/repo, and "
                                    f"{len(panes)} of the {len(sessions)} "
                                    f"sessions herdr lists carry that name")
        slug = NAMES.campaign_of(t)
        if slug is None:
            raise Refused("target", f"session {t} carries no campaign name")
        n = campaign_named(slug, f"session {t}")
        scope, argv = "worker", ["worker", n, panes[0]]
        how = f"{t} is a session herdr lists, pane {panes[0]}, of #{n}"
    extra = [f for f in ("close", "delete", "not_planned")
             if getattr(args, f) and f not in FLAGS[scope]]
    if extra:
        raise Refused("target", f"read as scope {scope} ({how}), which does not "
                                f"take --{extra[0].replace('_', '-')}")
    print(f"{'target':<11} read as scope {scope} -- {how}")
    if scope == "sub-issue":
        if not args.not_planned:
            raise Halt(f"#{n} is a sub-issue; dropping it not planned is the "
                       f"person's disposition", '--not-planned "<why>"')
        argv += ["--not-planned", args.not_planned]
    return argv + ["--close"] * bool(args.close) + ["--delete"] * bool(args.delete)


def front_parser():
    ap = argparse.ArgumentParser(
        prog="campaign-close.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?",
                    help="an issue number, a session name, owner/repo, or none")
    ap.add_argument("--not-planned", metavar="WHY")
    ap.add_argument("--close", action="store_true")
    ap.add_argument("--delete", action="store_true")
    return ap


def answered(fn):
    """Run one step of the close, printing a refusal or a halt the one way."""
    try:
        return 0, fn()
    except Refused as r:
        print(f"REFUSE {r.gate}: {r.reason}")
        print(f"  why: {WHY[r.gate]}")
        print(f"  {r.changed}")
        return 1, None
    except Halt as h:
        print(f"HALT: {h.question}"
              + (f" -- re-run with {h.flag} once they say so" if h.flag else ""))
        return 3, None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] not in SCOPES + ("-h", "--help"):
        code, argv = answered(lambda: front_door(front_parser().parse_args(argv)))
        if code:
            return code
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="scope", required=True)

    def number(s):
        return s.lstrip("#")

    s = sub.add_parser("sub-issue", help="close one sub-issue not planned, "
                                         "then release its claim")
    s.add_argument("campaign_issue", type=number)
    s.add_argument("issue", type=number)
    s.add_argument("--not-planned", required=True, metavar="WHY",
                   help="the person's reason, written into the closing comment")
    s.set_defaults(fn=sub_issue)
    w = sub.add_parser("worker", help="send /exit to a worker the heartbeat "
                                      "reads as retirable, and wait for it")
    w.add_argument("campaign_issue", type=number)
    w.add_argument("pane")
    w.set_defaults(fn=worker)
    r = sub.add_parser("repo", help="drop a member repository the README "
                                    "no longer lists, and its clone")
    r.add_argument("campaign_issue", type=number)
    r.add_argument("repo")
    r.add_argument("--delete", action="store_true",
                   help="the person's word to delete the clone")
    r.set_defaults(fn=drop_repo)
    h = sub.add_parser("here", help="let this machine's directory go; the "
                                    "campaign stays open")
    h.add_argument("campaign_issue", type=number)
    h.add_argument("--delete", action="store_true",
                   help="the person's word to delete the directory")
    h.set_defaults(fn=here)
    c = sub.add_parser("campaign", help="close the campaign, then delete its "
                                        "directory")
    c.add_argument("campaign_issue", type=number)
    c.add_argument("--close", action="store_true",
                   help="the person's word to close the campaign")
    c.add_argument("--delete", action="store_true",
                   help="the person's word to delete the directory")
    c.set_defaults(fn=campaign)
    args = ap.parse_args(argv)
    return answered(lambda: args.fn(args))[0]


if __name__ == "__main__":
    sys.exit(main())
