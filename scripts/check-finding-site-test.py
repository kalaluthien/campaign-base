#!/usr/bin/env python3
# witnesses: JV1_ARepliedConfidentFittingJudgmentAdvises, JV1b_AFailedLowOrNoMatchAnswerNeverAdvises
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
REPO = ROOT / "repo"
(REPO / "sub").mkdir(parents=True)
git(REPO, "init", "-q")
(REPO / "a.py").write_text("".join(f"line{i} = {i}\n" for i in range(1, 101)))
(REPO / "sub" / "b.py").write_text("x = 1\ny = 2\n")
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "reviewed")
REVIEWED = git(REPO, "rev-parse", "HEAD")
(REPO / "a.py").write_text((REPO / "a.py").read_text().replace("line50 = 50", "line50 = 'fixed'"))
git(REPO, "commit", "-q", "-am", "fix")
WANT_A = "\n".join(f"{i}: line{i} = {i}" for i in range(10, 91))

REVIEW = (f"REVIEW demo-worker-1: at {REVIEWED[:7]}, four findings\n\n"
          "1. defect, `a.py:50` -- the loop stops one line short of the end\n"
          "2. refinement -- `b.py:2` names y where the docstring says z\n"
          "3. refinement -- the docstring names a flag the code no longer has\n"
          "4. defect -- `a.py:400` the parser drops the last line it reads\n")

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
    return (r.returncode == 0 and r.stdout == "" and len(SEEN) == 2
            and a == WANT_A), (sorted(got), (a or "")[:200], r.stderr[-300:])


def resolves_by_suffix(t):
    run(t)
    b = [s["state"]["slice"] for s in SEEN if "b.py:2" in s["state"]["finding"]]
    # `git show` ends in a newline, so the last numbered line is empty, as measured.
    return b == ["1: x = 1\n2: y = 2\n3: "], b


def labels_the_site(t):
    run(t, argv=("468", "o/r"))
    got = sorted(x["read"] for x in LOGGED if "skipped" not in x)
    return got == ["o/r#468 REVIEW f1 a.py:50", "o/r#468 REVIEW f2 sub/b.py:2"], got


def skips_what_it_cannot_place(t):
    run(t)
    got = sorted((x["read"], x["skipped"]) for x in LOGGED if "skipped" in x)
    return got == [("tracker#468 REVIEW f3", "the finding names no path:line"),
                   ("tracker#468 REVIEW f4", f"a.py has no line 400 at {REVIEWED[:12]}")], got


def unknown_sha_skips_once(t):
    r = run(t, cwd=ROOT)
    return (r.returncode == 0 and not SEEN and [(x["read"], x.get("skipped")) for x in LOGGED]
            == [("tracker#468 REVIEW", "the first line names no sha this checkout holds")]), LOGGED


def other_comment_asks_nothing(t):
    r = run(t, review=REVIEW.replace("REVIEW ", "REPORT ", 1))
    return r.returncode == 0 and not SEEN and not LOGGED, (len(SEEN), LOGGED)


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"]["c"] if SEEN else {}
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
    "each call is labelled with the finding's number and its resolved site": labels_the_site,
    "a finding naming no path:line, or a line past the end, logs one skip row each": skips_what_it_cannot_place,
    "a sha the checkout does not hold asks nothing and logs one skip row": unknown_sha_skips_once,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "a reading that raised exits 0, says nothing and logs a skip": failure_logs_skip,
}

MUTATIONS = [
    ("the file read at HEAD", 'git("show", f"{sha}:{path}")', 'git("show", f"HEAD:{path}")',
     "each finding with a site is asked against the file at the reviewed sha, 40 lines each side"),
    ("no suffix match", 'hits = [p for p in paths if p.endswith("/" + name)]', "hits = []",
     "a path written without its directory resolves to the one file ending in it"),
    ("the site left out of the label", 'asks.append((f"{subject} f{n} {site[0]}:{site[1]}",',
     'asks.append((f"{subject} f{n}",',
     "each call is labelled with the finding's number and its resolved site"),
    ("a finding with no site not logged", "            jev.skip(READER, f\"{subject} f{n}\", got, env)",
     "            pass", "a finding naming no path:line, or a line past the end, logs one skip row each"),
    ("an unknown sha read on", "        if not sha:\n", "        if False:\n",
     "a sha the checkout does not hold asks nothing and logs one skip row"),
    ("the comment kind not read", 'if not review.lstrip().startswith("REVIEW "):', "if False:",
     "a comment of another kind asks nothing"),
    ("the criteria not sent", 'if k in ("type", "criteria")}', 'if k in ("type",)}',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the skip not logged", 'READER, subject, f"the reading raised {e.__class__.__name__}", env)',
     'READER, subject, "x", {"CAMPAIGN_JEV_LOG": "/nonexistent/x/y"})',
     "a reading that raised exits 0, says nothing and logs a skip"),
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording."""
    m = load(SOURCE).m
    jev = m.load_sibling("campaign-jev.py")
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    t = ENTRY["thresholds"]
    wording = hashlib.sha256(json.dumps(ENTRY["question"], sort_keys=True)
                             .encode()).hexdigest()[:12]
    today = datetime.date.today().isoformat()
    misses = 0
    for row in rows:
        reading = jev.ask(m.READER, row["id"], row["state"], m.questions(ENTRY))
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
