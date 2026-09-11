#!/usr/bin/env python3
"""Run one spec/ module, hold its command list, and digest its traces.

    scripts/alloy-check.py <file.als> [-o <dir>]
    scripts/alloy-check.py --commands spec [--write]
    scripts/alloy-check.py --digest <solution-0.txt> [...]

Every command under spec/, whatever entity it belongs to, carries its own verdict, in the `expect`
clause the solver enforces: `expect 0` where the solver says UNSAT -- a check
with no counterexample, a run with no instance -- and `expect 1` where it says
SAT. Alloy exits non-zero and names each command that came out other than its
clause says, so the verdict is checked by the tool that computed it, and this
script neither restates nor re-reads it. There is no verdict table anywhere,
and reintroducing one would be a second reader of what the solver already
decided.

That leaves two holes and two jobs.

RUNNING (the default mode) is `alloy exec -f -t text -c '*'` into <dir>, a
fresh temporary directory unless -o names one, so the traces outlive the run
and `--digest` has something to read. It passes alloy's own output and exit
status through; a run that printed no command result at all -- a parse error, a
missing solver -- is reported as that and never as a pass, because looking and
finding nothing is not the same as being unable to look.

THE DEAD EVENT is the first hole. A `check` over an event no trace reaches
holds by vacuity, and comes out UNSAT exactly as a true one does: #289 shipped
four checks over a `Handoff` whose own predicate set `Where.machine`, which
every step above session pins empty. So a run also reads, for every event a
`check` in <file> names, a WITNESS: a `run` declared in <file> -- the only file
whose commands alloy runs -- of a predicate shaped `eventually Now.event = E`,
or `eventually (Now.event = E and ...)` whose other conjuncts are joined by
`and` alone, since a disjunct the witness does not name satisfies it without E
ever firing. The events are the `one sig ... extends Event` declarations of
<file> and every module it opens, comments stripped, and a check names one when
its `assert` body does, directly or through the preds and funs it calls. The
witness's verdict is the one alloy printed for it, so this reads a verdict
rather than computing one: SAT passes, UNSAT is DEAD and no witness is MISSING,
each refusal naming the event and the file. Two ceilings. A witness is read at
its own scope and not the check's, so one that fires only past the check's
bound passes here. And a witness in a shape this does not read -- an indented,
labelled or anonymous `run`, a body of two top-level lines -- counts as none,
which refuses rather than passes; so does a variable named like a pred,
whose events a check is then read as naming.

THE SECOND HOLE is deletion. `expect` is checked per command, so a command someone
removed misses no expectation: it simply is not there. Nothing generated *from*
the models can see it either -- regenerate an inventory after the deletion and
the command is absent from the claim exactly as it is from the model, so every
property over "the commands that exist" still holds, over a smaller set. Only a
second statement that does NOT regenerate can catch it.

--commands is that statement. It extracts every `check`/`run` declaration from
the .als files under <dir>, RECURSIVELY, and compares them to
<dir>/commands.snapshot.json, naming each command that appeared or went. The
committed one sits at spec/commands.snapshot.json, one snapshot over every
entity, so `--commands spec` is the form CI runs -- and the only form: a <dir>
that is not the spec root of its repository is refused, because a snapshot
written under one entity is a subset the next reader diffs against (#250).
`--write` regenerates the snapshot, which is how a deliberate change is
recorded. The snapshot holds the module, the kind and the name, and deliberately
NOT the scope, which is tuned often, nor the `expect` value, which would put a
verdict back in a file for a script to read. The module key is the path relative
to <dir> -- `campaign/orchestration/checks.als` -- so a command moving between entities
reads as one line gone and one line new, naming itself at both ends.

Its ceiling, stated rather than hidden: it does not stop a commit that deletes a
command and regenerates in one go, any more than a hand-kept count stops one
that also edits the number. It catches the careless deletion. A floor, not a
fence -- and unlike a count, what it prints is the command's name.

Exit 0 when the mode's checks pass, 1 when they fail -- a missed `expect` or a
dead event -- and 2 when it could not look: a run that produced no command
result, or a model whose checks and witnesses it could not read.

`--digest` condenses the traces the run above just wrote. The raw `-t text` dump
repeats every static signature in every state, which buries the handful of
relations a scenario is actually about; the digest prints the event, its
arguments, and the varying relations only, one line per state. The relations
it knows are the two tables below, spec/campaign's and spec/sdlc's. The
five entities in spec/campaign/ are layered and open one another, so a composed trace names
every relation and every atom by its module path -- the chain of `system`
modules, `system/system/system/system/system/Now<:event`. The path is stripped:
which entity declared a relation is the model's business, not a reader's. It
reads the run's output rather than the model, so it is the same command's
second half rather than a second script.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ALLOY = os.path.expanduser("~/.local/bin/alloy")
# `00. check Name   0   UNSAT` / `01. run   Name   0   1/1   SAT`, and the same
# line with ` expects=N` appended when the command missed its `expect` clause.
RESULT = re.compile(r"^\d+\.\s+(check|run)\s+(\S+)\s+\d+\s+(?:\d+/\d+\s+)?(SAT|UNSAT)\b")
# A command declaration, which always opens its line: `check Name for ...`.
DECL = re.compile(r"^(check|run)\s+(\w+)\b")
SNAPSHOT = "commands.snapshot.json"
# THE ONE DIRECTORY --commands TAKES: the spec root, under the repository root
# of whatever tree <dir> sits in. The snapshot is one statement over every
# entity, and a snapshot written under an entity's own directory is a subset
# that the next reader diffs against and the tree keeps (check-tree-shape
# refuses only markdown under spec/). So a <dir> that is not this is refused
# rather than inventoried, and --write never lands a second snapshot.
SNAPSHOT_ROOT = "spec"


def inventory(directory):
    """[[module, kind, name]] over every .als under <directory>, sorted.

    The module key is the path relative to <directory>, so the entity a command
    lives in is part of what the snapshot states.
    """
    # Three ways this can come back empty, and they are not the same answer.
    # `os.walk` yields nothing for all three, so each is asked before it runs:
    # a directory that is not there and a path that is not a directory are
    # "I could not look", and only the third is "I looked and found nothing".
    if not os.path.exists(directory):
        raise SystemExit(f"alloy-check --commands: {directory} does not exist, "
                         f"so nothing was read and no command list was compared")
    if not os.path.isdir(directory):
        raise SystemExit(f"alloy-check --commands: {directory} is not a directory, "
                         f"so nothing was read; name the directory holding the "
                         f"models and {SNAPSHOT}")
    als = []
    for root, _, names in os.walk(directory):
        for name in names:
            if name.endswith(".als"):
                als.append(os.path.relpath(os.path.join(root, name), directory))
    if not als:
        raise SystemExit(f"alloy-check --commands: {directory} was read and holds "
                         f"no .als file at any depth; the models are gone or this "
                         f"is the wrong directory")
    found = []
    for key in sorted(als):
        with open(os.path.join(directory, key)) as fh:
            for line in fh:
                m = DECL.match(line)
                if m:
                    found.append([key, m.group(1), m.group(2)])
    return sorted(found)


def snapshot_root(directory):
    """The one directory the snapshot sits in for the tree holding <directory>:
    `<repository root>/spec`, or a SystemExit naming why it could not be found."""
    try:
        top = subprocess.run(["git", "-C", directory, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise SystemExit(f"alloy-check --commands: could not resolve the repository "
                         f"root above {directory} ({e.__class__.__name__}), so "
                         f"nothing was compared; the snapshot sits at "
                         f"<root>/{SNAPSHOT_ROOT}/{SNAPSHOT}")
    return os.path.realpath(os.path.join(top, SNAPSHOT_ROOT))


def commands_mode(directory, write):
    """Compare the models' declarations to the committed snapshot at the spec root."""
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        inventory(directory)                     # raises with the right words
    root = snapshot_root(directory)
    if os.path.realpath(directory) != root:
        print(f"alloy-check --commands: {directory} is not the snapshot's root "
              f"{root}; the snapshot is one statement over the whole of "
              f"{SNAPSHOT_ROOT}/, and one written under an entity's directory "
              f"is a subset the next reader diffs against. Name {root}.",
              file=sys.stderr)
        return 1
    snapshot = os.path.join(directory, SNAPSHOT)
    found = inventory(directory)
    # Hand-rolled rather than json.dumps(indent=...), which puts every element
    # of a triple on its own line: one command per line is the whole point, so
    # that a deletion is one removed line naming the command that went.
    head = {
        "generated_by": "scripts/alloy-check.py --commands spec --write",
        "why": "A deleted command misses no `expect` clause, and an inventory "
               "regenerated from the models cannot see the deletion either. "
               "This copy is committed so the diff is the reader.",
    }
    rows = ",\n".join("    " + json.dumps(c) for c in found)
    text = ("{\n"
            + "".join(f"  {json.dumps(k)}: {json.dumps(v)},\n"
                      for k, v in head.items())
            + '  "commands": [\n' + rows + "\n  ]\n}\n")
    if write:
        open(snapshot, "w").write(text)
        print(f"wrote     {snapshot}  ({len(found)} commands)")
        return 0

    print(f"models    {directory}  ({len(found)} commands declared)")
    if not os.path.exists(snapshot):
        print(f"snapshot  ABSENT  {snapshot}")
        print("RESULT    could not compare: write it with --write")
        return 1
    print(f"snapshot  {snapshot}")
    was = [list(c) for c in json.load(open(snapshot))["commands"]]
    gone = [c for c in was if c not in found]
    new = [c for c in found if c not in was]
    for mod, kind, name in gone:
        print(f"GONE      {mod:<40} {kind:<6} {name}")
    for mod, kind, name in new:
        print(f"NEW       {mod:<40} {kind:<6} {name}")
    if gone or new:
        print(f"RESULT    {len(gone)} gone, {len(new)} new; if deliberate, "
              f"rerun with --write and commit {SNAPSHOT}")
        return 1
    print(f"RESULT    the snapshot names exactly the {len(found)} declared commands")
    return 0


def run_alloy(path, outdir):
    """(alloy's exit status, how many commands ran -- None if none could be
    read, {command name: SAT or UNSAT})."""
    cmd = [ALLOY, "exec", "-f", "-o", outdir, "-t", "text", "-c", "*", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Alloy prints its per-command lines and its expectation errors to stderr,
    # and a run's line carries backspaces from a progress counter (6.2.0).
    output = (proc.stdout + proc.stderr).replace("\b", "")
    sys.stdout.write(output)
    sys.stdout.flush()
    verdicts = {m.group(2): m.group(3) for m in map(RESULT.match, output.splitlines()) if m}
    if not verdicts:
        return proc.returncode, None, verdicts
    receipt = os.path.join(outdir, "receipt.json")
    if os.path.exists(receipt):
        return proc.returncode, len(json.load(open(receipt))["commands"]), verdicts
    return proc.returncode, len(verdicts), verdicts


# ------------------------------------------------------------- the dead event

COMMENT = re.compile(r"/\*.*?\*/|(?:--|//)[^\n]*", re.S)
MODULE = re.compile(r"^\s*module\s+([\w/]+)", re.M)
OPEN = re.compile(r"^\s*open\s+([\w/]+)", re.M)
EVENTS = re.compile(r"\bone\s+sig\s+([\w\s,]+?)\s+extends\s+Event\b")
# The event stands alone or is followed by `and`: `Now.event = E.r` is some
# other event.
WITNESS = re.compile(r"eventually\s+(?:Now\.event\s*=\s*(\w+)"
                     r"|\(\s*Now\.event\s*=\s*(\w+)((?:\s+and\b|\s*&&).*)?\s*\))", re.S)
# What may join a conjunct to the rest of a formula without making it
# optional. Anything else at the top level lets a trace satisfy the witness
# without its event: `or`, an implication, an equivalence. `<=>` is caught by
# its `=>`, and `else` only ever follows an implication.
NOT_AND = re.compile(r"\bor\b|\|\||\bimplies\b|=>|\biff\b")
# What follows a set comprehension's brace, `{x: S | ...}` or `{disj x, y: S
# | ...}`, and never a formula's: a body cannot open with a declaration. It
# can open with a range restriction, `r :> S`, which is not one.
COMPREHENSION = re.compile(r"\s*(?:disj\s+)?\w+(?:\s*,\s*\w+)*\s*:(?!>)")


def composed(path):
    """{module path: its text, comments stripped} for <path> and every module
    it opens, resolved as alloy resolves them: from the directory the root
    file's own `module` line names, or its own directory when it has none. A
    `util/` module not found there is alloy's own library, which declares no
    Event, and is not read."""
    path = os.path.abspath(path)
    top = COMMENT.sub(" ", open(path).read())
    m = MODULE.search(top)
    root = path[: -len(m.group(1) + ".als")] if m else os.path.dirname(path) + os.sep
    found, todo = {}, [path]
    while todo:
        p = todo.pop()
        if p in found:
            continue
        if not os.path.exists(p):
            raise LookupError(f"{p} is opened and is not there")
        found[p] = COMMENT.sub(" ", open(p).read())
        for o in OPEN.findall(found[p]):
            q = os.path.join(root, o + ".als")
            if not (o.startswith("util/") and not os.path.exists(q)):
                todo.append(q)
    return found


def declaration(text, keyword, name):
    """(head, body) of the first `<keyword> [S.]<name> <head> { <body> }` in
    <text>, or None. The head is whatever stands between the name and the
    first brace that neither opens a set comprehension nor sits inside one --
    parameters in `[...]` or `(...)` and a fun's return type, a comprehension
    in either."""
    for m in re.finditer(rf"\b{keyword}\s+(?:\w+\.)?{name}(?![\w.])", text):
        depth, i = 0, m.end()
        while depth or text[i] != "{" or COMPREHENSION.match(text, i + 1):
            depth += (text[i] == "{") - (text[i] == "}")
            i += 1
        start, depth = i + 1, 1
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if not depth:
                return text[m.end():start - 1], text[start:i]
    return None


def witnessed(pred_body):
    """The event a predicate body shows firing in every trace it admits, or None."""
    m = WITNESS.fullmatch(" ".join(pred_body.split()))
    if not m:
        return None
    if m.group(1):
        return m.group(1)
    rest = m.group(3) or ""
    depth, bound = 0, False
    for i, c in enumerate(rest):
        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(c, 0)
        if depth < 0:
            return None                  # the outer parenthesis closed early
        if depth or bound:
            continue
        if NOT_AND.match(rest, i):
            return None
        # A quantifier's or a `let`'s body runs to the outer parenthesis and
        # is one conjunct, so only an early close is read past its bar.
        bound = c == "|"
    return m.group(2)


def reach(path, verdicts):
    """(declared events, [(event, [checks naming it], [(witness, verdict)])])
    over the checks declared in <path>. A check names an event its `assert`
    body names, directly or through the preds and funs it calls, read by name.
    LookupError when a check's `assert` cannot be read, which is not the same
    as none; a run of anything but a pred is not a witness."""
    modules = composed(path)
    text = "\n".join(modules.values())
    events = sorted({e.strip() for m in EVENTS.finditer(text)
                     for e in m.group(1).split(",")})
    helpers = set(re.findall(r"\b(?:pred|fun)\s+(?:\w+\.)?(\w+)", text))
    own = [DECL.match(l) for l in modules[os.path.abspath(path)].splitlines()]
    named = {}
    for kind, name in (m.groups() for m in own if m):
        if kind == "check":
            d = declaration(text, "assert", name)
            if d is None:
                raise LookupError(f"no `assert {name}` was found for its check")
            todo, seen, hit = [d[1]], set(), set()
            while todo:
                for word in set(re.findall(r"\w+", todo.pop())):
                    if word in events:
                        hit.add(word)
                    elif word in helpers and word not in seen:
                        seen.add(word)
                        todo += [d[1] for d in (declaration(text, "pred", word),
                                                declaration(text, "fun", word)) if d]
            for e in hit:
                named.setdefault(e, []).append(name)
    root = modules[os.path.abspath(path)]
    shown = {}
    for kind, name in (m.groups() for m in own if m):
        if kind != "run":
            continue
        # Alloy runs the root's own declaration of the name, pred or fun, over
        # a namesake in a module it opens.
        own_decl = re.search(rf"\b(?:pred|fun)\s+(?:\w+\.)?{name}(?![\w.])", root)
        d = declaration(root if own_decl else text, "pred", name)
        if d is None:
            continue                     # a run of a fun
        e = witnessed(d[1])
        # A parameter named like the event, `Now` or `event` shadows what the
        # body reads: `pred W[Hand: Event]` shows some event firing, not Hand.
        if e and not re.search(rf"\b(?:{e}|Now|event)\b", d[0]):
            shown.setdefault(e, []).append((name, verdicts.get(name)))
    return events, [(e, named[e], shown.get(e, [])) for e in sorted(named)]


# ------------------------------------------------------------- the trace digest

# Relations worth showing, in the order a reader wants them.
VARYING = [
    # the observers: the event and its arguments, one per layer that adds one
    ("Now<:event", "ev"),
    ("Who<:session", "by"),
    ("Now<:issue", "arg"),
    ("Target<:agent", "agentArg"),
    ("Where<:machine", "on"),
    ("Where<:repo", "repoArg"),
    # sdlc: the observer's two arguments, then what a commit moves
    ("Now<:artifact", "artifact"),
    ("Now<:subject", "change"),
    ("Written", "written"),
    ("Landed", "landed"),
    # github
    ("Open", "open"),
    ("Merged", "merged"),
    ("Issue<:pullRequest", "pr"),
    ("Filed", "filed"),
    ("Campaign<:memberIssues", "members"),
    ("Campaign<:subIssues", "sub"),
    ("Campaign<:reposInBody", "body"),
    ("Claimed", "claimed"),
    # directory
    ("OnDisk", "dirs"),
    ("CampaignDir<:checkedOut", "co"),
    # synchronization
    ("BaseBehind", "behind"),
    ("BaseUnpushed", "unpushed"),
    ("CloneBehind", "cloneBehind"),
    # session
    ("Session<:worksOn", "holds"),
    ("Surveyed", "surveyed"),
    ("Session<:surveyResult", "saw"),
    ("Session<:reposInReadme", "readme"),
    ("Session<:reposInBodyAsRead", "seen"),
    ("Session<:claimedIssues", "claims"),
    # orchestration
    ("Launched", "launched"),
    ("Live", "live"),
    ("LocalOnly", "local"),
    ("PushedToRemote", "visible"),
    ("Reported", "reported"),
    ("Asked", "asked"),
    ("Answered", "answered"),
    ("Waiting", "waiting"),
    ("Confirmed", "confirmed"),
    ("StandDownTaken", "stoodDown"),
    ("Retired", "retired"),
    ("Stopped", "stopped"),
]
STATIC = ["Issue<:repo", "Campaign<:campaignIssue", "Request<:covers",
          "CampaignDir<:campaign", "CampaignDir<:machine", "Session<:machine",
          "Agent<:role", "Agent<:task", "Agent<:host", "Agent<:launcher",
          "Agent<:branch",
          # sdlc: which change an artifact is of and at which stage, what
          # it witnesses and drives, what the change's kind lets it skip,
          # and which spec artifacts grew a shape
          "Artifact<:change", "Artifact<:stage", "Artifact<:witnesses",
          "Artifact<:drives", "Change<:optional", "GrowsShape"]

WANTED = {key for key, _ in VARYING} | set(STATIC)

# `Now->OpenPR` and `Target->A0`: the observer atom adds nothing to a cell whose
# column already names it.
OBSERVER = re.compile(r"\b(?:Now|Where|Who|Target)->")

ATOM = re.compile(r"(\w+)\$(\d+)")
# `system/system/system/system/Issue$0` -> `Issue$0`: a layered model qualifies
# every name by the module path that declared it, and no reader wants that in
# every cell.
QUALIFIER = re.compile(r"[A-Za-z_]\w*(?:/[A-Za-z_]\w*)*/")

# Two letters for the sdlc signatures, so `Ch0` is never read as a Campaign
# and `Ar0` never as an Agent; the two entities open nothing of each other,
# but a reader of both should not have to know that. A stage or an event is
# a `one sig` and keeps its name.
LETTER = {"Issue": "I", "PullRequest": "P", "Campaign": "C", "Machine": "M",
          "Repo": "R", "Agent": "A", "Session": "S", "Branch": "B",
          "CampaignDir": "D",
          "Change": "Ch", "Artifact": "Ar"}


def unqualify(text):
    return QUALIFIER.sub("", text)


def short(text):
    """Issue$0 -> I0, Campaign$0 -> C0, Machine$1 -> M1, OpenPR$0 -> OpenPR."""
    def rep(m):
        name, idx = m.group(1), m.group(2)
        if name in LETTER:
            return LETTER[name] + idx
        if name == "Base":
            return "Base"
        return name
    return ATOM.sub(rep, unqualify(text))


def parse_trace(path):
    states = []
    cur = None
    for line in open(path):
        line = line.rstrip("\n")
        m = re.match(r"-+State (\d+)( \(loop\))?-+", line)
        if m:
            cur = {"n": int(m.group(1)), "loop": bool(m.group(2)), "rel": {}}
            states.append(cur)
            continue
        if cur is None or "=" not in line:
            continue
        key, _, val = line.partition("=")
        # The top module qualifies its own names with `this/` and every opened
        # module with its path; both reduce to the bare name, and anything that
        # is not a relation this digest shows is dropped here.
        name = unqualify(key)
        if name in WANTED:
            cur["rel"][name] = val.strip("{}")
    return states


def render(path):
    states = parse_trace(path)
    if not states:
        return f"{path}: no trace\n"
    out = [f"# {path.split('/')[-1]}"]
    fixed = states[0]["rel"]
    facts = [f"{label}={short(fixed[label]) or '-'}" for label in STATIC if fixed.get(label)]
    out.append("static: " + "; ".join(facts))
    for s in states:
        parts = []
        for key, label in VARYING:
            val = s["rel"].get(key, "")
            if not val:
                continue
            parts.append(f"{label}={OBSERVER.sub('', short(val))}")
        tag = f"S{s['n']}" + (" (loop)" if s["loop"] else "")
        out.append(f"{tag:>10}  " + "  ".join(parts))
    return "\n".join(out) + "\n"



# ------------------------------------------------------------------------ main


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "--digest":
        if len(argv) < 2:
            print("alloy-check --digest: name at least one trace file",
                  file=sys.stderr)
            return 1
        for arg in argv[1:]:
            print(render(arg))
        return 0
    if argv[0] == "--commands":
        rest = [a for a in argv[1:] if a != "--write"]
        if len(rest) != 1:
            print("alloy-check --commands: name exactly one directory",
                  file=sys.stderr)
            return 1
        return commands_mode(rest[0], "--write" in argv[1:])

    path, outdir = argv[0], None
    if len(argv) >= 3 and argv[1] == "-o":
        outdir = argv[2]
    if outdir is None:
        outdir = tempfile.mkdtemp(prefix="alloy-" + os.path.basename(path)[:-4] + "-")

    status, ran, verdicts = run_alloy(path, outdir)
    model = os.path.abspath(path)
    print(f"model     {model}")
    print(f"traces    {outdir}")
    if ran is None:
        print("commands  NONE READ  alloy printed no command result, so nothing "
              "about this model was checked")
        print(f"RESULT    could not look: alloy printed no command result "
              f"(alloy exit {status})")
        return 2
    print(f"commands  {ran} ran; each one's verdict was checked by its own "
          f"`expect` clause")
    try:
        events, rows = reach(model, verdicts)
    except (OSError, LookupError) as e:
        print(f"RESULT    could not look: the checks' events and their witnesses "
              f"were not read ({e}) (alloy exit {status})")
        return 2
    print(f"events    {len(events)} declared ({', '.join(events)}); "
          + (f"the checks here name {len(rows)}: {', '.join(r[0] for r in rows)}"
             if rows else "no check here names one"))
    dead, unread = [], []
    for event, checks, witnesses in rows:
        by = f"named by {', '.join(checks)}"
        sat = [w for w, v in witnesses if v == "SAT"]
        if sat:
            print(f"witness   {event:<16} {sat[0]:<28} SAT    {by}")
        elif not witnesses:
            dead.append(event)
            print(f"MISSING   {event:<16} no `run` of `eventually (Now.event = "
                  f"{event} ...)`  {by}  in {model}")
        elif all(v == "UNSAT" for _, v in witnesses):
            dead.append(event)
            print(f"DEAD      {event:<16} {', '.join(w for w, _ in witnesses):<28} "
                  f"UNSAT  {by}  in {model}")
        else:
            unread.append(event)
            print(f"UNREAD    {event:<16} {', '.join(w for w, _ in witnesses):<28} "
                  f"alloy printed no verdict for it  {by}")
    if dead:
        print(f"RESULT    alloy exit {status}; {len(dead)} event(s) a check names "
              f"cannot be shown to fire: {', '.join(dead)}")
        return 1
    if status == 0 and unread:
        print(f"RESULT    could not look: no verdict for the witness of "
              f"{', '.join(unread)} (alloy exit {status})")
        return 2
    print(f"RESULT    alloy exit {status}")
    return 0 if status == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
