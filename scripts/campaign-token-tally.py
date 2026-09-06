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
  branch       else `gitBranch` matching `<slug>/<issue>-`, or the retired
               `campaign-<N>/<issue>-` a branch cut before #181 carries.
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
  reviews    one row per in-process review subagent: its PR, level, and cost
  tool-echo  turns whose tool results are the output of this repository's own
             scripts, and what those results cost to carry

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
"""
import argparse
import json
import os
import re
import subprocess
import sys

WORKTREE = re.compile(r"/worktrees/(\d+)(?:/|$)")
REVIEW_CMD = re.compile(r"/code-review\s+(\w+)\s+(\d+)")
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


def shell_grammar():
    """check-campaign-claim.py, imported for its shell splitter.

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
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "check-campaign-claim.py")
    spec = importlib.util.spec_from_file_location("check_campaign_claim", path)
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


def die(why):
    sys.stderr.write(f"campaign-token-tally: {why}\n")
    sys.exit(2)


def base_root():
    """The main checkout, resolved the one sanctioned way (AGENTS.md § The three planes)."""
    here = os.path.dirname(os.path.abspath(__file__))
    common = subprocess.run(
        ["git", "-C", here, "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=True).stdout.strip()
    return os.path.realpath(os.path.dirname(common))


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


class Corpus:
    """Every transcript file under the roots, read once."""

    def __init__(self, args):
        self.args = args
        # BOTH FORMS OF THE CLAIM BRANCH. Since #181 a claim is cut as
        # `<slug>/<issue>-<topic>`; every branch before it is
        # `campaign-<N>/<issue>-<topic>`, and a tally that read one form would
        # attribute half a campaign's turns to nothing. `--campaign` and
        # `--slug` are both matched, so a window spanning the change is whole.
        self.branch = re.compile(
            rf"(?:campaign-{re.escape(args.campaign)}|{re.escape(args.slug)})"
            rf"/(\d+)-[A-Za-z0-9._-]+")
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
            on_branch = self.branch.match(branch_field)
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
                pr = int(m.group(2))
                if pr in self.pr_map:
                    return self.pr_map[pr]
            m = self.branch.search(text)
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
        m = self.branch.match(branch_field)
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


def cmd_sessions(corpus, args):
    sample_line(corpus)
    def name(t):
        if t["kind"] == "subagent":
            return f"(subagent of {t['session_name'] or t['session_id'][:8]})"
        return t["session_name"] or f"(unnamed {t['session_id'][:8]})"
    buckets = group(corpus.turns, name)
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


def cmd_reviews(corpus, args):
    """One row per review subagent: what a review round cost, and at what level."""
    sample_line(corpus)
    rounds = {}
    for t in corpus.turns:
        if t["kind"] != "subagent" or not t.get("agent_id"):
            continue
        rounds.setdefault(t["agent_id"], []).append(t)
    rows = []
    for agent_id, turns in rounds.items():
        head = min(turns, key=lambda t: t["timestamp"])
        brief = read_first_prompt(head["file"])
        m = REVIEW_CMD.search(brief or "")
        if not m:
            continue
        got = totals(turns)
        rows.append((int(m.group(2)), m.group(1), head["issue"], head["model"],
                     got, head["timestamp"][:16]))
    rows.sort(key=lambda r: (r[0], r[-1]))
    table([[r[0], r[1], r[2], r[3], fmt(r[4]["turns"]),
            f"{r[4]['settled']}/{r[4]['turns']}", fmt(r[4]["output"]),
            fmt(r[4]["input_new"]), fmt(r[4]["cache_read"]), r[5]]
           for r in rows],
          ["pr", "level", "issue", "model", "turns", "settled", "output",
           "input_new", "cache_read", "started"])
    if rows:
        print()
        settled = sum(r[4]["settled"] for r in rows)
        turns_read = sum(r[4]["turns"] for r in rows)
        print(f"{len(rows)} review rounds; "
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


def scan_script_calls(corpus):
    """What this repository's scripts printed back at an agent, per script.

    Returns the per-script rows, their byte total, and the byte total of *every*
    tool result in the kept turns, so a share can be read rather than asserted.
    """
    keep = {t["message_id"] for t in corpus.turns}
    grammar = shell_grammar()
    by_script = {}
    charged = 0
    all_bytes = 0
    unsplittable = 0
    invocations = 0
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
                    if message.get("id") not in keep:
                        continue
                    called = []
                    if block.get("name") == "Bash":
                        called = scripts_called(
                            str(block.get("input", {}).get("command", "")), grammar)
                        if called is None:
                            unsplittable += 1
                            called = []
                    pending[block.get("id")] = called
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                    called = pending.pop(block["tool_use_id"])
                    size = len("\n".join(text_blocks({"content": [block]})))
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


COMMANDS = {
    "issues": cmd_issues,
    "sessions": cmd_sessions,
    "turns": cmd_turns,
    "reviews": cmd_reviews,
    "tool-echo": cmd_tool_echo,
}


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("--since", help="UTC ISO timestamp, e.g. 2026-09-04T00:45:00Z; "
                                   "turns before it are dropped")
    p.add_argument("--until", help="UTC ISO timestamp; turns after it are dropped")
    p.add_argument("--campaign", default="1", help="campaign number in branch names")
    p.add_argument("--slug", default="machinery",
                   help="campaign slug in branch names, which replaced the "
                        "number in #181; both forms are matched")
    p.add_argument("--repo", default="kalaluthien/campaign-base")
    p.add_argument("--root", action="append", default=[],
                   help="transcript root (default ~/.claude/projects)")
    p.add_argument("--base", action="append", default=[],
                   help="base root a turn's cwd must be under (default: this checkout's)")
    p.add_argument("--pr-map", help="JSON list of {number, headRefName}, instead of gh")
    p.add_argument("--offline", action="store_true",
                   help="do not call gh; leave the pull-request map empty")
    args = p.parse_args(argv)
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
    corpus = Corpus(args).read()
    COMMANDS[args.command](corpus, args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
