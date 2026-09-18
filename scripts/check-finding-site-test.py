#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-finding-site.py asks each finding of a REVIEW against its site at the reviewed sha, skips what it cannot place, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question with one P(contradicts), and the reader runs in a fixture git
repository, from a directory holding it, the real check-finding-sort.py and
scripts/campaign-jev.py, and this reading's registry entry. Each case is then
broken by a mutation of the reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/finding-site.jsonl against the
real endpoint and fails a case whose word differs from the last one `seen`
under the same question wording; `--record` appends the reading to `seen`.

Usage: scripts/check-finding-site-test.py [--live [--record]]
"""
import datetime
import hashlib
import http.server
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-finding-site.py"
SOURCE = SCRIPT.read_text()
ENTRIES = json.loads((HERE / "jev" / "readings.json").read_text())
ENTRY = ENTRIES["finding-site"]
CORPUS = HERE / "jev" / "corpus" / "finding-site.jsonl"
ROOT = Path(tempfile.mkdtemp(prefix="finding-site-"))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


# THE REPOSITORY: `a.py` is 100 numbered lines at REVIEWED and has line 50
# rewritten after it, so a slice read at HEAD differs from one read at the sha.
# `c/dup.py` is on `origin/main` and `d/dup.py` came after it, so `dup.py` names
# two files and only the second is one the reviewed branch changed.
REPO = ROOT / "repo"
for sub in ("sub", "c", "d"):
    (REPO / sub).mkdir(parents=True)
git(REPO, "init", "-q")
(REPO / "a.py").write_text("".join(f"line{i} = {i}\n" for i in range(1, 101)))
(REPO / "sub" / "b.py").write_text("x = 1\ny = 2\n")
(REPO / "c" / "dup.py").write_text("main = 1\n")
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "main")
git(REPO, "update-ref", "refs/remotes/origin/main", "HEAD")
OLDER = git(REPO, "rev-parse", "HEAD")
(REPO / "d" / "dup.py").write_text("branch = 1\n")
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "reviewed")
REVIEWED = git(REPO, "rev-parse", "HEAD")
(REPO / "a.py").write_text((REPO / "a.py").read_text().replace("line50 = 50", "line50 = 'fixed'"))
git(REPO, "commit", "-q", "-am", "fix")
WANT_A = "\n".join(f"{i}: line{i} = {i}" for i in range(10, 91))

# The first line names an older sha the checkout also holds before the head,
# as a narrowed round does.
REVIEW = (f"REVIEW demo-worker-1: narrowed to {OLDER[:7]}..{REVIEWED[:7]}, at {REVIEWED[:7]}\n\n"
          "1. defect, `a.py:50` -- the loop stops one line short of the end\n"
          "2. refinement -- `b.py:2` names y where the docstring says z\n"
          "3. refinement -- the docstring names a flag the code no longer has\n"
          "4. defect -- `a.py:400` the parser drops the last line it reads\n"
          "5. defect -- `b.py:3` reads past the end\n"
          "6. refinement -- `dup.py:1` names branch where it means trunk\n"
          "7. defect -- `e.py:1` imports nothing\n")

# ANOTHER CHECKOUT: a git repository that holds no sha the REVIEW names.
OTHER = ROOT / "other"
OTHER.mkdir()
git(OTHER, "init", "-q")
git(OTHER, "commit", "-q", "--allow-empty", "-m", "other")

NEXT = {"p": 0.9}
SEEN = []
LOGGED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        p = NEXT["p"]
        answers = {q: {"type": "choice", "choice": "supports", "confidence": 0.5,
                       "probabilities": {"contradicts": p, "supports": 1 - p,
                                         "says_nothing": 0.0}}
                   for q in body["questions"]}
        data = json.dumps({"model": "jev-1.13.0", "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVER.server_address[1]}/v1/systemone"


def load(source):
    m = types.ModuleType("findingsite")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def run(t, review=REVIEW, argv=("468",), registry=True, cwd=REPO):
    """The finished process; `SEEN` holds the states asked, `LOGGED` the log."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "check-finding-site.py").write_text(t.source)
    shutil.copy(HERE / "check-finding-sort.py", d / "check-finding-sort.py")
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    shutil.copy(HERE / "check-merge-review.py", d / "check-merge-review.py")
    if registry:
        (d / "jev" / "readings.json").write_text(json.dumps({"finding-site": ENTRY}))
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d))
    r = subprocess.run([sys.executable, str(d / "check-finding-site.py"), *argv],
                       input=review, capture_output=True, text=True, env=env, cwd=cwd)
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    return r


def asks_at_the_reviewed_sha(t):
    r = run(t)
    got = {b["state"]["finding"]: b["state"]["slice"] for b in SEEN}
    a = got.get("[label], `a.py:50` -- the loop stops one line short of the end")
    return (r.returncode == 0 and r.stdout == "" and len(SEEN) == 3
            and a == WANT_A), (sorted(got), (a or "")[:200], r.stderr[-300:])


def resolves_by_suffix(t):
    run(t)
    b = [s["state"]["slice"] for s in SEEN if "b.py:2" in s["state"]["finding"]]
    return b == ["1: x = 1\n2: y = 2"], b


def narrows_by_changed_files(t):
    run(t)
    d = [s["state"]["slice"] for s in SEEN if "dup.py:1" in s["state"]["finding"]]
    return d == ["1: branch = 1"], d


def labels_the_site(t):
    run(t, argv=("468", "o/r"))
    got = sorted(x["read"] for x in LOGGED if "skipped" not in x)
    return got == ["o/r#468 REVIEW f1 a.py:50", "o/r#468 REVIEW f2 sub/b.py:2",
                   "o/r#468 REVIEW f6 d/dup.py:1"], got


def skips_what_it_cannot_place(t):
    run(t)
    got = sorted((x["read"], x["skipped"]) for x in LOGGED if "skipped" in x)
    return got == [("tracker#468 REVIEW f3", "the finding names no path:line"),
                   ("tracker#468 REVIEW f4", f"a.py has no line 400 at {REVIEWED[:12]}"),
                   ("tracker#468 REVIEW f5", f"sub/b.py has no line 3 at {REVIEWED[:12]}"),
                   ("tracker#468 REVIEW f7", f"e.py is no one file at {REVIEWED[:12]}")], got


def unknown_sha_skips_each(t):
    r = run(t, cwd=OTHER)
    why = "the first line names no sha this checkout holds"
    return (r.returncode == 0 and not SEEN and [(x["read"], x.get("skipped")) for x in LOGGED]
            == [(f"tracker#468 REVIEW f{n}", why) for n in range(1, 8)]), LOGGED


def reads_the_last_sha_named(t):
    run(t)
    a = [s["state"]["slice"] for s in SEEN if "dup.py:1" in s["state"]["finding"]]
    return a == ["1: branch = 1"], a


def other_comment_asks_nothing(t):
    r = run(t, review=REVIEW.replace("REVIEW ", "REPORT ", 1))
    return r.returncode == 0 and not SEEN and not LOGGED, (len(SEEN), LOGGED)


def row_carries_its_join_key(t):
    """WHAT THE MOVE FROM `ask` TO `judge` BOUGHT: the row names the reading
    and its wording and carries the key as FIELDS -- the repository, the pull
    request and which finding it was -- so the thread's next REVIEW can be
    joined to the answer. A call given no repository carries neither number."""
    run(t, argv=("468", "o/r"))
    keyed = [x for x in LOGGED if x.get("reading")]
    run(t)
    bare = [x for x in LOGGED if x.get("reading")]
    return (bool(keyed) and all(x.get("repo") == "o/r" for x in keyed)
            and all(x.get("pull_request") == 468 for x in keyed)
            and all(x.get("finding") for x in keyed)
            and all(len(x.get("wording") or "") == 12 for x in keyed)
            and all("repo" not in x for x in bare)), (keyed, bare)


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"]["finding-site"] if SEEN else {}
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions") == ENTRY["question"]["instructions"]
            and "yes_over" not in q), q


def failure_logs_skip(t):
    r = run(t, registry=False)
    return (r.returncode == 0 and not SEEN and r.stdout == "" and r.stderr == ""
            and [x.get("skipped") for x in LOGGED]
            == ["the reading raised FileNotFoundError"]), (r.stderr[-300:], LOGGED)


CASES = {
    "each finding with a site is asked against the file at the reviewed sha, 40 lines each side": asks_at_the_reviewed_sha,
    "a path written without its directory resolves to the one file ending in it": resolves_by_suffix,
    "a name several files end in resolves to the one the branch changed": narrows_by_changed_files,
    "the slice is read at the last sha the first line names": reads_the_last_sha_named,
    "each call is labelled with the finding's number and its resolved site": labels_the_site,
    "a finding naming no path:line, a line past the end or no one file logs one skip row each": skips_what_it_cannot_place,
    "a sha the checkout does not hold asks nothing and logs one skip row a finding": unknown_sha_skips_each,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the row carries the reading, the wording and the join key": row_carries_its_join_key,
    "a reading that raised exits 0, says nothing and logs a skip": failure_logs_skip,
}

MUTATIONS = [
    ("the file read at HEAD", 'git("show", f"{sha}:{path}")', 'git("show", f"HEAD:{path}")',
     "each finding with a site is asked against the file at the reviewed sha, 40 lines each side"),
    ("the trailing newline counted as a line",
     'lines = text.removesuffix("\\n").split("\\n") if text else []', 'lines = text.split("\\n")',
     "a finding naming no path:line, a line past the end or no one file logs one skip row each"),
    ("several suffix hits not narrowed", "hits = [p for p in hits if p in changed]", "pass",
     "a name several files end in resolves to the one the branch changed"),
    ("the first sha named read", "for named in reversed(", "for named in (",
     "the slice is read at the last sha the first line names"),
    ("no suffix match", 'hits = [p for p in paths if p.endswith("/" + name)]', "hits = []",
     "a path written without its directory resolves to the one file ending in it"),
    ("the site left out of the label",
     '"read": f"{inp.subject} f{n} {site[0]}:{site[1]}",',
     '"read": f"{inp.subject} f{n}",',
     "each call is labelled with the finding's number and its resolved site"),
    ("a finding with no site not logged", "            yield jev.Skip(f\"{inp.subject} f{n}\", got)",
     "            pass", "a finding naming no path:line, a line past the end or no one file logs one skip row each"),
    ("an unknown sha read on", "    if not sha:\n", "    if False:\n",
     "a sha the checkout does not hold asks nothing and logs one skip row a finding"),
    ("one skip for the whole REVIEW", "        for n in range(1, len(cut) + 1):\n",
     "        for n in range(1, 2):\n",
     "a sha the checkout does not hold asks nothing and logs one skip row a finding"),
    ("the reading's group not read from the entry",
     'group = reg[READING]["group"]',
     'group = "issue-shape"',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the row keyed by a number with no repository",
     'key = {"repo": inp.repo, "pull_request": int(inp.number)} if inp.repo else {}',
     'key = {"pull_request": int(inp.number)}',
     "the row carries the reading, the wording and the join key"),
    ("the finding never numbered on the row",
     '"key": dict(key, finding=n)}', '"key": key}',
     "the row carries the reading, the wording and the join key"),
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording."""
    m = load(SOURCE).m
    jev = importlib.import_module("campaign-jev")
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    t = ENTRY["thresholds"]
    wording = hashlib.sha256(json.dumps(ENTRY["question"], sort_keys=True)
                             .encode()).hexdigest()[:12]
    today = datetime.date.today().isoformat()
    misses = 0
    for row in rows:
        reading = jev.ask(m.READER, row["id"], row["state"],
                          {"c": jev.question_of(ENTRY)})
        a = reading.answers["c"]
        p = ((a.raw or {}).get("probabilities") or {}).get(t["option"])
        raw = None if p is None else round(p, 2)
        word = ("unknown" if raw is None else "yes" if raw >= t["yes_over"]
                else "no" if raw <= t["no_under"] else "unknown")
        print(f"{row['id']}  {row['role']:<5} truth {row['truth']:<3} "
              f"{'-' if raw is None else f'{raw:.2f}'} {word}  {row['source']['ref']}")
        misses += word != row["truth"]
        before = [x for x in row["seen"] if x.get("wording") == wording]
        if before:
            check(f"live {row['id']} reads {before[-1]['word']} as last recorded",
                  word == before[-1]["word"], f"{word} at {raw}")
        row["seen"].append({"model": reading.model, "wording": wording,
                            "raw": raw, "word": word, "at": today})
    print(f"finding-site: {misses} of {len(rows)} case(s) off their truth")
    if record:
        CORPUS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                  for r in rows))
        print(f"recorded into {CORPUS}")


def main(argv):
    try:
        if "--live" in argv:
            live("--record" in argv)
            return harness.report()
        harness.mutate(SOURCE, load, CASES, MUTATIONS)
        return harness.report()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
