#!/usr/bin/env python3
"""Print the comments a worker must read for one sub-issue, gathered from GitHub.

    campaign-context.py <issue> [owner/repo]

`owner/repo` is the tracker the sub-issue is filed on, the base by default.

WHY IT EXISTS. A worker is assigned by one sentence naming the sub-issue, and
reads the body. The DECISION, NOTE, BLOCKED and REVIEW comments on that issue,
on what its body cites, and the campaign issue's NOTEs naming it reach it only
if the planner points at them (rule-check#416). This gathers them, through
`gh` alone, in one fixed order:

  1. the issue's own comments whose first line carries a kind, any of the
     five, oldest first;
  2. one hop: the DECISION and NOTE comments of each `<slug>#N`, and the
     REVIEW comments and review bodies of each `pr#N`, that the body or those
     own comments cite, one read per number whatever slug it wears. The
     issue itself and its parent are not followed --
     section 3 reads the parent -- and a bare `#N` names no campaign
     (AGENTS.md § Sub-issues), so it is never followed. A pull request is read
     on the repository the body's `## Lands in` names;
  3. the parent campaign issue's NOTE and DECISION comments citing this issue
     as `<slug>#N`.

A ROW is the kind, the author the first line names, the date, the comment id,
the rest of the first line, then the body under COMMENT_CAP characters. The
whole print holds at most ROW_CEILING rows, shared out own rows first, then the
campaign issue's, then the hop's -- the first two are about this issue, the
hop only near it -- and a thread over its share keeps its newest rows and says
how many it cut and where its full thread is. Both numbers are printed beside
what they measured.

WHAT IT OWNS AND WHAT IT BORROWS. The kind-line grammar is
check-campaign-claim.py's `comment_first_line`, the slug is
campaign-name-session.py's `SLUG`, the `gh` call shape campaign-tracker.py's
`gh_read`, and `## Lands in` campaign-repos.py's `lands_in`: each is imported,
none restated.

EXIT. 0 when every reading was made. 1 when any was not: that section prints
`unread` and what `gh` said, and every other section still prints, since a
worker needs what was read more than it needs a clean status.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(src, alias):
    """The script at `src` as a module: these are scripts, not a package."""
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TRACKER = load(HERE / "campaign-tracker.py", "campaign_tracker")
GUARD = load(HERE / "check-campaign-claim.py", "check_campaign_claim")
NAMES = load(HERE.parent / ".claude" / "skills" / "assuming-role" / "scripts"
             / "campaign-name-session.py", "campaign_name_session")
REPOS = TRACKER.REPOS

# The body of one row, in characters, and the rows in one print. A DECISION
# rarely needs more than the cap to be read, and the ceiling bounds the print at
# about 30K characters however many threads the body cites.
COMMENT_CAP = 1000
ROW_CEILING = 30

# `<slug>#N` and `pr#N`, the forms AGENTS.md § Sub-issues spells. The slug is
# NAMES.SLUG's body; a preceding `/` keeps `owner/repo#N` out, which names an
# issue on another tracker.
CITATION = re.compile(r"(?<![\w/-])(" + NAMES.SLUG.pattern.strip("^$")
                      + r")#(\d+)(?!\d)")
PR = "pr"

OWN_KINDS = GUARD.COMMENT_KINDS
ISSUE_KINDS = ("DECISION", "NOTE")
PR_KINDS = ("REVIEW",)
# The kind-line pattern, built in `main` by the guard's own reader.
FIRST_LINE = None


def gh(*args):
    """(parsed JSON, why unreadable) for one `gh` call."""
    text, why = TRACKER.gh_read(["gh", *args])
    if why:
        return None, why
    try:
        return json.loads(text), None
    except ValueError as e:
        return None, f"gh printed something that is not JSON ({e.__class__.__name__})"


def comments(repo, number, reviews=False):
    """(comments, what was read, why unreadable). Review bodies join a pull
    request's comments, since `gh pr review` posts a REVIEW there too."""
    paths = [f"repos/{repo}/issues/{number}/comments?per_page=100"]
    if reviews:
        paths.append(f"repos/{repo}/pulls/{number}/reviews?per_page=100")
    out = []
    for path in paths:
        data, why = gh("api", "--paginate", path)
        if why is None and not isinstance(data, list):
            why = f"gh returned {type(data).__name__}, not a list"
        if why:
            return None, " and ".join(paths), why
        out += data
    return out, " and ".join(paths), None


def kind_line(body):
    """(kind, author, rest of the first line), or None when the first line
    opens with no kind. The first line is taken as the guard takes it."""
    text = (body or "").strip()
    first = text.splitlines()[0] if text else ""
    if not FIRST_LINE.match(first):
        return None
    kind, rest = first.split(" ", 1)
    author, _, line = rest.partition(":")
    return kind, author, line.strip()


def citations(text):
    """Every cited `(slug, number)` in `text`, first appearance first, one per
    number: every slug but `pr` names the same tracker, so `a#5` and `b#5` are
    one issue and are read once, under the slug seen first."""
    seen, out = set(), []
    for m in CITATION.finditer(text or ""):
        slug, n = m.group(1), int(m.group(2))
        if (slug == PR, n) not in seen:
            seen.add((slug == PR, n))
            out.append((slug, n))
    return out


class Block:
    """One thread's reading: its heading, and its rows or why it did not read."""

    def __init__(self, head, items=None, kinds=(), keep=lambda c: True, why=None):
        self.head, self.why, self.items = head, why, items or []
        self.rows = sorted(
            ((c.get("created_at") or c.get("submitted_at") or "", c, parsed)
             for c in self.items
             if (parsed := kind_line(c.get("body"))) and parsed[0] in kinds
             and keep(c)),
            key=lambda r: r[0])
        self.allowed = len(self.rows)


def allot(blocks):
    """Share ROW_CEILING out: own rows first, then the campaign issue's, then
    the hop's in print order, since the first two are about this issue and the
    hop only near it. A block over its share keeps its newest rows, which
    supersede the older ones. Returns the rows cut."""
    left, cut = ROW_CEILING, 0
    for b in blocks:
        b.allowed = min(len(b.rows), left)
        left -= b.allowed
        cut += len(b.rows) - b.allowed
    return cut


def show(b, counts):
    """Print one block; `counts` gathers the unread and cut bodies."""
    print(b.head)
    if b.why:
        counts["unread"] += 1
        print(f"  unread: {b.why}")
        return
    print(f"  {len(b.items)} comment(s) read, {len(b.rows)} kept")
    if not b.rows:
        print("  (empty)")
    dropped = len(b.rows) - b.allowed
    if dropped:
        print(f"  {dropped} oldest row(s) cut by the ceiling of {ROW_CEILING}; "
              f"full thread: {b.rows[0][1]['html_url'].split('#')[0]}")
    for when, c, (kind, author, line) in b.rows[dropped:]:
        cid = (c.get("html_url") or "").rpartition("#")[2] or str(c.get("id"))
        print(f"- {kind} {author} {when[:10]} {cid}: {line}")
        body = "\n".join(c["body"].strip().splitlines()[1:]).strip()
        note = ""
        if len(body) > COMMENT_CAP:
            counts["bodies"] += 1
            note = f"... body {len(body)} chars, cut at {COMMENT_CAP}"
            body = body[:COMMENT_CAP]
        for ln in body.splitlines() + ([note] if note else []):
            print(f"    {ln}")


def reading(head, repo, number, kinds, reviews=False, keep=lambda c: True):
    items, read, why = comments(repo, number, reviews)
    return Block(f"{head}\n  read gh api {read}", items, kinds, keep, why)


def pr_repo(body, tracker):
    """(repository pull requests are read on, what said so)."""
    raw, why = REPOS.lands_in(body or "")
    if why:
        return tracker, f"the tracker, since ## Lands in did not read ({why})"
    if raw.strip(REPOS.WRAPPERS).lower() == REPOS.NONE:
        return tracker, "## Lands in: none"
    return REPOS.slug(raw), "## Lands in"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("issue")
    ap.add_argument("repo", nargs="?", default=TRACKER.DEFAULT_REPO)
    args = ap.parse_args()
    issue, repo = int(args.issue.lstrip("#")), args.repo

    global FIRST_LINE
    FIRST_LINE = GUARD.comment_first_line()
    if FIRST_LINE is None:
        print(f"could not look: {GUARD.FIRST_LINE_UNREADABLE}", file=sys.stderr)
        return 1

    print(f"campaign-context: {repo}#{issue}, read through gh; at most "
          f"{ROW_CEILING} rows, each body at most {COMMENT_CAP} chars")
    view, why = gh("issue", "view", str(issue), "-R", repo,
                   "--json", "body,url,parent")
    if why:
        print(f"unread: gh issue view {issue} -R {repo}: {why}")
        return 1
    body = view.get("body") or ""
    parent = (view.get("parent") or {}).get("number")

    own = reading(f"\n== 1. {repo}#{issue}'s own comments, kinds "
                  f"{', '.join(OWN_KINDS)}", repo, issue, OWN_KINDS)

    cited = citations("\n".join([body] + [c["body"] for _, c, _ in own.rows]))
    follow = [r for r in cited if not (r[0] != PR and r[1] in (issue, parent))]
    prs_on, said = pr_repo(body, repo)
    hop = []
    for slug, n in ([r for r in follow if r[0] != PR]
                    + [r for r in follow if r[0] == PR]):
        if slug == PR:
            hop.append(reading(f"-- pr#{n} on {prs_on} ({said}), kinds "
                               f"{', '.join(PR_KINDS)}", prs_on, n, PR_KINDS,
                               reviews=True))
        else:
            hop.append(reading(f"-- {slug}#{n}, kinds {', '.join(ISSUE_KINDS)}",
                               repo, n, ISSUE_KINDS))

    head3 = (f"\n== 3. the campaign issue's {', '.join(ISSUE_KINDS)} citing "
             f"{repo}#{issue}")
    camp = None
    if parent is not None:
        camp = reading(f"{head3}\n  {repo}#{parent}", repo, parent, ISSUE_KINDS,
                       keep=lambda c: any(s != PR and n == issue
                                          for s, n in citations(c["body"])))

    cut = allot([own] + ([camp] if camp else []) + hop)
    counts = {"unread": 0, "bodies": 0}
    show(own, counts)
    print("\n== 2. one hop: what the body and those comments cite")
    if not hop:
        print("  (empty: the body and those comments cite nothing to follow)")
    for b in hop:
        show(b, counts)
    if camp:
        show(camp, counts)
    else:
        print(f"{head3}\n  (empty: {repo}#{issue} has no parent)")

    printed = sum(b.allowed for b in [own] + hop + ([camp] if camp else []))
    print(f"\nrows: {printed} printed, {cut} cut by the ceiling of "
          f"{ROW_CEILING}; {counts['bodies']} body(ies) cut at {COMMENT_CAP} "
          f"chars" + (f"; {counts['unread']} section(s) unread"
                      if counts["unread"] else ""))
    return 1 if counts["unread"] else 0


if __name__ == "__main__":
    sys.exit(main())
