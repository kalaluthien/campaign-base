#!/usr/bin/env python3
"""Run one spec/ module, hold its command list, and digest its traces.

    scripts/alloy-check.py <file.als> [-o <dir>]
    scripts/alloy-check.py --commands <dir> [--write]
    scripts/alloy-check.py --digest <solution-0.txt> [...]

Every command under spec/, whatever entity it belongs to, carries its own verdict, in the `expect`
clause the solver enforces: `expect 0` where the solver says UNSAT -- a check
with no counterexample, a run with no instance -- and `expect 1` where it says
SAT. Alloy exits non-zero and names each command that came out other than its
clause says, so the verdict is checked by the tool that computed it, and this
script neither restates nor re-reads it. There is no verdict table anywhere,
and reintroducing one would be a second reader of what the solver already
decided.

That leaves one hole and two jobs.

RUNNING (the default mode) is `alloy exec -f -t text -c '*'` into <dir>, a
fresh temporary directory unless -o names one, so the traces outlive the run
and `--digest` has something to read. It passes alloy's own output and exit
status through; a run that printed no command result at all -- a parse error, a
missing solver -- is reported as that and never as a pass, because looking and
finding nothing is not the same as being unable to look.

THE HOLE is deletion. `expect` is checked per command, so a command someone
removed misses no expectation: it simply is not there. Nothing generated *from*
the models can see it either -- regenerate an inventory after the deletion and
the command is absent from the claim exactly as it is from the model, so every
property over "the commands that exist" still holds, over a smaller set. Only a
second statement that does NOT regenerate can catch it.

--commands is that statement. It extracts every `check`/`run` declaration from
the .als files under <dir>, RECURSIVELY, and compares them to
<dir>/commands.snapshot.json, naming each command that appeared or went. The
committed one sits at spec/commands.snapshot.json, one snapshot over every
entity, so `--commands spec` is the form CI runs.
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

Exit 0 when the mode's checks pass, 1 when they fail, and 2 when a run produced
no command result to check at all.

`--digest` condenses the traces the run above just wrote. The raw `-t text` dump
repeats every static signature in every state, which buries the handful of
relations a scenario is actually about; the digest prints the event, its
arguments, and the varying relations only, one line per state. The relations
it knows are spec/campaign's; an sdlc trace digests to its events alone. The
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


def commands_mode(directory, write):
    """Compare the models' declarations to the committed snapshot beside them."""
    directory = os.path.abspath(directory)
    snapshot = os.path.join(directory, SNAPSHOT)
    found = inventory(directory)
    # Hand-rolled rather than json.dumps(indent=...), which puts every element
    # of a triple on its own line: one command per line is the whole point, so
    # that a deletion is one removed line naming the command that went.
    head = {
        "generated_by": "scripts/alloy-check.py --commands <dir> --write",
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
        print(f"GONE      {mod:<22} {kind:<6} {name}")
    for mod, kind, name in new:
        print(f"NEW       {mod:<22} {kind:<6} {name}")
    if gone or new:
        print(f"RESULT    {len(gone)} gone, {len(new)} new; if deliberate, "
              f"rerun with --write and commit {SNAPSHOT}")
        return 1
    print(f"RESULT    the snapshot names exactly the {len(found)} declared commands")
    return 0


def run_alloy(path, outdir):
    """(alloy's exit status, how many commands ran -- None if none could be read)."""
    cmd = [ALLOY, "exec", "-f", "-o", outdir, "-t", "text", "-c", "*", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Alloy prints its per-command lines and its expectation errors to stderr,
    # and a run's line carries backspaces from a progress counter (6.2.0).
    output = (proc.stdout + proc.stderr).replace("\b", "")
    sys.stdout.write(output)
    sys.stdout.flush()
    names = {m.group(2) for m in map(RESULT.match, output.splitlines()) if m}
    if not names:
        return proc.returncode, None
    receipt = os.path.join(outdir, "receipt.json")
    if os.path.exists(receipt):
        return proc.returncode, len(json.load(open(receipt))["commands"])
    return proc.returncode, len(names)


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
]
STATIC = ["Issue<:repo", "Campaign<:campaignIssue", "Request<:covers",
          "CampaignDir<:campaign", "CampaignDir<:machine", "Session<:machine",
          "Agent<:role", "Agent<:task", "Agent<:host", "Agent<:launcher",
          "Agent<:branch"]

WANTED = {key for key, _ in VARYING} | set(STATIC)

# `Now->OpenPR` and `Target->A0`: the observer atom adds nothing to a cell whose
# column already names it.
OBSERVER = re.compile(r"\b(?:Now|Where|Who|Target)->")

ATOM = re.compile(r"(\w+)\$(\d+)")
# `system/system/system/system/Issue$0` -> `Issue$0`: a layered model qualifies
# every name by the module path that declared it, and no reader wants that in
# every cell.
QUALIFIER = re.compile(r"[A-Za-z_]\w*(?:/[A-Za-z_]\w*)*/")

LETTER = {"Issue": "I", "PullRequest": "P", "Campaign": "C", "Machine": "M",
          "Repo": "R", "Agent": "A", "Session": "S", "Branch": "B",
          "CampaignDir": "D"}


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

    status, ran = run_alloy(path, outdir)
    print(f"model     {os.path.abspath(path)}")
    print(f"traces    {outdir}")
    if ran is None:
        print("commands  NONE READ  alloy printed no command result, so nothing "
              "about this model was checked")
        print(f"RESULT    could not read the model (alloy exit {status})")
        return 2
    print(f"commands  {ran} ran; each one's verdict was checked by its own "
          f"`expect` clause")
    print(f"RESULT    alloy exit {status}")
    return 0 if status == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
