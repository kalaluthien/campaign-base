#!/usr/bin/env python3
# witnesses: M1_MergedWithNothingReadingTheReview, M1c_TheReaderAdmitsTheReadMerge
# witnesses: M2_MergeInTheStateAfterAPush, M2b_TheReaderExcludesTheStalePush
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

Usage: scripts/check-merge-review-test.py
"""
import json
import os
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
    return {"author": {"login": "kalaluthien"}, "body": body}


def fake_gh(bindir, payload=None, status=0, stdout=None):
    """A `gh` on PATH that answers `pr view` with this payload and nothing else.

    `status` and `stdout` are the two ways the answer goes wrong -- a call that
    failed, and one that answered with something that is not JSON."""
    text = stdout if stdout is not None else json.dumps(payload or {})
    gh = Path(bindir) / "gh"
    gh.write_text("#!/bin/sh\n"
                  f"cat <<'JSON'\n{text}\nJSON\n"
                  f"exit {status}\n")
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


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        bindir = Path(d) / "bin"
        bindir.mkdir()

        # ---- the gate ------------------------------------------------------

        # PR #262's shape: comments on the pull request, and not one of them
        # opens REVIEW. This is the branch that had no reader at all.
        fake_gh(bindir, {"headRefOid": HEAD,
                         "comments": [comment(f"REPORT upkeep-worker-3: at {HEAD[:7]}"),
                                      comment("NOTE upkeep-worker-3: a note")],
                         "reviews": []})
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request whose comments hold no REVIEW is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the head it read",
              HEAD in text, text)
        check("...and says how many comments it read",
              "2 comment(s) read" in text, text)

        # A REVIEW that names an older sha is the same refusal from the sha's
        # end: the review it points at is at a revision nobody will merge.
        fake_gh(bindir, {"headRefOid": HEAD,
                         "comments": [comment(f"REVIEW upkeep-worker-3: full round at "
                                              f"{OTHER[:7]}, no findings")],
                         "reviews": []})
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming a sha that is not the head is unreviewed",
              (word, code) == ("unreviewed", 1), f"{word} {code}")
        check("...and the refusal prints the sha that REVIEW did name",
              OTHER[:7] in text, text)

        # CONTROL: the gate is not one that refuses every pull request.
        fake_gh(bindir, {"headRefOid": HEAD,
                         "comments": [comment(f"REVIEW upkeep-worker-3: full round at "
                                              f"{HEAD[:7]}, no findings")],
                         "reviews": []})
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW naming the head is reviewed", (word, code) == ("reviewed", 0),
              f"{word} {code}")

        # ...and a REVIEW posted as a pull-request review, not as a comment,
        # counts too. `gh pr review --comment -b` is a spelling AGENTS.md
        # admits, and reading only `comments` refused it.
        fake_gh(bindir, {"headRefOid": HEAD, "comments": [],
                         "reviews": [comment(f"REVIEW upkeep-worker-3: at {HEAD[:7]}")]})
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a REVIEW posted as a pull-request review counts",
              (word, code) == ("reviewed", 0), f"{word} {code}")

        # A sha too short to be one is not one: six hex characters is an issue
        # number or a colour, and matching it would pass a REVIEW that pins
        # nothing.
        fake_gh(bindir, {"headRefOid": HEAD,
                         "comments": [comment(f"REVIEW upkeep-worker-3: at {HEAD[:6]}")],
                         "reviews": []})
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("six hex characters do not name a sha",
              (word, code) == ("unreviewed", 1), f"{word} {code}")

        # ---- could not look, which is never a pass -------------------------

        fake_gh(bindir, {"headRefOid": HEAD}, status=1)
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("a gh call that failed is unknown, not a pass",
              (word, code) == ("unknown", 2), f"{word} {code}")

        fake_gh(bindir, stdout="not json at all")
        word, code, _ = call(bindir, "274", "--repo", "o/r")
        check("an answer that is not JSON is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")

        fake_gh(bindir, {"comments": [], "reviews": []})
        word, code, text = call(bindir, "274", "--repo", "o/r")
        check("a pull request with no headRefOid is unknown",
              (word, code) == ("unknown", 2), f"{word} {code}")
        check("...and says there is no sha to read a review against",
              "headRefOid" in text, text)

        # ---- the REPORT's end ----------------------------------------------

        fake_gh(bindir, {"headRefOid": HEAD, "comments": [], "reviews": []})

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

    for name in FAILED:
        print(f"FAIL  {name}")
    print(f"{len(RAN) - len(FAILED)}/{len(RAN)} cases pass")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
