#!/usr/bin/env python3
"""Tally what a campaign spent, per sub-issue and per session, from the transcripts.

A campaign's cost is not written anywhere. The only record of it is the harness's
own transcripts under `~/.claude/projects/<slugged-cwd>/`, one JSONL file per
session and one more per in-process subagent, and every question about what the
campaign costs is a question about how those turns group. This is the one reader
of that grouping, so a later run can be compared with an earlier one.

THE METHOD, IN THE ORDER IT IS APPLIED

A *turn* is one assistant API message. The transcript writes one record per
content block, and every record repeats that one call's `usage`, so a run that
sums records double counts -- on this machine's corpus 48,564 records carry
25,088 messages, and summing them inflates output by 1.9x. Turns are therefore
keyed by `message.id`; the first record decides attribution, and `fold` says how
the rest are taken.

`output_tokens` needs one more reading. The records written before a call
settles carry a placeholder rather than the count -- a 7,493-character
`tool_use` block records `output_tokens: 2` -- and the settled record is the one
whose `usage.iterations` is non-empty. The largest per message is that record
when the message settled. When *no* record of a message settled the number is a
floor and nothing better exists in the file, so every subcommand prints how many
turns and how many body bytes are in that state: an output column read without
that line is a lower bound presented as a measurement.

Then, in order, each turn is either dropped or attributed:

  window       `message.timestamp`, never the file's mtime: a session file is
               appended to for as long as the session lives, so mtime admits
               turns from before the window and hides none of them.
  place        the record's `cwd` must be inside one of the `--base` roots. A
               path that no longer exists is *not* the test -- a finished
               sub-issue's worktree is deleted and its turns are still this
               campaign's -- so containment is read as a string.
  brief        for a subagent transcript only, its own first prompt: a
               `/code-review <level> <pr>` operand or an explicit
               `<owner>/<repo>#<issue>`, mapped through `--pr-map`. It comes
               first because a subagent inherits the place its parent was
               standing in -- all seven reviews of PR #184, whose head is
               `campaign-1/177-`, ran from a session on
               `campaign-1/178-delegate-clone-hooks` -- so the place says where
               the parent was and the brief says what the subagent was for.
  worktree     `cwd` ending `/worktrees/<issue>` names the sub-issue outright.
  branch       else `gitBranch` matching `<slug>/<issue>-`. A window that
               predates #181 is read by naming its old token to `--slug`,
               which is used as a literal.
  parent       else, for a subagent transcript, whichever issue its parent
               session was last attributed to when the subagent started.
  carry        else, only for a record carrying no `gitBranch` at all, the last
               one this transcript did record. A record that says `main` is not
               missing its branch -- it is on `main`, and inheriting the claim
               branch a session left an hour ago is how a planner's turns get
               charged to whichever sub-issue it happened to visit.
  unattributed else -- and that row is the honest one for a planner, which works
               at the base root on `main` and whose turns split across no
               sub-issue at all.

Two things are deliberately not read. A bare number is never an issue: line
numbers, shas, byte counts and Korean JSON escapes all match one, and a tally
keyed on them puts its largest rows on issues that have no worktree and no
branch. A branch *name in text* is not one either: `campaign-claim live` prints
every claim of the campaign, so a session that ran it once would otherwise carry
the last-printed branch over every turn that followed -- measured here, that
alone attributed 20,585 output tokens to `campaign-1/7-`, an issue with no work
in the window.

Every subcommand prints the sample it read -- files, turns, and the turns each
of the drops above took away -- because an empty corpus and a quiet campaign
print the same table otherwise.

SUBCOMMANDS

  issues     one row per sub-issue: turns, output, new input, cache read
  sessions   the same, per session name (`<slug>-<role>-<n>`)
  turns      one JSON object per turn, for an analysis this script does not make
  reviews    one row per review round: its PR, level, and cost, with every
             subagent its `/code-review` fanned out into rolled into the round
             that spawned it (`nested` counts how many)
  tool-echo  turns whose tool results are the output of this repository's own
             scripts, and what those results cost to carry
  reads      what reading files returned: per file, per session, and the
             shares the routing verdict below reads
  denials    auto-mode classifier denials, by reason, over every transcript
             under --root, every project and no window
  review-posts  the `gh pr comment`/`gh pr review` calls that posted a REVIEW,
             and how each ended: the denominator beside `denials`

THE READS RULE, WRITTEN BEFORE ITS FIRST RUN (rule-check#412)

A read is a Read tool call, or a Bash command whose FIRST segment's command
word is `cat`, `head`, `tail`, or `sed` with `-n`; nothing else. A read word in
a later segment -- `cd x && cat f`, `git log | head` -- is counted apart as a
floor line, never as a read. Its file is the Read's `file_path`, or the
segment's last path argument resolved against the record's cwd; a read naming
none, or only a path the shell would expand (`$P/f`, `*.py`), is unsplittable and
counted apart. Its bytes are its result's, measured
as `tool-echo` measures them, over the one walk both share.

A file is over the threshold when it has more than `--threshold` lines, 350 by
default: counted on disk when the file exists now, else from the largest
result it returned, and the table says which. A re-read is a read of a file
the same context -- a session, or one subagent -- already read.

The verdict: when the bytes of reads that are over the threshold OR re-reads
-- the union, since one read can be both -- are at least 30% of all read
bytes, build the routing step; below that, stop.

Columns are `output`, `input_new` (`input_tokens` + `cache_creation_input_tokens`)
and `cache_read`, kept apart because they are priced apart and move for different
reasons: output is what the model wrote, `input_new` is what was newly read into
the window, and `cache_read` is the same context re-read on every turn.

Usage:
  scripts/campaign-token-tally.py issues --since 2026-09-04T00:45:00Z
  scripts/campaign-token-tally.py sessions --since ... --json
  scripts/campaign-token-tally.py turns --since ... > turns.jsonl
  scripts/campaign-token-tally.py reviews --since ...
  scripts/campaign-token-tally.py tool-echo --since ...
  scripts/campaign-token-tally.py reads --since ... [--threshold 350]
  scripts/campaign-token-tally.py denials [--root DIR]
  scripts/campaign-token-tally.py review-posts [--root DIR]
"""
import argparse
import collections
import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

WORKTREE = re.compile(r"/worktrees/(\d+)(?:/|$)")
REVIEW_CMD = re.compile(
    r"/code-review\s+(?P<level>\w+)\s+(?P<pr>\d+)"
    # Anchored to the start of the brief, unlike the slash form above: a slash
    # command essentially never occurs by accident in prose, but "review PR
    # <N> at <level>" is ordinary English a fix-round brief can easily quote
    # back ("address the findings from review PR 276 at medium") without
    # being the round's OWN brief -- anchoring keeps that mention from
    # promoting an unrelated subagent into a round or misattributing its
    # turns. Case-insensitive because nothing about a plain brief's spelling
    # is a wire format the way `/code-review` is: `reviewing.md`'s own call
    # block writes "Review PR <N>" capitalized one line above the lowercase
    # prompt, and a launcher who capitalizes the sentence the way English
    # sentences start would otherwise vanish from every round this exists to
    # price. `#?` because "review PR #276" is as plausible a way to write the
    # number as "review PR 276", and GitHub's own UI writes a pull request
    # with the `#`.
    r"|\A\s*review PR\s+#?(?P<pr2>\d+)\s+at\s+(?P<level2>\w+)",
    re.IGNORECASE)


def review_cmd_groups(m):
    """(level, pr) from a REVIEW_CMD match, either of its two shapes.

    `/code-review <level> <pr>` and the plain-brief `review PR <pr> at
    <level>` write the same two facts in opposite order -- named groups so
    every reader takes one pair, never the position that shape happens not
    to use.
    """
    return m.group("level") or m.group("level2"), int(m.group("pr") or m.group("pr2"))


SCRIPT_NAME = re.compile(r"^((?:campaign|check|install)-[a-z0-9-]+)\.(?:py|sh)$")
# An interpreter runs the file that follows it, and check-campaign-claim's
# PREFIXES deliberately holds no interpreter -- it is looking for `gh`, which
# nothing interprets. Named here, one word per form, for the same reason that
# set names its shells: adding a name reads one more shape and promises nothing
# about the next.
#
# NO SHELL BELONGS HERE, and the shape that costs is named rather than implied.
# The guard already re-reads a shell's `-c` string as segments of its own, so
# `bash -c "scripts/campaign-claim.py"` would be read twice -- once as that
# segment, once as bash's file operand -- and the double count hides behind the
# printed note that says a repeat is legitimate. The price is `sh
# scripts/install-hooks.sh`, a shell running a script *file*, which is no longer
# counted: measured over 17,840 unique Bash commands in this machine's
# transcripts, 4 commands hold that shape and 2 are genuine runs. Two missed
# runs against a double count on every argument-less `-c`, and the missed ones
# land in the `charged` floor this subcommand already prints.
INTERPRETERS = {"python", "python3"}
# The reads rule in the docstring, as the two values it names.
SHELL_READS = {"cat", "head", "tail", "sed"}
BUILD_AT = 0.30


@functools.cache
def guard_module():
    """check-campaign-claim.py, imported for its shell splitter and its
    `base_root`. Cached, so one run loads the 3000-line guard once.

    That guard already owns the one reading of a Bash command's grammar in this
    repository -- `segments` (shlex, with `;|&(){}` as their own tokens, and a
    shell's `-c` string re-read) and `head` (a segment's command word, with
    `VAR=x` and `time`-shaped prefixes stripped and a path reduced to its
    basename). A second reader here drifts from it, and drifted the moment it
    was written: a hand-rolled splitter counted heredoc body lines as commands,
    missed `"$W/scripts/campaign-claim.py" take ...` because of the quote, and
    missed `; do python3 scripts/x.py` because `do` was not in its prefix list.
    All three are cases that guard already had right.
    """
    return load("check-campaign-claim.py", "check_campaign_claim")


@functools.cache
def repos_module():
    """campaign-repos.py, for the base's name alone: `--repo`'s default needs
    that one constant, not the guard (pr#406's REVIEW)."""
    return load("campaign-repos.py", "campaign_repos")


def load(name, alias):
    """A sibling script, imported by path."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scripts_called(command, grammar):
    """The repository's scripts this command *runs*, in the order it runs them.

    A name is not a call. `sed -n 1,120p scripts/check-campaign-claim.py`,
    `grep -n foo scripts/campaign-claim.py` and `git show <sha>:scripts/...`
    each name a script and none of them runs it, and what they return is the
    script's own source -- charged to the script as its output, a majority of
    the bytes, by any reader that matches a name anywhere in the command.

    Returns None when the command will not split, which is not the same answer
    as "runs nothing" and is counted apart.
    """
    segs, _why = grammar.segments(command)
    if segs is None:
        return None
    called = []
    for seg in segs:
        word, rest = grammar.head(seg)
        if word is None:
            continue
        if word in INTERPRETERS:
            operands = [t for t in rest[1:] if not t.startswith("-")]
            if not operands:
                continue
            word = operands[0].rsplit("/", 1)[-1]
        m = SCRIPT_NAME.match(word)
        if m:
            called.append(m.group(1))
    return called


def shell_read(command, grammar):
    """(word, path) for one Bash command, by the reads rule in the docstring.

    `read` with the path the first segment names, or None when it names none;
    `later` when only a later segment reads a named file, which the rule does
    not count; `none` when it reads no file into the window; `unsplit` when it
    will not split. The segments and the command word are the guard's, as for
    `scripts_called`.
    """
    segs, _why = grammar.segments(command)
    if segs is None:
        return "unsplit", None
    words = [(w, rest) for w, rest in map(grammar.head, segs) if w is not None]
    if words and words[0][0] in SHELL_READS:
        return read_operand(*words[0])
    if any(w in SHELL_READS and read_operand(w, rest)[1] for w, rest in words[1:]):
        return "later", None
    return "none", None


def read_operand(word, tokens):
    """(word, path) for a segment opening with a read word: its last path argument.

    Operands stop at the first redirection. Stdout sent to a file returns no
    content, so that segment is no read; `2>/dev/null` and `1>&2` still
    return it. `sed` reads only with `-n` (or `--quiet`, `--silent`) and never
    with `-i` or `-I`, and its first operand is the script unless `-e` or `-f` gave
    one; `head` and `tail` take a value after a bare `-n` or `-c`. A path the
    shell would expand -- `$P/f`, `$(ls)`, `*.py` -- names no file this can read, so
    it is no path.
    """
    args = tokens[1:]
    cut = next((i for i, t in enumerate(args) if t and set(t) <= set("<>&|")),
               len(args))
    fd = args[cut - 1] if 0 < cut < len(args) and args[cut - 1].isdigit() else None
    if cut < len(args) and args[cut] in (">", ">>", ">|", "&>", "&>>") and fd in (None, "1"):
        return "none", None
    args = args[:cut - 1] if fd else args[:cut]
    operands, quiet, script_given, i = [], False, False, 0
    while i < len(args):
        t = args[i]
        i += 1
        if t.startswith("-") and len(t) > 1:
            if word == "sed" and (t.startswith("--in-place")
                                  or (not t.startswith("--") and set(t) & set("iI"))):
                return "none", None
            if word == "sed" and (t in ("--quiet", "--silent")
                                  or (not t.startswith("--") and "n" in t)):
                quiet = True
            if word == "sed" and t in ("-e", "-f"):
                script_given = True
                i += 1
            elif word in ("head", "tail") and t in ("-n", "-c"):
                i += 1
            continue
        operands.append(t)
    if word == "sed":
        if not quiet:
            return "none", None
        if not script_given:
            operands = operands[1:]
    path = operands[-1] if operands else None
    return "read", (None if path and set(path) & set("$`*?[") else path)


def die(why):
    sys.stderr.write(f"campaign-token-tally: {why}\n")
    sys.exit(2)


def base_root():
    """The base root, as the claim guard's `base_root` reads it from this file
    (rule-check#370 row 2)."""
    here = Path(__file__).resolve().parent
    root, note = guard_module().base_root(here)
    if root is None:
        die(f"the base root did not resolve from {here}: {note}")
    return str(root)


def usage_of(message):
    u = message.get("usage")
    if not isinstance(u, dict):
        return None
    return {
        "output": u.get("output_tokens", 0),
        "input_new": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
        "cache_read": u.get("cache_read_input_tokens", 0),
    }


def fold(turn, usage, body_bytes, settled):
    """Fold one more record of a message already seen into its turn.

    Every record of a message repeats that one API call's `usage`, so input and
    cache read are taken once, never summed. `output_tokens` is the exception:
    the records written before the call settled carry a placeholder -- a
    seven-thousand-character tool_use block records `output_tokens: 2` -- and
    only the last record carries the real count, marked by a non-empty
    `usage.iterations`. Taking the largest is that last one whenever the message
    settled, and the best available floor when it did not.
    """
    turn["output"] = max(turn["output"], usage["output"])
    turn["body_bytes"] += body_bytes
    turn["settled"] = turn["settled"] or settled


def text_blocks(message):
    """Every string a message carries, whatever block shape it came in."""
    content = message.get("content")
    if isinstance(content, str):
        yield content
        return
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            yield block.get("text", "")
        elif kind == "tool_use":
            yield json.dumps(block.get("input", {}), ensure_ascii=False)
        elif kind == "tool_result":
            inner = block.get("content")
            if isinstance(inner, str):
                yield inner
            elif isinstance(inner, list):
                for part in inner:
                    if isinstance(part, dict) and part.get("type") == "text":
                        yield part.get("text", "")


def read_pr_map(path, repo, offline):
    """PR number -> issue number, from each pull request's own head branch.

    A review's brief names the pull request; the tally is keyed on the
    sub-issue, and the branch is what carries one to the other.
    """
    if path:
        raw = json.load(open(path))
    elif offline:
        return {}
    else:
        listed = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--state", "all", "--limit", "300",
             "--json", "number,headRefName"],
            capture_output=True, text=True)
        if listed.returncode != 0:
            die(f"gh pr list failed: {listed.stderr.strip()}")
        raw = json.loads(listed.stdout)
    issue_of = {}
    for pr in raw:
        m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*/(\d+)-",
                     pr.get("headRefName", ""))
        if m:
            issue_of[int(pr["number"])] = int(m.group(1))
    return issue_of


def resolve_slug(args):
    """(slug or None, note) -- the campaign's slug for the branch pattern.

    NOT A DEFAULT IN THE FLAG. `--slug machinery` hardcoded one campaign's name
    into a tool every campaign runs, which is a wrong answer for all the others
    and a silent one. Read from the `campaign:<slug>` label instead, through the
    one reader of it, as the WORD it prints. A read that did not happen leaves
    NO branch pattern at all since #237, and the note says so, so a tally with
    no branch attribution is never mistaken for a whole one. A window that
    predates #181 is read by passing the old token to `--slug`, which is used
    as a literal."""
    if args.slug:
        return args.slug, f"slug {args.slug}, given on the command line"
    if getattr(args, "offline", False):
        return None, ("--offline, so no slug was read and NO branch is "
                      "attributed; pass --slug to name one")
    tracker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "campaign-tracker.py")
    try:
        r = subprocess.run([sys.executable, tracker, "slug", str(args.campaign)],
                           capture_output=True, text=True)
    except OSError as e:
        return None, (f"campaign-tracker could not run ({e.__class__.__name__}); "
                      f"NO branch is attributed")
    word = r.stdout.strip()
    if word and word != "none":
        return word, f"slug {word}, from #{args.campaign}'s campaign: label"
    # THE TWO ABSENCES, KEPT APART, as `campaign-local-work.py` keeps them: exit
    # 1 is the tracker having READ the campaign issue and found no `campaign:`
    # label, and any other exit is a reading that did not happen. The fix
    # differs -- a label to add against a reading to retry -- so one sentence
    # for both sends the reader to the wrong one.
    if r.returncode == 1:
        why = f"#{args.campaign} carries no `campaign:` label, so it has no slug"
    else:
        why = (f"campaign-tracker slug {args.campaign} exited {r.returncode} "
               f"without a verdict: {r.stderr.strip()[:120] or 'no message'}")
    return None, f"{why}; NO branch is attributed"


class Corpus:
    """Every transcript file under the roots, read once."""

    def __init__(self, args):
        self.args = args
        # ONE FORM OF THE CLAIM BRANCH SINCE #237: `<slug>/<issue>-<topic>`.
        # The retired `campaign-<N>/` was matched beside it while both were
        # worn. A WINDOW THAT PREDATES #181 IS STILL TALLIED, by naming the old
        # token to `--slug` -- it is used as a literal, not validated as a slug
        # -- so `--slug campaign-1` reads that history and nothing here has to
        # keep a form the tree no longer mints.
        #
        # NO SLUG MEANS NO BRANCH ATTRIBUTION AT ALL, and `slug_note` says so.
        # It used to fall back to `campaign-<N>/`, which for any campaign filed
        # after #181 matched nothing while reading like a pattern.
        slug, self.slug_note = resolve_slug(args)
        self.branch = (re.compile(rf"{re.escape(slug)}/(\d+)-[A-Za-z0-9._-]+")
                       if slug else None)
        self.issue_ref = re.compile(rf"{re.escape(args.repo)}#(\d+)")
        self.pr_map = read_pr_map(args.pr_map, args.repo, args.offline)
        self.bases = [os.path.realpath(b).rstrip("/") for b in args.base]
        self.dropped = {"window": 0, "off_base": 0, "folded": 0,
                        "seen_elsewhere": 0}
        self.files_read = 0
        self.seen_messages = set()
        self.session_timeline = {}   # parent session id -> [(ts, issue)]
        self.session_names = {}      # session id -> the last name it was given
        self.turns = []

    def files(self):
        for root in self.args.root:
            for dirpath, _dirs, names in os.walk(os.path.expanduser(root)):
                for name in sorted(names):
                    if name.endswith(".jsonl"):
                        yield os.path.join(dirpath, name)

    def in_base(self, cwd):
        """Is this record's directory inside a base root?

        Both sides are resolved, because a session reaching the base through a
        symlink records the symlinked path and would otherwise be dropped as
        somebody else's work -- silently, since a dropped record and a campaign
        that was quiet print the same nothing.
        """
        real = os.path.realpath(cwd) if cwd else ""
        return any(real == b or real.startswith(b + "/") for b in self.bases)

    def in_window(self, ts):
        """Both sides cut to whole seconds, `2026-09-04T00:45:00`.

        The harness writes `...T00:45:00.123Z`, and a bound normalised with its
        `Z` would sort *after* a message in the same second, because `.` sorts
        below `Z` -- one second of turns dropped at each end for a reason no
        reader of the output could see.
        """
        stamp = ts[:19]
        if self.args.since and stamp < self.args.since:
            return False
        if self.args.until and stamp > self.args.until:
            return False
        return True

    def read(self):
        # Parent sessions first: a subagent's fallback is where its parent was.
        paths = sorted(self.files(), key=lambda p: ("/subagents/" in p, p))
        for path in paths:
            self.read_file(path)
            self.files_read += 1
        self.turns.sort(key=lambda t: t["timestamp"])
        return self

    def read_file(self, path):
        is_sub = "/subagents/" in path
        pending = {}            # message id -> the turn its records fold into
        carried = None          # last branch mention seen in this transcript
        brief_issue = None      # a subagent's own brief, read from its first prompt
        first_prompt_seen = False
        session_name = None
        for line in open(path, errors="replace"):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "agent-name":
                session_name = record.get("agentName")
                if record.get("sessionId"):
                    self.session_names[record["sessionId"]] = session_name
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            ts = record.get("timestamp") or ""
            if is_sub and not first_prompt_seen and record.get("type") == "user":
                first_prompt_seen = True
                brief_issue = self.read_brief(message)
            branch_field = record.get("gitBranch") or ""
            on_branch = self.branch.match(branch_field) if self.branch else None
            if on_branch:
                carried = int(on_branch.group(1))
            if record.get("type") != "assistant":
                continue
            usage = usage_of(message)
            if usage is None:
                continue
            if not self.in_window(ts):
                self.dropped["window"] += 1
                continue
            mid = message.get("id") or record.get("uuid")
            cwd = record.get("cwd") or ""
            if not self.in_base(cwd):
                self.dropped["off_base"] += 1
                continue
            body = len(json.dumps(message.get("content"), ensure_ascii=False))
            settled = bool(message.get("usage", {}).get("iterations"))
            if mid in pending:
                self.dropped["folded"] += 1
                fold(pending[mid], usage, body, settled)
                continue
            if mid in self.seen_messages:
                self.dropped["seen_elsewhere"] += 1
                continue
            issue, how = self.attribute(record, cwd, branch_field, is_sub,
                                        brief_issue, carried, ts)
            turn = {
                "timestamp": ts,
                "issue": issue,
                "how": how,
                "kind": "subagent" if is_sub else "session",
                "session_id": record.get("sessionId"),
                "session_name": session_name or self.session_names.get(record.get("sessionId")),
                "agent_id": record.get("agentId"),
                "model": message.get("model"),
                "effort": record.get("effort"),
                "cwd": cwd,
                "file": path,
                "message_id": mid,
                "tools": [b.get("name") for b in message.get("content", [])
                          if isinstance(b, dict) and b.get("type") == "tool_use"],
                "body_bytes": body,
                "settled": settled,
                **usage,
            }
            pending[mid] = turn
            if not is_sub and issue is not None:
                self.session_timeline.setdefault(record.get("sessionId"), []).append((ts, issue))
        for mid, turn in pending.items():
            self.seen_messages.add(mid)
            self.turns.append(turn)

    def read_brief(self, message):
        for text in text_blocks(message):
            m = REVIEW_CMD.search(text)
            if m:
                _level, pr = review_cmd_groups(m)
                if pr in self.pr_map:
                    return self.pr_map[pr]
            m = self.branch.search(text) if self.branch else None
            if m:
                return int(m.group(1))
            m = self.issue_ref.search(text)
            if m:
                # `<owner>/<repo>#N` numbers issues and pull requests from one
                # sequence, so a reference is an issue only when it is not a
                # pull request: a brief saying "review kalaluthien/campaign-base#183"
                # names PR #183, whose sub-issue is #176, and reading it as
                # issue 183 opens a row for an issue nobody ever filed.
                return self.pr_map.get(int(m.group(1)), int(m.group(1)))
        return None

    def attribute(self, record, cwd, branch_field, is_sub, brief_issue, carried, ts):
        # A subagent's brief outranks its place, and only a subagent's does. It
        # inherits the place its parent was standing in -- all seven reviews of
        # PR #184, head campaign-1/177-, ran from a session on
        # campaign-1/178-delegate-clone-hooks and recorded that branch on every
        # one of their 164 turns -- so the place says where the parent was and
        # the brief says what the subagent was asked to do.
        if is_sub and brief_issue is not None:
            return brief_issue, "brief"
        m = WORKTREE.search(cwd)
        if m:
            return int(m.group(1)), "worktree"
        m = self.branch.match(branch_field) if self.branch else None
        if m:
            return int(m.group(1)), "branch"
        if is_sub:
            parent = self.parent_issue(record.get("sessionId"), ts)
            if parent is not None:
                return parent, "parent"
        if carried is not None and not branch_field:
            return carried, "carry"
        return None, "unattributed"

    def parent_issue(self, session_id, ts):
        timeline = self.session_timeline.get(session_id)
        if not timeline:
            return None
        # By timestamp and not by position: a transcript's records are not
        # ordered by time -- a resumed session appends earlier turns after
        # later ones -- so "the last one seen" is not "the last one before".
        before = [(when, issue) for when, issue in timeline if when <= ts]
        if before:
            return max(before)[1]
        return min(timeline)[1]


def totals(turns):
    """Sums, and beside them the count of turns whose output is a measurement.

    `settled` travels with every total because the unsettled state is nearly
    the kind -- 86% of subagent turns against 0.7% of session turns on the
    corpus this was written against -- so a row's output column is a count or a
    floor depending on which turns fell into it, and only the row can say which.
    """
    out = {"turns": 0, "settled": 0, "output": 0, "input_new": 0, "cache_read": 0}
    for t in turns:
        out["turns"] += 1
        out["settled"] += 1 if t["settled"] else 0
        for k in ("output", "input_new", "cache_read"):
            out[k] += t[k]
    return out


def group(turns, key):
    buckets = {}
    for t in turns:
        buckets.setdefault(key(t), []).append(t)
    return buckets


def sample_line(corpus):
    print(f"read {corpus.files_read} transcript files under "
          f"{', '.join(corpus.args.root)}")
    print(f"window {corpus.args.since or '(open)'} .. {corpus.args.until or '(open)'}; "
          f"bases {', '.join(corpus.bases)}")
    # PRINTED, because a branch pattern missing the slug attributes half a
    # campaign's turns to nothing and the totals look merely smaller.
    print(f"branch attribution: {corpus.slug_note}")
    print(f"turns kept {len(corpus.turns):,} (one per message); "
          f"records folded into one of them {corpus.dropped['folded']:,}; "
          f"messages already counted in another file "
          f"{corpus.dropped['seen_elsewhere']:,}")
    print(f"records dropped: {corpus.dropped['window']:,} outside the window, "
          f"{corpus.dropped['off_base']:,} with a cwd outside every base root "
          f"(records, not messages: a dropped record is never folded, so its "
          f"message is never counted)")
    unsettled = [t for t in corpus.turns if not t["settled"]]
    settled = [t for t in corpus.turns if t["settled"]]
    if unsettled:
        bytes_out = sum(t["body_bytes"] for t in unsettled)
        rate = (sum(t["body_bytes"] for t in settled)
                / max(1, sum(t["output"] for t in settled)))
        print(f"unsettled turns {len(unsettled):,} of {len(corpus.turns):,} "
              f"({100 * len(unsettled) // max(1, len(corpus.turns))}%), carrying "
              f"{bytes_out:,} body bytes: their output column is a floor, not a "
              f"count")
        for kind in ("session", "subagent"):
            of_kind = [t for t in corpus.turns if t["kind"] == kind]
            if not of_kind:
                continue
            bad = [t for t in of_kind if not t["settled"]]
            print(f"  {kind:>9}: {len(bad):,} of {len(of_kind):,} unsettled "
                  f"({100 * len(bad) // len(of_kind)}%)")
        print(f"  the two rates differ that much because the state is nearly the "
              f"kind: every column counting subagent output is a floor, which is "
              f"why each row carries its own settled count")
        print(f"  at the settled turns' {rate:.1f} body bytes per output token, "
              f"those would add about {int(bytes_out / rate):,} output tokens -- "
              f"an estimate, and not part of any number below")
    if corpus.pr_map:
        print(f"pull-request map: {len(corpus.pr_map)} branches")
    print()


def table(rows, head):
    widths = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    for row in [head] + rows:
        print("  ".join(str(c).rjust(w) if i else str(c).ljust(w)
                        for i, (c, w) in enumerate(zip(row, widths))))


def fmt(n):
    return f"{n:,}"


def cmd_issues(corpus, args):
    sample_line(corpus)
    buckets = group(corpus.turns, lambda t: t["issue"])
    rows = []
    for issue in sorted(buckets, key=lambda k: (k is None, k)):
        both = totals(buckets[issue])
        subs = totals([t for t in buckets[issue] if t["kind"] == "subagent"])
        hows = sorted({t["how"] for t in buckets[issue]})
        rows.append([issue if issue is not None else "unattributed",
                     fmt(both["turns"]), fmt(subs["turns"]),
                     f"{both['settled']}/{both['turns']}",
                     fmt(both["output"]),
                     f"{subs['settled']}/{subs['turns']}",
                     fmt(subs["output"]),
                     fmt(both["input_new"]), fmt(both["cache_read"]),
                     ",".join(hows)])
    # sub_settled sits beside sub_output and not beside settled, because the
    # column it qualifies is that one: a row settled 89% overall can rest its
    # sub_output on 6 settled turns of 18, and the combined figure hides
    # exactly the floor the split was added to show.
    table(rows, ["issue", "turns", "sub_turns", "settled", "output",
                 "sub_settled", "sub_output", "input_new", "cache_read",
                 "attributed_by"])
    grand = totals(corpus.turns)
    print()
    print(f"total: {fmt(grand['turns'])} turns, {fmt(grand['output'])} output, "
          f"{fmt(grand['input_new'])} input_new, {fmt(grand['cache_read'])} cache_read")


def session_label(t):
    """A turn's session row: its name, or the name of the session a subagent ran under."""
    if t["kind"] == "subagent":
        return f"(subagent of {t['session_name'] or t['session_id'][:8]})"
    return t["session_name"] or f"(unnamed {t['session_id'][:8]})"


def cmd_sessions(corpus, args):
    sample_line(corpus)
    buckets = group(corpus.turns, session_label)
    rows = []
    for key in sorted(buckets, key=lambda k: -totals(buckets[k])["output"]):
        got = totals(buckets[key])
        issues = sorted({t["issue"] for t in buckets[key] if t["issue"] is not None})
        rows.append([key, fmt(got["turns"]),
                     f"{got['settled']}/{got['turns']}", fmt(got["output"]),
                     fmt(got["input_new"]), fmt(got["cache_read"]),
                     ",".join(str(i) for i in issues)[:40]])
    table(rows, ["session", "turns", "settled", "output", "input_new",
                 "cache_read", "issues"])


def cmd_turns(corpus, args):
    for t in corpus.turns:
        print(json.dumps(t, ensure_ascii=False))


def load_subagent_lineage(roots):
    """(parent_of, path_of): every subagent's parent id and its own transcript path.

    Both read from `agent-<id>.meta.json` and its sibling `.jsonl`, sitting
    beside each other in every `subagents/` directory under root -- a
    directory walk, not a turn, so a subagent whose own turns fell outside
    the corpus's `--since`/`--until`/`--base` filters is still found: its
    round is never silently absent just because the round's own head turn
    didn't survive the window.

    The harness writes `parentAgentId` into a subagent's own sidecar file --
    never into the transcript, and never onto a depth-1 subagent, whose
    launcher is the session itself rather than another agent. That absence is
    the base case a chain should stop at: an id with no `parentAgentId` names
    the round, whatever spawned it.

    An agent whose meta.json is missing or unreadable resolves to no parent
    below, the same answer `cmd_reviews` gave every subagent before this
    existed: its own round, on its own. A file not named `agent-<id>.jsonl`
    or `.meta.json` -- an unrelated sidecar dropped into `subagents/` -- is
    skipped rather than sliced into a bogus id.
    """
    parent_of = {}
    path_of = {}
    for root in roots:
        for dirpath, _dirs, names in os.walk(os.path.expanduser(root)):
            if os.path.basename(dirpath) != "subagents":
                continue
            for name in names:
                if not name.startswith("agent-"):
                    continue
                if name.endswith(".meta.json"):
                    agent_id = name[len("agent-"):-len(".meta.json")]
                    try:
                        data = json.load(open(os.path.join(dirpath, name)))
                    except (OSError, json.JSONDecodeError):
                        continue
                    parent = data.get("parentAgentId")
                    if parent:
                        parent_of[agent_id] = parent
                elif name.endswith(".jsonl"):
                    agent_id = name[len("agent-"):-len(".jsonl")]
                    path_of[agent_id] = os.path.join(dirpath, name)
    return parent_of, path_of


def review_rounds(roots, turns):
    """Every subagent turn, grouped by the top reviewer that its lineage traces to.

    A reviewer subagent running `/code-review` fans out into an orchestrator,
    finders and verifiers -- further subagents whose own turns were priced at
    the parent's alone unless the chain is walked back to the round it belongs
    to. `root_of` follows `parentAgentId` to the top, iteratively (a chain is
    three deep on this machine's corpus, but nothing bounds it) and memoized,
    because two grandchildren of one fan-out both walk the same middle link.
    """
    parent_of, agent_file = load_subagent_lineage(roots)
    root_cache = {}

    def root_of(agent_id):
        chain = []
        cur = agent_id
        while cur not in root_cache and cur not in chain:
            chain.append(cur)
            parent = parent_of.get(cur)
            cur = parent if parent else cur
            if parent is None:
                break
        root = root_cache.get(cur, cur)  # a cycle or a missing parent stops on itself
        for seen in chain:
            root_cache[seen] = root
        return root

    rounds = {}
    for t in turns:
        if t["kind"] != "subagent" or not t.get("agent_id"):
            continue
        agent_file.setdefault(t["agent_id"], t["file"])  # a turn's own file, if the walk missed it
        rounds.setdefault(root_of(t["agent_id"]), []).append(t)
    return rounds, agent_file


def cmd_reviews(corpus, args):
    """One row per review round: what it cost, at what level, nested subagents folded in."""
    sample_line(corpus)
    rounds, agent_file = review_rounds(args.root, corpus.turns)
    rows = []
    for agent_id, turns in rounds.items():
        head_file = agent_file.get(agent_id)
        if head_file is None:
            continue
        brief = read_first_prompt(head_file)
        m = REVIEW_CMD.search(brief or "")
        if not m:
            continue
        level, pr = review_cmd_groups(m)
        own_turns = [t for t in turns if t["agent_id"] == agent_id]
        head = min(own_turns or turns, key=lambda t: t["timestamp"])
        got = totals(turns)
        nested = len({t["agent_id"] for t in turns} - {agent_id})
        rows.append((pr, level, head["issue"], head["model"],
                     got, head["timestamp"][:16], nested))
    rows.sort(key=lambda r: (r[0], r[5]))
    table([[r[0], r[1], r[2], r[3], fmt(r[4]["turns"]),
            f"{r[4]['settled']}/{r[4]['turns']}", fmt(r[4]["output"]),
            fmt(r[4]["input_new"]), fmt(r[4]["cache_read"]), r[5], r[6]]
           for r in rows],
          ["pr", "level", "issue", "model", "turns", "settled", "output",
           "input_new", "cache_read", "started", "nested"])
    if rows:
        print()
        settled = sum(r[4]["settled"] for r in rows)
        turns_read = sum(r[4]["turns"] for r in rows)
        folded = sum(r[6] for r in rows)
        print(f"{len(rows)} review rounds, {folded} nested transcript(s) folded in; "
              f"{fmt(sum(r[4]['output'] for r in rows))} output over "
              f"{settled} settled turns of {turns_read}, "
              f"{fmt(sum(r[4]['input_new'] for r in rows))} input_new")
        if settled < turns_read:
            print("a review runs as a subagent, and a subagent's output is the "
                  "column the harness mostly leaves unsettled: read the output "
                  "figures here as a floor and the input figures as counts")


def read_first_prompt(path):
    for line in open(path, errors="replace"):
        if not line.strip().startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "user" and isinstance(record.get("message"), dict):
            return "\n".join(text_blocks(record["message"]))
    return None


def cmd_tool_echo(corpus, args):
    """Turns that carry the output of one of this repository's own scripts.

    A script's table read by an agent is paid for twice: once as the tool result
    entering the window, and again on every later turn of the same session as
    cache. This counts the first, per script, by the tool call that produced it.
    """
    sample_line(corpus)
    by_script, grand, all_bytes, unsplittable, invocations = scan_script_calls(corpus)
    rows = []
    for script in sorted(by_script, key=lambda s: -by_script[s]["result_bytes"]):
        got = by_script[script]
        rows.append([script, fmt(got["charged"]), fmt(got["also_run"]),
                     fmt(got["result_bytes"])])
    table(rows, ["script", "charged", "also_run", "result_bytes"])
    commands = sum(r["charged"] for r in by_script.values())
    print()
    print(f"{fmt(grand)} bytes from {fmt(commands)} commands running "
          f"{fmt(invocations)} invocations, of {fmt(all_bytes)} bytes in every "
          f"tool result of the kept turns "
          f"({100 * grand / max(1, all_bytes):.1f}%)")
    print("result_bytes is a partition: one command's result is charged once, to "
          "the first script that command runs. charged counts commands, and "
          "also_run counts every later invocation in a charged command -- "
          "including the same script run twice -- so charged + also_run is "
          "invocations, not commands.")
    if unsplittable:
        print(f"{fmt(unsplittable)} commands would not split and were read as "
              f"running nothing: that is a floor on this table, not a zero.")
    print("No token figure is printed. The transcript records no per-tool-result "
          "token count, and bytes/4 would be an estimate wearing a measurement's "
          "heading.")


def cmd_reads(corpus, args):
    """What reading files returned, per file and per session, and the verdict
    the reads rule in the docstring gives."""
    sample_line(corpus)
    reads, all_bytes, apart = scan_reads(corpus)
    files = {}
    for r in reads:
        f = files.setdefault(r["file"], {"reads": 0, "rereads": 0, "bytes": 0,
                                         "result_lines": 0})
        f["reads"] += 1
        f["rereads"] += r["reread"]
        f["bytes"] += r["bytes"]
        f["result_lines"] = max(f["result_lines"], r["lines"])
    for path, f in files.items():
        on_disk = disk_lines(path)
        f["from"] = "result" if on_disk is None else "disk"
        f["lines"] = f["result_lines"] if on_disk is None else on_disk
        f["over"] = f["lines"] > args.threshold
    table([[shown(path, corpus.bases), fmt(f["lines"]), f["from"],
            "yes" if f["over"] else "no", fmt(f["reads"]), fmt(f["rereads"]),
            fmt(f["bytes"])]
           for path, f in sorted(files.items(), key=lambda kv: -kv[1]["bytes"])],
          ["file", "lines", "from", "over", "reads", "rereads", "result_bytes"])
    sessions = {}
    for r in reads:
        s = sessions.setdefault(r["session"], {"reads": 0, "rereads": 0, "bytes": 0,
                                               "reread_bytes": 0, "over_bytes": 0})
        s["reads"] += 1
        s["bytes"] += r["bytes"]
        if r["reread"]:
            s["rereads"] += 1
            s["reread_bytes"] += r["bytes"]
        if files[r["file"]]["over"]:
            s["over_bytes"] += r["bytes"]
    print()
    table([[name, fmt(s["reads"]), fmt(s["rereads"]), fmt(s["bytes"]),
            fmt(s["reread_bytes"]), fmt(s["over_bytes"])]
           for name, s in sorted(sessions.items(), key=lambda kv: -kv[1]["bytes"])],
          ["session", "reads", "rereads", "result_bytes", "reread_bytes", "over_bytes"])

    def share(n, d):
        return f"{fmt(n)} ({100 * n / max(1, d):.1f}%)"
    read_bytes = sum(r["bytes"] for r in reads)
    over = sum(r["bytes"] for r in reads if files[r["file"]]["over"])
    again = sum(r["bytes"] for r in reads if r["reread"])
    either = sum(r["bytes"] for r in reads if r["reread"] or files[r["file"]]["over"])
    own = sum(r["bytes"] for r in reads if r["lines"] > args.threshold)
    print()
    print(f"{fmt(len(reads))} reads of {fmt(len(files))} files; read bytes "
          f"{fmt(read_bytes)} of {fmt(all_bytes)} in every "
          f"tool result of the kept turns ({100 * read_bytes / max(1, all_bytes):.1f}%)")
    print(f"of the read bytes: over-threshold (> {args.threshold} lines) "
          f"{share(over, read_bytes)}; re-read {share(again, read_bytes)}; "
          f"either {share(either, read_bytes)}")
    print(f"  over by the read's own result rather than the file: "
          f"{share(own, read_bytes)} -- a bounded read of a long file is over "
          f"by its file")
    print(f"  lines from a result, the file gone from disk: "
          f"{share(sum(r['bytes'] for r in reads if files[r['file']]['from'] == 'result'), read_bytes)}"
          f" -- a bounded read undercounts its file, so over-threshold is a floor")
    for key, what in (("no_path", "reads naming no file (unsplittable)"),
                      ("unsplit", "commands that would not split, so may hold a read"),
                      ("later", "commands reading a named file after their first "
                                "segment, which the rule does not count")):
        n, size = apart[key]
        print(f"{fmt(n)} {what}, carrying {fmt(size)} bytes: a floor on the "
              f"tables above, not a zero")
    verdict = "build" if either >= BUILD_AT * read_bytes and read_bytes else "stop"
    print(f"verdict: {verdict} -- over-threshold or re-read is "
          f"{100 * either / max(1, read_bytes):.1f}% of read bytes, against "
          f"{BUILD_AT:.0%} (the reads rule in this script's docstring)")


def shown(path, bases):
    """A path under a base root, relative to it; any other path whole."""
    for b in bases:
        if path.startswith(b + "/"):
            return path[len(b) + 1:]
    return path


def scan_script_calls(corpus):
    """What this repository's scripts printed back at an agent, per script.

    Returns the per-script rows, their byte total, and the byte total of *every*
    tool result in the kept turns, so a share can be read rather than asserted.
    """
    grammar = guard_module()
    by_script = {}
    charged = 0
    all_bytes = 0
    unsplittable = 0
    invocations = 0
    for _turn, use, text in tool_results(corpus):
        called = []
        if use.get("name") == "Bash":
            called = scripts_called(str(use.get("input", {}).get("command", "")), grammar)
            if called is None:
                unsplittable += 1
                called = []
        size = len(text)
        all_bytes += size
        invocations += len(called)
        for rank, script in enumerate(called):
            row = by_script.setdefault(
                script, {"charged": 0, "also_run": 0, "result_bytes": 0})
            if rank == 0:
                row["charged"] += 1
                row["result_bytes"] += size
                charged += size
            else:
                row["also_run"] += 1
    return by_script, charged, all_bytes, unsplittable, invocations


def tool_results(corpus):
    """(turn, tool_use block, result text) for every tool call a kept turn made.

    The one walk `tool-echo` and `reads` share, so their shares are of one
    denominator. A call is kept by its turn, which the corpus already
    attributed; a result is paired to its call by `tool_use_id` within one file.
    """
    keep = {}
    for t in corpus.turns:
        keep.setdefault(t["message_id"], t)
    for path in sorted({t["file"] for t in corpus.turns}):
        pending = {}
        for line in open(path, errors="replace"):
            if not line.strip().startswith("{"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    turn = keep.get(message.get("id"))
                    if turn is not None:
                        pending[block.get("id")] = (turn, block)
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                    turn, use = pending.pop(block["tool_use_id"])
                    yield turn, use, "\n".join(text_blocks({"content": [block]}))


@functools.cache
def disk_lines(path):
    """The file's line count now, or None when it is not a readable file."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def scan_reads(corpus):
    """Every read by the reads rule, in time order, and what the walk set aside.

    Returns (reads, all_bytes, apart): each read a dict of its file, context,
    session label, size and result lines; `apart` counts and sizes what is not
    a read but bears on the count -- unsplittable reads, commands that would
    not split, and reads in a later segment.
    """
    grammar = guard_module()
    reads, all_bytes = [], 0
    apart = {k: [0, 0] for k in ("no_path", "unsplit", "later")}
    for turn, use, text in tool_results(corpus):
        size = len(text)
        all_bytes += size
        name, inp = use.get("name"), use.get("input") or {}
        if name == "Read":
            word, path = "read", inp.get("file_path")
        elif name == "Bash":
            word, path = shell_read(str(inp.get("command", "")), grammar)
        else:
            continue
        if word == "read" and not path:
            word = "no_path"
        if word in apart:
            apart[word][0] += 1
            apart[word][1] += size
        if word != "read":
            continue
        reads.append({
            "file": os.path.normpath(os.path.join(turn["cwd"], os.path.expanduser(str(path)))),
            "context": (turn["session_id"], turn["agent_id"]),
            "session": session_label(turn),
            "timestamp": turn["timestamp"],
            "bytes": size,
            "lines": text.count("\n") + 1 if text else 0,
        })
    reads.sort(key=lambda r: r["timestamp"])
    seen = set()
    for r in reads:
        key = (r["context"], r["file"])
        r["reread"] = key in seen
        seen.add(key)
    return reads, all_bytes, apart


# THE CLASSIFIER COUNTERS (sdlc-alloy#427, landed by #430). Neither reads the
# corpus: a refusal is a fact about the machine, not about one campaign's
# turns, so both walk every transcript under --root, every project and no
# window. `review-posts` is the denominator beside `denials`.
DENY = re.compile(r"Permission for this action was denied by the Claude Code "
                  r"auto mode classifier\. Reason: \[([^\]]+)\]")
REVIEW_POST = re.compile(r"gh pr (comment|review)\b.*\bREVIEW ", re.S)
PR_POSTS = {("pr", "comment"), ("pr", "review")}
ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
VAR = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def posted_review(command, written, cwd):
    """The REVIEW text a call posts: the command itself, or the file a
    `gh pr comment|review` segment's `--body-file` names when the last Write
    to that path opened `REVIEW `.

    The segments and the flag are read by the guard's own `segments`,
    `gh_words` and `flag_value`, the one reading of that grammar here. A `$VAR`
    in the path is expanded only from a `VAR=value` word earlier in the same
    command, and a relative path against the record's cwd, as the guard does."""
    if REVIEW_POST.search(command):
        return command
    if "gh" not in command:
        return None
    grammar = guard_module()
    segs, _why = grammar.segments(command)
    env = {}
    for seg in segs or ():
        for t in seg:
            m = ASSIGN.match(t)
            if m:
                env[m.group(1)] = m.group(2)
        if tuple(grammar.gh_words(seg)[:2]) not in PR_POSTS:
            continue
        path = grammar.flag_value(seg, grammar.BODY_FILE_VALUED)
        if not isinstance(path, str) or path == "-":
            continue
        path = VAR.sub(lambda v: env.get(v.group(1) or v.group(2), v.group(0)), path)
        if cwd and not os.path.isabs(path):
            path = os.path.join(cwd, path)
        body = written.get(os.path.normpath(path), "")
        if body.startswith("REVIEW "):
            return body
    return None


def denial(txt):
    """The classifier's reason when txt opens with its denial; a quote of one
    deeper in is not a denial."""
    m = DENY.search(txt)
    return m.group(1) if m and m.start() <= 60 else None


def result_text(block):
    txt = block.get("content")
    if isinstance(txt, list):
        txt = " ".join(x.get("text", "") for x in txt if isinstance(x, dict))
    return txt if isinstance(txt, str) else ""


def transcript_blocks(path):
    """(record, content block) for every block of every record in one file."""
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:           # noqa: BLE001 -- a torn line is skipped
                continue
            content = (d.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict):
                    yield d, c


def transcript_files(roots):
    import glob
    return [f for r in roots for f in glob.glob(f"{r}/**/*.jsonl", recursive=True)]


def cmd_denials(roots):
    rows = []
    files = transcript_files(roots)
    for f in files:
        calls = {}
        for d, c in transcript_blocks(f):
            if c.get("type") == "tool_use":
                calls[c.get("id")] = (c.get("name"), c.get("input"))
            if c.get("type") == "tool_result":
                reason = denial(result_text(c))
                if not reason:
                    continue
                name, inp = calls.get(c.get("tool_use_id"), ("?", {}))
                cmd = (inp or {}).get("command") or (inp or {}).get("file_path") or str(inp)[:80]
                root = next(r for r in roots if f.startswith(r))
                rows.append((reason, os.path.relpath(f, root).split("/")[0],
                             d.get("sessionId", "?")[:8], d.get("timestamp", "?")[:19],
                             name, cmd[:140]))
    print(f"read {len(files)} transcript files under {', '.join(roots)}; "
          f"{len(rows)} classifier denial(s)")
    print("by reason:", dict(collections.Counter(r[0] for r in rows)))
    for r in sorted(rows, key=lambda r: r[3]):
        print(" | ".join(r))


def cmd_review_posts(roots):
    """A row is a Bash call whose command holds `REVIEW ` anywhere, so a REPORT
    quoting a REVIEW is a row too; or one posting a `--body-file` (`-F`) whose
    last Write in the same transcript opened `REVIEW `, the shape a reviewer
    posts in since sdlc-alloy#430. A body the shell wrote is not seen."""
    rows = []
    for f in transcript_files(roots):
        calls, written = {}, {}
        for d, c in transcript_blocks(f):
            if c.get("type") == "tool_use" and c.get("name") == "Write":
                inp = c.get("input") or {}
                if inp.get("file_path"):
                    written[os.path.normpath(inp["file_path"])] = inp.get("content") or ""
            if c.get("type") == "tool_use" and c.get("name") == "Bash":
                cmd = posted_review((c.get("input") or {}).get("command", ""),
                                    written, d.get("cwd"))
                if cmd:
                    calls[c["id"]] = (d.get("timestamp", "?")[:19],
                                      d.get("sessionId", "?")[:8], cmd)
            if c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                reason = denial(result_text(c))
                outcome = (f"REFUSED {reason}" if reason
                           else "error" if c.get("is_error") else "ok")
                ts, sid, cmd = calls[c["tool_use_id"]]
                who = re.search(r"REVIEW (\S+)", cmd)
                rows.append((ts, sid, os.path.basename(f).startswith("agent-"),
                             who.group(1) if who else "?", outcome))
    print(f"{len(rows)} REVIEW post(s) with a result, under {', '.join(roots)}")
    print("by outcome:", dict(collections.Counter(r[4] for r in rows)))
    print("by is-subagent-transcript:", dict(collections.Counter(r[2] for r in rows)))
    for r in sorted(rows):
        print(" | ".join(map(str, r)))


# Commands that read the whole machine rather than the corpus.
MACHINE_COMMANDS = {
    "denials": cmd_denials,
    "review-posts": cmd_review_posts,
}


COMMANDS = {
    "issues": cmd_issues,
    "sessions": cmd_sessions,
    "turns": cmd_turns,
    "reviews": cmd_reviews,
    "tool-echo": cmd_tool_echo,
    "reads": cmd_reads,
}


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=sorted({**COMMANDS, **MACHINE_COMMANDS}))
    p.add_argument("--since", help="UTC ISO timestamp, e.g. 2026-09-04T00:45:00Z; "
                                   "turns before it are dropped")
    p.add_argument("--until", help="UTC ISO timestamp; turns after it are dropped")
    p.add_argument("--campaign", default="1",
                   help="campaign issue number; used to look up the slug, and "
                        "not matched in a branch name")
    p.add_argument("--slug", default=None,
                   help="campaign slug in branch names, the one form matched "
                        "since #237. Read from the campaign's "
                        "`campaign:<slug>` label when not given, and when that "
                        "read fails NO branch is attributed, which is SAID "
                        "rather than assumed. Used as a literal, so a window "
                        "predating #181 is read with --slug campaign-<N>")
    p.add_argument("--repo", default=None,
                   help="the tracker (default: campaign-repos.py's BASE_REPO)")
    p.add_argument("--root", action="append", default=[],
                   help="transcript root (default ~/.claude/projects)")
    p.add_argument("--base", action="append", default=[],
                   help="base root a turn's cwd must be under (default: this checkout's)")
    p.add_argument("--pr-map", help="JSON list of {number, headRefName}, instead of gh")
    p.add_argument("--offline", action="store_true",
                   help="do not call gh; leave the pull-request map empty")
    p.add_argument("--threshold", type=int, default=350,
                   help="reads: a file over this many lines is over the threshold")
    args = p.parse_args(argv)
    if args.command in MACHINE_COMMANDS:
        # They read --root alone, so a corpus flag given to one is refused
        # rather than ignored, and no base or tracker default is resolved.
        given = [f"--{a.dest.replace('_', '-')}" for a in p._actions
                 if a.dest not in ("help", "command", "root")
                 and getattr(args, a.dest) != a.default]
        if given:
            die(f"{args.command} reads every transcript under --root and takes "
                f"no {', '.join(given)}")
        args.root = args.root or ["~/.claude/projects"]
        return args
    # The base's name is campaign-repos.py's (rule-check#370 row 5).
    if args.repo is None:
        try:
            args.repo = repos_module().BASE_REPO
        except Exception as e:          # noqa: BLE001 -- reported, not raised
            die(f"--repo has no default: campaign-repos.py would not load "
                f"({e.__class__.__name__}); name the tracker with --repo")
    for name in ("since", "until"):
        args.__dict__[name] = checked_bound(getattr(args, name), name)
    if not args.root:
        args.root = ["~/.claude/projects"]
    if not args.base:
        args.base = [base_root()]
    return args


def checked_bound(value, name):
    """Refuse a window bound the transcripts cannot be compared against.

    A timestamp is compared lexicographically against `message.timestamp`,
    which the harness writes as `2026-09-04T00:45:00.000Z`. So a bound that
    parses but is not in that shape -- `2026-9-04T00:45`, or an offset-bearing
    `2026-09-04T09:45:00+09:00` -- silently selects a different sample instead
    of failing, and a wrong window looks exactly like a quiet campaign.
    """
    if value is None:
        return None
    import datetime
    try:
        moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        die(f"--{name} {value!r} is not an ISO timestamp")
    if moment.utcoffset() not in (None, datetime.timedelta(0)):
        die(f"--{name} {value!r} is not UTC; transcripts are written in UTC "
            f"and the comparison is on the text")
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def main(argv):
    args = parse_args(argv)
    if args.command in MACHINE_COMMANDS:
        MACHINE_COMMANDS[args.command]([os.path.expanduser(r) for r in args.root])
        return 0
    corpus = Corpus(args).read()
    COMMANDS[args.command](corpus, args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
