#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-research-bar.py asks one call a research NOTE, a question per condition, asks nothing else, and never refuses.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question with one P(contradicts), and the reader runs from a fixture directory
holding the real scripts/campaign-jev.py, this reading's registry entry, and a
stub campaign-tracker.py whose `kind` word the case sets. Each case is then
broken by a mutation of the reader's text and must go red by its own assertion.

`--live` asks every line of scripts/jev/corpus/research-bar.jsonl against the
real endpoint and fails a case whose word differs from the last one `seen`
under the same question wording; `--record` appends the reading to `seen`.

Usage: scripts/check-research-bar-test.py [--live [--record]]
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
SCRIPT = HERE / "check-research-bar.py"
SOURCE = SCRIPT.read_text()
ENTRIES = json.loads((HERE / "jev" / "readings.json").read_text())
ENTRY = ENTRIES["research-bar"]
CORPUS = HERE / "jev" / "corpus" / "research-bar.jsonl"
ROOT = Path(tempfile.mkdtemp(prefix="research-bar-"))
NOTE = "NOTE demo-worker-1: measured 3 runs, 40 of 47 flagged by overlap\n\nbody\n"

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
    m = types.ModuleType("researchbar")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def run(t, note=NOTE, kind="research", argv=("458",), registry=True, url=None,
        kind_exit=0):
    """(the finished process, the argv the stub tracker was given)."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "check-research-bar.py").write_text(t.source)
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    (d / "campaign-tracker.py").write_text(
        "import json, sys\n"
        f"open({str(d / 'tracker-argv.json')!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        f"print({kind!r})\n"
        f"sys.exit({kind_exit})\n")
    if registry:
        (d / "jev" / "readings.json").write_text(json.dumps({"research-bar": ENTRY}))
    SEEN.clear()
    env = dict(os.environ, CAMPAIGN_JEV_URL=url or URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d))
    r = subprocess.run([sys.executable, str(d / "check-research-bar.py"), *argv],
                       input=note, capture_output=True, text=True, env=env)
    got = d / "tracker-argv.json"
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    return r, (json.loads(got.read_text()) if got.exists() else None)


def composed(name):
    return ENTRY["question"]["instructions"].replace(
        "{condition}", ENTRY["conditions"][name])


def asks_each_condition(t):
    r, _ = run(t)
    asked = {q.split("#", 1)[-1]: v["instructions"]
             for b in SEEN for q, v in b["questions"].items()}
    want = {name: composed(name) for name in ENTRY["conditions"]}
    return (r.returncode == 0 and len(SEEN) == 1 and r.stdout == ""
            and SEEN[0]["state"] == {"note": NOTE} and asked == want
            and [x["read"] for x in LOGGED] == ["tracker#458 NOTE"]), \
        (len(SEEN), asked, r.stdout, r.stderr, LOGGED)


def other_kind_asks_nothing(t):
    r, _ = run(t, kind="development")
    return r.returncode == 0 and not SEEN, (len(SEEN), r.stderr)


def other_comment_asks_nothing(t):
    r, _ = run(t, note="REPORT demo-worker-1: at abcdef1\n")
    return r.returncode == 0 and not SEEN, (len(SEEN), r.stderr)


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"].get("research-bar#baseline", {}) if SEEN else {}
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions") == composed("baseline")
            and "yes_over" not in q), q


def row_carries_its_join_key(t):
    """WHAT THE MOVE FROM `ask` TO `judge` BOUGHT: the row names the reading
    and its wording and carries the key as FIELDS, so the next DECISION on that
    sub-issue can be joined to the answer. A call given no repository carries
    NEITHER field, because a number alone names no issue when a member
    repository's numbers collide with this tracker's."""
    run(t, argv=("7", "o/r"))
    keyed = LOGGED[0] if LOGGED else {}
    run(t)
    bare = LOGGED[0] if LOGGED else {}
    return (keyed.get("repo") == "o/r" and keyed.get("issue") == 7
            and keyed.get("reading") == "research-bar"
            and len(keyed.get("wording") or "") == 12
            and "repo" not in bare and "issue" not in bare), (keyed, bare)


def repo_reaches_tracker(t):
    r, argv = run(t, argv=("7", "o/r"))
    return r.returncode == 0 and argv == ["kind", "7", "o/r"], argv


def failure_exits_zero(t):
    r, _ = run(t, registry=False)
    return (r.returncode == 0 and not SEEN and r.stdout == ""
            and r.stderr == ""
            and [x.get("skipped") for x in LOGGED] == ["the reading raised FileNotFoundError"]
            ), (r.returncode, r.stderr[-300:], LOGGED)


def failed_kind_read_logs_skip(t):
    r, _ = run(t, kind="", kind_exit=2)
    return (r.returncode == 0 and not SEEN and len(LOGGED) == 1
            and LOGGED[0]["read"] == "tracker#458 NOTE"
            and LOGGED[0]["skipped"].startswith("the kind read failed")), LOGGED


def crashed_tracker_logs_skip(t):
    r, _ = run(t, kind="", kind_exit=1)
    return (r.returncode == 0 and not SEEN and len(LOGGED) == 1
            and LOGGED[0]["skipped"].startswith("the kind read failed")), LOGGED


def other_kind_logs_nothing(t):
    r, _ = run(t, kind="none", kind_exit=1)
    return r.returncode == 0 and not SEEN and not LOGGED, LOGGED


CASES = {
    "a research NOTE asks one call, the note whole, a question per condition, printing nothing": asks_each_condition,
    "a NOTE on another work kind asks nothing": other_kind_asks_nothing,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the repository reaches the kind reader": repo_reaches_tracker,
    "the row carries the reading, the wording and the join key": row_carries_its_join_key,
    "a reader that could not read exits 0, says nothing and logs a skip": failure_exits_zero,
    "a failed kind read logs one skip row": failed_kind_read_logs_skip,
    "a tracker that raised, exit 1 and no word, logs one skip row": crashed_tracker_logs_skip,
    "an issue with no kind logs nothing": other_kind_logs_nothing,
}

MUTATIONS = [
    ("the conditions never handed to the call",
     '"state": {"note": inp.body, "condition": entry["conditions"]},',
     '"state": {"note": inp.body, "condition": {}},',
     "a research NOTE asks one call, the note whole, a question per condition, printing nothing"),
    ("the note sent as a condition's text",
     '"condition": entry["conditions"]},',
     '"condition": {k: inp.body for k in entry["conditions"]}},',
     "a research NOTE asks one call, the note whole, a question per condition, printing nothing"),
    ("the work kind not read", 'if kind != "research":', "if False:",
     "a NOTE on another work kind asks nothing"),
    ("the reading's group not read from the entry",
     '{"group": entry["group"]})', '{"group": "issue-shape"})',
     "a research NOTE asks one call, the note whole, a question per condition, printing nothing"),
    ("the repository dropped", "args + ([repo] if repo else [])", "args",
     "the repository reaches the kind reader"),
    ("the row keyed by a number with no repository",
     'key = {"repo": inp.repo, "issue": int(inp.number)} if inp.repo else {}',
     'key = {"issue": int(inp.number)}',
     "the row carries the reading, the wording and the join key"),
    ("a failed kind read taken for a kind",
     '    if p.returncode == 0 or (p.returncode == 1 and kind == "none"):', "    if True:",
     "a failed kind read logs one skip row"),
    ("any exit 1 taken for a kind",
     '(p.returncode == 1 and kind == "none")', "p.returncode == 1",
     "a tracker that raised, exit 1 and no word, logs one skip row"),
    ("a skip logged for a kind that is not research",
     '    if kind != "research":\n        return',
     '    if kind != "research":\n        yield jev.Skip(inp.subject, "x")\n        return',
     "an issue with no kind logs nothing"),
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
        # A CASE IS ONE CONDITION, and production asks all five in one call over
        # the note; the question of that one condition is what this case pins.
        name = next(n for n, text in ENTRY["conditions"].items()
                    if text == row["state"]["condition"])
        reading = jev.ask(m.READER, row["id"], {"note": row["state"]["note"]},
                          {name: jev.question_of(
                              ENTRY, name, {"condition": ENTRY["conditions"]})})
        a = reading.answers[name]
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
    print(f"research-bar: {misses} of {len(rows)} case(s) off their truth")
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
