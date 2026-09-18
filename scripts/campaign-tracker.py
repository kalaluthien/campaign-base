#!/usr/bin/env python3
"""Read the campaign plane: its campaign issues, its slugs, its binding, its index, its settlement.

    campaign-tracker.py campaign-issues [--repo owner/repo] [--limit N]
    campaign-tracker.py slug <N> [owner/repo]
    campaign-tracker.py issue <slug> [owner/repo]
    campaign-tracker.py slugs [owner/repo] [--limit N]
    campaign-tracker.py bound <N> [owner/repo]
    campaign-tracker.py standing <N> [owner/repo]
    campaign-tracker.py kind <issue> [owner/repo]
    campaign-tracker.py bind <N> [owner/repo]
    campaign-tracker.py check <N> [owner/repo] [--plan]
    campaign-tracker.py index <N> [owner/repo]
    campaign-tracker.py settlement <N> [owner/repo]

Ten readings of one plane -- GitHub issues and their labels, plus `hostname -s`
for `bound`, and the one write that changes what `bound` answers.
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

slug        The one reader of the `campaign:<slug>` LABEL, from the campaign
            issue's side. The slug is what every name a person reads is built
            from -- `<slug>-<role>-<n>`, `<slug>/<issue>-<topic>`, `<slug>/` --
            so a campaign without one cannot be worked, and `campaign-issues`
            refuses on exactly that. It prints `none` and exits 1 for a campaign
            that has no slug, which is a reading; 2 is the read that failed.

            THE SLUG'S RULE IS NOT HERE. `campaign-name-session.py` owns it,
            because the PreToolUse guard reads a session name on every tool call
            and must reach the rule without exec'ing this script's `gh`
            plumbing. This file owns only where the slug is STORED.

issue       The same label read from the other side: which campaign issue a slug
            names, over every state, because a closed campaign's slug is still
            spent. Two issues wearing one `campaign:` label is refused rather
            than resolved -- it is the only duplication GitHub does not already
            stop, since it keeps label NAMES unique by itself.

slugs       Every slug ever spent, read off the LABEL list and not off the
            issues wearing them: a label outlives its campaign, so this is what
            a planner minting a fresh slug must not collide with. Uniqueness
            needs no survey after that -- `gh label create` refuses a name that
            exists.

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

standing    The one reader of the `standing` LABEL: a campaign a person keeps
            open. Read like `bound` and for the same reason -- a label has no
            history to page through and no latest to pick -- and answered as a
            WORD, because a close acts on the word and must not read a failed
            request as consent. Only a person removes the label; nothing here
            can observe that they changed their mind, which is why this reads
            and never writes.

kind        The one reader of a sub-issue's `kind:<k>` LABEL -- the WORK kind,
            which is not the structural kind `check` reads off the `campaign`
            label and the parent link. Read like `slug` and for the same
            reasons: one label, by exact name, with no history to page through
            and so no latest to pick between two of them. It prints `none` and
            exits 1 for a sub-issue that carries none, which is a reading and
            the ordinary state of everything filed before the rule; 2 is the
            read that failed or the label set that cannot be read as one word.

            THE WORDS ARE `WORK_KINDS` and nowhere else here. A label whose
            word is outside them is refused rather than returned: the word names
            the `assuming-role` reference a worker is briefed from, so returning
            an unknown one hands out a path nothing resolves.

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
            and `chore` labels and the parent link, the three facts GitHub
            itself holds -- because the reading it replaces classified by BODY
            TEXT, so an issue that happened to contain `## Repos` was a campaign
            to one reader and not to another.

            THE CHORE IS A CAMPAIGN ISSUE THAT IS ITS OWN ONE UNIT OF WORK. It
            carries `campaign` AND `chore`, omits `## Scope`, `## Plan` and
            `## Lands in`, and `--plan` adds nothing to it: there is no
            sub-issue to plan. Two label states refuse here -- `chore` with
            `standing`, since a chore's close is pre-authorised where
            `standing` is the person's word that a campaign stays open, and
            `chore` without `campaign`, where the label names nothing.

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

            A BARE `#N` IS A WARNING, not a finding, and the TITLE is read
            beside the body: the rule exempts no field. It is printed with the
            reading and moves no exit status, because every body on this
            tracker predates the rule and a refusal would wall the history the
            first time anybody edited one. `check-campaign-claim.py` prints the
            same sentence over a comment's text, from `bare_references` here.

            TWO READINGS ARE JUDGEMENT, AND JEV MAKES THEM: whether the title
            opens with an imperative verb naming a mission, and -- only where no
            `kind:` label answers it -- which of `WORK_KINDS` the work is. They
            are the `issue-shape` group of `scripts/jev/readings.json`, asked
            BY NAME in one call through `scripts/campaign-jev.py`; no question
            and no threshold is written here. Both sit at tier `advise`, so
            each PRINTS and moves no exit status, and a call that failed prints
            `unknown` and why: a model's guess never refuses a claim. Where the
            `kind:` label already answers, the label is passed as the
            prefilter's word and nothing is asked of the model.

            WHAT IT DOES NOT CHECK, printed on every run: whether a body is
            bullets rather than prose, whether a `Definition of done` is
            checkable. Those are judgement that nothing reads. Nor does it
            reach issues nobody claims or binds -- the
            ceiling is a cut
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
            read off the remote's claim-branch prefixes through campaign-claim's
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
campaign-issues exits 3 -- not 1 -- when the listing was read and an open
                            campaign issue has no readable slug: a reading that
                            did not happen and an answer must not share a status.
slug, issue                 0 with the answer on stdout, 1 for `none`, which is
                            a reading, and 2 when the reading itself failed.
slugs                       0 when the label listing was read, 2 when it was not
                            or came back at the limit.
bound                       0 for any verdict, 2 when the reading itself failed
                            -- two `bound:` labels included, since that is a
                            question this refuses to answer, not a verdict.
standing                    0 for either word, 2 when the labels did not read.
kind                        0 with the work kind on stdout, 1 for `none`, which
                            is a reading, and 2 when the reading failed or two
                            `kind:` labels make the answer unchoosable.
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


def load(src, alias):
    """The script at `src` as a module: these are scripts, not a package.
    Raises what loading raised; each caller decides what that means."""
    spec = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# campaign-repos.py OWNS THE BASE'S NAME AND HOW A BODY'S SECTIONS ARE FOUND:
# `BASE_REPO`, the reader that refuses it in `## Repos`, and `headings`,
# `section` and `lands_in` (rule-check#370 rows 5 and 20). Loaded here once.
REPOS = load(Path(__file__).resolve().parent / "campaign-repos.py",
             "campaign_repos")
DEFAULT_REPO = REPOS.BASE_REPO
CAMPAIGN_LABEL = "campaign"
BOUND_LABEL_PREFIX = "bound:"
# The campaign's slug, the same shape as the binding's label and for the same
# reasons: read by exact name, no history to page through, one edit to change.
# `campaign` and `campaign:` do not collide -- the plain label has no colon --
# and `startswith` is not how the kind is decided, `==` is.
SLUG_LABEL_PREFIX = "campaign:"
# How many labels one listing asks for; a listing that fills it may be cut.
LABEL_LIMIT = 200
# THE SUB-ISSUE'S WORK KIND, stored the same way the slug and the binding are:
# one label, read by exact name. It is NOT the structural kind `kind_of` below
# decides -- that one is the `campaign` label and the parent link, and it names
# what an issue IS; this names what the work on it is.
WORK_KIND_LABEL_PREFIX = "kind:"
# THE WORDS, stated once, here. The sub-issue template offers them and the
# `assuming-role` skill's `references/kind-<k>.md` are NAMED by them, so a
# word invented on a label resolves to no reference and no template row, and is
# refused rather than returned.
# rule-check#354 folded five into these: `analysis` into `research`,
# `prototyping` into `development`, `migration` into `maintenance`.
WORK_KINDS = ("research", "development", "maintenance")
# --------------------------------------------------- what `check` asks of Jev
# NOTHING, HERE. The two readings `check` prints are the `issue-shape` group of
# `scripts/jev/readings.json`: the wording of each question, its `criteria`,
# the state slice and every cut live there as data, and this asks by GROUP NAME
# through `scripts/campaign-jev.py`. A question or a threshold written here
# would be a second wording nothing measured and no `report` counted, which is
# what these constants were.
#
# NEITHER MOVES THE EXIT STATUS. `shape_findings` alone decides that, and a
# judgment that gated a claim would be a model's guess wearing a check's
# authority. Both are printed with the reading, beside the bare-reference
# warning, for the same reason: they are readings, not verdicts.
JUDGMENT_GROUP = "issue-shape"
VERB_FIRST, WORK_KIND = "verb-first", "work-kind"
# THE PERSON'S HOLD ON THE CLOSE. A campaign wearing it is one a person keeps
# open, and only a person takes it off -- nothing here can observe that they
# changed their mind, which is the same reason `backlog` is the owner's alone.
# `campaign-close.py`'s `standing` gate reads it and refuses the close naming
# it; the survey prints it beside the row, so a campaign that will not close
# says so before anybody spends a step trying. ON A SUB-ISSUE the same hold
# keeps it open with no claim between tidies, and the heartbeat reads one
# wearing it as neither `drift unclaimed` nor a reason the campaign is not
# quiet (rule-check#369); the kind says what the work is, this says who holds
# it open.
STANDING_LABEL = "standing"

NOT_EMPTY = "An index that did not read is not an empty campaign."


def gh_read(cmd, timeout=None):
    """Run a `gh` invocation for its stdout. Returns (text, why_unreadable).

    A `gh` that is not installed comes back as a failed run rather than a
    traceback: "I could not look" is the case every reader here is written to
    report, and a stack trace loses the reason the caller was about to print.

    `timeout` is seconds, None for none. A caller on a hook's path passes one
    (check-campaign-claim.py, rule-check#354): a `gh` that hangs there hangs
    every tool call. A timeout is a read that did not happen, like any other."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, PermissionError) as e:
        return None, f"could not run {cmd[0]} ({e.__class__.__name__})"
    except subprocess.TimeoutExpired:
        return None, f"{cmd[0]} did not answer within {timeout}s"
    if r.returncode != 0:
        return None, (f"{cmd[0]} exited {r.returncode}: "
                      f"{(r.stderr.strip() or r.stdout.strip() or 'no message')[:200]}")
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
    issue itself says -- never by its absence from somewhere else. The kind is
    `kind_of`'s, and a sub-issue is in none of the three. A CHORE IS A CAMPAIGN
    ISSUE HERE, which is why the chore label is not read into the split: it is
    one of the open campaigns a request is routed against, and `rows` prints
    the label beside its number."""
    kinds = [(i, kind_of(CAMPAIGN_LABEL in label_names(i), bool(i.get("parent"))))
             for i in issues]
    return tuple([i for i, k in kinds if k == want]
                 for want in (CAMPAIGN, STRAY, THIRD_KIND))


def label_names(issue):
    """Every label name on one issue, as strings, off gh's `--json labels`.
    The one reading of it (rule-check#370 row 22): the survey, `check`,
    `settlement`, `slugs` and the heartbeat each built the list themselves."""
    return [l.get("name") for l in issue.get("labels") or []
            if isinstance(l, dict) and isinstance(l.get("name"), str)]


def is_standing(names):
    """Whether this label list holds the person's hold on the close.

    THE ONE READER of `standing`, asked by the survey's row, the `standing`
    verb and the heartbeat's index alike, so the word a close acts on and the
    word a survey prints can never disagree. A calculation over labels already
    fetched, so on and off are both cases with no network in them."""
    return STANDING_LABEL in names


def slugs_in(campaign_issues):
    """({number: slug}, {number: why}) over one listing's campaign issues.

    A calculation over labels already fetched, so it costs no second request
    and every case -- no slug, two slugs, a slug the rule refuses, two issues
    sharing one -- is reachable without a network.

    THE SHARED SLUG IS READ HERE and nowhere else on this side. GitHub keeps
    label NAMES unique, so a slug cannot be minted twice; what it does not stop
    is one label put on two issues, and this is the reading that sees it from
    the issues' side. `issue <slug>` is the same state read from the label's."""
    read, bad = {}, {}
    for i in campaign_issues:
        slug, why = slug_of(label_names(i))
        if why:
            bad[i["number"]] = why
        elif slug is None:
            bad[i["number"]] = ("no `campaign:` label; the planner mints the "
                                "slug at open from `slugs`")
        else:
            read[i["number"]] = slug
    shared = {s: [n for n, v in read.items() if v == s] for s in set(read.values())}
    for slug, numbers in shared.items():
        if len(numbers) > 1:
            for n in numbers:
                read.pop(n, None)
                bad[n] = (f"`{SLUG_LABEL_PREFIX}{slug}` is on "
                          f"{len(numbers)} campaign issues "
                          f"({', '.join('#' + str(x) for x in sorted(numbers))}); "
                          f"a slug names one campaign")
    return read, bad


def rows(title, items, note=""):
    print(f"\n{title} ({len(items)})" + (f" -- {note}" if note else ""))
    for i in sorted(items, key=lambda x: x["number"]):
        names = label_names(i)
        hold = f"  [{STANDING_LABEL}]" if is_standing(names) else ""
        # THE CHORE PRINTS LIKE THE HOLD, and for the same reason: a session
        # routing an arriving request reads these rows, and a chore takes no
        # sub-issue, so what covers the request is not what the row would
        # otherwise say it is.
        chore = f"  [{CHORE_LABEL}]" if CHORE_LABEL in names else ""
        print(f"  #{i['number']:<5} {i['title'][:88]}{hold}{chore}")


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
    read, bad = slugs_in(campaign_issues)
    print(f"\nslugs ({len(read)}/{len(campaign_issues)} open campaign issue(s) "
          f"name themselves)")
    for number, slug in sorted(read.items()):
        print(f"  #{number:<5} {slug}")
    if not read:
        print("  (none)")
    if stray:
        rows("!! labelled but has a parent", stray,
             "a sub-issue wearing the label; say so rather than joining it")
    if bare:
        rows("!! no parent and not labelled", bare,
             "a campaign issue whose label was forgotten, or the third kind of issue "
             "this\n   tracker holds. Read the body against the campaign issue template")
    if bad:
        # EXIT 3, NOT 1. `1` here means the listing did not happen; this is a
        # listing that DID happen and found a campaign that cannot be worked.
        # One status for both would put "I could not look" and an answer behind
        # the same number, which is the confusion every reader in this file is
        # written to avoid.
        print(f"\nREFUSING: {len(bad)} open campaign issue(s) have no readable "
              f"slug. Every name a\n  person reads is built from one, so a "
              f"campaign without one cannot be worked.", file=sys.stderr)
        for number, why in sorted(bad.items()):
            print(f"  #{number}  {why}", file=sys.stderr)
        return 3
    return 0


# ----------------------------------------------------------------------- bound


# The subcommand whose reading is being refused, so the refusal names the verb
# a person actually typed. `main` sets it; `bound` is the default because it is
# the reading this path was written for and the one `campaign_issue_number`
# refuses under before any subcommand is dispatched.
READING = "bound"


def refuse_label_reading(message):
    """Refuse a reading made off the campaign issue's LABELS, exit 2.

    Every caller here answers a question a person acts on by reading a printed
    word, so "I could not look" must not come back as one of the words: exit 2
    is the status that says the reading was never made."""
    print(f"campaign-tracker {READING}: {message}", file=sys.stderr)
    raise SystemExit(2)


def run_or_refuse(*args):
    """`gh_read`, refusing where it could not read."""
    text, why = gh_read(list(args))
    if why:
        refuse_label_reading(f"{' '.join(args)}: {why}")
    return text


def labels_of(repo, number):
    """Every label name on the issue. One request and no pagination: labels come
    back on the issue itself, so there is no page to stop early on."""
    raw = run_or_refuse("gh", "api", f"repos/{repo}/issues/{number}",
                        "--jq", "[.labels[].name]")
    try:
        names = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        refuse_label_reading(f"gh returned something that is not JSON: {exc}")
    if not isinstance(names, list):
        refuse_label_reading("gh returned a shape this script does not know")
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
        refuse_label_reading("hostname -s printed nothing")
    return name


def cmd_standing(args):
    """`standing` or `not-standing` on stdout, and the caller reads the WORD.

    THE STATUS SAYS WHETHER THE READING HAPPENED, never what it found:
    `labels_of` refuses with exit 2 when `gh` would not answer, because a
    campaign whose labels did not read is not a campaign nobody is holding open,
    and that absence is exactly what a close would take for consent."""
    print(STANDING_LABEL if is_standing(labels_of(args.repo, args.campaign_issue))
          else f"not-{STANDING_LABEL}")
    return 0


def cmd_bound(args):
    machine, why = binding_of(labels_of(args.repo, args.campaign_issue))
    if why:
        refuse_label_reading(why)
    if machine is None:
        print("unbound")
    elif machine == this_machine():
        print("here")
    else:
        print(f"elsewhere {machine}")
    return 0


# ------------------------------------------------------------------------ bind


# ------------------------------------------------------------------------ slug


def name_rule():
    """`campaign-name-session.py`, imported for `slug_ok` and `SLUG_CEILING`.

    THE LEAF OWNS THE SLUG RULE, not this file, although this file owns the
    label the slug is stored on. `check-campaign-claim.py` is a PreToolUse hook
    that reads a session name on every tool call and reaches the rule by
    exec'ing that leaf; were the rule here instead, that path would exec this
    script's `gh` plumbing on every call. Its header says the same from the
    other side."""
    return load(Path(__file__).resolve().parent.parent / ".claude" / "skills" / "assuming-role"
                / "scripts" / "campaign-name-session.py", "campaign_name_session")


def slug_labels(names):
    """Every `campaign:` label on the issue, sorted. A calculation, so none,
    one and two are each a case with no network in it."""
    return sorted(n for n in names if n.startswith(SLUG_LABEL_PREFIX))


def slug_of(names):
    """(slug, why_unreadable) from a label list.

    `None, None` is a campaign with no slug -- one filed before #181, or one
    whose planner did not mint one. `None, <why>` is TWO slugs, which is not a
    verdict for the same reason two `bound:` labels is not: a label set has no
    latest, so nothing here can choose.

    A slug the rule does not admit is `None, <why>` too and not a slug that
    merely reads oddly: it cannot appear in a session name, so a session of
    that campaign could not name itself, and a reader that returned it would
    hand out a name `campaign-name-session.py` then refuses."""
    found = slug_labels(names)
    if not found:
        return None, None
    if len(found) > 1:
        return None, (f"the campaign issue carries {len(found)} `campaign:` "
                      f"labels ({', '.join(found)}). A label set has no latest, "
                      f"so which slug names this campaign is unanswerable from "
                      f"here. Remove all but one.")
    slug = found[0][len(SLUG_LABEL_PREFIX):].strip()
    rule = name_rule()
    if not rule.slug_ok(slug):
        return None, (f"the label is `{found[0]}`, and {slug!r} is not a slug: "
                      f"kebab-case starting with a letter, at most "
                      f"{rule.SLUG_CEILING} characters, no segment "
                      f"{' or '.join(rule.RESERVED)}. No session could be named "
                      f"for it, so it is refused rather than returned.")
    return slug, None


def cmd_slug(args):
    """The one campaign's slug, as a word on stdout."""
    slug, why = slug_of(labels_of(args.repo, args.campaign_issue))
    if why:
        print(f"campaign-tracker slug: {why}", file=sys.stderr)
        return 2
    if slug is None:
        print("none")
        return 1
    print(slug)
    return 0


def cmd_issue(args):
    """The campaign issue number a slug names, as a word on stdout.

    Read over EVERY state, not the open ones: a slug names its campaign for as
    long as the label exists, and a closed campaign's slug is still spent. Two
    issues wearing one label is the state this refuses rather than resolves --
    GitHub keeps label NAMES unique, so this is the only duplication left, and
    it is the one `campaign-issues` reads from the other side."""
    label = f"{SLUG_LABEL_PREFIX}{args.slug}"
    text, why = gh_read(["gh", "issue", "list", "-R", args.repo, "--state", "all",
                         "--label", label, "--limit", "100",
                         "--json", "number,title,state"])
    if why:
        print(f"campaign-tracker issue: could not read {args.repo} -- {why}\n"
              f"  A reading that did not happen is not an unspent slug.",
              file=sys.stderr)
        return 2
    try:
        found = json.loads(text)
    except ValueError as e:
        print(f"campaign-tracker issue: could not parse gh's output "
              f"({e.__class__.__name__})", file=sys.stderr)
        return 2
    if len(found) > 1:
        print(f"campaign-tracker issue: {len(found)} issues carry `{label}` "
              f"({', '.join('#' + str(i['number']) for i in found)}). A slug "
              f"names one campaign; take the label off all but one.",
              file=sys.stderr)
        return 2
    if not found:
        print("none")
        return 1
    print(found[0]["number"])
    return 0


def spent_slugs(repo, limit):
    """(every slug this tracker has ever spent, the label count, why
    unreadable), read off the LABELS and not off the issues wearing them.

    A label outlives the campaign it was minted for and a closed campaign's
    slug stays spent, so this is what a planner minting a fresh one reads. It
    is also the reason nothing here has to survey issues for uniqueness: GitHub
    refuses a second label of one name. campaign-context.py reads it too, to
    tell a cited `<slug>#N` from a slug-shaped word."""
    text, why = gh_read(["gh", "label", "list", "-R", repo, "--limit",
                         str(limit), "--json", "name"])
    if why:
        return None, 0, (f"could not read {repo}'s labels -- {why}\n  A "
                         f"reading that did not happen is not an empty pool.")
    try:
        listed = json.loads(text)
        if not isinstance(listed, list):
            raise TypeError(type(listed).__name__)
    except (ValueError, TypeError) as e:
        return None, 0, f"could not parse gh's output ({e.__class__.__name__})"
    # A label listing is the `labels` array an issue carries.
    labels = label_names({"labels": listed})
    if len(listed) >= limit:
        return None, 0, (f"the label listing came back at --limit {limit}, so "
                         f"it may be truncated, and a truncated listing reads "
                         f"exactly like a complete one. Raise --limit and "
                         f"re-run.")
    return (sorted(n[len(SLUG_LABEL_PREFIX):] for n in labels
                   if n.startswith(SLUG_LABEL_PREFIX)), len(labels), None)


def cmd_slugs(args):
    """Every slug this tracker has ever spent: `spent_slugs`, printed."""
    spent, labels, why = spent_slugs(args.repo, args.limit)
    if why:
        print(f"campaign-tracker slugs: {why}", file=sys.stderr)
        return 2
    print(f"read {args.repo}: {labels} label(s), {len(spent)} spent slug(s)")
    for s in spent:
        print(f"  {s}")
    if not spent:
        print("  (none: this is a reading, not a failed one)")
    return 0


# ------------------------------------------------------------------- work kind


def work_kind_labels(names):
    """Every `kind:` label on the issue, sorted. A calculation, so none, one and
    two are each a case with no network in it."""
    return sorted(n for n in names if n.startswith(WORK_KIND_LABEL_PREFIX))


def work_kind_of(names):
    """(work kind, why_unreadable) from a label list.

    `None, None` is a sub-issue with no work kind -- every one filed before the
    rule, and the state `check` warns about rather than refusing. `None, <why>`
    is TWO `kind:` labels, which is not a verdict for the same reason two
    `bound:` labels is not: a label set has no latest, so nothing here can
    choose which kind the work is.

    A word outside `WORK_KINDS` is `None, <why>` too, and not a kind that merely
    reads oddly: the word names the reference a worker is briefed from, so
    returning an unknown one hands out a brief nothing resolves."""
    found = work_kind_labels(names)
    if not found:
        return None, None
    if len(found) > 1:
        return None, (f"the sub-issue carries {len(found)} `kind:` labels "
                      f"({', '.join(found)}). A label set has no latest, so "
                      f"which kind the work is is unanswerable from here. "
                      f"Remove all but one.")
    kind = found[0][len(WORK_KIND_LABEL_PREFIX):].strip()
    if kind not in WORK_KINDS:
        return None, (f"the label is `{found[0]}`, and {kind!r} is not a work "
                      f"kind: one of {', '.join(WORK_KINDS)}. The word names the "
                      f"brief a worker is given, so it is refused rather than "
                      f"returned.")
    return kind, None


def cmd_kind(args):
    """The sub-issue's work kind, as a word on stdout."""
    kind, why = work_kind_of(labels_of(args.repo, args.campaign_issue))
    if why:
        print(f"campaign-tracker kind: {why}", file=sys.stderr)
        return 2
    if kind is None:
        print("none")
        return 1
    print(kind)
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
    _, why = gh_read(["gh", "label", "create", want, "-R", args.repo,
                      "--force", "--color", "0E8A16", "--description",
                      "the machine this campaign is bound to"])
    if why:
        print(f"campaign-tracker bind: could not ensure the label {want} "
              f"exists: {why}", file=sys.stderr)
        return 1
    cmd = ["gh", "issue", "edit", str(args.campaign_issue), "-R", args.repo]
    if not already:
        cmd += ["--add-label", want]
    for n in drop:
        cmd += ["--remove-label", n]
    _, why = gh_read(cmd)
    if why:
        print(f"campaign-tracker bind: the edit failed: {why}", file=sys.stderr)
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
    kind = kind_of(CAMPAIGN_LABEL in names, parented, CHORE_LABEL in names)
    findings = shape_findings(kind, title, body, want_plan=False, names=names)
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
# THE TITLE IS READ IN A LIST, never on its own: `campaign-tracker index`, `gh
# issue list` and a terminal tab all put it beside its neighbours, and at 80 a
# title had room for a clause of reason or a second item and used it -- "..., the
# review fan-out cost first". 40 is the width at which only the mission fits, so
# the reason goes in `## Intent` where a reader can ask for it. The owner set it
# on 2026-09-10; closed issues keep the titles they were filed with.
TITLE_CEILING = 40
BACKLOG_LABEL = "backlog"
# A CHORE: a campaign issue carrying this label is its own one unit of work --
# no sub-issue, claimed as itself (AGENTS.md § Routing an arriving request;
# `WellFormed` in spec/campaign/github/system.als). One spelling, imported by
# `campaign-claim.py`, `campaign-close.py` and `campaign-open.py`.
CHORE_LABEL = "chore"

# THE SECTION VOCABULARY, stated once, here -- the NAMES, that is, but the two
# a script reads the entries of, which are campaign-repos.py's; the two
# ceilings below are stated once each as a constant, and the templates and
# AGENTS.md say a ceiling exists rather than repeating its number. A kind OMITS
# a section; it never renames one, which is what `## Requirements` beside a
# sub-issue's `Definition of done` was doing -- two names for one purpose.
# `## Plan` is conditional on the moment and so is not in any tuple; see
# `required_sections`.
#
# A CHORE OMITS THREE OF THEM. `## Scope` is the section routing reads to ask
# whether an arriving request belongs to an open campaign, and a chore is one
# unit of work that admits nothing further, so carrying one would invite a
# sub-issue it cannot take; `## Plan` and `## Lands in` are a sub-issue's, and
# a chore has none -- which repository its claim is cut in is `## Repos` and
# `--repo`.
CAMPAIGN_SECTIONS = ("Intent", "Scope", "Definition of done",
                     REPOS.REPOS_HEADING)
CHORE_SECTIONS = ("Intent", "Definition of done", REPOS.REPOS_HEADING)
LANDS_SECTION = REPOS.LANDS_HEADING
SUB_ISSUE_SECTIONS = ("Intent", "Definition of done", LANDS_SECTION)
PLAN_SECTION = "Plan"

# HOW AN ISSUE OR A PULL REQUEST IS NAMED (kalaluthien/campaign-base#217, the
# owner's word on 2026-09-10). An issue is `<slug>#N` -- `machinery#1`,
# `sdlc-alloy#246` -- and a pull request is `pr#N`. Five campaigns file onto one
# tracker, so a bare `#1` and a bare `#272` are the same shape and neither says
# which campaign it belongs to; the slug is the only thing that does.
# `kalaluthien/campaign-base#217`, the full name the `Closes` keyword needs, is
# already qualified and is not bare: what qualifies every one of these forms is
# the WORD CHARACTER immediately before the `#` -- the `y` of `sdlc-alloy`, the
# `r` of `pr`, the `e` of `campaign-base`. So the lookbehind is `\w` and not a
# hand-picked class: a list would need a case per member to say why each is in
# it, and the definition needs one case for the BOUNDARY instead. `#` is not a
# word character, so `##42` reads as a bare `#42`, which is warning-only and
# has its own case.
#
# `re.ASCII`, BECAUSE A SLUG IS ASCII. `campaign-name-session.py`'s `SLUG` is
# `[a-z][a-z0-9]*(-[a-z0-9]+)*`, so nothing that qualifies a reference is
# outside ASCII -- while `\w` is unicode by default, which made `한#42` and
# `café#42` read as qualified. Korean prose is what a person writes here, so
# that is the hole and not the edge case.
#
# A WIDER CLASS WAS MEASURED AND COST REAL MISSES. Barring `-`, `/` and `.`
# suppressed five occurrences in the BODIES of the 164 issues on this tracker
# -- `pre-#181`, `#116/#160`, `#59/#80`, `pre-#68`, `pre-#41` -- and a sixth in
# issue 48's TITLE, which the narrow class gains too but which only a `check`
# that reads titles ever reaches. OCCURRENCES AND NOT WARNINGS: this dedupes by
# number, and four of the five bodies name the same issue again somewhere the
# wide class already caught, so what a reader is newly told about is issue 48's
# `#41` alone. It protected no qualified form: each of those was already saved
# by its own last letter.
#
# A WARNING AND NOT A REFUSAL, and that is measured rather than lenient: every
# issue and every comment on this tracker predates the rule and carries bare
# references, so refusing would wall the tracker's own history the first time
# anybody edited one of them. `check` prints the finding and still exits on the
# shape alone.
BARE_REFERENCE = re.compile(r"(?<!\w)#(\d+)", re.ASCII)


def bare_references(text):
    """Every unqualified `#N` in the text, first appearance first, deduped.

    THE ONE READER of the reference form, and `check-campaign-claim.py` imports
    it for the comment half rather than restating the pattern: an issue body and
    a comment are the same rule read at two moments, and two patterns would
    drift on the first edit to either."""
    seen, out = set(), []
    for m in BARE_REFERENCE.finditer(text or ""):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append("#" + m.group(1))
    return out


def bare_reference_warning(bare):
    """The one sentence both readers print, or "" when there is nothing to say.

    Here so the guard prints the same words on a comment that `check` prints on
    a body -- one fact, one form, wherever a reader meets it."""
    if not bare:
        return ""
    return (f"{len(bare)} bare reference(s): {', '.join(bare)}. An issue is "
            f"`<slug>#N` and a pull request `pr#N`; five campaigns file onto "
            f"one tracker, so a bare number names no campaign. A warning and "
            f"not a refusal: every body written before the rule carries them.")


# THE WORDS ARE campaign-roles.py's ISSUE_KINDS (rule-check#370 row 21): its
# licences are keyed by them, and the guard reads that leaf on every call.
ISSUE_KINDS = load(Path(__file__).resolve().parent.parent / ".claude" / "skills"
                   / "assuming-role" / "scripts" / "campaign-roles.py",
                   "campaign_roles").ISSUE_KINDS
CAMPAIGN, SUB_ISSUE, STRAY, THIRD_KIND = ISSUE_KINDS
# THE CHORE'S WORD IS THIS FILE'S AND NOT THAT LEAF'S. `own_campaign_gh` keys a
# licence by the kind a `gh` write lands on, and a chore is a campaign issue to
# every one of those readers -- it carries the label, it is nobody's sub-issue,
# and the guard reaches it through the same carve-out. What tells the two apart
# is the SHAPE, which is this file's alone, so the word joins ISSUE_KINDS here:
# `campaign-close.py` builds its `read #N: <kind> (...)` pattern out of this
# module's tuple, and a word missing from it would leave a chore's `check` line
# unparsed. The spelling is the label's, so a rename moves both at once.
CHORE = CHORE_LABEL
ISSUE_KINDS += (CHORE,)


def kind_of(labelled, parented, chore=False):
    """The issue's kind from the structural facts, and nothing else.

    Four outcomes, not three: `stray` -- labelled AND parented -- is the row
    `classify` above already names, and it is a defect reported rather than a
    kind, because no reader can say whether it is a campaign somebody filed
    under a parent or a sub-issue somebody labelled.

    `chore` is the fifth, and it is a narrowing of the campaign issue rather
    than a kind beside it: only a labelled, parentless issue can be one. It
    defaults off, so a caller that reads no labels -- the survey's `classify`,
    the guard's sub-issue carve-out -- keeps reading a chore as the campaign
    issue it is."""
    if labelled and parented:
        return STRAY
    if labelled:
        return CHORE if chore else CAMPAIGN
    if parented:
        return SUB_ISSUE
    return THIRD_KIND


def required_sections(kind, want_plan):
    """The sections this kind must carry at this moment, or () for a kind with
    no shape."""
    if kind == CAMPAIGN:
        return CAMPAIGN_SECTIONS
    if kind == CHORE:
        return CHORE_SECTIONS
    if kind == SUB_ISSUE:
        return SUB_ISSUE_SECTIONS + ((PLAN_SECTION,) if want_plan else ())
    return ()


def shape_findings(kind, title, body, want_plan, names=()):
    """Every way this issue's shape is wrong, as a list of lines; empty when it
    holds. Pure, so each finding has a case that does not spend a request.

    IT REPORTS ALL OF THEM, not the first. A body that is both too long and
    missing a section needs two edits, and a checker that names one sends its
    reader back for the other.

    `names` is the issue's LABEL list, and two things are read off it. The
    `kind:` label a sub-issue carries: an unreadable one -- two labels, or a
    word outside `WORK_KINDS` -- is a finding, while a MISSING one is the
    warning `cmd_check` prints, because every sub-issue filed before the rule
    has none and `campaign-claim take` gates on these findings. And the two
    label states a `chore` may not be in, which are findings and not warnings
    because `take` is where a chore is claimed. Optional and
    empty by default, so a caller that has no labels to hand asks for no reading
    of them rather than being told the label is absent."""
    out = []
    if kind == STRAY:
        return [f"it carries the `{CAMPAIGN_LABEL}` label AND a parent. That is "
                f"not a kind: no reader can say whether it is a campaign filed "
                f"under a parent or a sub-issue wearing the label. Remove one."]
    # AN EMPTY TITLE IS CODE'S OWN REFUSAL, and it is stated here so that the
    # `verb-first` reading can be settled by it rather than asked: a `noul` has
    # no no-match option, so a state with no title at all comes back a confident
    # `no` that says nothing about a title nobody wrote (DECISION 5715993782).
    if not title.strip():
        out.append("the title is empty, so it names no mission to carry out")
    elif len(title) > TITLE_CEILING:
        out.append(f"the title is {len(title)} characters, over {TITLE_CEILING}")
    if len(body) > BODY_CEILING:
        out.append(f"the body is {len(body)} characters, over {BODY_CEILING}. "
                   f"Design longer than that is a file on the claim's branch, "
                   f"linked from `## {PLAN_SECTION}`")
    found = REPOS.headings(body)
    for want in required_sections(kind, want_plan):
        # THE DESTINATION IS NOT A PRESENCE TEST. Every other section here is
        # judged by its heading alone -- what belongs under `## Intent` is
        # judgement and stays prose. `## Lands in` is the one row a script
        # already decides in full, and it is asked rather than approximated:
        # the two disagreed on four bodies, and `check` printed "the shape
        # holds" where `campaign-claim take` then refused
        # (kalaluthien/campaign-base#217).
        if want == LANDS_SECTION:
            _entry, why = REPOS.lands_in(body)
            if why:
                out.append(f"`## {want}`: {why}")
            continue
        if want not in found:
            out.append(f"no `## {want}` section, which a {kind} requires"
                       + (" at a claim" if want == PLAN_SECTION else ""))
    if kind == SUB_ISSUE:
        _work_kind, why = work_kind_of(names)
        if why:
            out.append(f"the `{WORK_KIND_LABEL_PREFIX}<k>` label does not read: "
                       f"{why}")
    # THE CHORE'S TWO LABEL STATES, read off `names` and not off the kind --
    # the second of them is exactly the case where the kind is something else.
    # A stray returned above and is untouched by either: what a chore label
    # means on an issue that is both a campaign and a sub-issue is the question
    # nobody can answer, and one finding names the one repair.
    if CHORE_LABEL in names:
        if is_standing(names):
            out.append(f"it carries `{CHORE_LABEL}` AND `{STANDING_LABEL}`: a "
                       f"chore's close is pre-authorised by the work it is, "
                       f"and `{STANDING_LABEL}` is the person's word that a "
                       f"campaign stays open. Remove one")
        if CAMPAIGN_LABEL not in names:
            out.append(f"it carries `{CHORE_LABEL}` without `{CAMPAIGN_LABEL}`: "
                       f"a chore IS a campaign issue, worked as itself, so off "
                       f"one the label names nothing")
    return out


def issue_shape(repo, number, timeout=None):
    """(title, body, labels, the parent's number or None, why_unreadable).
    The number and not a bool, because `check` prints it: a sub-issue is
    closed as a sub-issue OF its parent, and `campaign-close.py` reads which
    one off that line rather than asking GitHub a second time."""
    text, why = gh_read(["gh", "issue", "view", str(number), "-R", repo,
                         "--json", "title,body,labels,parent"], timeout)
    if why:
        return None, None, None, None, why
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, None, None, None, f"could not parse gh's output ({e})"
    names = label_names(data)
    return (data.get("title") or "", data.get("body") or "", names,
            (data.get("parent") or {}).get("number"), None)


def judgment_lines(verdicts, logged, model, settled_kind, show_kind=True,
                   settled_verb=None):
    """The lines `check` prints for one reading. A calculation, so every branch
    -- warned, read, unknown, uncertain, suggested, settled -- has a case that
    spends no request.

    EVERY LINE SAYS WHAT IT IS. A reader meeting `WARNING` beside the findings
    needs to know which of the two can refuse it, and only one can; a line the
    LABEL settled says so, because a suggestion that merely repeats the owner's
    own word would read as a second opinion agreeing with them.

    THE TIER DECIDES WHETHER A LINE IS PRINTED AT ALL. Both readings sit at
    `advise`, whose verdict is `show`; one moved to `shadow` would print
    nothing here and still log, which is what a reading entering the process is
    meant to cost."""
    out = []
    verb = verdicts[VERB_FIRST]
    # THE PREFILTER SAYS SO, as the `kind:` label's does below: a line the
    # model never saw must not read as a second opinion agreeing with code.
    if settled_verb:
        out.append(f"  verb-first  `{settled_verb}`, settled by code: the title "
                   f"is empty, which `check` refuses above, so nothing was asked")
    # AN `unknown` IS ALWAYS REPORTED, whatever the tier asks for a decided
    # answer: it is this reading's own failure and its reason, not advice the
    # tier is rationing.
    elif verb.word == "unknown":
        out.append(f"  verb-first  unknown: {verb.why}")
    # AN `uncertain` IS PRINTED AS THAT WORD AND WARNS NOTHING (DECISION
    # 5715993782). It is an answer that landed between the two measured edges,
    # so the `no` it would otherwise have warned about is the one the band says
    # is not earned -- and a warning nobody can act on is a warning that teaches
    # a reader to skip them.
    elif verb.word == "uncertain":
        out.append(f"  verb-first  uncertain: {verb.why}")
    elif verb.does != "show":
        out.append(f"  verb-first  not shown: tier `{verb.tier}`")
    elif verb.word == "no":
        out.append("  WARNING the title does not open with an imperative verb "
                   "naming a mission, Jev reads. A warning and not a refusal: "
                   "a judgment advises and never refuses.")
    else:
        out.append("  verb-first  yes")
    kind = verdicts[WORK_KIND]
    # ASKED WHATEVER THE ISSUE IS, PRINTED ONLY WHERE IT MEANS SOMETHING. One
    # group is one state and one call, so the kind question rides along on a
    # campaign issue too and its answer is logged and joined like any other;
    # what a campaign issue has no room for is the SUGGESTION, since only a
    # sub-issue wears a `kind:` label.
    if not show_kind:
        pass
    elif kind.word in ("unknown", "uncertain") and not settled_kind:
        out.append(f"  kind suggestion {kind.word}: {kind.why}")
    elif settled_kind:
        out.append(f"  kind        `{WORK_KIND_LABEL_PREFIX}{settled_kind}` "
                   f"already, so nothing was asked")
    elif kind.does != "show":
        out.append(f"  kind suggestion not shown: tier `{kind.tier}`")
    elif kind.word in WORK_KINDS:
        out.append(f"  SUGGESTION Jev reads this as "
                   f"`{WORK_KIND_LABEL_PREFIX}{kind.word}`. A suggestion "
                   f"and not a label: only the owner of the issue sets one.")
    else:
        out.append(f"  kind suggestion unknown: the answer `{kind.word}` is no "
                   f"kind of work this tree names")
    out.append(f"  judged by {model or '<nothing answered>'}, {logged}")
    return out


def judgment_report(repo, number, title, body, settled_kind, show_kind=True):
    """The judgment lines for this issue, or the one line saying there are none.

    `scripts/campaign-jev.py` OWNS THE CALL AND `scripts/jev/readings.json` THE
    QUESTION: the key, the pinned model, every failure path, the log, the
    wording, the cuts and the tier are theirs, and this hands a group name, a
    state and the join key and reads the verdicts back. Loaded here and not at
    import, because `check-campaign-claim.py` imports this module on every tool
    call for `bare_references` and must not pay for a dependency no guard uses.

    THE LABEL IS THE PREFILTER. Where the issue carries a `kind:` label, code
    has settled that reading and the word is passed as `settled`: the model is
    never asked, the log counts the case all the same, and a reader is never
    invited to weigh a guess against the owner."""
    # THE GUARD COVERS THE CALL AND NOT ONLY THE LOAD. `ask` promises to answer
    # rather than raise, and this is the second reader of that promise: a
    # judgment is an aside to a reading already made, so a traceback from it
    # must not cost `check` its verdict -- and `campaign-claim take` gates on
    # that verdict, so it must not cost a worker its claim either. `judge`
    # DOES raise on a state field that is missing or extra, which is this
    # caller's own bug and lands here rather than in a reader's face.
    # THE PREFILTER COMES FIRST AND THE SETTLED READING IS NEVER SENT. The
    # `kind:` label settles `work-kind`; an empty or whitespace-only title
    # settles `verb-first` as `no`, since that is `check`'s own refusal two
    # findings up and a `noul` has no no-match option to answer it with.
    settled_verb = "no" if not title.strip() else None
    settled = {}
    if settled_kind:
        settled[WORK_KIND] = settled_kind
    if settled_verb:
        settled[VERB_FIRST] = settled_verb
    try:
        jev = load(Path(__file__).resolve().parent / "campaign-jev.py",
                   "campaign_jev")
        judged = jev.judge(JUDGMENT_GROUP, {"title": title, "body": body},
                           read=f"{repo}#{number}",
                           reader="campaign-tracker.py check",
                           key={"repo": repo, "issue": number},
                           settled=settled or None)
    except Exception as e:  # noqa: BLE001 -- a reading that did not happen
        return [f"  judgments not read: campaign-jev.py raised where it "
                f"promises not to ({e.__class__.__name__}: {e})"]
    # THE TWO NAMES ARE READ BEFORE THEY ARE INDEXED. `judgment_lines` reaches
    # for both by name, and a reading renamed or dropped from the group would
    # be a KeyError OUTSIDE the guard above -- a traceback out of `check`, and
    # `campaign-claim take` gates on `check`'s verdict, so it would cost a
    # worker its claim over a registry edit. Missing is `unknown` with a reason,
    # like every other reading that did not happen.
    missing = [n for n in (VERB_FIRST, WORK_KIND) if n not in judged.verdicts]
    if missing:
        return [f"  judgments not read: the `{JUDGMENT_GROUP}` group answers "
                f"{', '.join(sorted(judged.verdicts)) or '<nothing>'}, and "
                f"this reads {', '.join(missing)}: unknown"]
    return judgment_lines(judged.verdicts, judged.logged, judged.model,
                          settled_kind, show_kind, settled_verb)


# S7's two readings, sdlc-alloy#458 DECISION 5724477924: which scenario `spec/`
# already declares covers a sub-issue's `## Plan`. THEIR OWN GROUPS AND THEIR
# OWN CALLS, because the state is `{plan, scenarios}` and then `{plan,
# scenario}`, neither of which is `issue-shape`'s `{title, body}` -- one call a
# state (DECISION 5716072632). Both sit at `shadow` and this prints nothing.
PLAN_SELECT, PLAN_COVER = "plan-scenario-select", "plan-scenario-cover"
PLAN_READER = "campaign-tracker.py check"
# The committed snapshot, the one inventory of every declared command.
SNAPSHOT = "commands.snapshot.json"
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "spec" / SNAPSHOT
# The entity a Plan names, where it names one at all -- 5 of this tracker's 138
# Plans do. A Plan naming none is cut to nothing and gets every command.
PLAN_ENTITY = re.compile(r"\bspec/(campaign/[a-z]+|sdlc)/")
# An Alloy line comment, and a command declaration. The comment ABOVE a
# declaration is a group heading several commands share, which is why a blank
# line does not end the walk up and another declaration does.
ALS_COMMENT = re.compile(r"^\s*(?:--|//)\s*(\S.*?)\s*$")
ALS_COMMAND = re.compile(r"^\s*(?:run|check)\s+\w+")


def comment_above(lines, at):
    """The nearest line comment above the declaration at `lines[at]`, or "".

    NEITHER A BLANK LINE NOR ANOTHER DECLARATION ENDS THE WALK: these comments
    are group headings sitting above a RUN of commands -- `-- the floor` over
    four of them -- so the one belonging to a command is the last heading
    written before it, and stopping at the declaration above would leave every
    command but the first of each run with no text at all (86 of 244 rather
    than 203). A BLOCK COMMENT ENDS IT, so the module's own header, which is
    about the file and not about any command, never stands in for one."""
    for i in range(at - 1, -1, -1):
        line = lines[i].strip()
        if not line or ALS_COMMAND.match(lines[i]):
            continue
        if line.endswith("*/"):
            return ""
        found = ALS_COMMENT.match(lines[i])
        if found:
            return found.group(1)
    return ""


def scenarios_of(plan, root=None):
    """`{s1: "<verb> <Name>\\n<the comment line above it>"}` for every command
    the committed snapshot lists, cut to the entity the Plan names.

    A PLAN NAMING NO ENTITY GETS ALL OF THEM, which is the ordinary case and
    not a fallback: 133 of this tracker's 138 Plans name none, and all 244
    commands come to 26,244 bytes against `campaign-jev.py`'s 60,000 budget.
    So no state is skipped for want of an entity, and the cut buys a narrower
    field only where there is one to read (sdlc-alloy#458 NOTE 5724505059)."""
    path = Path(root) / "spec" / SNAPSHOT if root else SNAPSHOT_PATH
    try:
        commands = json.loads(path.read_text(encoding="utf-8"))["commands"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}, "the committed snapshot did not read"
    want = {m.group(1) for m in PLAN_ENTITY.finditer(plan)}
    kept = [c for c in commands
            if not want or str(c[0]).rsplit("/", 1)[0] in want]
    if not kept:
        return {}, (f"the snapshot holds no command"
                    + (f" under {', '.join(sorted(want))}" if want else ""))
    heads = {}
    out = {}
    for i, (rel, verb, name) in enumerate(kept, 1):
        src = (Path(root) / "spec" / rel if root
               else SNAPSHOT_PATH.parent / rel)
        if rel not in heads:
            try:
                heads[rel] = src.read_text(encoding="utf-8").splitlines()
            except OSError:
                heads[rel] = []
        lines = heads[rel]
        decl = re.compile(rf"^\s*{verb}\s+{re.escape(name)}\b")
        at = next((n for n, line in enumerate(lines) if decl.match(line)), None)
        above = comment_above(lines, at) if at is not None else ""
        out[f"s{i}"] = f"{verb} {name}" + (f"\n{above}" if above else "")
    return out, ""


def settled_scenario(plan, scenarios):
    """The option key where the Plan names one command by its EXACT name in
    backticks -- code has decided the reading and the model is never asked.

    TWO SUCH SPANS NAMING TWO COMMANDS SETTLE NOTHING: the author named more
    than one, and which of them covers the Plan is the question."""
    by_name = {v.split("\n", 1)[0].split(None, 1)[-1]: k
               for k, v in scenarios.items()}
    found = {by_name[t] for t in re.findall(r"`([^`]+)`", plan) if t in by_name}
    return found.pop() if len(found) == 1 else None


def plan_scenario_read(repo, number, body):
    """Ask both plan readings and print nothing. AT `shadow` THERE IS NOTHING
    TO PRINT: the call writes its log row, `corpus join` labels it off the
    closing pull request's diff, and no reader is shown a guess.

    EVERY FAILURE IS SWALLOWED HERE for the reason `judgment_report`'s is:
    `campaign-claim take` gates on `check`'s verdict, so a traceback from an
    aside must not cost a worker its claim."""
    try:
        # `section` GIVES THE NON-BLANK LINES AND NOT THE TEXT, and a list
        # handed to a regex raises rather than reading empty -- which the guard
        # below would have swallowed into a reading that never happened.
        plan = "\n".join(REPOS.section(body, PLAN_SECTION) or ())
        if not plan.strip():
            return
        scenarios, why = scenarios_of(plan)
        jev = load(Path(__file__).resolve().parent / "campaign-jev.py",
                   "campaign_jev")
        key = {"repo": repo, "issue": number}
        # THE OPTION CEILING IS THE ENDPOINT'S AND THE NUMBER IS `campaign-jev`'s
        # to state. The call carries one option a scenario PLUS the entry's own
        # `noMatch`, so a cut of the ceiling itself is already one too many.
        # This is the branch `spec/` grows into: 244 commands today against 255,
        # and a Plan naming no entity gets all of them. It is a SKIP ROW naming
        # the count, because the alternative -- dropping scenarios to fit -- is
        # a reading that silently stopped offering the right answer.
        if not why and len(scenarios) >= jev.OPTION_BUDGET:
            why = (f"the cut leaves {len(scenarios)} scenario(s) and the call "
                   f"takes {jev.OPTION_BUDGET} options counting `noMatch`: "
                   f"`spec/` has outgrown a Plan that names no entity")
        if why:
            jev.skip(PLAN_READER, f"{repo}#{number} {PLAN_SELECT}", why)
            return
        settled = settled_scenario(plan, scenarios)
        picked = jev.judge(
            PLAN_SELECT, {"plan": plan, "scenarios": scenarios},
            read=f"{repo}#{number}", reader=PLAN_READER,
            key=key, settled={PLAN_SELECT: settled} if settled else None)
        word = picked.verdicts[PLAN_SELECT].word
        if word not in scenarios:
            return
        jev.judge(PLAN_COVER, {"plan": plan, "scenario": scenarios[word]},
                  read=f"{repo}#{number}", reader=PLAN_READER, key=key)
    except Exception:  # noqa: BLE001 -- a reading that did not happen
        return


def cmd_check(args):
    repo, number = args.repo, args.campaign_issue
    title, body, names, parented, why = issue_shape(repo, number)
    if why:
        print(f"campaign-tracker check: could not read {repo}#{number} -- {why}\n"
              f"  An issue that did not read is not an issue with no shape.",
              file=sys.stderr)
        return 2
    kind = kind_of(CAMPAIGN_LABEL in names, parented, CHORE_LABEL in names)
    found = REPOS.headings(body)
    # WHAT WAS READ, ALWAYS, and before the verdict. A bare pass is the shape
    # that gets trusted for months while checking nothing.
    print(f"read {repo}#{number}: {kind}"
          f" (label `{CAMPAIGN_LABEL}`: {'yes' if CAMPAIGN_LABEL in names else 'no'},"
          f" parent: {'#' + str(parented) if parented else 'no'})")
    print(f"  title  {len(title)} chars (ceiling {TITLE_CEILING})")
    print(f"  body   {len(body)} chars (ceiling {BODY_CEILING})")
    print(f"  sections found: {', '.join(found) or '<none>'}")
    want = required_sections(kind, args.plan)
    print(f"  sections required: {', '.join(want) or '<none: this kind has no shape>'}")
    # THE WORK KIND, PRINTED WITH THE READING. An unreadable label is a finding
    # below; an ABSENT one is a warning here and moves no exit status, because
    # every sub-issue filed before the rule carries none and `campaign-claim
    # take` refuses on a finding -- a refusal would wall the claim on all of
    # them at once.
    settled_kind = None
    if kind == SUB_ISSUE:
        work_kind, work_why = work_kind_of(names)
        if work_kind:
            settled_kind = work_kind
            print(f"  kind   {work_kind}")
        elif not work_why:
            print(f"  WARNING no `{WORK_KIND_LABEL_PREFIX}<k>` label, so what "
                  f"kind of work this is is unrecorded: one of "
                  f"{', '.join(WORK_KINDS)}. A warning and not a refusal: every "
                  f"sub-issue filed before the rule carries none.")
    if BACKLOG_LABEL in names:
        print(f"  carries `{BACKLOG_LABEL}`: not worked until the owner removes "
              f"it; `campaign-claim take` refuses a claim on it")
    # THE JUDGMENTS, ONE CALL, printed with the reading. Both advise and neither
    # moves the exit status, so a failed call costs this reading nothing.
    for line in judgment_report(repo, number, title, body, settled_kind,
                                show_kind=kind == SUB_ISSUE):
        print(line)
    # THE PLAN READINGS, AT `shadow`, PRINTING NOTHING. They ride here and not
    # in the call above because their state is the Plan and the snapshot's
    # commands, not the title and body: one call a state.
    if kind == SUB_ISSUE:
        plan_scenario_read(repo, number, body)
    print("  NOT checked: whether the body is bullets rather than prose, "
          "whether `## Definition of done` is checkable. Those are judgement "
          "and nothing reads them; verb-first is read above, by Jev, as a "
          "warning.")
    # A WARNING, PRINTED WITH THE READING AND NOT WITH THE VERDICT. It is on
    # stdout beside everything else this read, and it moves no exit status: the
    # corpus predates the rule, so a body carrying nothing but bare references
    # still has a shape that holds.
    warning = bare_reference_warning(bare_references(title + "\n" + body))
    if warning:
        print(f"  WARNING {warning}")
    findings = shape_findings(kind, title, body, args.plan, names=names)
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
    what = f"gh {' '.join(args)}"
    text, why = gh_read(["gh", *args])
    if why:
        return None, f"{what}: {why}"
    if not text.strip():
        return None, f"{what} printed nothing"
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, (f"{what} returned something that is not JSON "
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

    Read off the REMOTE's claim refs since #176: a claim is a branch
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
    # THE SLUG MUST BE RESOLVED HERE, not left to `all_refs`'s own default: a
    # caller that skips this reads the slug as `None` every time, which reads
    # no prefix at all (`campaign-claim.py`'s `prefixes`) and reports "no slug
    # that could be read" for a campaign whose slug is in fact readable.
    slug, slug_note = module.campaign_slug(campaign_issue)
    found_map, unread = module.all_refs(repos, campaign_issue, slug)
    if unread:
        return (lambda n: ""), (f"the claim refs did not read -- "
                                f"{'; '.join(unread)}; the rows below say "
                                f"nothing about who holds what")
    branches = sorted(found_map)
    note = (f"{slug_note}; read refs under {slug + '/' if slug else 'no prefix'} "
            f"in {', '.join(repos)} -- {len(branches)} claim(s)")

    def word(number):
        found = module.refs_for_issue(branches, number, slug)
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
        module = load(path, "campaign_claim")
    except Exception as e:                      # noqa: BLE001 -- any of them
        return None, f"{path}: {e.__class__.__name__}: {e}"
    return module, None


# WHAT `settlement` PRINTS BESIDE ITS TABLE opens with a word of its own. The
# four lines opened `REPORT:`, which is a comment kind, and campaign-close.py
# told the two that refuse a close from the rest by matching the prose after
# it (rule-check#370 row 26); it reads NOT_CAMPAIGN now.
NOT_CAMPAIGN = "not a campaign issue:"


def campaign_issue_reports(head):
    """What says the number handed in is not a campaign issue. Costs no extra call.

    The campaign issue repository is a member of its own campaigns, so the number handed
    in may be a sub-issue and a sub-issue may be a campaign issue. Neither is visible in a
    settlement table. These reports read labels and the parent relation, never
    the body: prose is editable and the parent relation is not."""
    if CAMPAIGN_LABEL not in label_names(head):
        yield (f"{NOT_CAMPAIGN} no `{CAMPAIGN_LABEL}` label, so this may be a "
               "sub-issue read as a campaign issue")
    if head["parent"]:
        yield (f"{NOT_CAMPAIGN} it is itself a sub-issue of "
               f"#{head['parent']['number']} -- closing that campaign will not "
               "settle this one")


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
        print(f"  -- nested: {ref} has {total} sub-issue(s) of its own, not "
              "listed above; run this on it too")

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
        print("  -- closed early: the campaign issue is closed with sub-issues "
              "still open")
    return 0


# ------------------------------------------------------------------------ main


def campaign_issue_number(text):
    """The campaign issue as `bound` validates it: a bare positive issue number.

    Only `bound` refuses a malformed one before spending a request, because it
    is the reading whose caller acts on a printed word and would otherwise read
    a usage error as a verdict."""
    n = text.lstrip("#")
    if not n.isascii() or not n.isdigit() or int(n) <= 0:
        refuse_label_reading(f"not an issue number: {text!r}")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("campaign-issues", help="the open-campaign issue survey")
    a.add_argument("--repo", default=DEFAULT_REPO)
    a.add_argument("--limit", type=int, default=200)
    a.set_defaults(fn=cmd_campaign_issues)

    # `issue` and `slugs` take no campaign issue number, so neither joins the
    # loop below: one is keyed by the slug and the other by nothing.
    a = sub.add_parser("issue", help="the campaign issue a slug names")
    a.add_argument("slug")
    a.add_argument("repo", nargs="?", default=DEFAULT_REPO)
    a.set_defaults(fn=cmd_issue)

    a = sub.add_parser("slugs", help="every slug this tracker has spent")
    a.add_argument("repo", nargs="?", default=DEFAULT_REPO)
    a.add_argument("--limit", type=int, default=LABEL_LIMIT)
    a.set_defaults(fn=cmd_slugs)

    # The optional positional repository is the override seam these three share.
    # One spelling across all three: `campaign-issues` takes `--repo` because it takes
    # `--limit` beside it, and a positional there would read as the campaign issue.
    for name, fn, help_text in (
            ("slug", cmd_slug, "the campaign's slug, or `none`"),
            ("bound", cmd_bound, "here | elsewhere <machine> | unbound"),
            ("standing", cmd_standing, "standing | not-standing: the person's "
                                       "hold on the close"),
            ("kind", cmd_kind, "the sub-issue's work kind, or `none`"),
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
        p.set_defaults(fn=fn)

    args = ap.parse_args()
    global READING
    READING = args.cmd
    if args.cmd in ("slug", "bound", "standing", "kind", "bind", "check"):
        args.campaign_issue = campaign_issue_number(args.campaign_issue)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
