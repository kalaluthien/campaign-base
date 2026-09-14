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
     own comments cite. The issue itself and its parent are not followed --
     section 3 reads the parent -- and a bare `#N` names no campaign
     (AGENTS.md § Sub-issues), so it is never followed. A pull request is read
     on the repository the body's `## Lands in` names;
  3. the parent campaign issue's NOTE and DECISION comments citing this issue
     as `<slug>#N`.

A ROW is the kind, the author the first line names, the date, the comment id,
the rest of the first line, then the body under COMMENT_CAP characters. The
whole print holds at most ROW_CEILING rows; a section losing rows to it says
how many and where its full thread is. Both numbers are printed beside what
they measured.

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
    """Every `(slug, number)` cited in `text`, first appearance first."""
    seen = []
    for m in CITATION.finditer(text or ""):
        ref = (m.group(1), int(m.group(2)))
        if ref not in seen:
            seen.append(ref)
    return seen


class Printer:
    """Rows under the one ceiling, and the counts the last line prints."""

    def __init__(self):
        self.printed = self.cut = self.bodies_cut = 0
        self.unread = 0

    def rows(self, items, kinds, keep=lambda c: True):
        """Print the items opening with one of `kinds`, oldest first."""
        kept = []
        for c in items:
            parsed = kind_line(c.get("body"))
            if parsed and parsed[0] in kinds and keep(c):
                kept.append((c.get("created_at") or c.get("submitted_at") or "",
                             c, parsed))
        kept.sort(key=lambda k: k[0])
        print(f"  {len(items)} comment(s) read, {len(kept)} kept")
        if not kept:
            print("  (empty)")
        for n, (when, c, (kind, author, line)) in enumerate(kept):
            if self.printed >= ROW_CEILING:
                left = len(kept) - n
                self.cut += left
                print(f"  {left} row(s) cut by the ceiling of {ROW_CEILING}; "
                      f"full thread: {c['html_url'].split('#')[0]}")
                return
            self.printed += 1
            cid = c.get("html_url", "").rpartition("#")[2] or str(c.get("id"))
            print(f"- {kind} {author} {when[:10]} {cid}: {line}")
            body = "\n".join(c["body"].strip().splitlines()[1:]).strip()
            if len(body) > COMMENT_CAP:
                self.bodies_cut += 1
                note = f"... body {len(body)} chars, cut at {COMMENT_CAP}"
                body = body[:COMMENT_CAP]
            else:
                note = ""
            for ln in (body.splitlines() + ([note] if note else [])):
                print(f"    {ln}")

    def unreadable(self, why):
        self.unread += 1
        print(f"  unread: {why}")


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

    p = Printer()
    print(f"campaign-context: {repo}#{issue}, read through gh; at most "
          f"{ROW_CEILING} rows, each body at most {COMMENT_CAP} chars")
    view, why = gh("issue", "view", str(issue), "-R", repo,
                   "--json", "body,url,parent")
    if why:
        print(f"unread: gh issue view {issue} -R {repo}: {why}")
        return 1
    body = view.get("body") or ""
    parent = (view.get("parent") or {}).get("number")

    print(f"\n== 1. {repo}#{issue}'s own comments, kinds {', '.join(OWN_KINDS)}")
    own, read, why = comments(repo, issue)
    print(f"  read gh api {read}")
    own_kept = []
    if why:
        p.unreadable(why)
    else:
        own_kept = [c for c in own if kind_line(c.get("body"))]
        p.rows(own, OWN_KINDS)

    print("\n== 2. one hop: what the body and those comments cite")
    cited = citations("\n".join([body] + [c["body"] for c in own_kept]))
    follow = [r for r in cited
              if not (r[0] != PR and r[1] in (issue, parent))]
    prs_on, said = pr_repo(body, repo)
    if not follow:
        print("  (empty: the body and those comments cite nothing to follow)")
    for slug, n in [r for r in follow if r[0] != PR] + \
                   [r for r in follow if r[0] == PR]:
        if slug == PR:
            print(f"-- pr#{n} on {prs_on} ({said}), kinds {', '.join(PR_KINDS)}")
            items, read, why = comments(prs_on, n, reviews=True)
            kinds = PR_KINDS
        else:
            print(f"-- {slug}#{n}, kinds {', '.join(ISSUE_KINDS)}")
            items, read, why = comments(repo, n)
            kinds = ISSUE_KINDS
        print(f"  read gh api {read}")
        if why:
            p.unreadable(why)
        else:
            p.rows(items, kinds)

    print(f"\n== 3. the campaign issue's {', '.join(ISSUE_KINDS)} citing "
          f"#{issue}")
    if parent is None:
        print(f"  (empty: {repo}#{issue} has no parent)")
    else:
        items, read, why = comments(repo, parent)
        print(f"  {repo}#{parent}; read gh api {read}")
        if why:
            p.unreadable(why)
        else:
            p.rows(items, ISSUE_KINDS, keep=lambda c: any(
                s != PR and n == issue for s, n in citations(c["body"])))

    print(f"\nrows: {p.printed} printed, {p.cut} cut by the ceiling of "
          f"{ROW_CEILING}; {p.bodies_cut} body(ies) cut at {COMMENT_CAP} chars"
          + (f"; {p.unread} section(s) unread" if p.unread else ""))
    return 1 if p.unread else 0


if __name__ == "__main__":
    sys.exit(main())
