#!/usr/bin/env python3
"""Push a session its role's brief, and answer what role it holds.

    campaign-role-brief.py            read a hook payload on stdin, emit a brief
    campaign-role-brief.py --role     print this session's role, one line

Registered on SessionStart and UserPromptSubmit, where a hook's stdout is
injected into the model's context -- so "brief" means this prints the text
itself. There is no model judgement in the path: a session cannot forget to
invoke it, which is why the role's instructions live behind a hook and not
behind a skill the model chooses.

WHY BOTH EVENTS, and they do different things. SessionStart is the only moment
a compacted session can be reached: probed 2026-09-06, `/compact` fires it with
`source=compact` and its stdout survives into the new context, while the
pre-compaction one is gone. AUTO-COMPACTION IS THE SAME EVENT AND THE SAME
WORD, probed the same day by filling a `--autocompact 100000` session past its
window: three compactions fired three `SessionStart source=compact` hooks
mid-turn, with no user prompt between them -- so the hook reaches an
auto-compacted session without waiting for one, which is the case that actually
happens to a long worker. `resume` is a fourth source, observed in the same
probe. So SessionStart ALWAYS emits and always rewrites the record, whatever
its `source`, because each of those is a context this session has not been
briefed in.
UserPromptSubmit is the catch-up: it consults the record and emits only when
(role, shas) differ, so an ordinary turn costs one read and no output.

WHAT IT CANNOT REACH. An in-process subagent fires neither event (probed
2026-09-06: only PreToolUse, under the parent's session id, carrying `agent_id`
and `agent_type`). A subagent is briefed by its parent's context or not at all,
and its writes are judged by the parent's role, so it needs no brief of its own.

THE ROLE IS READ BY SESSION ID, never by pane. By pane, a nested `claude -p`
run and a subagent would both inherit the pane's role. By id, a session herdr
does not name reads as NO ROLE, which emits nothing and says so -- the safer
failure, and the one that happens for real: a pane's `agent_session` ref is
write-once, so a stale row leaves a live session unnameable for its whole life.

AN ACK IS NOT A WRITE. The record is written and then READ BACK, and the
verdict line says which branch was taken. The neighbouring hook this one sits
beside reports a link it never verified, and two silent successes read exactly
like a repair; a mechanised rule that cannot say what it observed is worse than
the unenforced rule it replaced.

IT DOES NOT WRITE `guard.log`. That log is the claim guard's own verdict stream
and `guard-precision.py` counts every non-REFUSED row in it as an allow, so a
brief line there would inflate the denominator of the one measurement the log
exists for. What is durable here is the record file, whose path every line
prints.

EXIT. Always 0, and never a traceback: a hook that fails must not wall the
session it was meant to help. Every path prints one line to stderr saying what
was read and which branch was taken.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent.parent.parent      # .../.claude/skills/<skill>/scripts
SKILL = HERE.parent
REFERENCES = {"planner": SKILL / "references" / "planner.md",
              "worker": SKILL / "references" / "worker.md"}


def say(line):
    print(f"campaign-role-brief: {line}", file=sys.stderr)


def load(stem, alias):
    """A sibling module out of this skill, by path."""
    import importlib.machinery
    import importlib.util
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(HERE / f"{stem}.py")))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def role_of(session_id):
    """(role, campaign token, how). `None` role means no brief: either the
    session has no campaign name, or the reading itself failed.

    THE TWO ARE TOLD APART BY THE FIRST WORDS OF `how`, and that is a contract
    `SKILL.md` documents: every could-not-look opens `could not`, every
    looked-and-found-nothing opens `no role read for`. A reader testing one
    exact sentence would go stale on the next branch added here. The two are
    kept apart in `how` because one is repaired by naming the session and the
    other is a defect to report.

    THE CAMPAIGN IS A TOKEN, not a number: since #181 a session is named for
    its campaign's SLUG, and `campaign_of` is the one reader that admits the
    slug and the retired `campaign-<N>` alike. Asking it, rather than reading
    NAME's group 1, is what keeps this in step with what the guard admits."""
    if not session_id:
        return None, None, "could not read a session id from the payload"
    try:
        rule = load("campaign-name-session", "cns")
    except Exception as e:                  # noqa: BLE001 -- reported, not raised
        return None, None, f"could not read the name rule ({e.__class__.__name__})"
    try:
        r = subprocess.run(["herdr", "agent", "list"], capture_output=True,
                           text=True, timeout=10)
        rows = json.loads(r.stdout)["result"]["agents"] if r.returncode == 0 else None
    except Exception as e:                  # noqa: BLE001
        return None, None, f"could not read herdr ({e.__class__.__name__})"
    if rows is None:
        return None, None, f"could not read herdr: agent list exited {r.returncode}"
    for a in rows:
        if not isinstance(a, dict):
            return None, None, "could not read herdr: a row was not an object"
        if ((a.get("agent_session") or {}) if isinstance(a.get("agent_session"), dict)
                else {}).get("value") != session_id:
            continue
        name = a.get("name") or ""
        campaign = rule.campaign_of(name) if isinstance(name, str) else None
        if campaign is None:
            return None, None, (f"no role read for {session_id}: herdr names it "
                                f"{name or 'nothing'}")
        return ("planner" if "-planner-" in name else "worker"), campaign, name
    return None, None, f"no role read for {session_id}: herdr holds no row for it"


def body(path):
    """A markdown file with its frontmatter stripped, or None."""
    try:
        text = path.read_text()
    except OSError:
        return None
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        if end != -1:
            text = text[end + 5:]
    return text.lstrip("\n")


# What opens or closes a fenced block, and what ends a section. A HEADING OF
# LEVEL 1 OR 2 ends it: the template's `## Worker` is its last section, so
# anything a campaign appends -- a `# Notes` of its own -- used to be swallowed
# into the brief. `###` does not, because a subheading is part of its section.
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}#{1,2} ")


def fenced_lines(lines):
    """The line numbers inside a CLOSED fence.

    AN OPENER WITH NO CLOSER IS NOT A FENCE, and that is the whole reason this
    is a first pass rather than a running flag. A stray triple backtick made
    everything after it text: a heading below it stopped closing sections, so
    an unclosed fence before the role's heading dropped the campaign's section
    entirely and one inside it emitted to end of file. Both failures are
    silent, and a campaign document is somebody's prose -- the shape shows up.
    Unbalanced, the run is read as the text it is."""
    inside, open_at, run = set(), None, None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if not m:
            continue
        if open_at is None:
            open_at, run = i, m.group(1)
        elif m.group(1)[0] == run[0] and len(m.group(1)) >= len(run):
            inside.update(range(open_at, i + 1))
            open_at, run = None, None
    return inside


def campaign_section(role):
    """The campaign `AGENTS.md`'s section for one role, if there is one. The
    campaign directory is found from cwd, so a session outside one gets no
    section rather than another campaign's.

    A HEADING INSIDE A FENCE IS TEXT, not a heading. A campaign document
    quoting `## Worker` in an example opened the section there and emitted the
    rest of the file -- the same reading `check-rule-readers.py` gets right for
    the opposite reason, and the shape a markdown scanner gets wrong first."""
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    for d in [cwd, *cwd.parents]:
        f = d / "AGENTS.md"
        if not (f.is_file() and (d / "runtime").is_dir()):
            continue
        want = f"## {role.capitalize()}"
        lines = f.read_text().splitlines()
        fenced = fenced_lines(lines)
        out, keep = [], False
        for i, line in enumerate(lines):
            if i not in fenced and HEADING.match(line):
                keep = line.strip() in (want, "## Every session")
            if keep:
                out.append(line)
        return "\n".join(out) or None
    return None


def record_path(session_id):
    """`<campaign>/runtime/briefed/<session>` where a campaign directory is
    reachable, else `<base>/runtime/`. Printed, never guessed at by the reader:
    a base worktree cannot reach a campaign directory's runtime."""
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    for d in [cwd, *cwd.parents]:
        if (d / "runtime").is_dir() and (d / "AGENTS.md").is_file():
            return d / "runtime" / "briefed" / session_id
    return BASE / "runtime" / "briefed" / session_id


def brief(role, campaign):
    parts = [f"You are a {role} of campaign `{campaign}`. This is that role's "
             f"standing brief; it replaces nothing you were told, and adds."]
    for p in (SKILL / "SKILL.md", REFERENCES[role]):
        t = body(p)
        if t:
            parts.append(t)
    section = campaign_section(role)
    if section:
        parts.append(section)
    return "\n\n".join(parts)


def main():
    argv = sys.argv[1:]
    if "--role" in argv:
        role, campaign, how = role_of(os.environ.get("CLAUDE_CODE_SESSION_ID"))
        print(f"{role} {campaign}" if role else how)
        return 0

    try:
        hook = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        say("the hook payload would not read; briefed nothing")
        return 0
    if hook.get("agent_id"):
        say("a subagent fires no brief; it is judged by its parent's role")
        return 0
    event = hook.get("hook_event_name") or ""
    session_id = hook.get("session_id")
    role, campaign, how = role_of(session_id)
    if not role:
        say(f"{how}; briefed nothing and recorded nothing")
        return 0

    text = brief(role, campaign)
    # (role, campaign, the brief's sha) -- a length would let a same-length
    # edit to any briefed file pass as already read.
    stamp = f"{role} {campaign} {hashlib.sha256(text.encode()).hexdigest()[:12]}"
    record = record_path(session_id)
    # SessionStart always emits: every source of it is a context this session
    # has not been briefed in, compaction included. UserPromptSubmit is the
    # catch-up and consults the record.
    if event == "UserPromptSubmit":
        try:
            if record.read_text().strip() == stamp:
                say(f"already briefed as {role} of `{campaign}` "
                    f"(record {record}); emitted nothing")
                return 0
        except OSError:
            pass
    print(text)
    written = "not written"
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(stamp)
        written = ("written and read back"
                   if record.read_text().strip() == stamp
                   else "written but read back different")
    except OSError as e:
        written = f"not written ({e.__class__.__name__})"
    say(f"{event}: briefed {role} of `{campaign}` ({len(text)} chars); "
        f"record {record} {written}")
    return 0


try:
    raise SystemExit(main())
except SystemExit:
    raise
except Exception as e:                       # noqa: BLE001 -- never wall a session
    say(f"failed ({e.__class__.__name__}); briefed nothing")
    raise SystemExit(0)
