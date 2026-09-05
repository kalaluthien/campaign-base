#!/usr/bin/env python3
"""Read the campaign plane: its campaign issues, its binding, its index, its settlement.

    campaign-tracker.py campaign-issues [--repo owner/repo] [--limit N]
    campaign-tracker.py bound <N> [owner/repo]
    campaign-tracker.py bind <N> [owner/repo]
    campaign-tracker.py check <N> [owner/repo] [--plan]
    campaign-tracker.py index <N> [owner/repo]
    campaign-tracker.py settlement <N> [owner/repo]

Five readings of one plane -- GitHub issues, plus `hostname -s` for `bound`,
and the one write that changes what `bound` answers.
They were four scripts, and every one of them carried the same lesson in its own
words: a listing that stopped early reads exactly like a complete one, and a
reading that did not happen reads exactly like an empty tracker. One script means
one place that gets it right.

**Read the printed word, never the exit status.** The status is about the
reading; the verdict is on stdout. `bound` in particular prints `here`,
`elsewhere <machine>`, or `unbound`, and only `here` licenses a campaign-wide
write -- a failed read that exited like `unbound` would invite a session to bind
a campaign another machine is working.

WHAT EACH SUBCOMMAND OWNS

campaign-issues     The open-campaign issue survey, and the two ways its readings disagree.
            Both readings come off ONE listing: an earlier version made two `gh`
            calls and inferred a property from *absence* in the other, which
            denounced a real campaign issue as a sub-issue wearing the label. `--limit` is
            raised past `gh`'s default of thirty because campaign issues are the oldest
            issues here, and a listing that comes back *at* the limit refuses
            rather than printing rows that are wrong rather than merely short.

bound       The one reader of the `bound:<machine>` LABEL. A label set is read
            by exact name and carries no history, so the four things the comment
            reading had to get right -- paginating a thread, taking the LAST
            match rather than the first, reading only the first line, and
            stripping a carriage return off a body stored with CRLF -- are four
            ways to be wrong that no longer exist. What replaces them is one
            state this refuses rather than resolves: TWO `bound:` labels on one
            campaign issue. A thread has a latest and a label set has not, so no
            rule could pick between them, and guessing hands one machine a
            campaign another is working. The comparison against this machine is
            folded in, because every caller ran `hostname -s` on its next line
            and compared by eye.

bind        The write `bound` reads. It adds `bound:<this machine>` and removes
            every other `bound:` label in the same edit, so the refusal above is
            a state this command cannot leave behind. Gated by the person's word
            and by nothing here: AGENTS.md names the two cases a session binds
            in, and neither has a premise anything mechanical can observe.

check       The one reader of an issue's SHAPE (kalaluthien/campaign-base#217)
            except its destination, which `campaign-repos.py`'s `lands_in`
            owns and this asks:
            its title length, its body length, and the sections its kind
            requires. The kind is decided by structure alone -- the `campaign`
            label and the parent link, the two facts GitHub itself holds --
            because the reading it replaces classified by BODY TEXT, so an
            issue that happened to contain `## Repos` was a campaign to one
            reader and not to another.

            IT IS ITS OWN VERB AND NOT PART OF `bind`. `bind` is the only
            repair for the two-`bound:`-label state, and a `bind` that refused
            an oversize body would refuse to run on exactly the campaign that
            needs repairing. So `bind` calls this and prints what it said, and
            never gates on it; `campaign-claim take` calls it and does gate,
            because a claim is the moment a brief becomes somebody's work.

            `--plan` adds `## Plan` to what a sub-issue must carry. Two moments,
            one shape: a sub-issue is FILED with the intent, the destination and
            the definition of done, and gains its plan before anybody is
            prompted onto it, so a worker reads one issue and nobody plans in a
            pane. `take` passes the flag; a bare `check` does not.

            WHAT IT DOES NOT CHECK, printed on every run: whether a title is
            verb-first, whether a body is bullets rather than prose, whether a
            `Done when` is checkable. Those are judgement and stay prose. Nor
            does it reach issues nobody claims or binds -- the ceiling is a cut
            applied at two moments, not a property of the tracker.

index       The sub-issue index -- the whole of it. `gh issue create --parent` is
            the only write that records a campaign's membership and this endpoint
            is the only read. It pages at thirty, and the close is the one place
            the index is read before a directory is deleted.

settlement  The observable spec/campaign/ scenarios are judged by. Verdicts match
            spec/campaign/github/system.als: `complete` (closed, and a pull request that
            closed it is merged), `dropped` (closed with no merged pull request),
            `open`. Settled is "the issue is closed", both verdicts alike; the
            merged pull request only says which kind.

            Each OPEN row also carries whether its claim branch exists,
            read off the remote's `campaign-<N>/` refs through campaign-claim's
            own reader: `claimed: <branch>`, or `unclaimed`. That column is what
            an open sub-issue nobody had started was missing -- it read exactly
            like one somebody was three hours into. When the ref listing does
            not happen the column is EMPTY and a note says so, because printing
            `unclaimed` for a listing nobody made is the absence dressed as a
            reading that this exists to end. It says nothing about WHO is
            standing in the branch; that is `campaign-claim live`, and it is a
            per-machine reading where this table is not.

`settlement` reads the index through `index`'s own reader rather than issuing its
own request. Moving only the parse behind a script once left `--paginate`
hand-written in the settlement path, where deleting it turned a live campaign's
verdict from "NOT closable" into "closable" with fourteen sub-issues silently gone
and nothing red.

scripts/check-rule-readers.py is the second reader that keeps these claims true: it
refuses a commit that stages a hand-rolled copy of the campaign issue survey, the index
read, or the settlement verdict as code in any tracked markdown outside scripts/.
It catches a pasted copy, not a re-implementation that names nothing.

EXIT

campaign-issues, index, settlement  0 when the reading was made, 1 when it was not.
bound                       0 for any verdict, 2 when the reading itself failed
                            -- two `bound:` labels included, since that is a
                            question this refuses to answer, not a verdict.
bind                        0 when the label was set, 1 when it was not.
check                       0 when the shape holds (a third-kind issue included,
                            which is asked for no SECTION -- both ceilings still
                            apply to it), 1 when it does not, 2 when the issue
                            could not be read at all.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "kalaluthien/campaign-base"
CAMPAIGN_LABEL = "campaign"
BOUND_LABEL_PREFIX = "bound:"

NOT_EMPTY = "An index that did not read is not an empty campaign."


def gh_read(cmd):
    """Run a `gh` invocation for its stdout. Returns (text, why_unreadable).

    A `gh` that is not installed comes back as a failed run rather than a
    traceback: "I could not look" is the case every reader here is written to
    report, and a stack trace loses the reason the caller was about to print."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except (FileNotFoundError, PermissionError) as e:
        return None, f"could not run gh ({e.__class__.__name__})"
    if r.returncode != 0:
        return None, f"gh exited {r.returncode}: {r.stderr.strip()[:200]}"
    return r.stdout, None


# --------------------------------------------------------------------- campaign issues


def listing(repo, limit):
    cmd = ["gh", "issue", "list", "-R", repo, "--state", "open",
           "--limit", str(limit), "--json", "number,title,labels,parent"]
    text, why = gh_read(cmd)
    if why:
        return None, why
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, f"could not parse gh's output ({e.__class__.__name__})"
    if not isinstance(data, list):
        return None, f"gh returned {type(data).__name__}, not a list of issues"
    return data, None


def classify(issues):
    """Split one listing by its two readings. Returns (campaign issues, stray, bare).

    Every issue carries both properties, so each row is decided by what that
    issue itself says -- never by its absence from somewhere else."""
    def labelled(i):
        return any(l.get("name") == CAMPAIGN_LABEL for l in i.get("labels") or [])
    campaign_issues = [i for i in issues if labelled(i) and not i.get("parent")]
    stray = [i for i in issues if labelled(i) and i.get("parent")]
    bare = [i for i in issues if not labelled(i) and not i.get("parent")]
    return campaign_issues, stray, bare


def rows(title, items, note=""):
    print(f"\n{title} ({len(items)})" + (f" -- {note}" if note else ""))
    for i in sorted(items, key=lambda x: x["number"]):
        print(f"  #{i['number']:<5} {i['title'][:88]}")


def cmd_campaign_issues(args):
    issues, why = listing(args.repo, args.limit)
    if why:
        print(f"campaign-tracker campaign-issues: could not read {args.repo} -- {why}\n"
              f"  A reading that did not happen is not an empty tracker.",
              file=sys.stderr)
        return 1
    print(f"read {args.repo}, limit {args.limit}: {len(issues)} open issue(s)")
    if len(issues) >= args.limit:
        print(f"REFUSING: the listing came back at --limit {args.limit}, so it "
              f"may be truncated,\n  and a truncated listing reads exactly like "
              f"a complete one. Raise --limit and re-run.", file=sys.stderr)
        return 1

    campaign_issues, stray, bare = classify(issues)
    rows("open campaign issues", campaign_issues, "labelled `campaign`, and with no parent")
    if not campaign_issues:
        print("  (none: this is a reading, not a failed one)")
    if stray:
        rows("!! labelled but has a parent", stray,
             "a sub-issue wearing the label; say so rather than joining it")
    if bare:
        rows("!! no parent and not labelled", bare,
             "a campaign issue whose label was forgotten, or the third kind of issue "
             "this\n   tracker holds. Read the body against the campaign issue template")
    return 0


# ----------------------------------------------------------------------- bound


def refuse_bound(message):
    print(f"campaign-tracker bound: {message}", file=sys.stderr)
    raise SystemExit(2)


def run_or_refuse(*args):
    try:
        out = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as exc:
        refuse_bound(f"cannot run {args[0]}: {exc}")
    if out.returncode != 0:
        refuse_bound(f"{' '.join(args)} exited {out.returncode}: "
                     f"{out.stderr.strip() or out.stdout.strip() or 'no message'}")
    return out.stdout


def labels_of(repo, number):
    """Every label name on the issue. One request and no pagination: labels come
    back on the issue itself, so there is no page to stop early on."""
    raw = run_or_refuse("gh", "api", f"repos/{repo}/issues/{number}",
                        "--jq", "[.labels[].name]")
    try:
        names = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        refuse_bound(f"gh returned something that is not JSON: {exc}")
    if not isinstance(names, list):
        refuse_bound("gh returned a shape this script does not know")
    return [n for n in names if isinstance(n, str)]


def bound_labels(names):
    """Every `bound:` label on the issue, sorted. A calculation, so none, one
    and two are each a case with no network in it."""
    return sorted(n for n in names if n.startswith(BOUND_LABEL_PREFIX))


def binding_of(names):
    """(machine, why_unreadable) from a label list.

    `None, None` is a campaign nobody has bound. `None, <why>` is TWO bindings,
    which is not a verdict: a label set has no latest, so nothing here can
    choose, and choosing wrongly hands the campaign to a machine that is not
    working it."""
    found = bound_labels(names)
    if not found:
        return None, None
    if len(found) > 1:
        return None, (f"the campaign issue carries {len(found)} `bound:` labels "
                      f"({', '.join(found)}). A label set has no latest, so which "
                      f"machine holds the campaign is unanswerable from here. "
                      f"Run `campaign-tracker.py bind <N>` on the machine that "
                      f"holds it, which removes the others in the same edit.")
    machine = found[0][len(BOUND_LABEL_PREFIX):].strip()
    return (machine or None), None


def this_machine():
    name = run_or_refuse("hostname", "-s").strip()
    if not name:
        refuse_bound("hostname -s printed nothing")
    return name


def cmd_bound(args):
    machine, why = binding_of(labels_of(args.repo, args.campaign_issue))
    if why:
        refuse_bound(why)
    if machine is None:
        print("unbound")
    elif machine == this_machine():
        print("here")
    else:
        print(f"elsewhere {machine}")
    return 0


# ------------------------------------------------------------------------ bind


def bind_plan(names, machine):
    """(label_to_add, labels_to_remove, already_there). Pure, so unbound, bound
    here already, and bound elsewhere each have a case.

    `already_there` is not a no-op on its own: a campaign carrying `bound:X`
    and `bound:Y` at once has the wanted label already and still needs the
    other removed, which is the state `bound` refuses to read."""
    want = f"{BOUND_LABEL_PREFIX}{machine}"
    have = bound_labels(names)
    return want, [n for n in have if n != want], want in have


def cmd_bind(args):
    machine = this_machine()
    names = labels_of(args.repo, args.campaign_issue)
    have = bound_labels(names)
    want, drop, already = bind_plan(names, machine)
    print(f"{args.repo}#{args.campaign_issue} carries {len(have)} `bound:` "
          f"label(s): {', '.join(have) or '<none>'}")
    if already and not drop:
        print(f"already {want}; nothing to change")
        return 0
    # `--force` because the label existing is the ordinary case, and its
    # non-zero exit would otherwise read as a failure to create one.
    c = subprocess.run(["gh", "label", "create", want, "-R", args.repo,
                        "--force", "--color", "0E8A16", "--description",
                        "the machine this campaign is bound to"],
                       capture_output=True, text=True)
    if c.returncode != 0:
        print(f"campaign-tracker bind: could not ensure the label {want} "
              f"exists: {c.stderr.strip() or 'no message'}", file=sys.stderr)
        return 1
    cmd = ["gh", "issue", "edit", str(args.campaign_issue), "-R", args.repo]
    if not already:
        cmd += ["--add-label", want]
    for n in drop:
        cmd += ["--remove-label", n]
    e = subprocess.run(cmd, capture_output=True, text=True)
    if e.returncode != 0:
        print(f"campaign-tracker bind: the edit failed: "
              f"{e.stderr.strip() or 'no message'}", file=sys.stderr)
        return 1
    print(f"{'kept' if already else 'added'} {want}")
    for n in drop:
        print(f"removed {n}")
    # THE SHAPE READING, PRINTED AND NOT OBEYED. `bind` is the only repair for
    # the two-`bound:`-label state, so gating it on the body would refuse to run
    # on exactly the campaign that needs repairing. Saying nothing at all was
    # the other wrong answer: the campaign issue's shape is nobody else's to
    # notice, and the moment a person binds is the moment they can fix it. So
    # the label edit above has already happened, and this is a report.
    title, body, names, parented, why = issue_shape(args.repo,
                                                    args.campaign_issue)
    if why:
        print(f"the shape was NOT read ({why}); the label above is set "
              f"regardless, which is what this command is for")
        return 0
    kind = kind_of(CAMPAIGN_LABEL in names, parented)
    findings = shape_findings(kind, title, body, want_plan=False)
    if findings:
        print(f"shape ({kind}), reported and not enforced here -- "
              f"`campaign-tracker check {args.campaign_issue}` for the full "
              f"reading:")
        for f in findings:
            print(f"  {f}")
    else:
        print(f"shape ({kind}): title {len(title)}, body {len(body)}, and "
              f"every required section present")
    return 0


# ----------------------------------------------------------------------- check

# ONE NUMBER FOR BOTH KINDS, and it is measured rather than chosen. Over the 127
# issues on this tracker at 2026-09-05, with the boilerplate section and the
# prose paragraphs cut -- the two rules this shape adds -- the body length
# distribution is median 1,013, p75 2,028, p90 3,519. 2,000 sits on that p75 and
# keeps 74% of what is already written; 1,500 would keep 65% and push a third of
# routine sub-issues into a linked file on day one, and a rule broken routinely
# stops being read. A second number per kind was rejected for the same reason a
# second reader is: it needs an explanation beside it.
BODY_CEILING = 2000
TITLE_CEILING = 80
BACKLOG_LABEL = "backlog"

# THE SECTION VOCABULARY, stated once, here -- the NAMES, that is; the two
# ceilings below are stated once each as a constant, and the templates and
# AGENTS.md say a ceiling exists rather than repeating its number. A kind OMITS a section; it never
# renames one, which is what `## Requirements` beside a sub-issue's `Done when`
# was doing -- two names for one purpose. `## Plan` is conditional on the
# moment and so is not in either tuple; see `required_sections`.
CAMPAIGN_SECTIONS = ("Intent", "Scope", "Done when", "Repos")
LANDS_SECTION = "Lands in"
SUB_ISSUE_SECTIONS = ("Intent", "Done when", LANDS_SECTION)
PLAN_SECTION = "Plan"

SECTION = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


def repos_module():
    """`campaign-repos.py`, imported for `lands_in`.

    THE DESTINATION HAS ONE READER AND THIS IS NOT IT. `SECTION` above finds a
    heading; `lands_in` decides whether the SECTION under it is an answer, and
    the two disagreed on four bodies -- a `## Lands in` inside an HTML comment,
    `##  Lands in` with two spaces, an empty section, and two entries. On each,
    `check` printed "the shape holds" and `campaign-claim take` then refused the
    claim, which is the drift a second reader always produces. So this row is
    delegated rather than re-derived, and `check` and the claim path can no
    longer answer differently (kalaluthien/campaign-base#217, review of
    e73ec4b)."""
    src = Path(__file__).resolve().parent / "campaign-repos.py"
    spec = importlib.util.spec_from_loader(
        "campaign_repos", importlib.machinery.SourceFileLoader(
            "campaign_repos", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

CAMPAIGN, SUB_ISSUE, STRAY, THIRD_KIND = (
    "campaign issue", "sub-issue", "stray", "third kind")


def kind_of(labelled, parented):
    """The issue's kind from the two structural facts, and nothing else.

    Four outcomes, not three: `stray` -- labelled AND parented -- is the row
    `classify` above already names, and it is a defect reported rather than a
    kind, because no reader can say whether it is a campaign somebody filed
    under a parent or a sub-issue somebody labelled."""
    if labelled and parented:
        return STRAY
    if labelled:
        return CAMPAIGN
    if parented:
        return SUB_ISSUE
    return THIRD_KIND


def required_sections(kind, want_plan):
    """The sections this kind must carry at this moment, or () for a kind with
    no shape."""
    if kind == CAMPAIGN:
        return CAMPAIGN_SECTIONS
    if kind == SUB_ISSUE:
        return SUB_ISSUE_SECTIONS + ((PLAN_SECTION,) if want_plan else ())
    return ()


def shape_findings(kind, title, body, want_plan):
    """Every way this issue's shape is wrong, as a list of lines; empty when it
    holds. Pure, so each finding has a case that does not spend a request.

    IT REPORTS ALL OF THEM, not the first. A body that is both too long and
    missing a section needs two edits, and a checker that names one sends its
    reader back for the other."""
    out = []
    if kind == STRAY:
        return [f"it carries the `{CAMPAIGN_LABEL}` label AND a parent. That is "
                f"not a kind: no reader can say whether it is a campaign filed "
                f"under a parent or a sub-issue wearing the label. Remove one."]
    if len(title) > TITLE_CEILING:
        out.append(f"the title is {len(title)} characters, over {TITLE_CEILING}")
    if len(body) > BODY_CEILING:
        out.append(f"the body is {len(body)} characters, over {BODY_CEILING}. "
                   f"Design longer than that is a file on the claim's branch, "
                   f"linked from `## {PLAN_SECTION}`")
    found = SECTION.findall(body)
    for want in required_sections(kind, want_plan):
        # THE DESTINATION IS NOT A PRESENCE TEST. Every other section here is
        # judged by its heading alone -- what belongs under `## Intent` is
        # judgement and stays prose. `## Lands in` is the one row a script
        # already decides in full, and it is asked rather than approximated.
        if want == LANDS_SECTION:
            try:
                _entry, why = repos_module().lands_in(body)
            except Exception as e:                 # noqa: BLE001 -- any of them
                out.append(f"the `## {want}` reader would not load "
                           f"({e.__class__.__name__}), so this section was not "
                           f"read; that is not a section that is right")
                continue
            if why:
                out.append(f"`## {want}`: {why}")
            continue
        if want not in found:
            out.append(f"no `## {want}` section, which a {kind} requires"
                       + (" at a claim" if want == PLAN_SECTION else ""))
    return out


def issue_shape(repo, number):
    """(title, body, labels, has a parent, why_unreadable)."""
    text, why = gh_read(["gh", "issue", "view", str(number), "-R", repo,
                         "--json", "title,body,labels,parent"])
    if why:
        return None, None, None, None, why
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, None, None, None, f"could not parse gh's output ({e})"
    names = [l.get("name") for l in data.get("labels") or []]
    return (data.get("title") or "", data.get("body") or "", names,
            bool(data.get("parent")), None)


def cmd_check(args):
    repo, number = args.repo, args.campaign_issue
    title, body, names, parented, why = issue_shape(repo, number)
    if why:
        print(f"campaign-tracker check: could not read {repo}#{number} -- {why}\n"
              f"  An issue that did not read is not an issue with no shape.",
              file=sys.stderr)
        return 2
    kind = kind_of(CAMPAIGN_LABEL in names, parented)
    found = SECTION.findall(body)
    # WHAT WAS READ, ALWAYS, and before the verdict. A bare pass is the shape
    # that gets trusted for months while checking nothing.
    print(f"read {repo}#{number}: {kind}"
          f" (label `{CAMPAIGN_LABEL}`: {'yes' if CAMPAIGN_LABEL in names else 'no'},"
          f" parent: {'yes' if parented else 'no'})")
    print(f"  title  {len(title)} chars (ceiling {TITLE_CEILING})")
    print(f"  body   {len(body)} chars (ceiling {BODY_CEILING})")
    print(f"  sections found: {', '.join(found) or '<none>'}")
    want = required_sections(kind, args.plan)
    print(f"  sections required: {', '.join(want) or '<none: this kind has no shape>'}")
    if BACKLOG_LABEL in names:
        print(f"  carries `{BACKLOG_LABEL}`: not worked until the owner removes "
              f"it; `campaign-claim take` refuses a claim on it")
    print("  NOT checked: whether the title is verb-first, whether the body is "
          "bullets rather than prose, whether `## Done when` is checkable. "
          "Those are judgement.")
    findings = shape_findings(kind, title, body, args.plan)
    if not findings:
        print("RESULT   the shape holds" if want else
              "RESULT   no shape to hold: every reader leaves this kind alone")
        return 0
    for f in findings:
        print(f"REFUSING {f}", file=sys.stderr)
    return 1


# ----------------------------------------------------------------------- index


def parse_index(text):
    """Returns (items, why_unreadable).

    `gh api --paginate` behaves by the response's own shape: an endpoint
    returning a JSON **array** has its pages merged into one array, while an
    object endpoint has its page objects concatenated and needs a streaming
    decode. This endpoint returns an array, so a plain decode is right."""
    text = text.strip()
    if not text:
        return [], None
    try:
        items = json.loads(text)
    except ValueError as e:
        return None, (f"could not parse the index ({e.__class__.__name__}: "
                      f"{str(e)[:60]})")
    if not isinstance(items, list):
        return None, (f"the endpoint returned {type(items).__name__}, not a "
                      f"list; --paginate concatenates object pages, so this "
                      f"needs a streaming decode rather than a plain one")
    return items, None


def fetch_index(repo, campaign_issue):
    """Ask GitHub for a campaign's members. Returns (items, why_unreadable).

    The request and the parse are one call on purpose: a caller that got only
    the parse would hand-write `--paginate`, and dropping it there is invisible.
    `settlement` below is that caller."""
    text, why = gh_read(["gh", "api", "--paginate",
                         f"repos/{repo}/issues/{campaign_issue}/sub_issues"])
    if why:
        return None, why
    return parse_index(text)


def cmd_index(args):
    print(f"read repos/{args.repo}/issues/{args.campaign_issue}/sub_issues --paginate")
    items, why = fetch_index(args.repo, args.campaign_issue)
    if why:
        print(f"FAILED -- {why}. {NOT_EMPTY}", file=sys.stderr)
        return 1

    for it in items:
        repo = (it.get("repository") or {}).get("full_name", "?")
        print(f"  {repo}#{it.get('number', '?'):<6} {it.get('state', '?'):<7} "
              f"{(it.get('title') or '')[:70]}")
    print(f"{len(items)} sub-issue(s)"
          + ("  (an empty index is a reading, not a failure)" if not items else ""))
    return 0


# ------------------------------------------------------------------ settlement


def gh_json(*args):
    """(parsed, why_unreadable). Never raises on a reading it could not make.

    This is the shape the whole file uses, and settlement is why: one sub-issue
    whose repository went private would otherwise abort the table before the
    reader saw any verdict at all, and a close reads that table."""
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
    except OSError as exc:
        return None, f"cannot run gh: {exc}"
    if out.returncode != 0:
        return None, (f"gh {' '.join(args)} exited {out.returncode}: "
                      f"{out.stderr.strip().splitlines()[0][:100] if out.stderr.strip() else 'no message'}")
    if not out.stdout.strip():
        return None, f"gh {' '.join(args)} printed nothing"
    try:
        return json.loads(out.stdout), None
    except ValueError as exc:
        return None, (f"gh {' '.join(args)} returned something that is not JSON "
                      f"({exc.__class__.__name__})")


def verdict(repo, number):
    """(verdict, note, title) for one sub-issue.

    Four verdicts, not three. `unread` is a sub-issue whose issue, or whose
    closing pull request, this account cannot see -- a repository since made
    private, transferred, or deleted. It is neither settled nor open: an
    absence is not a pass and it is not a failure, and settlement counts it in
    a column of its own so a close is refused over it with the reason said.
    Before it existed, the failed read raised out of the table and the reader
    got a message about `gh` where it had asked for a settlement."""
    info, why = gh_json("issue", "view", str(number), "-R", repo,
                        "--json", "state,stateReason,closedByPullRequestsReferences,title")
    if why:
        return "unread", f"the issue could not be read -- {why}", ""
    if info["state"] == "OPEN":
        return "open", "", info["title"]
    title = info["title"]
    for ref in info["closedByPullRequestsReferences"]:
        home = ref.get("repository") or {}
        owner = (home.get("owner") or {}).get("login")
        if not owner or not home.get("name"):
            # A pull request the API declined to place: deleted, or moved
            # somewhere this account cannot follow it to.
            return ("unread", f"the pull request at {ref.get('url') or '?'} is in "
                    "a repository the API did not name", title)
        pr, why = gh_json("pr", "view", str(ref["number"]), "-R",
                          f"{owner}/{home['name']}", "--json", "state")
        if why:
            return ("unread", f"the closing pull request could not be read -- {why}",
                    title)
        if pr["state"] == "MERGED":
            return "complete", ref["url"], title
    # The note says which kind of closed, because "dropped" alone reads as
    # abandoned and a completed sub-issue with nothing to merge lands here too.
    note = {"NOT_PLANNED": "not planned",
            "COMPLETED": "completed, no merged pull request",
            "DUPLICATE": "duplicate"}.get(info["stateReason"] or "",
                                          "closed, no reason recorded")
    return "dropped", note, title


def claim_column(repo, campaign_issue):
    """(a function issue -> claim word, a note saying what was read).

    Read off the REMOTE's `campaign-<N>/` refs since #176: a claim is a branch
    and there is no record to import. That also drops the `--dir` this used to
    need -- the answer is the same from any machine now, which is the point of
    moving the claim onto a ref.

    The note is not decoration. A ref listing that did not happen would print
    `unclaimed` for every row, which is an absence dressed as a reading --
    exactly the failure this column was added to end. It says which branch, and
    NOT who is standing in it: that is `campaign-claim live`'s reading and it is
    per-machine, where this table is not."""
    module, why = claim_reader()
    if why:
        return (lambda n: ""), f"the claim reader would not load -- {why}"
    # EVERY repository the campaign's claims can be on, not just `--repo`. A
    # member-repo sub-issue's branch is on that member's remote, and reading the
    # base alone printed `unclaimed` for it under a note saying the reading
    # succeeded -- which is how a planner hands a claimed sub-issue to a second
    # worker. Same reader as `campaign-claim live`, so the two cannot drift.
    root, _ = module.base_root()
    repos, repo_note = module.claim_repos(repo, root)
    found_map, unread = module.all_refs(repos, campaign_issue)
    if unread:
        return (lambda n: ""), (f"the claim refs did not read -- "
                                f"{'; '.join(unread)}; the rows below say "
                                f"nothing about who holds what")
    branches = sorted(found_map)
    note = (f"read refs under campaign-{campaign_issue}/ in "
            f"{', '.join(repos)} -- {len(branches)} claim(s)")

    def word(number):
        found = module.refs_for_issue(branches, campaign_issue, number)
        if not found:
            return "unclaimed"
        return f"claimed: {', '.join(found)}"
    return word, note


def claim_reader():
    """campaign-claim's own ref reading, imported rather than rewritten.

    Returns (module, why_unreadable). What a claim branch is named, and which
    sub-issue a name belongs to, are written in exactly one place; a settlement
    that split the name itself would be the second reader AGENTS.md forbids --
    and the one that drifts, since nothing re-runs it against a ref
    campaign-claim just cut."""
    path = Path(__file__).resolve().parent / "campaign-claim.py"
    try:
        spec = importlib.util.spec_from_loader(
            "campaign_claim",
            importlib.machinery.SourceFileLoader("campaign_claim", str(path)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:                      # noqa: BLE001 -- any of them
        return None, f"{path}: {e.__class__.__name__}: {e}"
    return module, None


def campaign_issue_reports(head):
    """What says the number handed in is not a campaign issue. Costs no extra call.

    The campaign issue repository is a member of its own campaigns, so the number handed
    in may be a sub-issue and a sub-issue may be a campaign issue. Neither is visible in a
    settlement table. These reports read labels and the parent relation, never
    the body: prose is editable and the parent relation is not."""
    if CAMPAIGN_LABEL not in [l["name"] for l in head["labels"]]:
        yield (f"REPORT: no `{CAMPAIGN_LABEL}` label, so this may be a sub-issue read"
               " as a campaign issue")
    if head["parent"]:
        yield (f"REPORT: this campaign issue is itself a sub-issue of #{head['parent']['number']}"
               " -- closing that campaign will not settle this one")


def cmd_settlement(args):
    head, why = gh_json("issue", "view", args.campaign_issue, "-R", args.repo,
                        "--json", "state,title,labels,parent")
    if why:
        sys.exit(f"campaign-tracker settlement: could not read the campaign issue "
                 f"{args.repo}#{args.campaign_issue} -- {why}\n  No verdict was reached "
                 f"for any sub-issue.")
    subs, why = fetch_index(args.repo, args.campaign_issue)
    if why:
        sys.exit(f"campaign-tracker settlement: could not read the sub-issue "
                 f"index -- {why}\n  {NOT_EMPTY}")

    print(f"campaign issue {args.repo}#{args.campaign_issue}  [{head['state']}]  {head['title']}")
    for line in campaign_issue_reports(head):
        print(f"  -- {line}")
    if not subs:
        print("  (no sub-issues: the index is empty)")
        return 0

    claim_word, claim_note = claim_column(args.repo, args.campaign_issue)
    print(f"  -- claims: {claim_note}")

    rows_out, settled, unread, nested = [], 0, 0, []
    for s in subs:
        repo = "/".join(s["repository_url"].split("/")[-2:])
        v, note, title = verdict(repo, s["number"])
        settled += v in ("complete", "dropped")
        unread += v == "unread"
        # Only an open row: a settled sub-issue's claim answers nothing a reader
        # is about to act on, and printing one invites a release that is not
        # needed.
        held = claim_word(s["number"]) if v == "open" else ""
        rows_out.append((f"{repo}#{s['number']}", v, title[:44],
                         "; ".join(x for x in (note, held) if x)))
        # sub_issues is not recursive (probed), so a sub-issue that is itself an
        # campaign issue hides its own members from this table.
        if s["sub_issues_summary"]["total"]:
            nested.append((f"{repo}#{s['number']}", s["sub_issues_summary"]["total"]))

    width = max(len(r[0]) for r in rows_out)
    for ref, v, title, note in rows_out:
        print(f"  {ref:<{width}}  {v:<9} {title}" + (f"  [{note}]" if note else ""))

    for ref, total in nested:
        print(f"  -- REPORT: {ref} has {total} sub-issue(s) of its own, not listed"
              " above; run this on it too")

    # Two ways not to be closable, named apart because they want different
    # repairs: an open sub-issue is work to finish, an unread one is a reading to
    # get back -- an account to re-authorise, a repository to ask for.
    blockers = []
    if any(v == "open" for _, v, _, _ in rows_out):
        blockers.append("open sub-issues remain")
    if unread:
        blockers.append(f"{unread} sub-issue(s) could not be read, which settles "
                        "nothing either way")
    closable = not blockers
    print(f"  -- {settled}/{len(rows_out)} settled"
          + (f", {unread} unread" if unread else "") + "; "
          + ("closable" if closable else "NOT closable: " + "; ".join(blockers)))
    if head["state"] == "CLOSED" and not closable:
        print("  -- REPORT: the campaign issue is closed with sub-issues still open")
    return 0


# ------------------------------------------------------------------------ main


def campaign_issue_number(text):
    """The campaign issue as `bound` validates it: a bare positive issue number.

    Only `bound` refuses a malformed one before spending a request, because it
    is the reading whose caller acts on a printed word and would otherwise read
    a usage error as a verdict."""
    n = text.lstrip("#")
    if not n.isascii() or not n.isdigit() or int(n) <= 0:
        refuse_bound(f"not an issue number: {text!r}")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("campaign-issues", help="the open-campaign issue survey")
    a.add_argument("--repo", default=DEFAULT_REPO)
    a.add_argument("--limit", type=int, default=200)
    a.set_defaults(fn=cmd_campaign_issues)

    # The optional positional repository is the override seam these three share.
    # One spelling across all three: `campaign-issues` takes `--repo` because it takes
    # `--limit` beside it, and a positional there would read as the campaign issue.
    for name, fn, help_text in (
            ("bound", cmd_bound, "here | elsewhere <machine> | unbound"),
            ("bind", cmd_bind, "set this machine's `bound:` label, dropping any other"),
            ("check", cmd_check, "an issue's title, body length and sections"),
            ("index", cmd_index, "the sub-issue index"),
            ("settlement", cmd_settlement, "every sub-issue's verdict")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("campaign_issue")
        p.add_argument("repo", nargs="?", default=DEFAULT_REPO)
        if name == "check":
            p.add_argument("--plan", action="store_true",
                           help="require `## Plan` too, which a sub-issue gains "
                                "before anybody is prompted onto it; "
                                "`campaign-claim take` passes it")
        # Only settlement reads it, and only settlement is given it: a flag the
        # other two accept and ignore reads as though naming a directory
        # changed what they answer.
        if name == "settlement":
            p.add_argument("--dir", help="accepted and ignored since #176: "
                                         "the claim is a branch on the remote, "
                                         "so no directory is read")
        p.set_defaults(fn=fn)

    args = ap.parse_args()
    if args.cmd in ("bound", "bind", "check"):
        args.campaign_issue = campaign_issue_number(args.campaign_issue)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
