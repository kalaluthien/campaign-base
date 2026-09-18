#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-finding-sort.py asks one masked state per finding of a REVIEW, labels it with the reviewer's word, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question with one P(defect), and the reader runs from a fixture directory
holding the real scripts/campaign-jev.py and this reading's registry entry. Each case is then
broken by a mutation of the reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/finding-sort.jsonl against the
real endpoint and fails a case whose word differs from the last one `seen`
under the same question wording; `--record` appends the reading to `seen`.

Usage: scripts/check-finding-sort-test.py [--live [--record]]
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
SCRIPT = HERE / "check-finding-sort.py"
SOURCE = SCRIPT.read_text()
ENTRIES = json.loads((HERE / "jev" / "readings.json").read_text())
ENTRY = ENTRIES["finding-sort"]
CORPUS = HERE / "jev" / "corpus" / "finding-sort.jsonl"
ROOT = Path(tempfile.mkdtemp(prefix="finding-sort-"))
REVIEW = ("REVIEW demo-worker-1: at abcdef1, two findings\n\n"
          "1. defect, `a.py:3` -- the parser drops the last line of every file it reads\n"
          "2. refinement, low -- the docstring names a flag the code no longer has\n\n"
          "Refinements:\n"
          "- `b.py:9` the usage line spells the option two different ways\n"
          "- resolved: the earlier wording note is closed in 1234567\n")

NEXT = {"p": 0.9}
SEEN = []
LOGGED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        p = NEXT["p"]
        answers = {q: {"type": "choice", "choice": "supports", "confidence": 0.5,
                       "probabilities": {"defect": p, "refinement": 1 - p,
                                         "unclear": 0.0}}
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
    m = types.ModuleType("findingsort")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def run(t, review=REVIEW, argv=("468",), registry=True):
    """The finished process; `SEEN` holds the states asked, `LOGGED` the log."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "check-finding-sort.py").write_text(t.source)
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    if registry:
        (d / "jev" / "readings.json").write_text(json.dumps({"finding-sort": ENTRY}))
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d))
    r = subprocess.run([sys.executable, str(d / "check-finding-sort.py"), *argv],
                       input=review, capture_output=True, text=True, env=env)
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    return r


def asks_each_finding(t):
    r = run(t)
    got = sorted(b["state"]["finding"] for b in SEEN)
    want = sorted(["[label], `a.py:3` -- the parser drops the last line of every file it reads",
                   "[label],  the docstring names a flag the code no longer has",
                   "`b.py:9` the usage line spells the option two different ways"])
    return (r.returncode == 0 and r.stdout == "" and got == want), (got, r.stderr[-300:])


def masks_the_word(t):
    run(t)
    text = json.dumps([b["state"] for b in SEEN])
    return (bool(SEEN) and "defect" not in text and "refinement" not in text
            and "low" not in text), text


def labels_the_word(t):
    run(t, argv=("468", "o/r"))
    got = sorted(x["read"] for x in LOGGED)
    return got == ["o/r#468 REVIEW f1 defect", "o/r#468 REVIEW f2 refinement",
                   "o/r#468 REVIEW f3 refinement"], got


def other_comment_asks_nothing(t):
    r = run(t, review=REVIEW.replace("REVIEW ", "REPORT ", 1))
    return r.returncode == 0 and not SEEN and not LOGGED, (len(SEEN), LOGGED)


def clean_review_asks_nothing(t):
    r = run(t, review="REVIEW demo-worker-1: at abcdef1, clean\n\nFindings: none.\n")
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
            and sorted(x.get("finding") or 0 for x in keyed)
            == list(range(1, len(keyed) + 1))
            and all(len(x.get("wording") or "") == 12 for x in keyed)
            and all("repo" not in x for x in bare)), (keyed, bare)


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"]["finding-sort"] if SEEN else {}
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions") == ENTRY["question"]["instructions"]
            and "yes_over" not in q), q


def failure_logs_skip(t):
    r = run(t, registry=False)
    return (r.returncode == 0 and not SEEN and r.stdout == "" and r.stderr == ""
            and [x.get("skipped") for x in LOGGED]
            == ["the reading raised FileNotFoundError"]), (r.stderr[-300:], LOGGED)


CASES = {
    "a REVIEW asks one state per finding, verification notes left out, printing nothing": asks_each_finding,
    "the reviewer's word and severity never reach the model": masks_the_word,
    "each call is labelled with the reviewer's word, by item or by section": labels_the_word,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "a REVIEW with no finding asks nothing": clean_review_asks_nothing,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the row carries the reading, the wording and the join key": row_carries_its_join_key,
    "a reading that raised exits 0, says nothing and logs a skip": failure_logs_skip,
}

MUTATIONS = [
    ("verification notes kept", "if len(text) < MIN_CHARS or NOT_A_FINDING.search(masked):",
     "if len(text) < MIN_CHARS:",
     "a REVIEW asks one state per finding, verification notes left out, printing nothing"),
    ("the word not masked", 'masked = SEVERITY.sub(r"\\1 ", LABEL.sub("[label]", LEAD.sub("", text)))',
     "masked = text", "the reviewer's word and severity never reach the model"),
    ("the section heading unread", 'word = section or "none"', 'word = "none"',
     "each call is labelled with the reviewer's word, by item or by section"),
    ("the comment kind not read", 'if not review.lstrip().startswith("REVIEW "):', "if False:",
     "a comment of another kind asks nothing"),
    ("the row keyed by a number with no repository",
     '{"repo": repo, "pull_request": int(pr)} if repo else None, env)',
     '{"pull_request": int(pr)}, env)',
     "the row carries the reading, the wording and the join key"),
    ("the finding never numbered on the row",
     '"key": dict(key or {}, finding=n)}', '"key": key}',
     "the row carries the reading, the wording and the join key"),
    ("the reading's group not read from the entry",
     'group=entry["group"], reader=READER, env=env)]',
     'group="issue-shape", reader=READER, env=env)]',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the failure boundary removed",
     "    jev.shielded(READER, subject, lambda: read(pr, repo, subject, stdin, jev,\n"
     "                                               env), env)",
     "    read(pr, repo, subject, stdin, jev, env)",
     "a reading that raised exits 0, says nothing and logs a skip"),
]


def live(record):
    """Every corpus case against the real endpoint, once. A case is red when
    its word differs from the last one recorded under the same wording."""
    m = load(SOURCE).m
    jev = m.jev_module()
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
    print(f"finding-sort: {misses} of {len(rows)} case(s) off their truth")
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
