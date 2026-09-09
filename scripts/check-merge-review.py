#!/usr/bin/env python3
"""Refuse a merge with no REVIEW at the sha being merged.

    check-merge-review.py <pr> [--repo OWNER/REPO]
                        THE MERGE GATE. Reads the pull request's head sha and
                        every comment on it, and answers whether any comment
                        opening `REVIEW` names that head. The FIRST WORD of the
                        answer is `reviewed`, `unreviewed` or `unknown`, and the
                        status agrees: 0, 1, 2.
    check-merge-review.py <pr> --report FILE|-  [--repo OWNER/REPO]
                        THE SAME GAP FROM THE OTHER END. Judges a REPORT
                        comment's body -- from a file, or `-` for stdin --
                        against the same head: a REPORT pinning any other sha
                        asks for a review at a revision nobody is going to
                        merge. The first word is `pinned`, `stale` or
                        `unknown`, and the status agrees: 0, 1, 2.

WHAT THIS IS FOR

Merge condition 1 in AGENTS.md -- a review read at the sha being merged -- was
readable and read by nothing. PR kalaluthien/campaign-base#262 merged at 8ca2609
carrying no comment opening `REVIEW` and no pull-request review at all, and
nothing on the machine or in CI refused it. This is that reader. The model is
`mergeReadsTheReview` in spec/campaign/orchestration/scenarios.als, and
`AReadingIsOfAReview` in the sibling system module is why a reading implies the
condition rather than merely accompanying it.

CONDITION 2 IS NOT HERE. One `gh` account signs every session's writes, so who
wrote a REVIEW is not a fact this can read; AGENTS.md says as much and this
narrows to the half GitHub can answer. A REVIEW naming the head is the whole
verdict.

WHAT NAMES A SHA

A body names the head when it holds a hex run of at least MIN_ABBREV characters
that the head sha starts with. Abbreviated, because that is how every REVIEW and
REPORT in this tracker pins one (`full round at fb1bd4f`), and prefix-matched
against the head rather than pattern-matched on its own, so a sha that is not
this head's is not mistaken for it.

WHICH COMMENTS ARE READ

Issue comments on the pull request and pull-request reviews alike. AGENTS.md
admits both spellings -- `gh pr comment` and `gh pr review --comment -b` are
both `COMMENT_WRITES` in check-campaign-claim.py -- so reading one of them would
refuse a correctly written REVIEW for the channel it arrived on.

THE FIRST LINE IS NOT PARSED HERE. `check-campaign-claim.py` owns what
`KIND <session name|owner>: <one line>` is; this imports that pattern and reads
which kind matched. A pattern that will not load is `unknown`, never a pass:
with no way to tell a REVIEW from a NOTE there is no reading to report.

EXIT

0 answered yes, 1 answered no -- the refusal -- and 2 could not look. The two
are apart on purpose, and CI fails on either: a pull request whose comments went
unread is not a pull request with a review on it.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "check-campaign-claim.py"
REPOS = HERE / "campaign-repos.py"

# SEVEN, which is git's own floor for an abbreviation and this tracker's habit.
# Shorter is not a sha anybody writes, and matching it would let a four-digit
# issue number stand in for a revision.
MIN_ABBREV = 7
# A hex run, bounded so a sha inside a longer word is not read as one.
SHA = re.compile(r"\b([0-9a-f]{%d,40})\b" % MIN_ABBREV)


def load(path, name):
    """(module, why). A module that will not load is a reading not made."""
    try:
        spec = importlib.util.spec_from_loader(
            name, importlib.machinery.SourceFileLoader(name, str(path)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:                      # noqa: BLE001 -- reported
        return None, f"{path}: {e.__class__.__name__}: {e}"
    return module, None


def default_repo():
    """The base's name, from the script that owns it. A fourth copy of the
    string is the copy that drifts when the repository is renamed."""
    module, why = load(REPOS, "campaign_repos")
    return (module.BASE_REPO if module else None), why


def run(*args):
    """(returncode, stdout, stderr). A missing `gh` is a status, not a stack
    trace: this runs in CI and inside another script's refusal path."""
    try:
        p = subprocess.run(args, capture_output=True, text=True)
    except OSError as e:
        return 127, "", f"{args[0]}: {e}"
    return p.returncode, p.stdout, p.stderr


def kind_of(body, pattern):
    """The comment kind this body opens with, or None when its first line is
    not one. The SHAPE is the imported pattern's; all this adds is which of the
    kinds it admits actually matched, which the pattern guarantees is the first
    space-separated word."""
    lines = (body or "").lstrip().splitlines()
    if not lines:
        return None
    line = lines[0].strip()
    if not pattern.match(line):
        return None
    return line.split(" ", 1)[0]


def names(body, head):
    """Every sha in this body that the head starts with, and every one it does
    not -- both, because the refusal has to say what it read instead."""
    hit, miss = [], []
    for sha in SHA.findall(body or ""):
        (hit if head.startswith(sha) else miss).append(sha)
    return hit, miss


def comments_of(repo, pr):
    """(head, [(where, author, body)], why). One `gh` call, three fields.

    `headRefOid` is the head of the BRANCH, which is the sha a merge of this
    pull request lands and the sha a required status attaches to -- not the
    runner's merge commit, which exists only inside a checkout."""
    code, out, err = run("gh", "pr", "view", str(pr), "-R", repo, "--json",
                         "headRefOid,comments,reviews")
    if code != 0:
        return None, None, (f"gh pr view {pr} -R {repo} exited {code}: "
                            f"{(err or '').strip()[:200]}")
    try:
        data = json.loads(out or "{}")
    except json.JSONDecodeError as e:
        return None, None, f"{repo}#{pr} answered with something that is not JSON: {e}"
    head = data.get("headRefOid")
    if not head:
        return None, None, (f"{repo}#{pr} came back with no headRefOid, so "
                            f"there is no sha to read a review against")
    found = []
    for where, rows in (("comment", data.get("comments") or []),
                        ("review", data.get("reviews") or [])):
        for row in rows:
            found.append((where, (row.get("author") or {}).get("login") or "?",
                          row.get("body") or ""))
    return head, found, None


def answer(word, line, extra=()):
    """THE WORD IS THE ANSWER and it is printed first, on stdout for a caller
    that reads it and stderr for the two that are refusals. The status agrees
    with the word; a caller that read the status alone could not tell a pull
    request with no review from one nobody could ask about."""
    status = {"reviewed": 0, "pinned": 0, "unreviewed": 1, "stale": 1,
              "unknown": 2}[word]
    stream = sys.stdout if status == 0 else sys.stderr
    print(f"{word} check-merge-review: {line}", file=stream)
    for note in extra:
        print(f"  {note}", file=stream)
    return status


def gate(repo, pr, pattern):
    """Is there a REVIEW at this pull request's head?"""
    head, found, why = comments_of(repo, pr)
    if why:
        return answer("unknown", why,
                      ["A pull request that could not be read is not a pull "
                       "request with a review on it."])
    reviews, read, other = [], [], []
    for where, author, body in found:
        kind = kind_of(body, pattern)
        if kind != "REVIEW":
            other.append(f"{where} by {author}: {kind or 'no kind on its first line'}")
            continue
        hit, miss = names(body, head)
        reviews.append((where, author, hit, miss))
        read.extend(hit + miss)
    trail = [f"head {head} on {repo}#{pr}",
             f"{len(found)} comment(s) read; {len(reviews)} open REVIEW",
             ("shas named by those REVIEWs: " + ", ".join(read)) if read
             else "those REVIEWs name no sha"]
    trail += [f"  not a REVIEW -- {note}" for note in other]
    for where, author, hit, _miss in reviews:
        if hit:
            return answer("reviewed",
                          f"a REVIEW ({where} by {author}) names {hit[0]}, "
                          f"which is the head {head[:12]} of {repo}#{pr}", trail)
    return answer("unreviewed",
                  f"no comment opening REVIEW names the head {head} of "
                  f"{repo}#{pr}", trail
                  + ["A merge needs a review read AT the sha being merged "
                     "(AGENTS.md, merge condition 1)."])


def report(repo, pr, body, pattern):
    """Does this REPORT pin the head? A REPORT that pins anything else asks for
    a review at a revision nobody is going to merge."""
    head, _found, why = comments_of(repo, pr)
    if why:
        return answer("unknown", why,
                      ["A head that could not be read cannot say whether a "
                       "REPORT pins it."])
    kind = kind_of(body, pattern)
    if kind != "REPORT":
        return answer("unknown",
                      f"this body opens {kind or 'no kind'}, not REPORT, so "
                      f"there is no REPORT here to judge",
                      [f"head {head} on {repo}#{pr}",
                       "Comment shape is check-campaign-claim.py's; this reads "
                       "a REPORT's sha and nothing else."])
    hit, miss = names(body, head)
    trail = [f"head {head} on {repo}#{pr}",
             ("shas named: " + ", ".join(hit + miss)) if (hit or miss)
             else "this REPORT names no sha"]
    if hit:
        return answer("pinned", f"this REPORT names {hit[0]}, which is the "
                                f"head {head[:12]} of {repo}#{pr}", trail)
    if miss:
        return answer("stale", f"this REPORT names {', '.join(miss)}, and the "
                               f"head of {repo}#{pr} is {head}", trail
                      + ["A REPORT that pins a sha other than the head asks "
                         "for a review nobody will merge at."])
    return answer("stale", f"this REPORT names no sha, and the head of "
                           f"{repo}#{pr} is {head}", trail
                  + ["A REPORT that does not pin its sha is unactionable "
                     "(AGENTS.md, § The four messages)."])


def read_body(where):
    """(body, why). `-` is stdin, so a caller can pipe the comment it is about
    to post rather than writing it out twice."""
    if where == "-":
        try:
            return sys.stdin.read(), None
        except OSError as e:
            return None, f"stdin: {e}"
    try:
        return Path(where).read_text(), None
    except OSError as e:
        return None, f"{where}: {e}"


def main() -> int:
    base, repo_why = default_repo()
    ap = argparse.ArgumentParser(
        description="Refuse a merge with no REVIEW at the sha being merged.")
    ap.add_argument("pr", type=int, help="the pull request number")
    ap.add_argument("--repo", default=base,
                    help=f"owner/repo the pull request is on (default: "
                         f"{base or 'unreadable -- pass --repo'})")
    ap.add_argument("--report", metavar="FILE",
                    help="judge this REPORT body's sha instead, `-` for stdin")
    args = ap.parse_args()
    if not args.repo:
        return answer("unknown", f"no --repo was given and {repo_why}")
    # THE FIRST-LINE RULE, IMPORTED. None is could-not-look and not a bad
    # shape: with no way to tell a REVIEW from a NOTE this has read nothing,
    # and reporting a pass would be the silent downgrade the whole check exists
    # to stop.
    guard, why = load(GUARD, "guard")
    if why:
        return answer("unknown", f"could not import the comment-kind reading "
                                 f"-- {why}")
    pattern = guard.comment_first_line()
    if pattern is None:
        return answer("unknown", f"the comment-kind reading would not build: "
                                 f"{guard.FIRST_LINE_UNREADABLE}")
    if args.report is None:
        return gate(args.repo, args.pr, pattern)
    body, why = read_body(args.report)
    if why:
        return answer("unknown", f"could not read the REPORT body -- {why}")
    return report(args.repo, args.pr, body, pattern)


if __name__ == "__main__":
    sys.exit(main())
