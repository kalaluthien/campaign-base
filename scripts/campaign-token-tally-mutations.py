#!/usr/bin/env python3
"""Break one branch of campaign-token-tally's method at a time; require a named case to fail.

A tally returns a plausible number however wrong it is, so a green suite over
one proves less than a green suite usually does. This is the evidence behind the
claim that suite makes: each mutation below removes exactly one branch of the
method -- an attribution rule, the fold, a filter, the call parser -- and a
*named* case must go red for it. A mutation that survives is a branch nothing
pins, whatever the case count says; three did survive here and each was a real
gap in the fixture rather than in the assertions.

It edits `campaign-token-tally.py` in place and restores it after every run,
including on the way out, so run it on a clean tree and run the suite after.

0 when every mutation was caught. 1 with a line per mutation that survived, or
that could not be applied at all -- an anchor that no longer matches is not a
pass, it is a mutation that never ran.

Usage: scripts/campaign-token-tally-mutations.py
"""
import pathlib
import subprocess
import sys

S = pathlib.Path(__file__).resolve().parent / "campaign-token-tally.py"
T = S.parent / "campaign-token-tally-test.py"
orig = S.read_text()

MUT = [
    ("fold keeps the placeholder output",
     '    turn["output"] = max(turn["output"], usage["output"])',
     '    turn["output"] = turn["output"]'),
    ("no dedupe: every record is a turn",
     '            pending[mid] = turn',
     '            pending[mid + ts] = turn'),
    ("input summed per record",
     '    turn["body_bytes"] += body_bytes',
     '    turn["input_new"] += usage["input_new"]\n    turn["body_bytes"] += body_bytes'),
    ("off-base filter removed",
     '            if not self.in_base(cwd):\n                self.dropped["off_base"] += 1\n                continue',
     '            if False:\n                pass'),
    ("window filter removed",
     '            if not self.in_window(ts):\n                self.dropped["window"] += 1\n                continue',
     '            if False:\n                pass'),
    ("worktree rule removed",
     '        m = WORKTREE.search(cwd)\n        if m:\n            return int(m.group(1)), "worktree"',
     '        m = None'),
    ("branch rule removed",
     '        m = self.branch.match(branch_field) if self.branch else None\n        if m:\n            return int(m.group(1)), "branch"',
     '        m = None'),
    ("brief rule removed",
     '        if is_sub and brief_issue is not None:\n            return brief_issue, "brief"',
     '        if False:\n            pass'),
    ("brief rule demoted below the place it inherited",
     '        if is_sub and brief_issue is not None:\n            return brief_issue, "brief"\n        m = WORKTREE.search(cwd)\n        if m:\n            return int(m.group(1)), "worktree"',
     '        m = WORKTREE.search(cwd)\n        if m:\n            return int(m.group(1)), "worktree"\n        if is_sub and brief_issue is not None:\n            return brief_issue, "brief"'),
    ("parent rule removed",
     '            parent = self.parent_issue(record.get("sessionId"), ts)\n            if parent is not None:\n                return parent, "parent"',
     '            pass'),
    ("a plain-brief mention anywhere in the brief launches a round",
     r'    r"|\A\s*review PR\s+#?(?P<pr2>\d+)\s+at\s+(?P<level2>\w+)",',
     r'    r"|review PR\s+#?(?P<pr2>\d+)\s+at\s+(?P<level2>\w+)",'),
    ("a capitalized plain brief no longer matches",
     "    re.IGNORECASE)",
     "    0)"),
    ("a review round no longer rolls up its own fan-out",
     '            parent = parent_of.get(cur)',
     '            parent = None'),
    ("a round's file is found only by a turn, not by the directory walk",
     '                    path_of[agent_id] = os.path.join(dirpath, name)',
     '                    pass'),
    ("carry accepts a record already on main",
     '        if carried is not None and not branch_field:',
     '        if carried is not None:'),
    ("per-row settled counts removed",
     '        out["settled"] += 1 if t["settled"] else 0',
     '        out["settled"] += 1'),
    ("the window bound is used unchecked",
     '        args.__dict__[name] = checked_bound(getattr(args, name), name)',
     '        pass'),
    ("the window bound keeps its Z, so a message in the same second sorts before it",
     '    return moment.strftime("%Y-%m-%dT%H:%M:%S")',
     '    return moment.strftime("%Y-%m-%dT%H:%M:%S") + "Z"'),
    # scripts_called, one branch at a time.
    ("a script named anywhere in a segment counts as a call",
     '        m = SCRIPT_NAME.match(word)',
     '        m = next((SCRIPT_NAME.match(w.rsplit("/", 1)[-1]) for w in seg\n                  if SCRIPT_NAME.match(w.rsplit("/", 1)[-1])), None)'),
    ("the shared splitter is replaced by splitting on lines",
     '    segs, _why = grammar.segments(command)\n    if segs is None:\n        return None',
     '    segs = [line.split() for line in command.split("\\n") if line.split()]\n    if False:\n        return None'),
    ("an interpreter's operand is not read, so a loop body is missed",
     '        if word in INTERPRETERS:',
     '        if False:'),
    ("the result is charged to every script the command runs",
     '            if rank == 0:',
     '            if True:'),
    # reads, one branch at a time.
    ("a re-read is any read of the file, whatever context read it first",
     '        key = (r["context"], r["file"])',
     '        key = r["file"]'),
    ("the verdict sums over-threshold and re-read bytes, double counting",
     '    either = sum(r["bytes"] for r in reads if r["reread"] or files[r["file"]]["over"])',
     '    either = over + again'),
    ("lines come from the result even when the file is on disk",
     '        on_disk = disk_lines(path)',
     '        on_disk = None'),
    ("a shell read's path is not resolved against the record's cwd",
     '            "file": os.path.normpath(os.path.join(turn["cwd"], os.path.expanduser(str(path)))),',
     '            "file": os.path.normpath(os.path.expanduser(str(path))),'),
    ("the floors are never counted",
     '            apart[word][0] += 1',
     '            pass'),
    ("sed without -n is a read",
     '        if not quiet:\n            return "none", None',
     '        if False:\n            return "none", None'),
    ("stdout sent to a file is still a read",
     '    if cut < len(args) and args[cut] in (">", ">>", ">|", "&>", "&>>") and fd in (None, "1"):\n        return "none", None',
     '    if False:\n        return "none", None'),
    ("a read word in a later segment is a read",
     '    if words and words[0][0] in SHELL_READS:\n        return read_operand(*words[0])',
     '    for w, rest in words:\n        if w in SHELL_READS:\n            return read_operand(w, rest)'),
    ("a file of exactly --threshold lines is over it",
     '        f["over"] = f["lines"] > args.threshold',
     '        f["over"] = f["lines"] >= args.threshold'),
    ("an empty corpus says build",
     '    verdict = "build" if either >= BUILD_AT * read_bytes and read_bytes else "stop"',
     '    verdict = "build" if either >= BUILD_AT * read_bytes else "stop"'),
    ("a path the shell would expand is taken as a file",
     '    return "read", (None if path and set(path) & set("$`*?[") else path)',
     '    return "read", path'),
    ("a glob is taken as a file",
     'set(path) & set("$`*?[")',
     'set(path) & set("$`")'),
    ("sed -I edits in place, yet is a read",
     'set(t) & set("iI")',
     'set(t) & set("i")'),
    ("sed --in-place=<suffix> edits in place, yet is a read",
     't.startswith("--in-place")',
     't == "--in-place"'),
    ("`>|` is not a redirection",
     'set(t) <= set("<>&|")',
     'set(t) <= set("<>&")'),
    ("`>|` is a redirection, yet not one sending stdout to a file",
     'args[cut] in (">", ">>", ">|", "&>", "&>>")',
     'args[cut] in (">", ">>", "&>", "&>>")'),
]

fails = 0
try:
    for name, old, new in MUT:
        if old not in orig:
            print(f"MUTATION NOT APPLIED  {name}")
            fails += 1
            continue
        S.write_text(orig.replace(old, new, 1))
        out = subprocess.run([sys.executable, str(T)],
                             capture_output=True, text=True)
        S.write_text(orig)
        # A NAMED CASE, never the exit status. A suite that crashes on the
        # mutant -- an attribution rule removed leaves a row absent and a case
        # subscripts None -- exits 1 exactly like a suite whose case went red,
        # and scoring on the status alone reports a branch as pinned by a
        # traceback. One mutation here did exactly that.
        named = [l for l in out.stdout.splitlines() if l.startswith("FAIL")]
        if not named:
            why = ("suite still green" if out.returncode == 0
                   else f"suite exited {out.returncode} with no failing case")
            print(f"SURVIVED ({why})  {name}")
            if out.returncode != 0:
                print("    " + (out.stderr.strip().splitlines() or ["(no stderr)"])[-1])
            fails += 1
        else:
            print(f"caught by {len(named)} case(s)  {name}")
            for l in named[:2]:
                print("    " + l)
finally:
    S.write_text(orig)
print("all mutations caught" if not fails else f"{fails} mutation(s) uncaught")
sys.exit(1 if fails else 0)
