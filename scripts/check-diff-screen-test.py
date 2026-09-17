#!/usr/bin/env python3
# witnesses: JudgmentStandsInOrIsHandedUp, JudgmentGuard_Bites
"""Prove check-diff-screen.py asks one call a file the commit touched, its branch patch and the tests beside it, skips what it cannot send, and never refuses; and that the push hook starts it only after pushing to GitHub.

THE DEFAULT RUN IS OFFLINE: a stub HTTP server on 127.0.0.1 answers every
question with one noul, and the reader runs in a fixture git repository from a
directory holding the real scripts/campaign-jev.py and this reading's registry
entry. Each case is then broken by a mutation of the reader's text and must go
red by its own assertion. The hook cases run the real push-campaign-branch.sh
beside a stub claim reader and a stub screen that writes a marker.

`--live` asks every line of scripts/jev/corpus/diff-screen.jsonl against the
real endpoint and fails a case whose word differs from the last one `seen`
under the same question wording; `--record` appends the reading to `seen`.

Usage: scripts/check-diff-screen-test.py [--live [--record]]
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
import time
import types
from pathlib import Path

harness = importlib.import_module("suite-harness-test")
check = harness.check

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-diff-screen.py"
SOURCE = SCRIPT.read_text()
ENTRY = json.loads((HERE / "jev" / "readings.json").read_text())["diff-screen"]
CORPUS = HERE / "jev" / "corpus" / "diff-screen.jsonl"
ROOT = Path(tempfile.mkdtemp(prefix="diff-screen-"))
NOULS = sorted(ENTRY["nouls"])


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


# THE REPOSITORY. `origin/main` holds `a.py`, `x.md` and `old.bin`. The branch's
# first commit changes `a.py` and `x.md` and adds `b-test.py`; HEAD changes
# `a.py` again, puts `x.md` back as it was on main, rewrites the binary and adds
# a patch over the ceiling. So HEAD touched four files: `a.py` is asked with
# its whole branch patch, `x.md` has no branch patch, the binary and the big
# file are skipped, and `b-test.py`, the branch's but not HEAD's, is not asked
# and is still a changed test.
REPO = ROOT / "repo"
REPO.mkdir()
git(REPO, "init", "-q", "-b", "main")
(REPO / "a.py").write_text("def f():\n    return 1\n")
(REPO / "x.md").write_text("prose\n")
(REPO / "old.bin").write_bytes(b"\x00\x01\x02")
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "main")
git(REPO, "update-ref", "refs/remotes/origin/main", "HEAD")
BASE = git(REPO, "rev-parse", "HEAD")
git(REPO, "checkout", "-q", "-b", "demo/9-topic")
(REPO / "a.py").write_text("def f():\n    return 2\n")
(REPO / "x.md").write_text("changed prose\n")
(REPO / "b-test.py").write_text("assert True\n")
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "first")
(REPO / "a.py").write_text("def f():\n    return 3\n")
(REPO / "x.md").write_text("prose\n")
(REPO / "old.bin").write_bytes(b"\x00\x09\x02")
(REPO / "big.py").write_text("x = 1\n" * 20000)
git(REPO, "add", "-A")
git(REPO, "commit", "-q", "-m", "head")
HEAD = git(REPO, "rev-parse", "HEAD")
# THE PATCH IN ITS PINNED FORM, whatever this machine's git config: no prefix.
WANT_A = git(REPO, "diff", "--no-prefix", "--diff-algorithm=histogram", BASE, HEAD, "--", "a.py") + "\n"

# A MERGE COMMIT on another branch: main moved, and the branch took it in.
MERGED = ROOT / "merged"
shutil.copytree(REPO, MERGED)
git(MERGED, "checkout", "-q", "main")
(MERGED / "m.py").write_text("main moved\n")
git(MERGED, "add", "-A")
git(MERGED, "commit", "-q", "-m", "main moves")
git(MERGED, "update-ref", "refs/remotes/origin/main", "HEAD")
git(MERGED, "checkout", "-q", "demo/9-topic")
git(MERGED, "merge", "-q", "--no-edit", "main")

# NO origin/main at all.
LONE = ROOT / "lone"
shutil.copytree(REPO, LONE)
git(LONE, "update-ref", "-d", "refs/remotes/origin/main")

SEEN = []
LOGGED = []


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        answers = {q: {"type": "noul", "noul": 0.3} for q in body["questions"]}
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
    m = types.ModuleType("diffscreen")
    m.__file__ = str(SCRIPT)
    exec(compile(source, str(SCRIPT), "exec"), m.__dict__)
    return types.SimpleNamespace(source=source, m=m)


def run(t, argv=(), registry=True, cwd=REPO):
    """The finished process; `SEEN` holds the calls, `LOGGED` the log rows."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    (d / "jev").mkdir()
    (d / "check-diff-screen.py").write_text(t.source)
    shutil.copy(HERE / "campaign-jev.py", d / "campaign-jev.py")
    if registry:
        (d / "jev" / "readings.json").write_text(json.dumps({"diff-screen": ENTRY}))
    SEEN.clear()
    # A HOME OF ITS OWN, so no git config of this machine shapes the patch;
    # the mutation dropping `--no-prefix` goes red only because of it.
    env = dict(os.environ, CAMPAIGN_JEV_URL=URL, TYPESAFE_API_KEY="stub",
               CAMPAIGN_JEV_LOG=str(d / "jev.log"), HOME=str(d),
               GIT_CONFIG_GLOBAL=os.devnull)
    r = subprocess.run([sys.executable, str(d / "check-diff-screen.py"), *argv],
                       capture_output=True, text=True, env=env, cwd=cwd)
    log = d / "jev.log"
    LOGGED[:] = ([json.loads(x) for x in log.read_text().splitlines() if x]
                 if log.exists() else [])
    return r


def skips():
    return {row["read"].rsplit(" ", 1)[-1]: row["skipped"] for row in LOGGED if "skipped" in row}


def asks_the_branch_patch(t):
    r = run(t)
    states = [b["state"] for b in SEEN]
    return (r.returncode == 0 and r.stdout == "" and r.stderr == ""
            and states == [{"file": {"path": "a.py", "patch": WANT_A},
                            "changedTests": ["b-test.py"]}]), (states, r.stderr[-300:])


def asks_only_the_commits_files(t):
    run(t)
    asked = sorted(b["state"]["file"]["path"] for b in SEEN)
    logged = sorted(row["read"].rsplit(" ", 1)[1] for row in LOGGED)
    return asked == ["a.py"] and logged == ["a.py", "big.py", "old.bin", "x.md"], (asked, logged)


def asks_five_nouls_composed(t):
    run(t)
    q = SEEN[0]["questions"] if SEEN else {}
    ask = {n: ENTRY["nouls"][n]["ask"] for n in NOULS}
    return (sorted(q) == NOULS
            and {n: v.get("instructions") for n, v in q.items()} == ask
            and q["boundary"]["criteria"]["true"]["what"] == ENTRY["nouls"]["boundary"]["true"]
            and q["boundary"]["criteria"]["false"]["examples"] == [ENTRY["nouls"]["boundary"]["false_example"]]
            and all(v.get("type") == "noul" and "yes_over" not in v for v in q.values())), q


def labels_branch_sha_path(t):
    run(t)
    return [row["read"] for row in LOGGED if "answers" in row] == \
        [f"demo/9-topic {HEAD[:12]} a.py"], LOGGED


def skips_what_it_cannot_send(t):
    run(t)
    got = skips()
    return (got.get("x.md") == "the branch's patch of it is empty"
            and got.get("old.bin") == "a binary file"
            and got.get("big.py", "").startswith("a patch of ")
            and len(got) == 3), got


def merge_asks_nothing(t):
    r = run(t, cwd=MERGED)
    return r.returncode == 0 and not SEEN and not LOGGED, (len(SEEN), LOGGED)


def no_merge_base_skips_once(t):
    r = run(t, cwd=LONE)
    return (r.returncode == 0 and not SEEN
            and [x.get("skipped") for x in LOGGED] == ["no merge-base with origin/main"]), LOGGED


def failure_logs_skip(t):
    r = run(t, registry=False)
    return (r.returncode == 0 and not SEEN and r.stdout == "" and r.stderr == ""
            and [x.get("skipped") for x in LOGGED] == ["the reading raised FileNotFoundError"]
            ), (r.stderr[-300:], LOGGED)


CASES = {
    "a file the commit touched is asked with its whole branch patch and the branch's tests, printing nothing": asks_the_branch_patch,
    "only the commit's own files are read, not the rest of the branch": asks_only_the_commits_files,
    "one call carries the five nouls, each its own words, thresholds unsent": asks_five_nouls_composed,
    "the log label is the branch, the sha and the path": labels_branch_sha_path,
    "an empty branch patch, a binary and a patch over the ceiling each log a skip": skips_what_it_cannot_send,
    "a merge commit asks and logs nothing": merge_asks_nothing,
    "a commit with no merge-base logs one skip": no_merge_base_skips_once,
    "a reading that raised exits 0, says nothing and logs a skip": failure_logs_skip,
}

MUTATIONS = [
    ("the patch read from the parent, not the merge-base",
     'git("diff", *PATCH_FORM, base, commit,', 'git("diff", *PATCH_FORM, commit + "^", commit,',
     "a file the commit touched is asked with its whole branch patch and the branch's tests, printing nothing"),
    ("the patch form left to the machine's config", '"--no-prefix", ', "",
     "a file the commit touched is asked with its whole branch patch and the branch's tests, printing nothing"),
    ("the tests not collected", "sorted(p for p in stat if TEST.search(p))", "[]",
     "a file the commit touched is asked with its whole branch patch and the branch's tests, printing nothing"),
    ("the whole branch read", "for path in filter(None, touched):", "for path in stat:",
     "only the commit's own files are read, not the rest of the branch"),
    ("the placeholders left unfilled",
     'filled = filled.replace("{" + key + "}", json.dumps(value)[1:-1])', "pass",
     "one call carries the five nouls, each its own words, thresholds unsent"),
    ("the path dropped from the label", 'jev.ask(READER, f"{label} {path}",', "jev.ask(READER, label,",
     "the log label is the branch, the sha and the path"),
    ("an empty branch patch sent", "if path not in stat:", "if False:",
     "an empty branch patch, a binary and a patch over the ceiling each log a skip"),
    ("a binary sent", 'elif stat[path] == "-":', "elif False:",
     "an empty branch patch, a binary and a patch over the ceiling each log a skip"),
    ("no ceiling", "if not why and len(patch) > PATCH_CEILING:", "if False:",
     "an empty branch patch, a binary and a patch over the ceiling each log a skip"),
    ("no merge-base passes silently",
     '            jev.skip(READER, label, "no merge-base with origin/main", env)\n',
     "",
     "a commit with no merge-base logs one skip"),
    ("the failure boundary removed",
     "except Exception as e:  # noqa: BLE001 -- a reading never refuses, and nobody reads this",
     "except ZeroDivisionError as e:",
     "a reading that raised exits 0, says nothing and logs a skip"),
]


def hook(origin, pushable=True):
    """(the hook's output, whether it started the screen, with which argument).
    The real push script runs beside a stub claim reader answering `claim` and
    a stub screen writing its argv; the clone's fetch url is `origin` and it
    pushes to a local bare repository, or to nowhere."""
    d = Path(tempfile.mkdtemp(dir=ROOT))
    scripts, bare, clone = d / "scripts", d / "bare.git", d / "clone"
    scripts.mkdir()
    shutil.copy(HERE / "push-campaign-branch.sh", scripts / "push-campaign-branch.sh")
    marker = d / "screened"
    (scripts / "check-commit-claim.py").write_text(
        "#!/usr/bin/env python3\nimport sys\nprint('claim demo/9-topic')\nsys.exit(0)\n")
    (scripts / "check-diff-screen.py").write_text(
        f"#!/usr/bin/env python3\nimport sys\nopen({str(marker)!r}, 'w').write(' '.join(sys.argv[1:]))\n")
    for s in scripts.iterdir():
        s.chmod(0o755)
    git(d, "init", "-q", "--bare", str(bare))
    shutil.copytree(REPO, clone)
    git(clone, "remote", "add", "origin", origin)
    git(clone, "config", "remote.origin.pushurl", str(bare if pushable else d / "nowhere.git"))
    r = subprocess.run([str(scripts / "push-campaign-branch.sh")], cwd=clone,
                       capture_output=True, text=True)
    for _ in range(50):
        if marker.exists():
            break
        time.sleep(0.1)
    return r.stdout + r.stderr, marker.read_text() if marker.exists() else None


def hook_cases():
    out, arg = hook("git@github.com:o/r.git")
    check("the push hook starts the screen on the pushed sha after pushing a claim to GitHub",
          "pushed demo/9-topic" in out and arg == HEAD, (out, arg))
    out, arg = hook(str(ROOT / "elsewhere.git"))
    check("...and not for a remote that is not GitHub",
          "pushed demo/9-topic" in out and arg is None, (out, arg))
    out, arg = hook("https://github.com/o/r", pushable=False)
    check("...nor after a push that failed",
          "could NOT push" in out and arg is None, (out, arg))


def live(record):
    """Every corpus case against the real endpoint, once, all five nouls in the
    call; a case reads as its highest noul. Red when its word differs from the
    last one recorded under the same wording."""
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
        nouls = {n: (a.raw or {}).get("noul") for n, a in reading.answers.items()}
        raw = None if None in nouls.values() else round(max(nouls.values()), 2)
        word = ("unknown" if raw is None else "yes" if raw >= t["yes_over"]
                else "no" if raw <= t["no_under"] else "unknown")
        print(f"{row['id']}  truth {row['truth']:<3} "
              f"{'-' if raw is None else f'{raw:.2f}'} {word}  {row['source']['ref']}")
        misses += word != row["truth"]
        before = [x for x in row["seen"] if x.get("wording") == wording]
        if before:
            check(f"live {row['id']} reads {before[-1]['word']} as last recorded",
                  word == before[-1]["word"], f"{word} at {raw}")
        row["seen"].append({"model": reading.model, "wording": wording, "raw": raw,
                            "nouls": nouls, "word": word, "at": today})
    print(f"diff-screen: {misses} of {len(rows)} case(s) off their truth")
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
        hook_cases()
        return harness.report()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
