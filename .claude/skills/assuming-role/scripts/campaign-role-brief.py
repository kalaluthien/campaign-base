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

IT DOES NOT WRITE `guard.log`. That log is the CLAIM GUARD's own verdict
stream, one row per call it judged, and `guard-precision.py` pairs a refusal
with the same session's next `allowed` row on the same target. A brief line
is neither verdict and would sit in that stream as a row nothing can pair,
between a refusal and the allow that answers it. What is durable here is the
record file, whose path every line prints.

THE KIND OF THE SUB-ISSUE. The assignment prompt is the first moment a session
knows WHICH sub-issue it works, so it is the first moment the kind's reference
can reach it: the prompt names `<repo>#<issue>`, `campaign-tracker.py kind`
answers what the `kind:` label says, and the reference for that word is emitted
beside the role brief. Before this, rule-check#313 measured the kind's advice
reaching a base worker zero times -- it was written down and nothing delivered
it. `campaign-assign.py`'s `ASSIGNMENT` is the one home of the sentence's
shape and is imported from there, so the writer and the reader cannot drift,
and the label is read by the TRACKER and never here: two readers of one label
drift.

It is recorded so a compaction re-emits it while that sub-issue is still open --
a closed one is work that is over, and SessionStart deletes the record instead
of briefing a session on it again -- the same reason the role is recorded, and
THE TWO ARE SEPARATE RECORDS because they change at different moments -- a
rename moves the role, a new assignment moves the kind, and one stamp holding
both would re-emit each whenever the other moved. DELIVERY IS INDEPENDENT OF
THE ROLE: a session herdr does not name has no role to brief and is still
working a sub-issue, so the no-role branch says so and the kind path runs
anyway. A subagent still gets neither.

EXIT. Always 0, and never a traceback: a hook that fails must not wall the
session it was meant to help. Every path prints one line to stderr saying what
was read and which branch was taken, and the kind path's own lines open
`kind:` so the two readings are never mistaken for one.
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
# The one reader of the `kind:` label, asked as a subprocess. BASE is derived
# from this file's own path, so the tracker is found from a session started
# anywhere -- a worktree, a clone, a campaign directory.
TRACKER = BASE / "scripts" / "campaign-tracker.py"


def say(line):
    print(f"campaign-role-brief: {line}", file=sys.stderr)


def say_kind(line):
    """The kind path's verdict line. Its own prefix, because the role reading
    and the kind reading are two readings and a reader acts on them apart."""
    say(f"kind: {line}")


def load(path, alias):
    """A module by path -- a sibling out of this skill, or one of the base's
    own `scripts/`, which a hook in a skill cannot import any other way."""
    import importlib.machinery
    import importlib.util
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha12(text):
    """The stamp's digest. A LENGTH WOULD NOT DO: a same-length edit to a
    briefed file would then pass as already read."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


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
    its campaign's SLUG, and `campaign_of` is the one reader of which tokens
    count. Asking it, rather than reading NAME's group 1, is what keeps this in
    step with what the guard admits -- including #237's narrowing to the slug
    alone, which reached here without an edit."""
    if not session_id:
        return None, None, "could not read a session id from the payload"
    try:
        rule = load(HERE / "campaign-name-session.py", "cns")
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


def write_record(path, entry):
    """Write a record and READ IT BACK, answering what to say about it: an ack
    is not a write, and a successful write that comes back wrong is neither a
    failure nor a success until somebody says which."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry)
        return ("written and read back" if path.read_text().strip() == entry
                else "written but read back different")
    except OSError as e:
        return f"not written ({e.__class__.__name__})"


def kind_record_path(session_id):
    """The kind's record, beside the role's. Two files because the two change
    at different moments: a rename moves the role, a new assignment moves the
    kind, and one stamp holding both re-emits each when the other moves."""
    r = record_path(session_id)
    return r.parent / (r.name + ".kind")


def kind_reference(word):
    """(the reference's body or None, its path). `development` has no reference
    on purpose, and a word naming no file is the same absence to a reader, so
    both come back as the same no and the path is printed either way."""
    p = SKILL / "references" / f"kind-{word}.md"
    return body(p), p


def tracker_kind(repo, issue):
    """(the kind's word, why not) from `campaign-tracker.py kind`.

    THE TRACKER IS THE ONE READER of the `kind:` label (AGENTS.md § Sub-issues),
    so this asks it as a subprocess rather than reading labels itself: a second
    reader of a label set would drift on the very cases the tracker refuses to
    answer -- two `kind:` labels, and a word outside its `WORK_KINDS`.

    Its answers are separate readings and are not folded together: exit 1 with
    `none` is a sub-issue with no kind, and any other status is a reading that
    never happened. EXIT 2 COVERS TWO THINGS -- a refusal to answer (two
    `kind:` labels, a word outside `WORK_KINDS`) and a `gh` read the tracker could
    not make -- so the line says neither happened rather than calling both a
    refusal, and the QUOTED FIRST LINE is what tells them apart. A MISSING
    TRACKER IS NOT EITHER OF THEM, and neither is python's own exit 2 for a file
    it could not open -- which is why the file is looked for first and that
    branch wants the tracker's own prefix on the line it quotes."""
    if not TRACKER.is_file():
        return None, f"could not read {TRACKER}: no such file"
    try:
        r = subprocess.run([sys.executable, str(TRACKER), "kind", issue, repo],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:                      # noqa: BLE001 -- reported
        return None, f"could not run {TRACKER} ({e.__class__.__name__})"
    word = (r.stdout or "").strip()
    first = ((r.stderr or "").strip().splitlines() or [""])[0]
    if r.returncode == 2 and first.startswith("campaign-tracker"):
        return None, (f"campaign-tracker would not answer the kind (a refusal, "
                      f"or a read it could not make): {first}")
    if r.returncode == 1 and word == "none":
        return None, "campaign-tracker said `none`; it carries no `kind:` label"
    if r.returncode != 0 or not word:
        return None, (f"could not run campaign-tracker kind: exit "
                      f"{r.returncode}, said {(first or word or 'nothing')!r}")
    return word, None


def issue_state(repo, issue):
    """(`OPEN`, `CLOSED`, or None with why not) for one sub-issue.

    THE ONLY QUESTION SESSIONSTART ASKS, and it is asked of `gh` directly: the
    kind is already in the record, so the tracker -- the one reader of the
    `kind:` label -- has nothing to add here, and this reads no label. A state
    that is neither word is the same as a `gh` that failed: a reading never
    made, which the caller must not take for a close."""
    try:
        r = subprocess.run(["gh", "issue", "view", issue, "-R", repo,
                            "--json", "state", "--jq", ".state"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"could not run gh issue view ({e.__class__.__name__})"
    word = (r.stdout or "").strip()
    if r.returncode != 0:
        first = ((r.stderr or "").strip().splitlines() or [""])[0]
        return None, (f"gh issue view exited {r.returncode}, said "
                      f"{(first or word or 'nothing')!r}")
    if word not in ("OPEN", "CLOSED"):
        return None, f"gh issue view said {word!r}, which is neither state"
    return word, None


def deliver_kind(hook, event, session_id):
    """Emit the reference for the kind of the sub-issue this session works.

    On UserPromptSubmit the assignment prompt names it, and the tracker is
    asked exactly then. On SessionStart the record answers what the kind is,
    with no tracker call: compaction is the case this exists for, and what the
    label said is already recorded. SESSIONSTART ASKS EXACTLY ONE QUESTION AND
    NO OTHER -- whether the recorded sub-issue is still OPEN, of `gh issue
    view`. A closed one is work that is over, so its record goes and nothing is
    emitted; a state that could not be read is NOT a close, so that branch
    re-emits and keeps the record, because a compaction mid-work with `gh` down
    must not lose the reference. Prints nothing on stdout unless it delivers,
    and always one line on stderr saying which branch it took."""
    if not session_id:
        say_kind("could not read a session id from the payload; delivered "
                 "nothing")
        return
    record = kind_record_path(session_id)
    if event == "SessionStart":
        try:
            recorded = record.read_text().strip()
        except OSError:
            say_kind(f"no record at {record}; this session has been assigned "
                     f"no sub-issue, so there is no kind to re-emit")
            return
        parts = recorded.split()
        if len(parts) < 2 or "#" not in parts[0]:
            say_kind(f"the record at {record} reads {recorded!r}, which is not "
                     f"`<repo>#<issue> <kind> <sha>`; delivered nothing")
            return
        subject, word = parts[0], parts[1]
        repo, _, issue = subject.partition("#")
        source = hook.get("source") or "none"
        state, why = issue_state(repo, issue)
        if state == "CLOSED":
            try:
                record.unlink(missing_ok=True)
                gone = f"deleted the record at {record}"
            except OSError as e:
                gone = (f"could not delete the record at {record} "
                        f"({e.__class__.__name__}), which therefore stands")
            say_kind(f"{event} source={source}: {subject} is closed, so this "
                     f"work is over; {gone} and emitted nothing")
            return
        ref, path = kind_reference(word)
        if not ref:
            say_kind(f"{subject} is `{word}`, which has no reference at "
                     f"{path}; delivered nothing")
            return
        text = f"# Kind of {repo}#{issue}: {word}\n\n{ref}"
        print(text)
        written = write_record(record, f"{subject} {word} {sha12(text)}")
        standing = ("is open" if state == "OPEN" else
                    f"could not read the state ({why}), so kept the record")
        say_kind(f"{event} source={source}: {subject} {standing}, re-emitted "
                 f"`{word}` from the record with no tracker call "
                 f"({len(text)} chars); record {record} {written}")
        return
    if event != "UserPromptSubmit":
        say_kind(f"{event or 'an event with no name'} carries no assignment; "
                 f"asked the tracker nothing and delivered nothing")
        return
    try:
        pattern = load(BASE / "scripts" / "campaign-assign.py", "ca").ASSIGNMENT
    except Exception as e:                      # noqa: BLE001 -- reported
        say_kind(f"could not read the assignment sentence's shape from "
                 f"{BASE / 'scripts' / 'campaign-assign.py'} "
                 f"({e.__class__.__name__}); delivered nothing")
        return
    hit = pattern.search(hook.get("prompt") or "")
    if not hit:
        say_kind("no assignment sentence in the prompt; asked the tracker "
                 "nothing and delivered nothing")
        return
    repo, issue = hit.group("repo"), hit.group("issue")
    word, why = tracker_kind(repo, issue)
    if word is None:
        say_kind(f"{repo}#{issue}: {why}; delivered nothing")
        return
    ref, path = kind_reference(word)
    if not ref:
        say_kind(f"{repo}#{issue} is `{word}`, which has no reference at "
                 f"{path}; delivered nothing")
        return
    text = f"# Kind of {repo}#{issue}: {word}\n\n{ref}"
    entry = f"{repo}#{issue} {word} {sha12(text)}"
    try:
        if record.read_text().strip() == entry:
            say_kind(f"already delivered {repo}#{issue} `{word}` "
                     f"(record {record}); emitted nothing")
            return
    except OSError:
        pass
    print(text)
    written = write_record(record, entry)
    say_kind(f"{event}: {repo}#{issue} is `{word}`; emitted {len(text)} chars; "
             f"record {record} {written}")


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


def brief_role(event, session_id):
    """The role's own brief. Returns nothing: the kind path runs after it
    whatever this decided, so no branch here may return out of `main`."""
    role, campaign, how = role_of(session_id)
    if not role:
        say(f"{how}; briefed nothing and recorded nothing")
        return

    text = brief(role, campaign)
    # (role, campaign, the brief's sha) -- a length would let a same-length
    # edit to any briefed file pass as already read.
    stamp = f"{role} {campaign} {sha12(text)}"
    record = record_path(session_id)
    # SessionStart always emits: every source of it is a context this session
    # has not been briefed in, compaction included. UserPromptSubmit is the
    # catch-up and consults the record.
    if event == "UserPromptSubmit":
        try:
            if record.read_text().strip() == stamp:
                say(f"already briefed as {role} of `{campaign}` "
                    f"(record {record}); emitted nothing")
                return
        except OSError:
            pass
    print(text)
    written = write_record(record, stamp)
    say(f"{event}: briefed {role} of `{campaign}` ({len(text)} chars); "
        f"record {record} {written}")


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
    brief_role(event, session_id)
    # THE KIND IS NOT THE ROLE'S. A session herdr does not name has no role to
    # brief and is still working a sub-issue, so this runs whatever the reading
    # above said -- and after it, so a session reads who it is before what the
    # work is.
    deliver_kind(hook, event, session_id)
    return 0


try:
    raise SystemExit(main())
except SystemExit:
    raise
except Exception as e:                       # noqa: BLE001 -- never wall a session
    say(f"failed ({e.__class__.__name__}); briefed nothing")
    raise SystemExit(0)
