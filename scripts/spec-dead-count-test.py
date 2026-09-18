#!/usr/bin/env python3
# witnesses: S9_DeadElimination
"""Prove spec-dead-count.py lists a scenario no suite witnesses, and only that one.

`S9_DeadElimination` is the removal of a scenario nothing witnesses, beside a
code path that stays tied through another. Which scenario that is gets judged
outside the model, from the candidates this script prints; so the case is the
fixture S9 starts from: one code path, its suite declaring `S1_Live`, an html
form refining `S3_Refined`, and `S2_Dead` declared by nothing.

THE NAMED FAILING CASE is `the dead scenario is listed, the witnessed and the
refined ones are not`:
it reddens a reader that drops the declaration filter (every command listed),
reads declarations off no suite, or reads no html form's refinement -- the
difference between a candidate set and the whole snapshot.

THE RULING MODE runs offline: a stub HTTP server on 127.0.0.1 answers every
question with one `choice`, and a fake `gh` on PATH answers the `bound:`
labels. Its named failing case is `the unwitnessed and the premise commands
are asked, the Cov_ and the witnessed are not`, and each mutation below
reddens the case it names.

Usage: scripts/spec-dead-count-test.py
"""
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

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "spec-dead-count.py"

harness = importlib.import_module("suite-harness-test")
check = harness.check

MODULE = "spec/demo/checks.als"
FIXTURE = {
    "spec/commands.snapshot.json": json.dumps({"commands": [
        [MODULE, "run", "S1_Live"], [MODULE, "run", "S2_Dead"],
        [MODULE, "run", "S3_Refined"]]}),
    MODULE: ("pred S1_Live { some univ }\npred S2_Dead { no univ }\n"
             "pred S3_Refined { lone univ }\n"
             "run S1_Live expect 1\nrun S2_Dead expect 1\nrun S3_Refined expect 1\n"),
    "spec/demo/refined.html": '<section data-scenario data-refines="S3_Refined"></section>\n',
    "scripts/demo.py": "print('demo')\n",
    "scripts/demo-test.py": "# witnesses: S1_Live\nprint('S1_Live')\n",
}


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args, str(root)],
                          capture_output=True, text=True)


def main() -> int:
    print(f"reading {SCRIPT}")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        harness.write_tree(root, FIXTURE)
        harness.git(root, "init", "-q", "-b", "main", check=True)
        harness.git(root, "add", "-A", check=True)

        r = run(root, "--mode", "unwitnessed")
        lines = r.stdout.splitlines()
        rows = [l.split("\t") for l in lines[1:]]
        check("unwitnessed exits 0", r.returncode == 0, f"exit {r.returncode}: {r.stderr[:300]}")
        check("the count line counts one of three snapshot commands",
              lines[:1] and lines[0].startswith("unwitnessed\t1\tof 3 snapshot commands"),
              repr(lines[:1]))
        check("the dead scenario is listed, the witnessed and the refined ones are not",
              [x[2] for x in rows] == ["S2_Dead"], repr(rows))
        check("its row carries the entity and the reason",
              rows[:1] and rows[0][1] == "demo" and "declared by no suite" in rows[0][3],
              repr(rows[:1]))

        # A ROOT below the tree's top reads the whole tree, not an empty one:
        # `git ls-files` there lists paths relative to it, none under spec/.
        r = run(root / "scripts", "--mode", "unwitnessed")
        check("a ROOT below the top reads the same tree",
              r.stdout.splitlines() == lines, repr(r.stdout.splitlines()[:2]))

        r = run(root)
        modes = [l.split("\t")[0] for l in r.stdout.splitlines() if l.split("\t")[1:2] != ["-"]]
        check("every mode runs over the fixture and exits 0",
              r.returncode == 0 and {"defs", "unwitnessed", "unpaired", "duplicate",
                                     "undefined", "untied", "premise", "mismatch"} <= set(modes),
              f"exit {r.returncode}: {r.stderr[:300]}")
    harness.mutate(SCRIPT.read_text(), ruling_run, RULING_CASES, RULING_MUTATIONS)
    return harness.report()


# THE SNAPSHOT NAMES A MODULE RELATIVE TO spec/, the key its path from the
# top: `fetch_commits` reads `origin/main:<path>`, so a relative key is a row
# the join can never label (pr#504 F1).
RULED = "spec/two/checks.als"
SNAPPED = "two/checks.als"
RULING_TREE = {
    "spec/commands.snapshot.json": json.dumps({"commands": [
        [SNAPPED, "run", "R1_Live"], [SNAPPED, "run", "R2_Dead"],
        [SNAPPED, "run", "Cov_Gate"], [SNAPPED, "check", "R3_TwoMachines"]]}),
    RULED: ("pred R1_Live { some univ }\n\n-- the rejected candidate\npred R2_Dead { no univ }\n\n"
            "pred Cov_Gate { lone univ }\n\nassert R3_TwoMachines { no univ }\n\n"
            "run R1_Live expect 1\nrun R2_Dead expect 1\nrun Cov_Gate expect 1\n"
            "check R3_TwoMachines for exactly 2 Machine expect 0\n"),
    "scripts/two.py": "print('R2_Dead')\n",
    "scripts/two-test.py": "# witnesses: R1_Live, R3_TwoMachines\nprint('R1_Live')\n",
}
LABELS = [{"number": 1, "createdAt": "2026-01-01T00:00:00Z",
           "labels": [{"name": "campaign"}, {"name": "bound:mac1"}]},
          {"number": 2, "createdAt": "2026-02-01T00:00:00Z",
           "labels": [{"name": "bound:mac1"}]}]
FAKE_GH = f'''#!/usr/bin/env python3
import sys
print({json.dumps(json.dumps(LABELS))} if sys.argv[1:3] == ["issue", "list"] else "")
'''
P = {"not_shown": 0.61, "shown": 0.2, "no_premise": 0.1, "live": 0.3, "dead": 0.64,
     "unclear": 0.06}
SEEN = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {q: {"type": "choice", "choice": "unclear", "confidence": 0.5,
                       "probabilities": {o: P[o] for o in spec["criteria"]}}
                   for q, spec in body["questions"].items()}
        data = json.dumps({"model": "jev-1.13.0", "answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def ruling_run(source):
    """`--mode ruling` of `source` over RULING_TREE, beside the real siblings:
    its stdout, the questions the stub was sent, and the log rows."""
    d = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(HERE, d / "base" / "scripts",
                        ignore=shutil.ignore_patterns("*-test.py", "corpus", "__pycache__"))
        (d / "base" / "scripts" / SCRIPT.name).write_text(source)
        root = d / "tree"
        harness.write_tree(root, RULING_TREE)
        harness.git(root, "init", "-q", "-b", "main", check=True)
        harness.git(root, "remote", "add", "origin",
                    "https://github.com/kalaluthien/two.git", check=True)
        harness.git(root, "add", "-A", check=True)
        harness.git(root, "commit", "-qm", "tree", check=True)
        harness.fake(d / "bin", "gh", FAKE_GH)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        SEEN.clear()
        env = dict(os.environ, TYPESAFE_API_KEY="stub", CAMPAIGN_JEV_LOG=str(d / "jev.log"),
                   CAMPAIGN_JEV_URL=f"http://127.0.0.1:{server.server_address[1]}/v1/systemone",
                   HOME=str(d), GIT_CONFIG_GLOBAL=os.devnull,
                   PATH=f"{d / 'bin'}{os.pathsep}{os.environ['PATH']}")
        r = subprocess.run([sys.executable, str(d / "base" / "scripts" / SCRIPT.name),
                            "--mode", "ruling", str(root)],
                           capture_output=True, text=True, env=env)
        server.shutdown()
        log = d / "jev.log"
        rows = [json.loads(x) for x in log.read_text().splitlines() if x] \
            if log.exists() else []
        return types.SimpleNamespace(r=r, seen=list(SEEN), rows=rows)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def asked(m):
    return sorted((q, b["state"]["row"].split("\n")[0]) for b in m.seen for q in b["questions"])


def asks_the_candidates(m):
    return asked(m) == [("dead-premise", "assert R3_TwoMachines { no univ }"),
                        ("dead-reader", "-- the rejected candidate")], \
        f"{asked(m)} {m.r.stderr[-300:]}"


def premise_fact_is_the_labels(m):
    facts = [b["state"]["fact"] for b in m.seen if "dead-premise" in b["questions"]]
    return facts and "mac1 on 2" in facts[0] and "1 machine(s)" in facts[0], facts


def prints_nothing_and_flags_the_option(m):
    flags = sorted((r["reading"], (r.get("flag") or {}).get("code")) for r in m.rows)
    return m.r.stdout == "" and m.r.returncode == 0 and flags == [
        ("dead-premise", P["not_shown"]), ("dead-reader", P["dead"])], \
        f"stdout {m.r.stdout[:200]!r} exit {m.r.returncode} flags {flags}"


def key_names_path_and_command(m):
    keys = sorted((r.get("repo"), r.get("path"), r.get("name")) for r in m.rows)
    return keys == [("kalaluthien/two", RULED, "R2_Dead"),
                    ("kalaluthien/two", RULED, "R3_TwoMachines")], keys


RULING_CASES = {
    "the unwitnessed and the premise commands are asked, the Cov_ and the witnessed are not":
        asks_the_candidates,
    "the premise fact is the bound: labels gh returned": premise_fact_is_the_labels,
    "the ruling prints nothing and each row's flag is its option's P":
        prints_nothing_and_flags_the_option,
    "each row's key is the repository, the path and the command": key_names_path_and_command,
}
ASKS, FACT, FLAGS, KEY = RULING_CASES
RULING_MUTATIONS = [
    ("a Cov_ asked", 'if n.startswith("Cov_") or n not in table:', "if n not in table:", ASKS),
    ("a witnessed command asked", "        if n not in declared:\n", "        if True:\n", ASKS),
    ("the premise fact not sent", '{"row": row, "fact": fetched[kind]}', '{"row": row, "fact": ""}',
     FACT),
    ("the flag on the wrong option", '"dead-premise": "not_shown"', '"dead-premise": "shown"',
     FLAGS),
    ("the key relative to spec/", 'row, path = row_of(n, table), "spec/" + m',
     "row, path = row_of(n, table), m", KEY),
    ("the key without the command", '"key": dict(key, path=path, name=name)',
     '"key": dict(key, path=path)', KEY),
]


if __name__ == "__main__":
    sys.exit(main())
