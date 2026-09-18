#!/usr/bin/env python3
# witnesses: SessionCompactsBetweenSubIssues
"""Prove campaign-transcript reads a session's transcript and the claim refs
-- and that each branch is pinned by a case.

The transcript cases feed `transcript_reading` records in the shape this
machine's transcripts were measured to have (2026-09-10): a compaction a
`compact_boundary` record, a prompt a user record carrying text, an
assignment a prompt carrying the assignment sentence. The refs cases drive
`refs_reader` over `claim_reading`'s answer, against a fake `gh` on a PATH
holding nothing else, so nothing here reaches GitHub.

Then EVERY BRANCH IS BROKEN IN TURN: the source is mutated in memory, loaded
as the same file, and the case named for that branch must go red by its own
assertion. A case that crashes has asserted nothing, so a crash fails the
mutation. A control run of every case on the unmutated source goes first.

Usage: .claude/skills/assuming-role/scripts/campaign-transcript-test.py
"""
import importlib
import json
import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "campaign-transcript.py"
BASE_SCRIPTS = HERE.parents[3] / "scripts"
sys.path.append(str(BASE_SCRIPTS))
harness = importlib.import_module("suite-harness-test")


def load(source):
    """The script from `source`, loaded AS its own file, so the siblings it
    loads by path are the real ones."""
    m = types.ModuleType("campaign_transcript")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return m


# ------------------------------------------------------------- records


def ts(minute):
    return f"2026-09-10T10:{minute:02d}:00.000Z"


def gh_ts(minute):
    """GitHub's precision, which does not sort against the transcript's as
    a string: `10:03:00Z` > `10:03:00.500Z`."""
    return f"2026-09-10T10:{minute:02d}:00Z"


def work(n):
    return f"Work sub-issue kalaluthien/campaign-base#{n} now"


def boundary(minute):
    return {"type": "system", "subtype": "compact_boundary",
            "timestamp": ts(minute)}


def prompt(minute, text="Work sub-issue kalaluthien/campaign-base#9 now", **extra):
    return dict({"type": "user", "timestamp": ts(minute),
                 "message": {"content": text}}, **extra)


def queued(minute, text="Work sub-issue kalaluthien/campaign-base#9 now",
           mode="prompt", **extra):
    """A prompt typed while the pane was busy, in the measured shape
    (2026-09-11): an attachment record, not a user record."""
    return {"type": "attachment", "timestamp": ts(minute), "attachment": dict(
        {"type": "queued_command", "prompt": text, "commandMode": mode,
         "timestamp": ts(minute)}, **extra)}


def lines(*records):
    return [json.dumps(r) for r in records]


def result(minute, text):
    return {"type": "user", "timestamp": ts(minute), "message": {"content": [
        {"type": "tool_result", "content": text}]}}


def reading(m, *records):
    return m.transcript_reading(lines(*records))


# ------------------------------------------------------------- cases

CASES = {}


def case(name):
    def register(fn):
        CASES[name] = fn
        return fn
    return register


# transcript_reading

@case("the assignment is the sub-issue the last assignment prompt names, typed or queued")
def _(m):
    r = reading(m, prompt(1, work(5)), queued(3, work(7)), prompt(4, "hello"))
    return (r["assigned"], r["assigned_at"]) == (7, ts(3)), r


@case("an assignment in a summary, a harness note or a tool result is none")
def _(m):
    r = reading(m, prompt(1, work(5), isCompactSummary=True),
                prompt(2, work(6), isMeta=True), result(3, work(8)))
    return r["assigned"] is None, r


@case("the compaction marker printed as text is not a compaction")
def _(m):
    r = reading(m, {"type": "user", "timestamp": ts(2), "message": {
        "content": [{"type": "tool_result", "content":
                     "Compacted (ctrl+o to see full summary)"}]}})
    return r["compacted"] is None, r


@case("the model is the latest assistant's, and each slash command carries what it printed")
def _(m):
    def said(minute, model):
        return {"type": "assistant", "timestamp": ts(minute), "message": {"model": model}}
    r = reading(m, said(3, "claude-opus-5"), said(1, "claude-fable-5-1"),
                said(4, "<synthetic>"),
                prompt(2, "<command-name>/model</command-name> <command-args>opus</command-args>"),
                prompt(2, "<local-command-stdout>Set model to `Opus 5`</local-command-stdout>"),
                prompt(5, "<command-name>/effort</command-name>"))
    return ((r["model"], r["commands"]) == ("claude-opus-5", [
        ["model", "Set model to `Opus 5`"], ["effort", None]])), r


@case("every last is by time, not by position in the file")
def _(m):
    r = reading(m, prompt(5, work(5)), prompt(1, work(1)), boundary(3),
                boundary(2))
    return (r["assigned"], r["compacted"]) == (5, ts(3)), r


def gone(minute, standing=(), read="tk/9-* on o/r; the feed: o/r 40 event(s)"):
    """A `refs` whose sub-issue's refs are `standing`, the last gone at
    `minute` (None: no deletion read), recording each sub-issue asked."""
    asked = []

    def refs(n):
        asked.append(n)
        return (list(standing), gh_ts(minute) if minute is not None else None,
                read), None
    refs.asked = asked
    return refs


@case("compacted after the ref went is compacted, before it stale, and no time unknown")
def _(m):
    r = reading(m, prompt(1, work(9)), boundary(4))
    a = m.compacted_since_ref(r, gone(3))
    b = m.compacted_since_ref(reading(m, prompt(1, work(9)), boundary(2)), gone(3))
    # The three ways there is no time it went: no assignment prompt, a ref
    # still standing, and a deletion the sources did not answer.
    c = m.compacted_since_ref(reading(m, prompt(1, "hello"), boundary(4)), gone(3))
    d = m.compacted_since_ref(r, gone(3, standing=("tk/9-a",)))
    e = m.compacted_since_ref(r, gone(None))
    return ((a[0], b[0], c[0], d[0], e[0])
            == ("compacted", "stale", "unknown", "unknown", "unknown")
            and "no assignment prompt" in c[1] and "tk/9-a standing" in d[1]
            and "no deletion read" in e[1]), (a, b, c, d, e)


@case("a subagent's records are not this session's")
def _(m):
    r = reading(m, prompt(1, work(5)), prompt(2, work(7), isSidechain=True))
    return (r["assigned"], r["records"]) == (5, 1), r


@case("a command's own echoes are not a prompt")
def _(m):
    r = reading(m, prompt(1, "<command-name>/compact</command-name>\n" + work(5)),
                prompt(2, "<local-command-stdout>" + work(6)))
    return r["assigned"] is None, r


@case("an assignment typed into a busy pane is the assignment, whatever its origin")
def _(m):
    r = reading(m, prompt(1, work(9)), queued(4, work(9),
                                              origin={"kind": "human"}))
    return (r["assigned"], r["assigned_at"]) == (9, ts(4)), r


@case("a peer's message queued into the pane is not a prompt")
def _(m):
    r = reading(m, queued(2, f"<cross-session-message from=x>{work(9)}",
                          isMeta=True, origin={"kind": "peer"}))
    return r["assigned"] is None, r


@case("a queued command in any mode but prompt is not a prompt")
def _(m):
    r = reading(m, queued(2, "Work sub-issue kalaluthien/campaign-base#9 now",
                          mode="task-notification"))
    return r["assigned"] is None, r


@case("a task notification reaching an idle pane is not a prompt")
def _(m):
    r = reading(m, boundary(2),
                prompt(3, f"<task-notification>\n<task-id>b1</task-id>{work(9)}"))
    return r["assigned"] is None, r


@case("a command's output queued while busy is not a prompt")
def _(m):
    r = reading(m, queued(2, "<local-command-stdout>" + work(9)), boundary(3))
    return r["assigned"] is None, r


def enqueued(minute, text="/compact"):
    """A command sent into a busy pane, in the measured shape (2026-09-13):
    a `queue-operation` record, written before any user record carries it."""
    return {"type": "queue-operation", "operation": "enqueue",
            "timestamp": ts(minute), "content": text}


@case("every shape of /compact is asked, and pending until a boundary after it")
def _(m):
    shapes = [enqueued(2), prompt(2, "/compact"), queued(2, "/compact"),
              prompt(2, "<command-name>/compact</command-name>\n")]
    open_ = [reading(m, boundary(1), s) for s in shapes]
    shut = [reading(m, boundary(1), s, boundary(3)) for s in shapes]
    other = reading(m, boundary(1), enqueued(2, "wait"))
    return (all(r["compact_asked"] == ts(2) and m.compaction_pending(r)
                for r in open_)
            and not any(m.compaction_pending(r) for r in shut)
            and other["compact_asked"] is None), (open_, shut, other)


def local(minute, text):
    return {"type": "system", "subtype": "local_command",
            "timestamp": ts(minute), "content": text}


@case("a /compact refused or failed ends the window, and other command output does not")
def _(m):
    ends = [reading(m, prompt(2, "/compact"), local(3, t)) for t in (
        "<local-command-stdout>Not enough messages to compact.</local-command-stdout>",
        "<local-command-stderr>Error during compaction: You've hit your session limit")]
    other = reading(m, prompt(2, "/compact"), local(3,
        "<local-command-stdout> Context Usage\n Autocompact buffer"))
    earlier = reading(m, local(1, "<local-command-stdout>Not enough messages "
                               "to compact."), prompt(2, "/compact"))
    return (not any(m.compaction_pending(r) for r in ends)
            and m.compaction_pending(other) and m.compaction_pending(earlier)
            ), (ends, other, earlier)


# the claim refs


GH = r'''#!%(py)s
import json, os, sys
a = sys.argv[1:]
d = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
T = "repos/kalaluthien/campaign-base"
with open(os.path.join(d, "gh.log"), "a") as fh:
    fh.write(" ".join(a) + "\n")
if a[:2] == ["api", T + "/issues/7"]:
    print('["campaign", "campaign:tk"]'); sys.exit(0)
broken = lambda f: os.path.exists(os.path.join(d, f))
if a[:3] == ["issue", "view", "7"] and not broken("repos-broken"):
    print("## Repos\n\n- none\n"); sys.exit(0)
if broken("gh-broken"):
    if a[:2] == ["pr", "list"]:
        print("not json"); sys.exit(0)
    sys.exit(1)
if broken("quiet") and a[:2] == ["api", T + "/git/matching-refs/heads/tk/"]:
    print("[]"); sys.exit(0)
if broken("quiet") and a[:3] == ["api", "--paginate", T + "/issues/7/sub_issues"]:
    print(json.dumps([
        {"number": 6, "state": "open", "labels": [{"name": "backlog"}]},
        {"number": 8, "state": "closed", "labels": []}])); sys.exit(0)
if a[:2] == ["api", T + "/git/matching-refs/heads/tk/"]:
    print(json.dumps(["refs/heads/tk/5-a", "refs/heads/tk/6-b"])); sys.exit(0)
if a[:3] == ["api", "--paginate", T + "/issues/7/sub_issues"]:
    print(json.dumps([
        {"number": 5, "state": "open", "labels": []},
        {"number": 6, "state": "open", "labels": [{"name": "backlog"}]},
        {"number": 8, "state": "closed", "labels": [{"name": "bug"}]},
        {"number": 9, "state": "open", "labels": [{"name": "standing"}]},
        {"number": 10, "state": "open", "labels": [{"name": "kind:maintenance"}]}]))
    sys.exit(0)
if a[:2] == ["pr", "list"]:
    pr = lambda n, head, k, st="OPEN": {
        "number": n, "headRefName": head, "state": st,
        "headRefOid": "abc1234def", "comments": [{}] * k, "reviews": [{}]}
    print(json.dumps([pr(11, "tk/5-a", 2), pr(3, "tk/5-a", 0),
                      pr(12, "other/5-a", 9), pr(4, "tk/5-old", 0, "MERGED"),
                      pr(20, "tk/13-z", 0, "MERGED"),
                      pr(21, "tk/14-a", 0, "MERGED"),
                      pr(22, "tk/14-b", 0, "MERGED")])); sys.exit(0)
if a[:2] == ["api", "--paginate"] and a[2].endswith("/timeline"):
    # What `--jq` leaves of a timeline: each head_ref_deleted's time.
    n = int(a[2].split("/")[-2])
    print({4: "2026-09-10T10:05:00Z", 20: "2026-09-10T10:04:00Z",
           21: "2026-09-10T10:02:00Z",
           22: "2026-09-10T10:05:00Z"}.get(n, "")); sys.exit(0)
if a[:1] == ["api"] and a[1].startswith(T + "/events?per_page=100&page="):
    if broken("events-broken"):
        sys.stderr.write("HTTP 502\n"); sys.exit(1)
    page = int(a[1].rsplit("=", 1)[1])
    gone = lambda ref, m, kind="branch": {
        "type": "DeleteEvent", "created_at": "2026-09-10T10:%%02d:00Z" %% m,
        "payload": {"ref": ref, "ref_type": kind}}
    push = [{"type": "PushEvent", "created_at": "2026-09-10T11:00:00Z",
             "payload": {}}] * 100
    # Newest first, as GitHub gives it: a prefix, a tag and an older
    # topic stand beside each worker's own deletion.
    feed = [gone("tk/90-y", 8), gone("tk/4-t", 7, "tag"), gone("tk/40-z", 6),
            gone("tk/5-old", 5), gone("tk/9-x", 3), {"type": "PushEvent"},
            gone("tk/9-old", 0)]
    deep = {"events-deep": 3, "events-deeper": 4}
    at = [deep[k] for k in deep if broken(k)]
    if at:
        print(json.dumps(feed if page == at[0] else push)); sys.exit(0)
    if broken("events-unordered"):
        # As measured: page 1 holds an older deletion than page 3's.
        pages = {1: [gone("tk/9-a", 1)] + push[:99], 2: push, 3: feed}
        print(json.dumps(pages.get(page, []))); sys.exit(0)
    if page == 1:
        print(json.dumps(feed)); sys.exit(0)
sys.exit(1)
'''


def refs_fake(d, *markers):
    """A directory holding the fake `gh` and nothing else, plus the `markers`
    that break it. `claim_reading` reaches `gh` through PATH and its own
    `campaign-repos.py` through sys.executable, so no other name is needed."""
    d = Path(d)
    (d / "bin").mkdir(parents=True)
    harness.fake(d / "bin", "gh", GH % {"py": sys.executable})
    for marker in markers:
        (d / marker).write_text("")
    return d


def refs_read(m, d, *ns):
    """(the answers `refs_reader` gives for `ns`, the fake gh's calls), over
    ONE reader, so what it asks GitHub once it asks once."""
    saved, cwd = dict(os.environ), os.getcwd()
    os.environ.update({"PATH": str(d / "bin"), "TMPDIR": str(d)})
    os.chdir(d)
    try:
        claim = m.load(BASE_SCRIPTS / "campaign-claim.py", "campaign_claim")
        refs = m.refs_reader(m.claim_reading("7", "tk", claim), "tk")
        got = [refs(n) for n in ns]
    finally:
        os.chdir(cwd)
        os.environ.clear()
        os.environ.update(saved)
    log = d / "gh.log"
    return got, (log.read_text().splitlines() if log.exists() else [])


@case("a pull request's timeline answers where the feed has no deletion")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (got,), _ = refs_read(m, refs_fake(d), 13)
    (standing, went, read), why = got
    return ((standing, went, why) == ([], "2026-09-10T10:04:00Z", None)
            and "the timeline of kalaluthien/campaign-base pr#20" in read), got


@case("a sub-issue with no pull request falls to the feed, and says it is the fallback")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (got,), _ = refs_read(m, refs_fake(d), 9)
    return got == (([], "2026-09-10T10:03:00Z",
                    "tk/9-* on kalaluthien/campaign-base; no pull request, so "
                    "the events feed, the fallback: kalaluthien/campaign-base "
                    "7 event(s)"), None), got


@case("two pull requests: the later head_ref_deleted wins")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (got,), _ = refs_read(m, refs_fake(d), 14)
    (_standing, went, read), _why = got
    return (went == "2026-09-10T10:05:00Z"
            and "pr#21, kalaluthien/campaign-base pr#22" in read), got


@case("the feed is read once per refs_reader, however many sub-issues ask")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        # #5 has a ref standing, so it asks GitHub nothing; #9 and #4 have
        # none, and each falls to the feed -- which is read once for both.
        got, calls = refs_read(m, refs_fake(d), 5, 9, 4)
    asked = [ln for ln in calls if "/events?" in ln]
    return (len(asked) == 1
            and got[0] == ((["tk/5-a"], None,
                            "tk/5-* on kalaluthien/campaign-base"), None)
            and got[1][0][1] == "2026-09-10T10:03:00Z"
            # Only a tag `tk/4-t` and a `tk/40-z` sit near #4's prefix.
            and got[2][0][1] is None), (got, asked)


@case("a later deletion on a later page wins over an older one on page 1")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (got,), _ = refs_read(m, refs_fake(d, "events-unordered"), 9)
    (_standing, went, read), _why = got
    return (went == "2026-09-10T10:03:00Z" and "207 event(s)" in read), got


@case("a deletion on the feed's third page is read, and no page past it")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (deep,), _ = refs_read(m, refs_fake(Path(d) / "a", "events-deep"), 9)
        (deeper,), calls = refs_read(
            m, refs_fake(Path(d) / "b", "events-deeper"), 9)
    return (deep[0][1] == "2026-09-10T10:03:00Z" and deeper[0][1] is None
            and [ln for ln in calls if "page=4" in ln] == []), (deep, deeper)


@case("a feed that would not read is a why, not a deletion")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        (got,), _ = refs_read(m, refs_fake(d, "events-broken"), 9)
    return (got[0] is None and "the events feed not read" in got[1]), got


@case("one transcript per session id: none, or two, is a why and no path")
def _(m):
    with tempfile.TemporaryDirectory() as d:
        home, keep = Path(d), os.environ.get("HOME")
        os.environ["HOME"] = d
        try:
            got = [m.transcript_path("sid")]
            (home / ".claude" / "projects" / "a").mkdir(parents=True)
            (home / ".claude" / "projects" / "a" / "sid.jsonl").write_text("")
            got.append(m.transcript_path("sid"))
            (home / ".claude" / "projects" / "b").mkdir()
            (home / ".claude" / "projects" / "b" / "sid.jsonl").write_text("")
            got.append(m.transcript_path("sid"))
        finally:
            os.environ["HOME"] = keep
    return (got[0][0] is None and "0 transcript(s)" in got[0][1]
            and got[1] == (home / ".claude" / "projects" / "a" / "sid.jsonl", None)
            and got[2][0] is None and "2 transcript(s)" in got[2][1]), got


# ------------------------------------------------------------- mutations

# (the branch broken, old text, new text, the case that must go red)
MUTATIONS = [
    ("one transcript per id", "if len(hits) != 1:", "if not hits:",
     "one transcript per session id: none, or two, is a why and no path"),
    ("a slash command's output dropped", "out[\"commands\"][-1][1] = content", "_ = content",
     "the model is the latest assistant's, and each slash command carries what it printed"),
    ("the model read by position", "if msg.get(\"model\") and (out[\"model_at\"] is None or ts > out[\"model_at\"]):",
     "if msg.get(\"model\"):",
     "the model is the latest assistant's, and each slash command carries what it printed"),
    ("no assignment, no time", '    if n is None:\n        return None, (f"no assignment prompt',
     '    if False:\n        return None, (f"no assignment prompt',
     "compacted after the ref went is compacted, before it stale, and no time unknown"),
    ("a ref standing, no time", "    if standing:\n        return None, f\"assigned #{n}; {', '.join(standing)}",
     "    if False:\n        return None, f\"assigned #{n}; {', '.join(standing)}",
     "compacted after the ref went is compacted, before it stale, and no time unknown"),
    ("no deletion read says so", '    if went is None:\n        return None, f"assigned #{n}; no ref standing',
     '    if False:\n        return None, f"assigned #{n}; no ref standing',
     "compacted after the ref went is compacted, before it stale, and no time unknown"),
    ("compacted means after the ref went", "if comp and when(comp) > when(went):", "if comp:",
     "compacted after the ref went is compacted, before it stale, and no time unknown"),
    ("the assignment by its sentence", 'hit = ASSIGNMENT.search("".join(texts(content)))',
     "hit = None", "the assignment is the sub-issue the last assignment prompt names, typed or queued"),
    ("a queued assignment", 'said(ts, a.get("prompt"))', 'pass',
     "the assignment is the sub-issue the last assignment prompt names, typed or queued"),
    ("the last assignment by time", 'or ts > out["assigned_at"])', "or True)",
     "every last is by time, not by position in the file"),
    ("no assignment in a note or a summary", 'if r.get("isMeta") or r.get("isCompactSummary"):',
     "if False:", "an assignment in a summary, a harness note or a tool result is none"),
    ("the feed only when no ref stands", "        if standing:\n            return (standing, None, read), None\n", "",
     "the feed is read once per refs_reader, however many sub-issues ask"),
    ("a deletion under the prefix", 'and str(e["payload"].get("ref")).startswith(prefix)', "and True",
     "a sub-issue with no pull request falls to the feed, and says it is the fallback"),
    ("the prefix ends at the number", 'prefix = f"{slug}/{n}-"', 'prefix = f"{slug}/{n}"',
     "a sub-issue with no pull request falls to the feed, and says it is the fallback"),
    ("a branch, not a tag", '.get("ref_type") == "branch"', '.get("ref_type") is not None',
     "the feed is read once per refs_reader, however many sub-issues ask"),
    ("the latest over every page", "return max(times, key=when, default=None)",
     "return times[0] if times else None", "a later deletion on a later page wins over an older one on page 1"),
    ("the timeline first", "    if heads:\n", "    if False:\n",
     "a pull request's timeline answers where the feed has no deletion"),
    ("the feed only without a pull request", "    if heads:\n", "    if heads and False:\n",
     "two pull requests: the later head_ref_deleted wins"),
    ("every pull request's timeline", "            times += got\n", "            times = times or got\n",
     "two pull requests: the later head_ref_deleted wins"),
    ("a head under the prefix", "for n, head in got if head.startswith(prefix)]", "for n, head in got]",
     "a sub-issue with no pull request falls to the feed, and says it is the fallback"),
    ("the fallback names itself", '"no pull request, so the events feed, the "', '"the "',
     "a sub-issue with no pull request falls to the feed, and says it is the fallback"),
    ("no hit ends the feed", "        events += got\n",
     "        events += got\n        if any(e.get('type') == 'DeleteEvent' for e in got):\n            break\n",
     "a later deletion on a later page wins over an older one on page 1"),
    ("a short page ends the feed", "        if len(got) < 100:\n            break\n", "",
     "the feed is read once per refs_reader, however many sub-issues ask"),
    ("the feed once per reader", "            if (fn, repo) not in once:\n", "            if True:\n",
     "the feed is read once per refs_reader, however many sub-issues ask"),
    ("the feed's later pages", "for page in range(1, EVENT_PAGES + 1):", "for page in range(1, 2):",
     "a deletion on the feed's third page is read, and no page past it"),
    ("the feed's bound", "EVENT_PAGES = 3", "EVENT_PAGES = 4",
     "a deletion on the feed's third page is read, and no page past it"),
    ("a feed unread says so", "        if r.returncode != 0:\n            return None, f\"gh api {path}:",
     "        if False:\n            return None, f\"gh api {path}:",
     "a feed that would not read is a why, not a deletion"),
    ("the compaction is a record type", 'r.get("subtype") == "compact_boundary"',
     'r.get("subtype") == "compact_boundary" or "Compacted" in line',
     "the compaction marker printed as text is not a compaction"),
    ("last by time", "if out[key] is None or ts > out[key]:",
     "if True:", "every last is by time, not by position in the file"),
    ("skip a subagent", 'if not isinstance(r, dict) or r.get("isSidechain"):',
     "if not isinstance(r, dict):", "a subagent's records are not this session's"),
    ("a prompt is text", "if is_prompt(content):\n                said(ts, content)",
     "if False:\n                said(ts, content)",
     "every last is by time, not by position in the file"),
    ("a prompt typed into a busy pane", 'elif kind == "attachment":', "elif False:",
     "an assignment typed into a busy pane is the assignment, whatever its origin"),
    ("a queued peer message", 'and not a.get("isMeta")):', "):",
     "a peer's message queued into the pane is not a prompt"),
    ("only a queued prompt", 'and a.get("commandMode") == "prompt"', "",
     "a queued command in any mode but prompt is not a prompt"),
    ("a queued echo", 'if is_prompt(a.get("prompt")):', "if True:",
     "a command's output queued while busy is not a prompt"),
    ("the compaction's echo", 'COMPACTION_ECHOES = ("<command-name>/compact<", "<local-command-")',
     'COMPACTION_ECHOES = ("\\x00",)', "a command's own echoes are not a prompt"),
    ("a harness note", 'if r.get("isMeta") or r.get("isCompactSummary"):',
     'if r.get("isCompactSummary"):',
     "an assignment in a summary, a harness note or a tool result is none"),
    ("skip a synthetic record", 'elif kind == "assistant" and msg.get("model") != "<synthetic>":',
     'elif kind == "assistant":',
     "the model is the latest assistant's, and each slash command carries what it printed"),
    ("a task notice is no prompt", "COMPACTION_ECHOES + (TASK_NOTICE,))", "COMPACTION_ECHOES)",
     "a task notification reaching an idle pane is not a prompt"),
    ("pending is after the last boundary", "when(asked) > when(done)", "True",
     "every shape of /compact is asked, and pending until a boundary after it"),
    ("a /compact enqueued into a busy pane", 'elif (kind == "queue-operation"', "elif (False",
     "every shape of /compact is asked, and pending until a boundary after it"),
    ("the bare /compact is asked", "if is_compact(content):\n                later",
     "if False:\n                later",
     "every shape of /compact is asked, and pending until a boundary after it"),
    ("its echo is asked", " or said.startswith(COMPACTION_ECHOES[0])", "",
     "every shape of /compact is asked, and pending until a boundary after it"),
    ("a queued /compact is asked", 'if is_compact(a.get("prompt")):', "if False:",
     "every shape of /compact is asked, and pending until a boundary after it"),
    ("a refusal ends the window", 'later("compact_refused", ts)', "pass",
     "a /compact refused or failed ends the window, and other command output does not"),
    ("a failure ends it too", '"<local-command-stderr>Error during compaction")', ")",
     "a /compact refused or failed ends the window, and other command output does not"),
    ("only a refusal ends it", "str(r.get(\"content\")).startswith(COMPACT_REFUSALS)",
     "True", "a /compact refused or failed ends the window, and other command output does not"),
    ("a refusal ends only an earlier /compact",
     "(done is None or when(asked) > when(done))", "done is None",
     "a /compact refused or failed ends the window, and other command output does not"),
]


def main():
    harness.mutate(SCRIPT.read_text(), load, CASES, MUTATIONS)
    return harness.report()


if __name__ == "__main__":
    sys.exit(main())
