#!/usr/bin/env python3
"""Extract the calls this machine's sessions really made into a replay corpus.

    scripts/guard-corpus.py [--days N] [--base PATH] [--out PATH]
                            [--transcripts GLOB] [--max-bytes N] [--all]

WHY A CORPUS AND NOT MORE CASES. Every false positive `check-campaign-claim.py`
has had was found by whoever it hit, after the fact: `install-hooks.sh` read as
the verb `install` (#170), any git repository read as a base (#184 round 1), a
heredoc body read as a command (#193), `--body-file /tmp/123` read as issue
#123 (#184 round 3). Each was a shape somebody had been typing for days. The
suite's hand-written cases are the shapes the author thought of; this file is
the shapes the campaign actually used, and a refusal against any of them fails
the suite (kalaluthien/campaign-base#196 step 4).

WHAT IS EXTRACTED, AND THE FOUR FILTERS. Assistant `tool_use` blocks in the
Claude transcripts under `~/.claude/projects/`, for `Bash` and the file tools.

  1. WINDOW. Transcript files modified within `--days` (default 5).
  2. PLACE. The transcript entry's own `cwd` is the base root or under it, so
     the corpus is this campaign's ordinary work and not every session on the
     machine. A session outside every base is one the guard allows unread.
  3. VERDICT. A call whose `tool_result` carries a `PreToolUse:<tool> hook
     error` naming this guard was REFUSED at the time and is not an allow. It
     is dropped and counted, never silently.
  4. READ FOR A TARGET. A Bash command in which the guard's own `segments`
     and `gh_token` find no `gh` is one it allows unread, so its verdict
     cannot change without the allow-unread branch itself changing, and its
     text is 2.3 MB of shell that no reviewer can read. `--all` keeps them.
     A command the guard cannot SPLIT is kept whatever it holds: it was
     allowed when it ran, so a guard refusing it now is a regression, and
     dropping it let the corpus miss the one defect it was built to catch.
     THE COST, STATED: the split branch runs on every command, and what this
     filter drops is the commands it splits SUCCESSFULLY and reads no `gh` in.
     So the corpus catches a splitter regression (those are kept, above) and a
     new refusal over a `gh` call, and it cannot catch a change to the
     allow-unread branch itself. #193's named cases are that branch's cover.

A call that a session made and the guard allowed is the corpus's subject, and
a session under the base root during this campaign was a session holding a
claim -- the guard would have refused it otherwise, which is filter 3.

WHY A FILE PATH IS STORED AS A KIND AND A TAIL. A recorded path names this
machine's directories, which no fixture has. Each is stored as the kind of
place it sat in -- `base`, `worktree`, `member`, `campaign` -- plus its tail
below that place, so the replay rebuilds it inside a fixture of the same shape.
A path under no base is dropped: the guard allows it unread and there is
nothing to protect.

A Bash command is stored VERBATIM, because the guard reads the command text and
nothing else about it: its cwd reading is the session's, which the replay
supplies. `--max-bytes` (default 16384) drops the handful of very long document
writes; the count is printed.

SECRETS. An entry matching `SECRET` is dropped and counted. The corpus is
committed, so this is a refusal and not a redaction: a redacted command is no
longer a real spelling, and a corpus of not-quite-real spellings is the thing
this exists to replace.

OUTPUT is JSONL on `--out` (default `scripts/fixtures/guard-allow-corpus.jsonl`),
one object per DISTINCT call, with `seen` counting how many times it appeared
and `first` its earliest timestamp -- so a re-run over a later window is a
diff and not a rewrite. A summary goes to stderr.
"""
import argparse
import glob
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "fixtures" / "guard-allow-corpus.jsonl"
DEFAULT_TRANSCRIPTS = "~/.claude/projects/**/*.jsonl"
FILE_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
PATH_KEYS = ("file_path", "notebook_path", "path")
def _name_rule():
    """`campaign-name-session.py`, imported for `BASE_DIRS` alone."""
    src = HERE.parent / ".claude" / "skills" / "assuming-role" / "scripts" / "campaign-name-session.py"
    spec = importlib.util.spec_from_loader(
        "cns", importlib.machinery.SourceFileLoader("cns", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# The base's own top-level directories, imported from the one file that names
# them: `campaign-name-session.py` bars the same words from a slug, so no
# campaign can be named for a directory the base already owns and this exclusion
# cannot swallow a real campaign's tree. Two copies pointing at each other in
# prose is the shape that drifts.
#
# A dot-directory is the base's own by the clause in `place` and is not listed
# there: `.claude` and `.github` in this set pinned nothing.
#
# NOT `.gitignore`'s allowlist, which this resembles and is not: that admits
# what is TRACKED, and `runtime/` is the base's own and ignored.
BASE_OWN = frozenset(_name_rule().BASE_DIRS)
# A token that must never be committed. Deliberately crude and deliberately
# wide: a dropped entry costs one shape, a committed token costs an account.
SECRET = re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9-]{16,}"
                    r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}")
REFUSAL = re.compile(r"PreToolUse:\w+ hook error.*check-campaign-claim", re.S)


def guard():
    """The guard module, imported rather than re-implemented. Filter 4 asks
    the guard's own question -- does this command carry a `gh` it reads -- so
    a change to how it finds one moves the corpus with it instead of leaving
    a second, drifting answer here (AGENTS.md: no second reader of a rule a
    script owns)."""
    src = HERE / "check-campaign-claim.py"
    spec = importlib.util.spec_from_loader(
        "ccc", importlib.machinery.SourceFileLoader("ccc", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def reads_for_a_target(g, command):
    """Whether the guard reads this Bash command for a target at all.

    A COMMAND THE GUARD CANNOT SPLIT IS KEPT, and the first cut of this dropped
    it as "not an allow". That was the filter reading the CURRENT guard's
    verdict to decide what the corpus may witness, which is circular: the
    entries were recorded as ALLOWED when they ran, so one the guard now
    refuses is a splitter regression -- exactly what a replay corpus is for.
    Four such commands existed at 1a3138e, all from one defect this filter had
    hidden from the very sweep meant to catch it (found by review, not by the
    corpus). Filter 3 is what keeps a genuine refusal out; this one only asks
    whether the guard READS the command at all."""
    segs, _why = g.segments(command)
    if segs is None:
        return True
    return any(g.head(s)[0] == "gh" or any(g.gh_token(t) for t in s)
               for s in segs)


def place(path: Path, base: Path):
    """(kind, tail) for a recorded absolute path, or None when it is under no
    base. The kinds are the four the guard reads apart, in the order that
    decides: a checkout under a campaign directory is code, the rest of that
    directory is campaign-plane scratch, and the base is neither."""
    try:
        rel = path.relative_to(base)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2 or parts[0] in BASE_OWN or parts[0].startswith("."):
        return "base", str(rel)
    rest = parts[1:]
    if len(rest) >= 2 and rest[0] == "worktrees":
        return "worktree", str(Path(*rest[2:])) if rest[2:] else "a.txt"
    if len(rest) >= 2 and rest[0] == "repos":
        return "member", str(Path(*rest[2:])) if rest[2:] else "a.txt"
    return "campaign", str(Path(*rest)) if rest else "a.txt"


def refused_ids(entry):
    """The tool_use ids this transcript entry reports the guard refused."""
    msg = entry.get("message") or {}
    out = []
    for b in msg.get("content") or []:
        if not isinstance(b, dict) or b.get("type") != "tool_result":
            continue
        text = b.get("content")
        if not isinstance(text, str):
            text = json.dumps(text)
        if REFUSAL.search(text):
            out.append(b.get("tool_use_id"))
    return [x for x in out if x]


def scan(files, base: Path, max_bytes: int, keep_all: bool):
    """(entries, counts). One pass per file, collecting calls and refusals
    together: the refusal arrives in a LATER entry than the call it names, so
    the drop is applied after the file is read and not while reading it."""
    g = None if keep_all else guard()
    calls, refused, counts = {}, set(), {
        "files": 0, "tool_use": 0, "outside": 0, "refused": 0,
        "too_long": 0, "secret": 0, "no_path": 0, "unread": 0,
    }
    for f in files:
        counts["files"] += 1
        with open(f, errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                kind = d.get("type")
                if kind == "user":
                    refused.update(refused_ids(d))
                    continue
                if kind != "assistant":
                    continue
                cwd = d.get("cwd") or ""
                inside = cwd == str(base) or cwd.startswith(str(base) + os.sep)
                when = d.get("timestamp") or ""
                for b in (d.get("message") or {}).get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    name = b.get("name")
                    if name != "Bash" and name not in FILE_TOOLS:
                        continue
                    counts["tool_use"] += 1
                    if not inside:
                        counts["outside"] += 1
                        continue
                    got = one(name, b.get("input") or {}, base, max_bytes,
                              counts, g)
                    if got is None:
                        continue
                    key = json.dumps(got, sort_keys=True)
                    row = calls.setdefault(key, dict(got, seen=0, first=when,
                                                     ids=[]))
                    row["seen"] += 1
                    row["ids"].append(b.get("id"))
                    if when and when < row["first"]:
                        row["first"] = when
    out = []
    for row in calls.values():
        ids = row.pop("ids")
        if any(i in refused for i in ids):
            counts["refused"] += 1
            continue
        out.append(row)
    out.sort(key=lambda r: (r["tool"], r.get("kind", ""),
                            r.get("path", ""), r.get("command", "")))
    return out, counts


def one(name, inp, base, max_bytes, counts, g):
    """One corpus row for one tool_use block, or None with a count bumped."""
    if name == "Bash":
        cmd = inp.get("command") or ""
        if not cmd:
            return None
        if len(cmd.encode()) > max_bytes:
            counts["too_long"] += 1
            return None
        if SECRET.search(cmd):
            counts["secret"] += 1
            return None
        if g is not None and not reads_for_a_target(g, cmd):
            counts["unread"] += 1
            return None
        return {"tool": "Bash", "command": cmd}
    raw = next((inp.get(k) for k in PATH_KEYS if inp.get(k)), None)
    if not raw:
        counts["no_path"] += 1
        return None
    if SECRET.search(str(raw)):
        counts["secret"] += 1
        return None
    where = place(Path(str(raw)), base)
    if where is None:
        counts["outside"] += 1
        return None
    kind, tail = where
    return {"tool": name, "kind": kind, "path": tail}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=float, default=5.0)
    p.add_argument("--base", default=str(Path.home() / "campaign-base"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--transcripts", default=DEFAULT_TRANSCRIPTS)
    p.add_argument("--max-bytes", type=int, default=16384)
    p.add_argument("--all", action="store_true",
                   help="keep the commands the guard allows unread too")
    args = p.parse_args(argv)

    base = Path(os.path.expanduser(args.base)).resolve()
    pattern = os.path.expanduser(args.transcripts)
    cutoff = time.time() - args.days * 86400
    files = sorted(f for f in glob.glob(pattern, recursive=True)
                   if os.path.getmtime(f) >= cutoff)
    if not files:
        # LOOKED AND FOUND NOTHING is a result; COULD NOT LOOK is not. A glob
        # that matches no file means the transcripts moved, and writing an
        # empty corpus over a real one would retire the whole replay silently.
        sys.exit(f"guard-corpus: no transcript matched {pattern} within "
                 f"{args.days} days; refusing to write an empty corpus")

    rows, counts = scan(files, base, args.max_bytes, args.all)
    out = Path(os.path.expanduser(args.out))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"guard-corpus: {len(rows)} distinct calls from {counts['files']} "
          f"transcripts under {base}, window {args.days}d -> {out}",
          file=sys.stderr)
    print(f"  read {counts['tool_use']} tool calls; dropped "
          f"{counts['outside']} outside the base, {counts['refused']} the "
          f"guard refused at the time, {counts['too_long']} over "
          f"{args.max_bytes} bytes, {counts['secret']} matching a secret "
          f"pattern, {counts['no_path']} naming no path, {counts['unread']} "
          f"the guard allows unread", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
