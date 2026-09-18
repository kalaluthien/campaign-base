#!/usr/bin/env python3
"""Read a session's transcript, and when the claim of the sub-issue it names went.

    .claude/skills/assuming-role/scripts/campaign-transcript.py <session id>

prints `read_transcript`'s reading as JSON and the file it was read from.

    exit 0   the transcript was found and read
    exit 1   it was not, and the line says why

A MODULE FIRST: four scripts import it rather than run it, for one of two
questions. `campaign-assign.py` asks whether a pane compacted since its last
sub-issue's claim went, which needs both; `campaign-claim.py` asks whether a
compaction is already pending; `campaign-model.py` reads the `/model` and
`/effort` a session ran; `campaign-push.py` reads a message's text blocks.

WHAT IS READ, AND FROM WHERE

  the transcript       `~/.claude/projects/*/<session id>.jsonl`, the file
                       herdr's session id names. The last assignment prompt,
                       the last compaction, the model and the commands run all
                       come from here and never from the screen:
                       `transcript_reading` is the one reader.
  the refs             a campaign's claim refs, through `campaign-claim.py`'s
                       readers (`claim_reading`): a `<slug>/<N>-` ref
                       standing is sub-issue N still claimed, and GitHub is
                       asked when none does.
  the pull requests    when N's claim went, on every repository the refs were
                       read on: the latest `head_ref_deleted` in the timeline
                       of each pull request whose head is under `<slug>/<N>-`
                       (`gh pr list`, the newest 100).
  the events feed      the fallback, only where N has no pull request: the
                       latest DeleteEvent of a branch under `<slug>/<N>-` in
                       `gh api repos/<repo>/events`. It is not the first
                       source because it drops or delays a delete -- two, an
                       hour late (2026-09-12) -- and is unordered across
                       pages (2026-09-13).

EVERY READING ERRS TOWARD UNKNOWN. A claim with no pull request -- or one
older than the newest 100 -- falls to the feed, which holds the last 300
events however long that is and drops some deletes, so one it dropped reads
as no deletion at all, and so does a pull request whose head is not deleted
yet. An assignment whose prompt sits in an earlier file a resume left behind
is no assignment. Each comes back `unknown` with what was read beside it,
never a time guessed at.

A COMPACTION PENDING IS A WINDOW, not a moment. It runs from a `/compact` --
the queue's `enqueue` record written the moment it is sent into a busy pane,
the bare user record, or the command's echo -- to the `compact_boundary` it
ends in, a minute or more later; inside it the transcript still reads the
context the compaction will replace, so a second `/compact` sent there
compacts the fresh context the first leaves (rule-check#296, 2026-09-13). A
`/compact` refused -- too few messages, or an error such as the session
limit -- ends the window as a boundary does. One taken off the queue unrun
reads pending until the next compaction, which errs toward keeping it.

NO READING IS STORED. Every answer here is a function of what the sources say
now, so a call repeated with nothing changed says the same thing.
"""
import argparse
import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[3]   # .claude/skills/assuming-role/scripts -> the base

# The assignment sentence's shape: `ASSIGNMENT` there is its one home.
ASSIGN_SCRIPT = BASE / "scripts" / "campaign-assign.py"
# GitHub's events feed: 100 a page, and HTTP 422 past the third page (probed
# 2026-09-12), so a repository's last 300 events.
EVENT_PAGES = 3

# What a compaction writes into the transcript around itself, which is not a
# prompt: the `/compact` that `release` queues (a bare user record), the
# command's own record, its caveat and its stdout. Read off this machine's
# transcripts 2026-09-10, where the bare one sat after 19 of 22 releases;
# everything else a user record carries as text counts as a prompt, which errs
# toward reading it as work.
COMPACTION_ECHOES = ("<command-name>/compact<", "<local-command-")
QUEUED_COMPACT = "/compact"   # exactly: `/compact <focus>` is not the queued one
# A `/compact` that ran and wrote no boundary: a `local_command` record opening
# with one of these (9 and 5 on this machine, 2026-09-13).
COMPACT_REFUSALS = ("<local-command-stdout>Not enough messages to compact",
                    "<local-command-stderr>Error during compaction")
# A background task's notice reaching an IDLE pane: a plain user record, no
# isMeta, its text opening with this tag (820 on this machine, 2026-09-11).
# Busy, the same notice is a queued_command of another mode.
TASK_NOTICE = "<task-notification>"
# A slash command the session ran, and what it printed: two user records in
# that order, sharing one timestamp (probed on rule-check#431).
COMMAND_OPEN, STDOUT_OPEN = "<command-name>/", "<local-command-stdout>"


def load(path, name):
    """The script at `path` as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ASSIGNMENT = load(ASSIGN_SCRIPT, "campaign_assign").ASSIGNMENT


def run(*args, **kw):
    """A command that is not installed is a failed run, not a traceback."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


# --------------------------------------------------------- the transcript


def transcript_path(session_id):
    """(path, None), or (None, why). The file herdr's session id names."""
    root = Path.home() / ".claude" / "projects"
    hits = sorted(root.glob(f"*/{session_id}.jsonl"))
    if len(hits) != 1:
        return None, (f"{len(hits)} transcript(s) named {session_id}.jsonl "
                      f"under {root}")
    return hits[0], None


def texts(content):
    """The text a message carries, as a list of strings."""
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in content or []
            if isinstance(b, dict) and b.get("type") == "text"]


def is_compact(content):
    """Is this content a `/compact` of any shape: the bare one, or its echo?"""
    said = "".join(texts(content)).strip()
    return said == QUEUED_COMPACT or said.startswith(COMPACTION_ECHOES[0])


def is_prompt(content):
    """Does this content carry text a person or a peer typed, rather than a
    command's own echo or a background task's notice? An assignment sentence
    counts only where this says yes, so a notice quoting one is not one."""
    said = "".join(texts(content)).strip()
    return bool(said) and not said.startswith(
        COMPACTION_ECHOES + (TASK_NOTICE,))


def assignment(content):
    """The sub-issue number an assignment sentence in this content names, or
    None: `ASSIGNMENT`, as the brief hook reads it."""
    hit = ASSIGNMENT.search("".join(texts(content)))
    return int(hit.group("issue")) if hit else None


def transcript_reading(lines):
    """What one session's transcript says. Pure, over its lines. Returns a
    dict of timestamps, the model and the commands run:

      assigned   the sub-issue the last prompt carrying an assignment
                 sentence names, at `assigned_at`: `campaign-assign.py`'s
                 prompt and the launch brief. Only a prompt counts, so a
                 summary or a tool result quoting the sentence does not.
      compacted  the last `compact_boundary` record. A record type, so no
                 text anything prints can forge it.
      compact_asked  the last `/compact`: a user record or a queued prompt
                 that `is_compact`, or a `queue-operation` enqueueing the
                 bare one. Later than `compacted` and `compact_refused`,
                 a compaction is pending.
      compact_refused  the last `local_command` record of COMPACT_REFUSALS:
                 a `/compact` that ran and compacted nothing.
      model      the model of the latest assistant record, at `model_at`. A
                 `<synthetic>` record -- a limit banner, an API error -- is
                 the harness's and is skipped.
      commands   every slash command the session ran, IN FILE ORDER, as
                 [name, what it printed or None]: `campaign-model.py` reads
                 its `/model` and `/effort` confirmations here.
      records    how many records were read, which `ref_went` quotes when it
                 finds no assignment among them.

    A PROMPT is a user record carrying text that is not a command's own echo
    and not a harness note (`isMeta`), or one typed while the pane was busy:
    an `attachment` record of type `queued_command`, mode `prompt`, not
    `isMeta` -- which a peer's message is, and a task notification is another
    mode. Only a prompt's assignment sentence counts.

    BY TIMESTAMP, NOT POSITION: a command's record carries the time it was
    queued, which can be earlier than records written before it, so every
    "the last" above is the latest timestamp. Records of a subagent
    (`isSidechain`) are its own, not this session's, and are not read."""
    out = {"assigned": None, "assigned_at": None, "compacted": None,
           "compact_asked": None, "compact_refused": None, "records": 0,
           "model": None, "model_at": None, "commands": []}

    def later(key, ts):
        if out[key] is None or ts > out[key]:
            out[key] = ts

    def said(ts, content):
        n = assignment(content)
        if n is not None and (out["assigned_at"] is None
                              or ts > out["assigned_at"]):
            out["assigned"], out["assigned_at"] = n, ts

    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("isSidechain"):
            continue
        ts = r.get("timestamp")
        if not isinstance(ts, str):
            continue
        out["records"] += 1
        kind, msg = r.get("type"), r.get("message") or {}
        if kind == "system" and r.get("subtype") == "compact_boundary":
            later("compacted", ts)
        elif (kind == "system" and r.get("subtype") == "local_command"
              and str(r.get("content")).startswith(COMPACT_REFUSALS)):
            later("compact_refused", ts)
        elif kind == "assistant" and msg.get("model") != "<synthetic>":
            if msg.get("model") and (out["model_at"] is None or ts > out["model_at"]):
                out["model"], out["model_at"] = msg["model"], ts
        elif kind == "user":
            if r.get("isMeta") or r.get("isCompactSummary"):
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.startswith(COMMAND_OPEN):
                out["commands"].append([content[len(COMMAND_OPEN):].split("<")[0], None])
            elif (isinstance(content, str) and content.startswith(STDOUT_OPEN)
                  and out["commands"] and out["commands"][-1][1] is None):
                out["commands"][-1][1] = content[len(STDOUT_OPEN):].split("</local-command-stdout>")[0]
            if is_compact(content):
                later("compact_asked", ts)
            if is_prompt(content):
                said(ts, content)
        elif kind == "attachment":
            a = r.get("attachment") or {}
            if (a.get("type") == "queued_command"
                    and a.get("commandMode") == "prompt"
                    and not a.get("isMeta")):
                if is_compact(a.get("prompt")):
                    later("compact_asked", ts)
                if is_prompt(a.get("prompt")):
                    said(ts, a.get("prompt"))
        elif (kind == "queue-operation" and r.get("operation") == "enqueue"
              and r.get("content") == QUEUED_COMPACT):
            later("compact_asked", ts)
    return out


def compaction_pending(reading):
    """Why a compaction is pending, or None: a `/compact` later than the last
    `compact_boundary` and the last refusal (the header's window)."""
    asked = reading["compact_asked"]
    done = max((t for t in (reading["compacted"], reading["compact_refused"])
                if t), key=when, default=None)
    if asked and (done is None or when(asked) > when(done)):
        return (f"compaction pending: /compact at {asked}, no compact_boundary "
                f"since" + (f" {done}" if done else ""))
    return None


def read_transcript(session_id):
    """(reading, where, None), or (None, where, why)."""
    path, why = transcript_path(session_id)
    if path is None:
        return None, "no transcript", why
    try:
        with open(path, encoding="utf-8") as fh:
            return transcript_reading(fh), str(path), None
    except OSError as e:
        return None, str(path), f"could not read it: {e}"


def when(ts):
    """A transcript's or GitHub's ISO timestamp, as a time: the two write
    different precisions, so their strings do not sort against each other."""
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ref_went(reading, refs):
    """(when, why): when the claim of the sub-issue this session was last
    assigned went, or None and why no such time is read. Pure over
    `transcript_reading`'s dict and `refs`, a function from a sub-issue to
    ((refs standing, when the last went or None, what was read), None) or
    (None, why)."""
    n = reading["assigned"]
    if n is None:
        return None, (f"no assignment prompt in {reading['records']} "
                      f"record(s)")
    got, why = refs(n)
    if got is None:
        return None, f"assigned #{n}; {why}"
    standing, went, read = got
    if standing:
        return None, f"assigned #{n}; {', '.join(standing)} standing ({read})"
    if went is None:
        return None, f"assigned #{n}; no ref standing and no deletion read ({read})"
    return went, f"assigned #{n}; no ref standing, the last went {went} ({read})"


def compacted_since_ref(reading, refs):
    """(verdict, why) for `campaign-assign.py`: has this session compacted
    since the claim of its last assigned sub-issue went?

      compacted  a compaction later than that
      stale      the claim went and no compaction after it
      unknown    no time it went: no assignment prompt, a ref still
                 standing, or a deletion not read"""
    went, why = ref_went(reading, refs)
    if went is None:
        return "unknown", why
    comp = reading["compacted"]
    if comp and when(comp) > when(went):
        return "compacted", f"{why}, compacted {comp}"
    return "stale", f"{why}, no compaction after it"


# --------------------------------------------------------- the claim refs


def claim_reading(issue, slug, claim, repos=None):
    """(({claim branch: its sub-issue}, the repositories read), None), or
    (None, why): the campaign's claim refs on the tracker and every
    `## Repos` entry, through campaign-claim's readers, which `claim` is the
    module of. `repos`, a list, receives the repositories once `## Repos`
    reads, refs or not, so a caller that wants them and no refs still has
    them."""
    listed, why = claim.campaign_repos(issue)
    if listed is None:
        return None, why
    repos = repos if repos is not None else []
    repos[:] = [claim.TRACKER] + [r for r in listed if r != claim.TRACKER]
    found, unread = claim.all_refs(repos, issue, slug)
    if unread:
        return None, "; ".join(unread)
    out = {}
    for b in found:
        n = claim.issue_of_branch(b, slug)
        out[b] = int(n) if n else None
    return (out, repos), None


def pull_requests(repo):
    """([(number, head branch)], None), or (None, why): the newest 100 pull
    requests of `repo`, any state."""
    r = run("gh", "pr", "list", "-R", repo, "--state", "all", "--limit",
            "100", "--json", "number,headRefName")
    if r.returncode != 0:
        return None, f"gh pr list -R {repo}: {r.stderr.strip()[:160]}"
    try:
        return [(p["number"], p["headRefName"])
                for p in json.loads(r.stdout or "[]")], None
    except (ValueError, KeyError, TypeError) as e:
        return None, f"gh pr list -R {repo}: {e.__class__.__name__}"


def head_deletions(repo, number):
    """([times], None), or (None, why): every `head_ref_deleted` in a pull
    request's timeline. Recorded at the delete, and kept for good."""
    path = f"repos/{repo}/issues/{number}/timeline"
    r = run("gh", "api", "--paginate", path, "--jq",
            '.[] | select(.event == "head_ref_deleted") | .created_at')
    if r.returncode != 0:
        return None, f"gh api {path}: {r.stderr.strip()[:160]}"
    return r.stdout.split(), None


def events_feed(repo):
    """(events, None), or (None, why): a repository's events feed, every page
    to EVENT_PAGES, or to a short one. The fallback for a claim with no pull
    request, for two facts measured here: it DROPS OR DELAYS A DELETE (two
    branch deletes absent an hour later, the events around them present,
    2026-09-12), and it is UNORDERED ACROSS PAGES (29 inversions over pages
    1-3, page 1 holding an event two days older than page 2's newest,
    2026-09-13). So every page is read, and no hit ends it."""
    events = []
    for page in range(1, EVENT_PAGES + 1):
        path = f"repos/{repo}/events?per_page=100&page={page}"
        r = run("gh", "api", path)
        if r.returncode != 0:
            return None, f"gh api {path}: {r.stderr.strip()[:160]}"
        try:
            got = json.loads(r.stdout or "[]")
        except ValueError as e:
            return None, f"gh api {path}: {e.__class__.__name__}"
        events += got
        if len(got) < 100:
            break
    return events, None


def latest(times):
    """The latest of ISO timestamps, or None."""
    return max(times, key=when, default=None)


def deletion_of(repos, prefix, pulls, timeline, feed):
    """((when or None, which source said it), None), or (None, why): when a
    branch under `prefix` was last deleted on `repos`. Pure over three
    readers -- `pull_requests`, `head_deletions`, `events_feed` -- in a fixed
    order: the timelines of the pull requests whose head is under `prefix`,
    latest wins; the feed only where there is none, since a claim with a
    pull request never needs it and reading it there re-imports its lag."""
    heads = []
    for repo in repos:
        got, why = pulls(repo)
        if got is None:
            return None, why
        heads += [(repo, n) for n, head in got if head.startswith(prefix)]
    if heads:
        times = []
        for repo, n in heads:
            got, why = timeline(repo, n)
            if got is None:
                return None, why
            times += got
        return (latest(times), "the timeline of " + ", ".join(
            f"{repo} pr#{n}" for repo, n in heads)), None
    times, read = [], []
    for repo in repos:
        events, why = feed(repo)
        if events is None:
            return None, f"no pull request, and the events feed not read: {why}"
        times += [e["created_at"] for e in events
                  if e.get("type") == "DeleteEvent"
                  and (e.get("payload") or {}).get("ref_type") == "branch"
                  and str(e["payload"].get("ref")).startswith(prefix)]
        read.append(f"{repo} {len(events)} event(s)")
    return (latest(times), "no pull request, so the events feed, the "
            "fallback: " + "; ".join(read)), None


def refs_reader(claims, slug):
    """A function from a sub-issue n to ((the `<slug>/<n>-` refs standing,
    when the last went or None, what was read), None) or (None, why), over
    `claims`, `claim_reading`'s answer. GitHub is asked only when no ref
    stands, and each repository's pull requests and feed once per reader,
    however many sub-issues ask."""
    once = {}

    def cached(fn):
        def read(repo):
            if (fn, repo) not in once:
                once[(fn, repo)] = fn(repo)
            return once[(fn, repo)]
        return read

    pulls, feed = cached(pull_requests), cached(events_feed)

    def of(n):
        got, why = claims
        if got is None:
            return None, f"the refs not read: {why}"
        branches, repos = got
        prefix = f"{slug}/{n}-"
        read = f"{prefix}* on {', '.join(repos)}"
        standing = sorted(b for b, m in branches.items() if m == n)
        if standing:
            return (standing, None, read), None
        found, why = deletion_of(repos, prefix, pulls, head_deletions, feed)
        if found is None:
            return None, f"{read}: no ref standing; its deletion not read: {why}"
        return ([], found[0], f"{read}; {found[1]}"), None
    return of


# --------------------------------------------------------- the command


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session_id", help="herdr's session id for the pane")
    args = ap.parse_args(argv)
    reading, where, why = read_transcript(args.session_id)
    if reading is None:
        print(f"could not read the transcript ({where}): {why}")
        return 1
    print(f"read: {where}")
    print(json.dumps(reading, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
