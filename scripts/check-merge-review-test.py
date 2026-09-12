#!/usr/bin/env python3
# witnesses: M2_MergeInTheStateAfterAPush, M2b_TheRuleExcludesTheStalePush
"""Prove check-merge-review refuses on every branch it claims to refuse on.

One case per refusal, each named after the branch it exercises, and each one
fails when that branch is deleted -- the sweep is recorded in the sub-issue's
REPORT rather than run from here.

PR kalaluthien/campaign-base#262's shape is among them: a pull request carrying
comments, none of which opens REVIEW, merged with nothing refusing it.

NO CASE REACHES THE NETWORK. `gh` is a script this writes onto PATH which
prints the canned JSON the case is about, so what is measured is this reader
and not GitHub's mood. Every case runs the real script end to end, because the
word and the exit status are the whole interface and a case calling the inner
functions would pass with `main`'s wiring cut.

ONE CASE RUNS THE MODEL'S OWN SITUATION rather than a hand-written one
(sdlc-alloy#342): alloy solves `M2_MergeInTheStateAfterAPush`, `alloy-check.py
--digest` prints its instance, and `instance_fixture` turns that into the
canned `gh` answer and the word the model says the reader owes. It needs the
solver, as CI installs it, and fails red without one.

Usage: scripts/check-merge-review-test.py   (needs ~/.local/bin/alloy)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-merge-review.py"
HEAD = "8ca2609f3b1d4e7a9c0b25d8e6f41a3b7c9d0e2f"
OTHER = "fb1bd4f2a7c3e59018d4b6f0a2c8e1d7b3f9a0c5e"
RAN, FAILED = [], []


def check(name, ok, detail=""):
    RAN.append(name)
    if not ok:
        FAILED.append(f"{name}{('  -- ' + detail) if detail else ''}")


def comment(body):
    """The REST shape, `user.login` -- not `gh pr view`'s `author.login`. The
    reader changed channels and a fixture still speaking the old one would test
    a mapping nothing performs."""
    return {"user": {"login": "kalaluthien"}, "body": body}


def fake_gh(bindir, head=HEAD, comments=(), reviews=(), status=0, stdout=None,
            view_stdout=None):
    """A `gh` on PATH answering the three calls this reader makes.

    THREE, not one, since the reader stopped taking its comments from
    `gh pr view`: the head comes from `pr view --json headRefOid`, and the two
    comment channels from `gh api --paginate` over their REST endpoints. The
    fake dispatches on the argument list exactly as the real one would, so a
    case cannot pass by answering a call the script does not make.

    `status` and `stdout` are the two ways an answer goes wrong -- a call that
    failed, and one that is not JSON -- and they apply to the `gh api` calls;
    `view_stdout` is the same for the head call."""
    body = json.dumps({"headRefOid": head} if head else {})
    if view_stdout is not None:
        body = view_stdout
    payloads = {"issues": json.dumps(list(comments)),
                "pulls": json.dumps(list(reviews))}
    if stdout is not None:
        payloads = {"issues": stdout, "pulls": stdout}
    gh = Path(bindir) / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"  *'pr view'*) cat <<'JSON'\n{body}\nJSON\n    exit 0 ;;\n"
        f"  *issues*) cat <<'JSON'\n{payloads['issues']}\nJSON\n    exit {status} ;;\n"
        f"  *pulls*) cat <<'JSON'\n{payloads['pulls']}\nJSON\n    exit {status} ;;\n"
        "esac\n")
    gh.chmod(0o755)
    return gh


def call(bindir, *args, stdin=None):
    """(word, returncode, everything printed). The word is the first token of
    the output, wherever it was printed: a refusal goes to stderr."""
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    p = subprocess.run([str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, input=stdin)
    text = (p.stdout or "") + (p.stderr or "")
    return (text.split(" ", 1)[0].strip() if text else ""), p.returncode, text


MODEL = SCRIPT.parent.parent / "spec" / "campaign" / "orchestration" / "checks.als"
WITNESS = "M2_MergeInTheStateAfterAPush"
ALLOY = Path.home() / ".local" / "bin" / "alloy"
STATE = re.compile(r"\s*S\d+(?: \(loop\))?  (.*)")


def witness_digest(d):
    """(the digest of WITNESS's instance, or None, and what went wrong)."""
    out = Path(d) / "alloy"
    try:
        subprocess.run([str(ALLOY), "exec", "-f", "-t", "text", "-c", WITNESS,
                        "-o", str(out), str(MODEL)], capture_output=True, text=True)
    except OSError as e:
        return None, f"alloy could not run: {e}"
    trace = out / f"{WITNESS}-solution-0.txt"
    if not trace.exists():
        return None, f"alloy wrote no instance of {WITNESS} under {out}"
    r = subprocess.run([sys.executable, str(SCRIPT.parent / "alloy-check.py"),
                        "--digest", str(MODEL), str(trace)], capture_output=True, text=True)
    return (r.stdout, "") if r.returncode == 0 else (None, r.stdout + r.stderr)


def sha(revision):
    """The model has no sha, so each revision of the pull request is given one."""
    return hashlib.sha1(f"revision {revision}".encode()).hexdigest()


def instance_fixture(digest):
    """(head, REVIEW bodies, (word, status) the model owes) for one digest.

    THE SHA RULE, stated here once: the pull request opens at revision 0, each
    `Push` of the merged issue makes the next revision the head, and each
    `Review` of it is a REVIEW naming the head in force in its state. The word
    is the model's own: `reviewed` exactly when the merged pull request is in
    `Reviewed` in the state whose event is `MergePullRequest`."""
    lines = digest.splitlines()
    if "Reviewed" not in next((l for l in lines if l.startswith("var (")), ""):
        raise LookupError("the digest read no `Reviewed`, so the model's word is unknown")
    rows = [dict(c.split("=", 1) for c in m.group(1).split("  "))
            for m in map(STATE.fullmatch, lines) if m]
    merge = next((i for i, r in enumerate(rows) if r.get("ev") == "MergePullRequest"), None)
    if merge is None:
        raise LookupError("the instance merges nothing")
    issue = rows[merge]["arg"]
    pr = dict(p.split("->") for p in rows[merge]["pr"].split(", "))[issue]
    revision, bodies = 0, []
    for row in rows[:merge]:
        if row.get("arg") != issue:
            continue
        if row.get("ev") == "Push":
            revision += 1
        if row.get("ev") == "Review":
            bodies.append(f"REVIEW {row.get('by', 'S')}: at {sha(revision)[:7]}")
    reviewed = pr in rows[merge].get("Reviewed", "").split(", ")
    return sha(revision), bodies, ("reviewed", 0) if reviewed else ("unreviewed", 1)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        bindir = Path(d) / "bin"
        bindir.mkdir()

        # ---- the gate ------------------------------------------------------

        # PR #262's shape: comments on the pull request, and not one of them
        # opens REVIEW. This is the branch that had no reader at all.
        fake_gh(bindir, comments=[comment(f"REPORT upkeep-worker-3: at {HEAD[:7]}"),
                                  comment("NOTE upkeep-worker-3: a note")])
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request whose comments hold no REVIEW is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the head it read",
              HEAD in text, text)
        check("...and says how many comments it read",
              "2 comment(s) read" in text, text)

        # A REVIEW that names an older sha is the same refusal from the sha's
        # end: the review it points at is at a revision nobody will merge.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: full round at "
                                          f"{OTHER[:7]}, no findings")])
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming a sha that is not the head is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the sha that REVIEW did name",
              OTHER[:7] in text, text)

        # CONTROL: the gate is not one that refuses every pull request.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: full round at "
                                          f"{HEAD[:7]}, no findings")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming the head is reviewed", (word, code) == ("reviewed", 0),
              f"{word} {code}")

        # ...and a REVIEW posted as a pull-request review, not as a comment,
        # counts too. `gh pr review --comment -b` is a spelling AGENTS.md
        # admits, and reading only `comments` refused it.
        fake_gh(bindir, reviews=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW posted as a pull-request review counts",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        # A sha too short to be one is not one: six hex characters is an issue
        # number or a colour, and matching it would pass a REVIEW that pins
        # nothing.
        fake_gh(bindir, comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:6]}")])
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("six hex characters do not name a sha",
              (word, code) == ("unreviewed", 1), f"{word} {code}")

        # ---- could not look, which is never a pass -------------------------

        fake_gh(bindir, status=1)
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a gh call that failed is unknown, not a pass",
              (word, code) == ("unknown", 2), f"{word} {code}")

        # THE LINE, NOT ONLY THE WORD -- the same lesson as the unreadable
        # body below, and this case did not carry it. A `json` handler replaced
        # by a silent `data = {}` lands on the no-head branch, which answers
        # `unknown` too, so the word alone left that branch deletable.
        fake_gh(bindir, stdout="not json at all")
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("an answer that is not JSON is unknown",
              (word, code) == ("unknown", 2) and "not JSON" in text,
              f"{word} {code} {text}")

        # A well-formed answer of the wrong SHAPE is not an empty list of
        # comments. Reading it as one would report "looked and found nothing"
        # for a channel that was never read.
        fake_gh(bindir, stdout='{"message": "Not Found"}')
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a comment channel that answered an object is unknown",
              (word, code) == ("unknown", 2) and "not a list" in text,
              f"{word} {code} {text}")

        fake_gh(bindir, head=None)
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request with no headRefOid is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")
        check("...and says there is no sha to read a review against",
              "headRefOid" in text, text)

        # ---- the REPORT's end ----------------------------------------------

        fake_gh(bindir)

        word, code, text = call(bindir, "274", "--repo", "o/r", "--report", "-",
                                stdin=f"REPORT upkeep-worker-3: #274 at {OTHER[:7]}\n")
        check("a REPORT pinning a sha that is not the head is stale",
              (word, code) == ("stale", 1), f"{word} {code}")
        check("...and the refusal names both shas",
              OTHER[:7] in text and HEAD in text, text)

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin="REPORT upkeep-worker-3: #274, done\n")
        check("a REPORT pinning no sha at all is stale",
              (word, code) == ("stale", 1), f"{word} {code}")

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin=f"REPORT upkeep-worker-3: #274 at {HEAD[:7]}\n")
        check("a REPORT pinning the head is pinned",
              (word, code) == ("pinned", 0), f"{word} {code}")

        # A body that is not a REPORT is not a REPORT this may judge. The shape
        # of a first line is check-campaign-claim.py's; this says so rather
        # than reading the sha out of whatever it was handed.
        word, code, text = call(bindir, "274", "--repo", "o/r", "--report", "-",
                                stdin=f"a plain line about {HEAD[:7]}\n")
        check("a body that opens no kind is unknown, not a verdict",
              (word, code) == ("unknown", 2), f"{word} {code}")

        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", "-",
                             stdin=f"REVIEW upkeep-worker-3: at {HEAD[:7]}\n")
        check("a REVIEW body handed to --report is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")

        # THE LINE, NOT ONLY THE WORD. A `read_body` that swallowed the error
        # and returned an empty body would answer `unknown` too -- by way of
        # "opens no kind" -- so a case asserting the word alone passes with
        # this branch deleted. The two refusals are told apart by what they
        # say they could not do.
        word, code, text = call(bindir, "274", "--repo", "o/r", "--report",
                                str(Path(d) / "no-such-file"))
        check("a REPORT body that could not be read is unknown",
              (word, code) == ("unknown", 2)
              and "could not read the REPORT body" in text, f"{word} {code} {text}")

        # A file, not only stdin -- the flag takes both and a caller pointing
        # at a written comment must not be the untested path.
        body = Path(d) / "report.md"
        body.write_text(f"REPORT upkeep-worker-3: #274 at {HEAD[:12]}\n")
        word, code, _ = call(bindir, "274", "--repo", "o/r", "--report", str(body))
        check("--report reads a file as well as stdin",
              (word, code) == ("pinned", 0), f"{word} {code}")

        # ---- the sha the run is recorded against ----------------------------

        # `--head` IS THE SUBJECT, and the live tip is a different question.
        # A REVIEW naming the live tip must not turn a run for an older sha
        # green: that is the whole reason the flag exists.
        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", OTHER)
        check("a REVIEW at the live tip does not review the sha given",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the trail says the branch has moved off it",
              "has since moved to" in text, text)

        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {OTHER[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", OTHER)
        check("...and a REVIEW at the sha given is a review of it",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        fake_gh(bindir, head=HEAD,
                comments=[comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")])
        word, code, text = call(bindir, "274", "--repo", "o/r", "--head", HEAD)
        check("a --head that IS the tip says so rather than warning",
              (word, code) == ("reviewed", 0) and "still the branch tip" in text,
              f"{word} {code}")

        # ---- every exit lands on one of the words ---------------------------

        # argparse prints `usage:` and exits 2 -- `unknown`'s status with a
        # different first word, and the first word is what every caller reads.
        word, code, text = call(bindir, "not-a-number")
        check("a call this reader does not take answers unknown, word first",
              (word, code) == ("unknown", 2), f"{word} {code} {text}")

        # ---- the model's own situation --------------------------------------

        digest, why = witness_digest(d)
        try:
            head, bodies, owed = instance_fixture(digest) if digest else (None, [], None)
        except LookupError as e:
            head, owed, why = None, None, f"{e}\n{digest}"
        if owed:
            fake_gh(bindir, head=head, comments=[comment(b) for b in bodies])
            word, code, text = call(bindir, "1", "--repo", "o/r")
        check(f"{WITNESS}'s instance gets the word the model gives it",
              owed is not None and (word, code) == owed,
              why or f"model {owed}, reader {word} {code}; {len(bodies)} REVIEW(s)\n{digest}")

    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
