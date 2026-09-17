#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-research-bar.py asks one state per condition of a research NOTE, asks nothing else, and never refuses.

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


def asks_each_condition(t):
    r, _ = run(t)
    states = sorted((b["state"]["condition"], b["state"]["note"]) for b in SEEN)
    want = sorted((c, NOTE) for c in ENTRY["conditions"].values())
    return (r.returncode == 0 and states == want and r.stdout == ""
            and len(SEEN) == len(ENTRY["conditions"])), (states, r.stdout, r.stderr)


def other_kind_asks_nothing(t):
    r, _ = run(t, kind="development")
    return r.returncode == 0 and not SEEN, (len(SEEN), r.stderr)


def other_comment_asks_nothing(t):
    r, _ = run(t, note="REPORT demo-worker-1: at abcdef1\n")
    return r.returncode == 0 and not SEEN, (len(SEEN), r.stderr)


def entry_reaches_model(t):
    run(t)
    q = SEEN[0]["questions"]["c"] if SEEN else {}
    return (q.get("criteria") == ENTRY["question"]["criteria"]
            and q.get("instructions") == ENTRY["question"]["instructions"]
            and "yes_over" not in q), q


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
    "a research NOTE asks one state per condition, the note whole, printing nothing": asks_each_condition,
    "a NOTE on another work kind asks nothing": other_kind_asks_nothing,
    "a comment of another kind asks nothing": other_comment_asks_nothing,
    "the entry's instructions and criteria reach the model, thresholds do not": entry_reaches_model,
    "the repository reaches the kind reader": repo_reaches_tracker,
    "a reader that could not read exits 0, says nothing and logs a skip": failure_exits_zero,
    "a failed kind read logs one skip row": failed_kind_read_logs_skip,
    "a tracker that raised, exit 1 and no word, logs one skip row": crashed_tracker_logs_skip,
    "an issue with no kind logs nothing": other_kind_logs_nothing,
}

MUTATIONS = [
    ("the condition's name sent for its text",
     'state = {"condition": entry["conditions"][name], "note": note}',
     'state = {"condition": name, "note": note}',
     "a research NOTE asks one state per condition, the note whole, printing nothing"),
    ("the work kind not read", 'if kind != "research":', "if False:",
     "a NOTE on another work kind asks nothing"),
    ("the comment kind not read", 'if not note.lstrip().startswith("NOTE "):', "if False:",
     "a comment of another kind asks nothing"),
    ("the criteria not sent", 'if k in ("type", "criteria")}', 'if k in ("type",)}',
     "the entry's instructions and criteria reach the model, thresholds do not"),
    ("the repository dropped", "args + ([repo] if repo else [])", "args",
     "the repository reaches the kind reader"),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this",
     "except ZeroDivisionError as e:",
     "a reader that could not read exits 0, says nothing and logs a skip"),
    ("a failed kind read taken for a kind",
     '    if p.returncode == 0 or (p.returncode == 1 and kind == "none"):', "    if True:",
     "a failed kind read logs one skip row"),
    ("any exit 1 taken for a kind",
     '(p.returncode == 1 and kind == "none")', "p.returncode == 1",
     "a tracker that raised, exit 1 and no word, logs one skip row"),
    ("a skip logged for a kind that is not research",
     '        if kind != "research":\n            return 0',
     '        if kind != "research":\n            jev.skip(READER, subject, "x", env)\n            return 0',
     "an issue with no kind logs nothing"),
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
