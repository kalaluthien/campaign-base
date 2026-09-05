#!/usr/bin/env python3
"""Take and release a sub-issue's claim, and say who is standing in one.

    campaign-claim.py take <N> <issue> <topic> [--repo owner/repo]
    campaign-claim.py release <N> <issue> [--branch B] [--confirmed-absent WHO]
                                          [--repo owner/repo]
    campaign-claim.py live <N> [--repo owner/repo]

THE CLAIM IS THE BRANCH, AND NOTHING ELSE

A claim used to be two things that had to agree: a branch on the remote, and a
`runtime/claims/<issue>` record on this machine saying which session held it.
The record answered attribution -- which session -- and liveness -- which pid.
Both answers are now read off facts that were already there:

  attribution   the WORKSPACE a claim branch is checked out in, read from
                `git worktree list`. Neither a harness restart nor a rename
                touches a checkout, which is exactly the pair the record's
                `session` field existed to survive.
  liveness      the herdr row itself.

So there is nothing to write, nothing to keep in step, and nothing that dies
with a directory. `spec/campaign/orchestration/system.als`'s `holder` is this
reading, and `AttributionIsSound` is what it costs: three events move a
checkout out from under a live agent -- an acquire, a directory delete, and a
sub-issue moved out of its campaign -- and after any of them the agent is live,
listed, and no longer the holder. `live` prints that state as its own group
rather than resolving it.

A WORKSPACE, NOT A SESSION, AND WHY THAT IS THE STRONGEST HONEST READING

The obvious join is a session's own directory: `herdr agent list` prints a
`cwd`, and `git -C <cwd> branch --show-current` prints a branch. Measured
against this machine on 2026-09-04 it found nothing, for two reasons that are
the ordinary case and not an edge:

  * herdr reports where a session was STARTED, not where it is working. A
    worker on the base works in a worktree (AGENTS.md, Execution mode) and
    its herdr `cwd` stays at the clone it launched from, on `main`.
  * that worktree belongs to the BASE ROOT's repository, while the clone the
    session sits in is a different repository with its own `.git`, so
    `git -C <cwd> worktree list` cannot see the branch at all.

Nothing else on disk ties a session to a worktree, and the name may not be
tested against the branch -- they are two strings on purpose (AGENTS.md, The
session name). So per-session attribution is not derivable, and this does not
pretend otherwise: it answers WHERE a claim is checked out, which is what both
of its readers actually ask. `release` needs to know somebody is sitting in the
ref before it deletes it, and a close needs to know whether any claim is still
occupied; neither needs a session id. Addressing a holder is `ListAgents` and
the four messages, which is where it already was.

WHAT create-ref SERIALISES, AND WHAT `take` HAS TO ADD

The ref name carries the topic as well as the sub-issue, so create-ref's
server-side refusal separates `7-parser` from `7-parse-fix` and admits both --
two workers on one sub-issue, which is the thing a claim exists to stop. The
record this replaced was keyed on the sub-issue and gave that for free. So
`take` lists `campaign-<N>/` first and refuses on any ref already naming the
sub-issue, whatever its topic -- and then lists AGAIN after its own create-ref.
The first read is a narrowing and is not atomic on its own: two takers on two
topics both see no sibling and both create. The second read is what settles it,
because by then both refs exist and both takers see the same set. EVERYONE WHO
SEES A RIVAL YIELDS and deletes the ref it just cut, which held nothing; a
smallest-name tiebreak was the first shape of this and left both racers holding
in two interleavings, because they do not read the same set at the same moment.

That matters because the record this replaced was keyed on the sub-issue and
`O_EXCL` was COMPLETE on one machine -- and one machine is the only place a
campaign runs. Leaving the survey alone would have been a weakening dressed up
as a ceiling.

EVERY CLAIM CUTS A REF, REPO-LESS WORK INCLUDED

`take --local` used to write the record and cut nothing, for work that lands no
commit -- a scaffold, a sweep, a decision written into the campaign issue. With
no record there is nothing for it to write, and the atomicity it had moved onto
`O_EXCL` goes back where it belongs: create-ref's server-side refusal, which
serialises every machine and not just this one. A repo-less campaign cuts its
ref on the base, which is what `R4_RepolessCampaign` in
`spec/campaign/github/system.als` already required.

`release` FINDS THE BRANCH RATHER THAN BEING TOLD IT

The record used to carry the branch, so `release <issue>` knew which ref to
delete. The remote carries it too: refs under `campaign-<N>/` whose segment
after the slash opens with the sub-issue number. Two refs matching one
sub-issue is a refusal, not a guess. `--branch` names one directly, for the
case where the naming rule was broken and the sweep finds nothing.

A GONE REF WITH A MERGED PULL REQUEST IS NOTHING BEYOND MAIN

The normal end of a branch claim is a merged pull request and a deleted ref,
and the comparison `release` asks for then answers 404. A comparison that did
not happen is not an empty branch, so that used to refuse -- on the one path
every finished sub-issue takes. The 404 is read apart from every other failure,
and it is not trusted alone: the compare 404s identically for a gone ref, a
missing base and an unreachable repository, so `release` then asks the ref's own
endpoint and goes on only when that says 404 too. Then it asks GitHub for a
merged pull request whose head was this branch, and one found is the durable
record that everything the branch held is on main. No ref and no merged pull
request is still a refusal, because a branch that vanished without merging is
reported, never released.

A REF AHEAD OF MAIN IS KEPT, ONE SOMEBODY IS SITTING IN IS KEPT, AND AN EMPTY
ONE THAT WAS NEVER MERGED NEEDS A PERSON

Three refusals guard the delete, and they answer different questions.

A branch still ahead of main is the pull request's head, and deleting it would
take commits with it.

A branch checked out in a workspace is somebody's, and deleting the ref under it
strands them. That one is only readable now that attribution is derived, and it
is the reading the record could not make: a record said who CLAIMED a sub-issue,
never who is standing in it.

A branch that is empty AND was never merged is the third, and it is the one that
cost real work when it was missing. A claim is cut BEFORE its delegate is
launched, so between the create-ref and the delegate's first checkout every
claim looks exactly like finished work: 0 ahead of main, in no workspace. Delete
one there and a second `take` succeeds. A merged pull request whose head was
this branch is what tells the two apart, and with none, `--confirmed-absent WHO`
is a person saying the holder is gone. This is the proof the record's `session`
field carried, restored in the one place its absence destroyed work rather than
merely losing an address.

None is resolved here; nothing is deleted when any of the three bites.

THE BINDING IS READ BEFORE A REF IS CUT

`take` runs campaign-tracker `bound <N>` and cuts a ref only on `here`:
`elsewhere`, `unbound` and a failed read each refuse by name. That makes the
claim one of the binding's mechanically gated writes.

`live` MAKES BOTH READINGS AND CONCLUDES FROM NEITHER

    remote refs under campaign-<N>/      every claim, readable from anywhere
    git worktree list                    where each one is checked out, here
    herdr agent list                     what is still running, here

The first two join on the branch name and on nothing else. Three groups come
out -- claims checked out on this machine, claims checked out nowhere on it,
and every live session of this campaign -- and `live` reaches no verdict; a
close reads the counts.

WHICH REPOSITORIES ARE SWEPT

The base root always, resolved the way AGENTS.md resolves it, because
`<campaign>/worktrees/` hangs off it. Then the repository root of every live
session's `cwd`, which picks up each member clone without this script being
told where the clones are. A root git will not answer for is named, never
skipped: a repository that could not be swept is a reading that failed, and its
claims are not evidence of an empty machine.

WHAT IT REFUSES TO GUESS

A worktree listing this cannot make is reported and denies the clean verdict,
the same way a failed herdr read does. A detached worktree is a real answer --
it holds no branch -- because git answered.

WHAT WENT WITH THE RECORD, AND IS GONE

`take --name` checked a session's name against
`scripts/campaign-name-session.py`'s rule and refused one belonging to another
campaign, because a stale name written into a record sent every later reader to
the wrong session. There is no record to write a name into, so nothing
here refuses a name AT THE CLAIM any more: a claim can be cut under a stale
name, and the write that follows is where it is caught.

Two readers took the name up, and they ask different questions. #185's
check-campaign-claim.py resolves the ROLE from it on every write, so a
worker named for another campaign is refused that campaign's issues and a
name of no shape is refused both planes -- that is the enforcement of AGENTS.md
'The session name'. `OTHER_CAMPAIGN` below is #187's, and is only a shape: it
answers "does this name say whose it is at all", which `classify` needs to
leave another campaign's sessions out of a close, and it decides nothing about
permission.

EXIT

take     0 claimed, 3 already claimed, 1 the claim was refused or failed.
release  0 released, 1 refused or the reading failed.
live     0 every reading made, 1 one of them did not happen.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repos_module():
    """`campaign-repos.py`, imported for the three things only it should say:
    what the base's slug is, what makes two spellings one repository, and what
    a `## Repos` entry may look like. The LIST is still read by running it as a
    subprocess (`campaign_repos` below) -- its refusals are exit strings, and
    reading them back is what keeps one reader rather than two."""
    src = HERE / "campaign-repos.py"
    spec = importlib.util.spec_from_loader(
        "campaign_repos", importlib.machinery.SourceFileLoader(
            "campaign_repos", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _tracker_module():
    """`campaign-tracker.py`, imported for the one thing it owns that this file
    also needs: the `backlog` label's spelling. It is imported and not restated
    for the same reason `campaign-repos.py` is -- the LIST is still read by
    running that script, and this is a constant, not a reading.

    NO CYCLE: `campaign-tracker.py` imports THIS file only inside
    `claim_reader()`, at call time, so a module-level import here resolves."""
    src = HERE / "campaign-tracker.py"
    spec = importlib.util.spec_from_loader(
        "campaign_tracker", importlib.machinery.SourceFileLoader(
            "campaign_tracker", str(src)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


REPOS = _repos_module()
DEFAULT_REPO = REPOS.BASE_REPO

# THE SAME STRING, TWO QUESTIONS, so it is named twice on purpose. `DEFAULT_REPO`
# is where a ref is cut when nothing says otherwise; `TRACKER` is where every
# sub-issue is FILED whatever repository its code lives in (AGENTS.md, "filed on
# this base's tracker whatever repository its code lives in"). A reader that
# collapses them cannot express "read #N's body from the tracker, then cut its
# ref on the member repository the body names", which is exactly what #187 does.
TRACKER = DEFAULT_REPO
SHA = re.compile(r"^[0-9a-f]{40}$")

# A session name that names SOME campaign. Only the shape matters here -- which
# campaign is compared by the caller -- and `campaign-name-session.py` owns the
# rule itself; this is the loose reading that answers "does this name say whose
# it is at all", which is a different question from "is it well formed".
OTHER_CAMPAIGN = re.compile(r"^campaign-\d+-")

# `<slug>-<YYMMDD>` -- the campaign directory shape, read as a shape. Nothing
# derives the list from GitHub, because the question is which directories are on
# THIS machine. The same regex the claim guard uses.
CAMPAIGN_DIR = re.compile(r"-\d{6}$")


def run(*args, **kw):
    """A command that is not installed comes back as a failed run, not a
    traceback: `gh` absent, or `herdr` absent, or `git` absent, is the "I could
    not look" case this script is written to report, and a stack trace loses
    the reason."""
    try:
        return subprocess.run(args, capture_output=True, text=True, **kw)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess(
            args, 127, "", f"{args[0]}: {e.__class__.__name__}: {e}")


# --------------------------------------------------------------- the binding


def binding_verdict(word):
    """Why the binding refuses a ref cut, or None. `word` is the first token
    campaign-tracker `bound` printed: `here` admits; `elsewhere` and `unbound`
    refuse by name; anything else is a reading that failed, which refuses too,
    because a binding that could not be read is not a binding here."""
    if word == "here":
        return None
    if word == "elsewhere":
        return ("the campaign is bound elsewhere; a claim is a write only its "
                "machine makes (AGENTS.md, The binding)")
    if word == "unbound":
        return ("the campaign is not bound to any machine; only a person's "
                "word binds it, and a claim comes after")
    return f"the binding could not be read (campaign-tracker bound said {word!r})"


def binding_refusal(campaign_issue):
    """Read the binding through its one reader and say why it refuses, or
    None."""
    b = run(sys.executable, str(HERE / "campaign-tracker.py"), "bound",
            str(campaign_issue))
    word = (b.stdout.strip().split() or [""])[0]
    # Whole, on one line: the tracker's prefix is over a hundred characters and
    # gh's auth failure is several lines with the cause on the first, so
    # neither a prefix cut nor a last-line keep carries both ends.
    why = " ".join(b.stderr.split()) or b.stdout.strip() or "no message"
    return binding_verdict(word if b.returncode == 0 else
                           f"exit {b.returncode}: {why}")


# ---------------------------------------------------------- branches as claims


def branch_name(campaign_issue, issue, topic):
    return f"campaign-{campaign_issue}/{issue}-{topic}"


def issue_of_branch(branch, campaign_issue):
    """The sub-issue number a claim branch names, or None. Pure.

    `campaign-<N>/<issue>-<topic>`: the number is what stands between the slash
    and the first hyphen after it. A branch whose second segment does not open
    with digits and a hyphen claims no sub-issue this can name, and it comes
    back None rather than guessed at."""
    prefix = f"campaign-{campaign_issue}/"
    if not branch.startswith(prefix):
        return None
    m = re.match(r"(\d+)-", branch[len(prefix):])
    return m.group(1) if m else None


def parse_refs(text):
    """(branches, why_unreadable) from the matching-refs listing. Pure."""
    try:
        refs = json.loads(text or "[]")
    except json.JSONDecodeError as e:
        return None, f"the ref listing did not parse ({e.__class__.__name__})"
    if not isinstance(refs, list):
        return None, "the ref listing was not a list"
    return sorted(x[len("refs/heads/"):] for x in refs
                  if isinstance(x, str) and x.startswith("refs/heads/")), None


def matching_refs(repo, campaign_issue):
    """Every claim branch of this campaign on the remote.

    `git/matching-refs/` answers a prefix in one request and 200s with an empty
    array when nothing matches, so an empty campaign and an unreachable
    repository do not come back looking the same."""
    r = run("gh", "api", f"repos/{repo}/git/matching-refs/heads/"
            f"campaign-{campaign_issue}/", "--jq", "[.[].ref]")
    if r.returncode != 0:
        return None, (f"could not list {repo}'s campaign-{campaign_issue}/ "
                      f"refs: {' '.join(r.stderr.split())[:160]}")
    return parse_refs(r.stdout)


def issue_repo(issue, default_repo):
    """(repo, named, note) -- the repository a sub-issue's work lands in, read
    from the sub-issue's own body. `None` for repo means the reading did not
    happen; `named` is that repository when the body named a MEMBER one, and
    None for either spelling of the base -- `none`, and the base's own slug.
    `named` is what the `## Repos` scope check reads, and None is what exempts
    a destination from it.

    THE DESTINATION IS A FACT ABOUT THE SUB-ISSUE, NOT AN ARGUMENT. `--repo`
    used to decide it, so two takers naming different repositories both cut a
    ref and both believed they held sub-issue #N: the one-claim-per-issue rule
    is keyed on the issue and cannot see a disagreement about where the issue
    lives (spec/campaign/orchestration/scenarios.als, `claimOnTheIssuesRepo`,
    with `R8_ClaimCutOnAnotherRepo` for the cost of dropping it). The template
    has carried the destination since the sub-issue template existed and
    NOTHING read it, which is the shape a declared contract takes just before it
    drifts.

    IT IS THE `## Lands in` SECTION SINCE kalaluthien/campaign-base#217, and was
    a `Repository:` keyword line before. One purpose had two shapes -- that line
    here, `## Repos` on the campaign issue -- and the section is the one
    vocabulary; `campaign-repos.py`'s `lands_in` is its one reader and its
    docstring says why it is not `## Repos` with a count of one. The three
    outcomes below did not move.

    `none` is the answer for a repo-less sub-issue and means the base: with no
    member repository the only place a ref can be cut is the base, which is what
    `R4_RepolessCampaign` says. Three outcomes, not two -- a body that could not
    be fetched is not a body with no line in it.

    THE BASE SPELLED OUT IS THE SAME DESTINATION AS `none`, and `named` is None
    for both. `## Repos` lists the MEMBER repositories a campaign clones when it
    opens; the base is a member of its own campaign by a different route and no
    campaign lists it. So a sub-issue whose `## Lands in` names the base -- which
    every sub-issue landing in `spec/`, `scripts/` or `AGENTS.md` writes, and
    which the template invites -- is naming the base, not widening the scope,
    and the scope check below must not see it. #187 read only the literal
    `none` and so refused every claim in every campaign whose sub-issues land on
    the base; the model already said otherwise (`claimWithinScope` and
    `R14d_ScopeAdmitsTheBaseWhateverTheListHolds` in
    spec/campaign/orchestration/scenarios.als)."""
    r = run("gh", "issue", "view", str(issue), "-R", TRACKER, "--json", "body",
            "--jq", ".body")
    if r.returncode != 0:
        return None, None, (f"could not read #{issue}'s body from {TRACKER} "
                            f"({r.stderr.strip()[:120]})")
    raw, why = REPOS.lands_in(r.stdout)
    if why:
        # THE READER'S OWN WORDS, and not a second wording of them. `lands_in`
        # names what it read -- a missing heading, a malformed line, two
        # entries, an entry that is no repository -- and each of those is a
        # different repair. Restating them here would be a second reader of one
        # rule, which is the defect the section replaced.
        return None, None, (
            f"#{issue}'s body: {why}. Fill it from "
            f".claude/skills/opening-campaign/assets/sub-issue.md")
    if raw.strip(REPOS.WRAPPERS).lower() == REPOS.NONE:
        return default_repo, None, (
            f"#{issue} names no member repository, so its ref is cut on the "
            f"base ({default_repo})")
    # NORMALIZED BEFORE ANYTHING IS COMPARED, through campaign-repos.py's one
    # reader (#205). The entry is prose a person types, so the same repository
    # arrives backticked, angle-bracketed, `.git`-suffixed or in another case;
    # compared raw, every one of those came out as the SCOPE refusal, which
    # says "this campaign is not for that repository" when the truth is "that
    # line was not read as a slug". Those are different diagnoses and they now
    # print apart -- the second is `lands_in`'s refusal above.
    named = REPOS.slug(raw)
    note = (f"#{issue} says its work lands in {named}"
            + (f" (read from {raw!r})" if raw.strip() != named else ""))
    if REPOS.key(named) == REPOS.key(default_repo):
        return default_repo, None, (
            f"#{issue} says its work lands in the base ({default_repo}), which "
            f"every campaign is for")
    return named, named, note


def issue_parent(issue):
    """(parent number or None, note, was it readable) -- which campaign issue
    this sub-issue actually hangs from, read from GitHub's sub-issue link and
    not from the number the caller typed.

    THREE OUTCOMES, KEPT APART, because they license different things
    (kalaluthien/campaign-base#206):

      * a parent read, and it is a number -- compared with the campaign named;
      * a parent read, and there is none -- an issue nobody linked. It is
        ALLOWED, and loudly: #213 is unparented because #1 sits at GitHub's
        100-sub-issue cap, so refusing here would refuse the repair of exactly
        the situation the cap creates. A mistyped campaign number almost always
        lands on a PARENTED issue, which is the case this check is for;
      * could not be read -- ALLOWED with the reading named. A parent that
        could not be read is not a parent that disagrees, and this script's
        rule everywhere is that "I could not look" never becomes a verdict.

    TAKE ONLY, AND ON PURPOSE. `release` and `live` are keyed on the typed
    campaign number too, and they must stay that way: they read refs that are
    ALREADY cut under `campaign-<N>/`, so a parentage check there would refuse
    to list or release exactly the mis-cut ref this check exists to prevent.
    `take` is the one command that creates the ref, so it is the one place the
    premise can still be tested before anything durable exists."""
    r = run("gh", "issue", "view", str(issue), "-R", TRACKER, "--json", "parent",
            "--jq", ".parent.number // \"\"")
    if r.returncode != 0:
        return None, (f"could not read #{issue}'s parent from {TRACKER} "
                      f"({r.stderr.strip()[:120]})"), False
    n = r.stdout.strip()
    if not n:
        return None, f"#{issue} is a sub-issue of no campaign issue", True
    return n, f"#{issue} is a sub-issue of #{n}", True


def issue_settled(issue):
    """(settled, note) -- is this sub-issue closed? None means the reading did
    not happen.

    BOTH CLOSED READINGS COUNT. AGENTS.md: a sub-issue is settled when it is
    closed as completed with its pull request merged, or as NOT PLANNED, which
    is how a sub-issue gets dropped. `take` needs only "is it closed", because
    either way the work is over and a fresh claim on it is a claim on work
    nobody is doing."""
    r = run("gh", "issue", "view", str(issue), "-R", TRACKER,
            "--json", "state,stateReason", "--jq", '.state + " " + (.stateReason // "")')
    if r.returncode != 0:
        return None, (f"could not read #{issue}'s state from {TRACKER} "
                      f"({r.stderr.strip()[:120]})")
    words = r.stdout.split()
    if not words:
        return None, f"{TRACKER} returned no state for #{issue}"
    state = words[0].upper()
    if state == "CLOSED":
        why = words[1] if len(words) > 1 else ""
        return True, f"#{issue} is CLOSED{(' as ' + why) if why else ''}"
    return False, f"#{issue} is {state}"


# ONE SPELLING, IMPORTED. `campaign-tracker.py` reads the label to REPORT it
# and this file reads it to REFUSE a claim on it; two string literals of one
# label is the drift this campaign exists to remove.
BACKLOG_LABEL = _tracker_module().BACKLOG_LABEL


def backlog_labelled(issue):
    """(is it parked, why_unreadable) -- whether this sub-issue carries
    `backlog`. `None` for the first means the reading did not happen, which is
    a refusal: a label listing that failed is not a sub-issue nobody parked.

    THE LABEL IS THE WHOLE MECHANISM (kalaluthien/campaign-base#217). A sub-issue
    without it is worked as soon as it is filed or reopened; one with it waits
    for the owner's word, and only the owner takes the label off, because
    nothing on this machine can observe that they changed their mind. It is a
    label and not a section for the same reason `bound:` is: a label is read by
    exact name, has no history, and does not cost a body edit to set."""
    r = run("gh", "issue", "view", str(issue), "-R", TRACKER, "--json",
            "labels", "--jq", "[.labels[].name]")
    if r.returncode != 0:
        return None, (f"could not read #{issue}'s labels from {TRACKER} "
                      f"({r.stderr.strip()[:120]})")
    try:
        names = json.loads(r.stdout or "[]")
    except ValueError as e:
        return None, (f"could not parse #{issue}'s labels "
                      f"({e.__class__.__name__})")
    return BACKLOG_LABEL in names, None


def campaign_repos(campaign_issue):
    """(repos, note) -- the campaign issue's `## Repos` list. None means the
    reading did not happen, which is a refusal and never an empty list.

    THROUGH ITS ONE READER. `scripts/campaign-repos.py` owns what that list
    admits -- the missing heading, the malformed line, the surviving
    `<owner/repo>` placeholder, `- none` mixed with entries -- and AGENTS.md
    forbids a second reader of a rule a script owns, so this hands it the body
    and reads its verdict rather than parsing the section again. It takes a
    path and calls `main()` at import time, so it is run and not imported."""
    r = run("gh", "issue", "view", str(campaign_issue), "-R", TRACKER,
            "--json", "body", "--jq", ".body")
    if r.returncode != 0:
        return None, (f"could not read campaign #{campaign_issue}'s body from "
                      f"{TRACKER} ({r.stderr.strip()[:120]})")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(r.stdout)
        tmp = fh.name
    try:
        v = run(sys.executable, str(HERE / "campaign-repos.py"), tmp)
    finally:
        os.unlink(tmp)
    if v.returncode != 0:
        return None, (f"campaign #{campaign_issue}'s `## Repos` list did not "
                      f"read: {v.stderr.strip()[:160]}")
    listed = [x for x in v.stdout.split() if x]
    if not listed:
        return [], (f"campaign #{campaign_issue} lists no member repository "
                    f"(`- none`)")
    return listed, (f"campaign #{campaign_issue} lists "
                    f"{', '.join(listed)}")


def refs_for_issue(branches, campaign_issue, issue):
    """The claim branches of one sub-issue. Pure, so none, one and two each
    have a case; two is what `release` refuses on rather than picking."""
    return [b for b in branches
            if issue_of_branch(b, campaign_issue) == str(issue)]


# ------------------------------------------------------------------------ take


def scope_for(campaign_issue):
    """(campaign_dir_or_None, note) -- the directory to sweep for THIS campaign.

    `own_campaign_dir` answers "which campaign directory is this script running
    under", which is the INVOKER's and not the subject's. Scoping on that alone
    was a regression the machine-wide sweep did not have: `live 5` run from
    campaign #1's worktree swept campaign #1's clones and printed that all three
    readings were made, so a dead delegate's clone under campaign #5 went
    unread. R11 says a holder is reached through `campaignDirAt[campaignOf[i],
    host]` -- the SUB-ISSUE's campaign.

    Nothing in a directory's name says which campaign it is until #181 puts the
    number there, so this confirms by the one artifact that does: the campaign
    README was derived from the campaign issue body, and `runtime/
    campaign-issue-body-derived.md` is the copy it was derived from. First lines
    equal means this directory is that campaign's.

    UNCONFIRMED FALLS BACK TO THE WIDE SWEEP AND SAYS SO. A scope that might be
    the wrong campaign's is worse than no scope: the wide sweep is noisy, the
    wrong scope is silently blind."""
    mine = own_campaign_dir()
    if mine is None:
        return None, ("not under a campaign directory, so every campaign "
                      "directory here was swept")
    derived = Path(mine) / "runtime" / "campaign-issue-body-derived.md"
    try:
        first = derived.read_text().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return None, (f"{mine.name} carries no readable "
                      f"campaign-issue-body-derived.md, so which campaign it "
                      f"is could not be confirmed and every campaign directory "
                      f"here was swept")
    r = run("gh", "issue", "view", str(campaign_issue), "-R", TRACKER,
            "--json", "body", "--jq", ".body")
    if r.returncode != 0:
        return None, (f"could not read campaign #{campaign_issue}'s body, so "
                      f"{mine.name} could not be confirmed as its directory; "
                      f"every campaign directory here was swept")
    body = r.stdout.strip().splitlines()
    if body and body[0].strip() == first:
        return mine, f"scoped to {mine.name}, this campaign's directory"
    return None, (f"{mine.name} is not campaign #{campaign_issue}'s directory, "
                  f"so every campaign directory here was swept")


def repo_named(args):
    """Did the caller pass `--repo` at all? The flag defaults to None so an
    explicit value equal to the base is still an assertion, not a silence."""
    return getattr(args, "repo", None) is not None


def partition_refs(repo, branches):
    """(held, residue, unread) -- which of these refs are live claims.

    A ref whose pull request merged is residue of settled work, not a claim
    (#187 question 3, `settledLeavesNoClaim`). ONE FUNCTION BECAUSE THERE ARE
    TWO READERS: the survey before the create and the re-check after it. The
    first shape of this filtered only the survey, so a `take` on a REOPENED
    sub-issue walked past its own residue, cut the ref, then counted that same
    residue as a rival in the re-check and deleted what it had just cut --
    reporting a race against a branch that merged weeks ago. Reopen-then-take
    is the only path by which a settled sub-issue is ever re-worked, so that
    left question 3 delivering nothing."""
    held, residue, unread = [], [], []
    for b in branches:
        pr = merged_pr_of(repo, b)
        if pr == "?":
            unread.append(b)
        elif pr:
            residue.append(f"{b} (merged as #{pr})")
        else:
            held.append(b)
    return held, residue, unread


def cmd_take(args):
    branch = branch_name(args.campaign_issue, args.issue, args.topic)
    # The binding, read before a ref is cut: a claim is one of the writes only
    # the bound machine makes. Read from the one reader, never re-derived.
    refusal = binding_refusal(args.campaign_issue)
    if refusal:
        print(f"refusing: {refusal}", file=sys.stderr)
        return 1
    print("bound here, so the claim may be cut")

    # WHOSE SUB-ISSUE, read from GitHub and not from the number typed (#206).
    # Before this, a mistyped campaign number cut a real ref under a campaign
    # the sub-issue does not belong to, and nobody could see it: `live` and
    # `release` list refs by the `campaign-<N>/` prefix, so the claim was
    # invisible to the campaign that owns the work and unreachable from the one
    # that does not. The model already says the right thing --
    # `claimWithinScope` reads `campaignOf[Now.issue]`, the sub-issue's actual
    # parent -- so this is the code moving up to the model.
    parent, parent_note, readable = issue_parent(args.issue)
    if readable and parent is not None and parent != str(args.campaign_issue):
        print(f"refusing: {parent_note}, not #{args.campaign_issue}.\n"
              f"  A ref cut under campaign-{args.campaign_issue}/ would be "
              f"invisible to the campaign that owns #{args.issue}\n  and "
              f"unreachable from the one named. Take it under #{parent}, or "
              f"fix the sub-issue's parent.", file=sys.stderr)
        return 1
    print(parent_note + (
        f", the campaign named" if parent == str(args.campaign_issue) else
        (", so nothing disagrees with the campaign named; a claim on an "
         "unparented issue is admitted" if readable else
         ", so the parentage could not be checked -- a parent that could not "
         "be read is not a parent that disagrees")))

    # WHERE, read from the sub-issue and not from the caller. Before #187 this
    # was `repo`, so two takers naming different repositories both cut a
    # ref and both held #N. `--repo` survives only as a confirmation, and a
    # disagreement is refused rather than resolved: whichever way it were
    # resolved silently, one of the two readers would be wrong for good.
    repo, named, note = issue_repo(args.issue, DEFAULT_REPO)
    if repo is None:
        print(f"refusing: {note}\n  Where a claim is cut is a fact about the "
              f"sub-issue, so a body this could not read is not a\n  "
              f"sub-issue whose ref may be cut anywhere.", file=sys.stderr)
        return 1
    print(note)
    if repo_named(args) and args.repo != repo:
        print(f"refusing: --repo says {args.repo}, #{args.issue} says {repo}.\n"
              f"  The sub-issue decides. Fix its `## Lands in` section, or drop "
              f"--repo.", file=sys.stderr)
        return 1

    # ...AND IT MUST BE A REPOSITORY THE CAMPAIGN IS FOR. `## Lands in` is
    # one sub-issue's; `## Repos` is the campaign's scope and the thing a
    # person signed up for. A sub-issue naming a repository outside it is a
    # scope change filed as a typo, and cutting the ref would make the campaign
    # silently wider than its charter. Only a MEMBER repository is checked, and
    # `issue_repo` is the one reader of which those are: both spellings of the
    # base -- `none`, and the base's own slug -- come back with `named` None,
    # because the base is never in the list and a campaign that changes it is
    # not thereby out of its own scope. The model is `claimWithinScope`, whose
    # `Base` disjunct R14d pins. That the base is never in the list HAS a
    # reader since kalaluthien/campaign-base#205: `campaign-repos.py` refuses
    # the entry, and `WellFormed` in spec/campaign/github/system.als forbids
    # the trace, pinned by `S20_TheBaseIsNeverListed`. Nothing here rests on it
    # either way -- a campaign that listed the base still reaches this block
    # with `named` None, so the list is not consulted and the claim is admitted
    # regardless; what #205 closed is the second clone the entry would produce
    # at acquire time.
    if named is not None:
        listed, repos_note = campaign_repos(args.campaign_issue)
        if listed is None:
            print(f"refusing: {repos_note}\n  #{args.issue} names {named}, and "
                  f"whether this campaign is for it could not be read.\n  "
                  f"A scope that could not be read is not a scope that admits "
                  f"it.", file=sys.stderr)
            return 1
        # COMPARED THROUGH THE ONE KEY (#205), not as raw strings. `issue_repo`
        # has already de-wrapped the `## Lands in` entry; the list entries come
        # from `campaign-repos.py`, which admits `owner/repo` and nothing else,
        # so the only difference left between two spellings of one repository
        # is case -- and GitHub does not tell `Web` from `web`.
        if REPOS.key(named) not in {REPOS.key(x) for x in listed}:
            print(f"refusing: #{args.issue} says its work lands in {named}, but "
                  f"{repos_note}.\n  Adding a repository is a scope change and "
                  f"belongs in the campaign issue's `## Repos`,\n  not in one "
                  f"sub-issue's body.", file=sys.stderr)
            return 1
        print(f"{repos_note}, which includes {named}")

    # ...AND THE BRIEF MUST BE A BRIEF. A claim is the moment a sub-issue
    # becomes somebody's work, so it is the one moment at which its shape is
    # worth refusing over -- title, ceiling, the sections its kind requires,
    # `## Plan` among them, because the plan is written by whoever will prompt
    # the work and not by the worker in a pane
    # (kalaluthien/campaign-base#217). Through `campaign-tracker check`, which
    # owns that reading; run as a subprocess and its refusal read back, for the
    # same reason `campaign_repos` above is.
    v = run(sys.executable, str(HERE / "campaign-tracker.py"), "check",
            str(args.issue), TRACKER, "--plan")
    for line in v.stdout.splitlines():
        print(f"  {line}")
    if v.returncode != 0:
        print(f"refusing: #{args.issue}'s shape does not admit a claim.\n"
              f"{v.stderr.rstrip()}\n"
              f"  The escape: a PLANNER edits the body -- a worker's `gh issue "
              f"edit {args.issue}` is narrowed to a claim on\n  #{args.issue}, "
              f"which is the claim just refused. Ask one, or take the planner "
              f"role yourself.", file=sys.stderr)
        return 1
    backlog, why_backlog = backlog_labelled(args.issue)
    if backlog is None:
        print(f"refusing: {why_backlog}\n  A label listing that did not happen "
              f"is not a sub-issue nobody parked.", file=sys.stderr)
        return 1
    if backlog:
        print(f"refusing: #{args.issue} carries `{BACKLOG_LABEL}`, so it is not "
              f"worked until the owner says so.\n  The owner removes the label; "
              f"nothing here does, because its premise -- that the owner has "
              f"changed\n  their mind -- is not observable from this machine.",
              file=sys.stderr)
        return 1
    print(f"#{args.issue} does not carry `{BACKLOG_LABEL}`, so it is worked as "
          f"filed")

    # THE SUB-ISSUE IS WHAT IS CLAIMED, AND THE REF NAME CARRIES THE TOPIC TOO,
    # so create-ref alone serialises topics rather than sub-issues: `7-parser`
    # and `7-parse-fix` are two names and the server refuses neither. The record
    # this replaced was keyed on the sub-issue and gave that for free; this
    # sweep is what gives it back. It is a survey before a create and therefore
    # NOT atomic -- two takers between the read and the create both pass -- and
    # that is the honest ceiling, not a bug hidden here: the binding already
    # limits a campaign to one machine, and this window is narrower than the
    # one `O_EXCL` on a record closed only for this machine anyway.
    existing, why = matching_refs(repo, args.campaign_issue)
    if why:
        print(f"refusing: {why}\n  A ref listing that did not happen is not "
              f"proof the sub-issue is free.", file=sys.stderr)
        return 1
    siblings = refs_for_issue(existing, args.campaign_issue, args.issue)
    if siblings:
        # A SETTLED SUB-ISSUE'S REF IS RESIDUE, NOT A CLAIM (#187 question 3,
        # spec/campaign/orchestration/scenarios.als `settledLeavesNoClaim`).
        # `delete_branch_on_merge` is off on this tracker, so a merged branch's
        # ref stands until somebody deletes it by hand -- and this sweep read it
        # as a live claim, so a sub-issue that had ever been settled could never
        # be re-worked. Probed 2026-09-04: `take 1 154 <topic>` exited 3
        # `already claimed` though #154 closed as completed via #162.
        #
        # The test is the ref's own pull request, which is the same reading
        # `release` makes on its merged path: a branch whose pull request merged
        # is finished work. Stated in `settledLeavesNoClaim` once so the two
        # cannot drift about when a ref stops meaning "somebody holds this".
        held, residue, unread = partition_refs(repo, siblings)
        if unread:
            print(f"refusing: could not ask {repo} whether "
                  f"{', '.join(unread)} was ever merged, so whether it is a "
                  f"live claim or\n  residue of a settled sub-issue is "
                  f"unknown.", file=sys.stderr)
            return 1
        if held:
            print(f"already claimed: sub-issue #{args.issue} is held by "
                  f"{', '.join(held)} on {repo}.")
            print("  A sub-issue has one claim whatever the topic, so a second "
                  "topic is not a second claim.")
            print("  Read who is standing in it before doing anything else:")
            print(f"    {sys.argv[0]} live {args.campaign_issue}")
            return 3
        print(f"{', '.join(residue)} is residue of settled work, not a claim")

    # ...AND A SETTLED SUB-ISSUE IS NOT RE-CLAIMED WHILE IT IS STILL CLOSED.
    # The model admits `claim[i]` only for `i in Open`, so re-working one means
    # reopening it first -- which is a person's decision and a GitHub fact, not
    # something a claim should make silently on their behalf.
    settled, state_note = issue_settled(args.issue)
    if settled is None:
        print(f"refusing: {state_note}\n  A sub-issue whose state could not be "
              f"read is not a sub-issue known to be open.", file=sys.stderr)
        return 1
    if settled:
        print(f"refusing: {state_note}, so it is settled and its work is over.\n"
              f"  Re-working it means reopening it first, which is a person's "
              f"call:\n    gh issue reopen {args.issue} -R {TRACKER}\n"
              f"  Or file a new sub-issue for what is left.", file=sys.stderr)
        return 1
    print(state_note)

    # Resolved and checked before the create, never written inline: a read that
    # fails and still prints goes up as the sha and comes back as the 422 that
    # means "already claimed", so the sub-issue reads as taken and is abandoned.
    r = run("gh", "api", f"repos/{repo}/commits/main", "--jq", ".sha")
    sha = r.stdout.strip()
    if r.returncode != 0 or not SHA.match(sha):
        print(f"refusing: could not resolve {repo}'s main sha.\n"
              f"  got {sha!r}; {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"cut from {repo}@main {sha}")

    r = run("gh", "api", f"repos/{repo}/git/refs",
            "-f", f"ref=refs/heads/{branch}", "-f", f"sha={sha}")
    if r.returncode != 0:
        if "already exists" in r.stderr.lower():
            print(f"already claimed: {branch} exists on {repo}.")
            print("  create-ref refuses an existing ref server-side, so this "
                  "is the claim working.")
            print("  Read who is standing in it before doing anything else:")
            print(f"    {sys.argv[0]} live {args.campaign_issue}")
            return 3
        print(f"refusing: create-ref failed.\n  {r.stderr.strip()}",
              file=sys.stderr)
        return 1
    # THE RE-CHECK, and it is what makes the sub-issue claim atomic rather than
    # merely narrowed. The survey above is a read before a write: two takers on
    # `7-parser` and `7-parse-fix` both see no sibling and both create, and
    # create-ref refuses neither because the names differ. Reading AGAIN after
    # the create closes it, because by then both refs exist and both takers see
    # the same set -- so a rule they can both apply without talking settles it.
    # The rule is that EVERYONE WHO SEES A RIVAL YIELDS, spelled out at the
    # block below; a smallest-name tiebreak is what this replaced and must not
    # come back. Do not replace this with a longer survey before the create: no
    # amount of looking first makes a read-then-write atomic.
    after, why = matching_refs(repo, args.campaign_issue)
    if why:
        print(f"refusing: {branch} WAS cut, but the re-check that makes the "
              f"claim atomic did not\n  happen ({why}). Read "
              f"`{sys.argv[0]} live {args.campaign_issue}` before working it: "
              f"a second\n  topic on this sub-issue would be invisible.",
              file=sys.stderr)
        return 1
    # THE SAME PARTITION AS THE SURVEY, and this is the whole of finding 1.
    # Counting residue here made a reopened sub-issue's `take` delete the ref it
    # had just cut and report a race against a branch merged weeks ago.
    all_after = refs_for_issue(after, args.campaign_issue, args.issue)
    rivals, after_residue, after_unread = partition_refs(repo, all_after)
    if after_unread:
        print(f"refusing: {branch} WAS cut, but whether "
              f"{', '.join(after_unread)} is a live claim or residue of "
              f"settled work\n  could not be read, so this claim cannot be "
              f"confirmed sole. Read `{sys.argv[0]} live "
              f"{args.campaign_issue}` before working it.", file=sys.stderr)
        return 1
    if after_residue:
        print(f"{', '.join(after_residue)} is residue of settled work, not a "
              f"rival")
    if len(rivals) > 1:
        # EVERYONE WHO SEES A RIVAL YIELDS. The smallest-name rule looked like a
        # tiebreak both racers could apply, and it is not: they do not read the
        # same set. Enumerating the interleavings of survey/create/list for two
        # takers, `min` leaves BOTH holding in two of them -- the one that
        # created first lists before the other creates, sees only itself, and
        # keeps its ref while the later one also finds itself smallest.
        #
        # Yielding has no such state. Its worst case is that both delete and the
        # sub-issue is left unclaimed, which the next `take` fixes; two
        # workers on one sub-issue is the thing that cannot be fixed after the
        # fact. Do not "improve" this back into a tiebreak: the property is
        # never two holders, not always one.
        others = ", ".join(r for r in rivals if r != branch)
        d = run("gh", "api", "-X", "DELETE", delete_path(repo, branch))
        print(f"already claimed: sub-issue #{args.issue} was taken in the same "
              f"moment by {others}.")
        if d.returncode == 0:
            print(f"  {branch} held nothing -- it was cut from main seconds "
                  f"ago -- and has been deleted again.")
        else:
            print(f"  !! {branch} was NOT deleted "
                  f"({' '.join(d.stderr.split())[:120]}), so it is a ref "
                  f"holding no work that\n     will refuse the next `take` on "
                  f"this sub-issue. Delete it by hand:")
            print(f"       gh api -X DELETE {delete_path(repo, branch)}")
        print(f"  Re-read `{sys.argv[0]} live {args.campaign_issue}`: whoever "
              f"else saw this race yielded too,\n  so the sub-issue may now be "
              f"free.")
        return 3

    print(f"claimed {branch}")
    print(f"  The ref IS the claim: nothing else was written, and "
          f"`{sys.argv[0]} live {args.campaign_issue}` reads it back.")
    return 0


# --------------------------------------------- the herdr half of the reading


def parse_agents(text):
    """The herdr reading, with no process in it, so it can be tested against a
    recorded listing instead of against whatever happens to be running."""
    try:
        agents = json.loads(text)["result"]["agents"]
    except (ValueError, KeyError, TypeError) as e:
        return None, f"could not parse herdr's output ({e.__class__.__name__})"
    # `agents: null` and a row that is not an object both used to raise here
    # instead of returning the `why` this promises, which turned "I could not
    # read it" into a traceback -- the one shape a caller cannot act on.
    if not isinstance(agents, list):
        return None, "herdr's `agents` was not a list"
    out = {}
    for a in agents:
        if not isinstance(a, dict):
            return None, f"a herdr row was {type(a).__name__}, not an object"
        sid = (a.get("agent_session") or {}).get("value")
        if sid is None:
            # A row herdr lists but cannot identify. Counted, never dropped:
            # silently skipping it would shrink "sessions on this machine",
            # which is the number a close gate reads.
            sid = f"<unidentified:{a.get('pane_id', '?')}>"
        out[sid] = {
            "name": a.get("name") or "<unnamed>",
            "status": a.get("agent_status", "?"),
            "cwd": a.get("cwd", "?"),
            "pane": a.get("pane_id", "?"),
        }
    return out, None


def herdr_sessions():
    """Every session on this machine. Listing needs no HERDR_ENV guard: that
    guard is against acting on somebody else's session, never against reading,
    and `agent list` answers the same from outside a pane as from inside."""
    r = run("herdr", "agent", "list")
    if r.returncode != 0:
        return None, (f"herdr agent list exited {r.returncode}: "
                      f"{r.stderr.strip()[:120]}")
    return parse_agents(r.stdout)


COMPACT = "/compact"
SESSION_ID_VAR = "CLAUDE_CODE_SESSION_ID"

# THE ONE LINE A LATER READER ANCHORS ON. Printed at both of `release`'s
# success exits and nowhere else, and printed whether or not the compaction
# succeeded. The compaction is SENT FIRST -- `release_line` takes the pane that
# `compact_own_pane` returns, so Python evaluates the inner call first -- and
# the anchor still precedes the marker in the pane, because the marker is only
# written at the end of the turn.
#
# IT NAMES THE PANE, and that is not decoration. A pane's text holds whatever
# it has DISPLAYED as well as whatever it printed -- `herdr agent read` puts
# another session's output into the reader's own scrollback, which AGENTS.md
# makes the ordinary planner move. Without the pane, a planner that released
# and then read a delegate's pane found its own anchor and the delegate's
# compaction marker, in order, and read itself as compacted. With it, an anchor
# copied from elsewhere names the pane it came from and is not this one's.
# Found by review at e680ef8. The marker cannot be qualified this way, so the
# residue is kalaluthien/campaign-base#220.
#
# `campaign-assign.py` reads it to answer "has this pane compacted since its
# last release". Keyed on the compaction's own success line instead -- which is
# how this shipped at 114e71a -- the one case the assignment guard exists for,
# a release that could NOT compact, left no release line at all and read as a
# pane that never released, which allows. Found by review and reproduced end to
# end before this was written.
RELEASED = "campaign-claim: released"


def own_pane(sessions, session_id):
    """(pane, what_was_read) -- which pane THIS process's session sits in, by
    joining `CLAUDE_CODE_SESSION_ID` to `herdr agent list`'s `agent_session
    .value`. Pure, so the join is testable against a recorded listing.

    A pane of None is always accompanied by a note saying which of the two
    absences it is -- no session id in the environment, or an id no row names.
    Neither is a failure to release: see `compact_own_pane`.

    NOT `HERDR_PANE_ID`, which is also in the environment and which measured
    equal to this on 2026-09-05. It is inherited shell state with no liveness
    behind it, where this join is a live reading; and a listing that does not
    name this session is exactly the state the caller has to say out loud."""
    if not session_id:
        return None, (f"no {SESSION_ID_VAR} in the environment, so this "
                      f"process cannot name its own session")
    if session_id not in sessions:
        return None, (f"{SESSION_ID_VAR}={session_id}, and no herdr row names "
                      f"it ({len(sessions)} row(s) listed)")
    row = sessions[session_id]
    return row["pane"], (f"{SESSION_ID_VAR}={session_id} -> pane {row['pane']} "
                         f"({row['name']})")


def compact_own_pane(sessions, session_id):
    """Enqueue `/compact` into the releasing session's own pane, and print what
    was read either way. Returns the pane it prompted, or None.

    WHY HERE. A worker's release is the last thing it does on a sub-issue,
    and the context it is holding at that instant is the finished sub-issue's
    whole transcript, carried into the next one turn after turn. herdr queues a
    prompt against a working pane, so a prompt sent from inside the release
    turn fires the moment that turn ends -- while the context is still in the
    prompt cache. Probed 2026-09-05: `herdr agent prompt <own pane> "/compact"`
    sent as a turn's last call runs as the command, not as text
    (`Compacting conversation... (41s)`), and the session comes back idle
    holding no plan it had named, which is why the next sub-issue arrives as a
    fresh prompt (`scripts/campaign-assign.py`).

    NOT A GATE, and this is the whole reason it lives after the delete rather
    than before it. Compaction is a cost rule: a release that could not find
    its own pane has still released. So every branch here prints and none
    returns a refusal -- but a missing row is SAID, because the failure mode a
    silent skip creates is a rule everyone believes is held while nothing
    sends anything.

    It never prompts a pane that is not its own: the only pane it can name is
    the one the join returned.

    NO `sessions is None` BRANCH, because `cmd_release` refuses on an unread
    listing long before either call site -- an occupant it could not read is
    not an absent one, and the suite asserts that ordering. A branch for it
    here would read as a live could-not-look while nothing could reach it,
    which is the shape that gets trusted for months while handling nothing."""
    pane, note = own_pane(sessions, session_id)
    if pane is None:
        print(f"not compacting: {note}. The claim is released; only the "
              f"compaction did not happen.")
        return None
    print(f"compacting: {note}")
    # The one herdr call here that DRIVES a pane rather than reading one, so it
    # carries the HERDR_ENV guard and names its target explicitly -- and the
    # target is this session's own pane, which is the guard's whole subject.
    r = run("herdr", "agent", "prompt", pane, COMPACT,
            env=dict(os.environ, HERDR_ENV="1"))
    if r.returncode != 0:
        print(f"not compacting: `herdr agent prompt {pane} {COMPACT}` exited "
              f"{r.returncode}: {r.stderr.strip()[:160]}. The claim is "
              f"released; only the compaction did not happen.")
        return None
    print(f"sent {COMPACT} to {pane}; it runs when this turn ends")
    return pane


def release_line(pane, branch):
    """The anchor, naming the pane it was printed in.

    A pane this could not name is said so, and reads as no anchor at all to
    `campaign-assign.py` -- which refuses. That is the right direction: a
    release whose pane is unknown is one whose compaction was not sent
    either, since both come from the same join."""
    where = pane or "<pane unknown>"
    print(f"{RELEASED} {branch} in {where}")


def parse_worktrees(text):
    """{branch: [path, ...]} from `git worktree list --porcelain`. Pure.

    The porcelain form is paragraphs of `key value` lines: `worktree <path>`
    opens one, `branch refs/heads/<name>` names its branch, and a detached
    worktree simply has no `branch` line -- a real answer, not a failure, so it
    is dropped rather than counted as unreadable."""
    out, path = {}, None
    for line in (text or "").splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
        elif line.startswith("branch refs/heads/") and path:
            out.setdefault(line[len("branch refs/heads/"):].strip(),
                           []).append(path)
        elif not line.strip():
            path = None
    return out


def base_root():
    """(path, why_unreadable) -- the base checkout whose campaign directories
    this sweeps.

    TWO RULES, and the first exists because the base is a member of its own
    campaigns. `<campaign>/repos/campaign-base/` is a second checkout of this
    very repository, script and all, so `git rev-parse --git-common-dir` run
    from THAT copy answers with the clone -- a base root holding no campaign
    directory at all, which comes back as a clean sweep of nothing and lets
    `release` delete a ref somebody is standing in.

    So: if any ancestor of this file is a `<slug>-<YYMMDD>` campaign directory,
    the base root is that directory's parent, whichever checkout is running.
    Only when none is -- the ordinary case, the base's own `scripts/` -- does
    the git rule apply, and there it is AGENTS.md's one form, which returns the
    main checkout even from a linked worktree."""
    for parent in HERE.parents:
        if CAMPAIGN_DIR.search(parent.name):
            return str(parent.parent), None
    r = run("git", "-C", str(HERE), "rev-parse", "--path-format=absolute",
            "--git-common-dir")
    if r.returncode != 0:
        return None, (f"could not resolve the base root from {HERE}: "
                      f"{' '.join(r.stderr.split())[:120]}")
    return str(Path(r.stdout.strip()).parent), None


def repo_root(cwd):
    """The repository root of one session's directory, or why not. A `cwd` that
    is not in a repository is not a failure -- a session may sit anywhere -- so
    it comes back as (None, None)."""
    if not cwd or cwd == "?":
        return None, None
    r = run("git", "-C", cwd, "rev-parse", "--path-format=absolute",
            "--git-common-dir")
    if r.returncode != 0:
        return None, None
    return str(Path(r.stdout.strip()).parent), None


def own_campaign_dir(start=None):
    """This session's own campaign directory, or None when it is not under one.

    THE SAME WALK `base_root` MAKES, kept rather than thrown away. `base_root`
    already looks for a `<slug>-<YYMMDD>` ancestor of this file and returns its
    PARENT; the directory it walked past is the one campaign this invocation is
    actually about, and #187 question 4 is what it cost to discard it.

    None is a real answer, not a failure: run from the base's own `scripts/`
    there is no campaign ancestor, and nothing on disk says which campaign a
    directory belongs to until #181 puts the number in the name.

    `start` is a parameter so the walk is a calculation a case can drive. Read
    from `HERE` alone it could only be tested by where this file happens to
    sit, which is a different answer in a worktree, in a clone, and on CI."""
    for parent in (start or HERE).parents:
        if CAMPAIGN_DIR.search(parent.name):
            return parent
    return None


def campaign_clones(root, only=None):
    """(paths, unread) -- the member checkouts under campaign directories at the
    base root; under `only` alone when a campaign directory is given.

    ONE CAMPAIGN'S READING DOES NOT DEPEND ON ANOTHER'S DIRECTORY (#187
    question 4). This walked EVERY campaign directory, so one with an
    unreadable `repos/` denied `live` and `release` for every other campaign on
    the machine, and a neighbour's clone counted toward this campaign's sweep.
    directory/system.als has said all along that `campaignDirAt` is the one way
    to reach a campaign's directory and that every reading about a campaign
    goes through it; this is the reader catching up, as in question 1.

    The residual, named because it does not go away here: run from the base's
    own `scripts/` there is no campaign ancestor, `only` is None, and the sweep
    is machine-wide again. Nothing on disk attributes a directory to a campaign
    until #181 puts the number in the name, so the wide sweep says so rather
    than pretending to be scoped.

    UNCONDITIONAL WITHIN WHAT IT SWEEPS, and that is the older fix: deriving
    the roots from live herdr rows
    made the sweep go blind exactly when a session died, which is the case it
    exists for. A delegate that exits leaves its clone on disk holding the
    branch, and a sweep that only followed living sessions reported that branch
    as standing in no workspace -- one step before deleting its ref.

    A campaign directory that will not enumerate is named, never skipped."""
    out, unread = [], []
    if only is not None:
        dirs = [Path(only)]
    else:
        try:
            dirs = [d for d in sorted(Path(root).iterdir())
                    if d.is_dir() and CAMPAIGN_DIR.search(d.name)]
        except OSError as e:
            return [], [f"{root}: could not list campaign directories "
                        f"({e.__class__.__name__})"]
    for d in dirs:
        repos = d / "repos"
        if not repos.is_dir():
            continue                      # a repo-less campaign, not a failure
        try:
            out.extend(str(c) for c in sorted(repos.iterdir()) if c.is_dir())
        except OSError as e:
            unread.append(f"{repos}: would not enumerate "
                          f"({e.__class__.__name__})")
    return out, unread


REMOTE = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$")


def remote_of(clone):
    """`owner/repo` for a clone's `origin`, or None. Pure enough to test: the
    two URL shapes git hands back, ssh and https, differ only in the separator
    before the owner."""
    r = run("git", "-C", clone, "remote", "get-url", "origin")
    if r.returncode != 0:
        return None
    m = REMOTE.search(r.stdout.strip())
    return m.group(1) if m else None


def claim_repos(default_repo, root, only=None, campaign_issue=None):
    """Every repository this campaign's claims can be on. Returns (repos, note).

    A CLAIM IS CUT ON THE REPOSITORY THE WORK LANDS IN, so `--repo` alone
    answers for the base and for nothing else: a member-repo sub-issue's branch
    is on that member's remote, and reading only the base returned `0 occupied,
    0 vacant` over a delegate standing in one -- a close passing over a held
    claim.

    TWO SOURCES, AND THE CLONES ALONE ARE NOT ENOUGH. A clone is what a branch
    can be checked out in, so it answers "where might somebody be standing";
    `## Repos` is what the campaign is FOR, so it answers "where might a claim
    be". They differ exactly when a member repository was never cloned here or
    its clone was removed -- and then the claim on it is real, on the remote,
    and invisible: `live` printed "all three readings were made, 0 occupied, 0
    vacant" and a close passed over a held claim. That is the false-clean this
    reading exists to prevent, so `## Repos` is read too, through
    `campaign-repos.py`, which owns what that list admits.

    A `## Repos` that will not read is NAMED in the note and does not silently
    narrow the sweep: the caller prints the note beside its counts."""
    repos, seen = [default_repo], {default_repo}
    if not root:
        return repos, "no base root, so only the named repository was read"
    clones, _ = campaign_clones(root, only)
    for c in clones:
        name = remote_of(c)
        if name and name not in seen:
            seen.add(name)
            repos.append(name)
    listed_note = ""
    if campaign_issue is not None:
        listed, why = campaign_repos(campaign_issue)
        if listed is None:
            listed_note = f"; {why}, so a repository it names may be unread"
        else:
            extra = [r for r in listed if r not in seen]
            for r in extra:
                seen.add(r)
                repos.append(r)
            if extra:
                listed_note = (f"; {', '.join(extra)} from `## Repos` with no "
                               f"clone here")
    return repos, (f"{len(repos)} repositor(y/ies) hold this campaign's claims"
                   f"{listed_note}")


def all_refs(repos, campaign_issue):
    """({branch: repo}, unread) across every repository.

    THE REPOSITORY TRAVELS WITH THE REF, because `release` deletes by name and a
    claim branch has the same name in every member repository -- so a delete
    aimed at the wrong one takes a different repository's ref holding somebody
    else's commits. A repository whose listing fails is NAMED: a claim that
    could not be read is not an absent one."""
    out, unread = {}, []
    for repo in repos:
        branches, why = matching_refs(repo, campaign_issue)
        if why:
            unread.append(why)
            continue
        for b in branches:
            out.setdefault(b, repo)
    return out, unread


def sweep_roots(sessions, only=None):
    """(roots, unread, why_unreadable) -- every repository to enumerate
    worktrees in.

    Three sources, and only the third depends on anything running: the base
    root, because a campaign's worktrees hang off it; every member clone under
    THIS campaign's directory (#187 question 4 -- it used to be every campaign
    directory here, so a neighbour's unreadable `repos/` denied this campaign's
    reading), because a dead delegate's clone still holds its branch; and each live session's own repository, which catches a session
    working somewhere none of the above covers. Failing to resolve the base root
    is a refusal -- not knowing where to look is not the same as looking and
    finding nothing."""
    root, why = base_root()
    if why:
        return None, [], why
    roots = {root}
    clones, unread = campaign_clones(root, only)
    roots.update(clones)
    for row in sessions.values():
        r, _ = repo_root(row.get("cwd", ""))
        if r:
            roots.add(r)
    return sorted(roots), unread, None


def checkouts(roots):
    """({branch: [path, ...]}, unread) across every root. A root git will not
    answer for is named, never skipped, because a repository that could not be
    swept is not an empty one."""
    out, unread = {}, []
    for root in roots:
        r = run("git", "-C", root, "worktree", "list", "--porcelain")
        if r.returncode != 0:
            unread.append(f"{root}: git worktree list exited {r.returncode}: "
                          f"{' '.join(r.stderr.split())[:120]}")
            continue
        for branch, paths in parse_worktrees(r.stdout).items():
            out.setdefault(branch, []).extend(paths)
    return {b: sorted(set(p)) for b, p in out.items()}, unread


def classify(branches, where, sessions, campaign_issue, root=None, caller=None):
    """(occupied, vacant, ours) -- the join, on the branch name and on nothing
    else.

    Pure, so it can be tested against recorded inputs.

    `ours` is the set a close sweeps, and it is NOT just "sessions named for
    this campaign". Nothing enforces that name any more -- the record whose
    `name` field `take` used to check is gone -- so a peer that never named
    itself, or renamed away, would be invisible to a gate keyed on the prefix
    alone. Three cases, and the middle one is the whole point:

      named for THIS campaign          counted
      named for ANOTHER campaign       NOT counted, wherever it sits
      named for no campaign at all     counted when it sits under the base root

    The second line is what a first cut of this got wrong by counting every
    session under the base root: `ours` then returned an identical set for
    campaigns 1, 116 and 999, so closing one campaign asked another's planner to
    stand down. A name that clearly says "some other campaign" is evidence and
    is believed; a name that says nothing is not, and the cwd decides instead.

    THE CALLER IS EXCLUDED, by session id. A close runs *from* a session of the
    campaign it is closing, so a gate that refuses on any live session of the
    campaign refuses on the closer itself and can never pass. The caller is the
    one session whose intent is known."""
    mine = f"campaign-{campaign_issue}-"
    occupied, vacant = [], []
    for b in branches:
        paths = where.get(b, [])
        (occupied if paths else vacant).append((b, paths))
    ours = []
    for sid, row in sorted(sessions.items()):
        if sid == caller:
            continue
        name = row.get("name", "") or ""
        if name.startswith(mine):
            ours.append((sid, row))
        elif OTHER_CAMPAIGN.match(name):
            continue                      # it says whose it is, and it is not ours
        elif root and under(row.get("cwd", ""), root):
            ours.append((sid, row))
    return occupied, vacant, ours


def under(path, root):
    """Is `path` inside `root`? Whole path segments, so `demo-1` is not under
    `demo`; both resolved, because herdr reports the path a shell was opened at
    and these comparisons run against `pwd -P`, which differ under /var on
    macOS.

    ONLY AN ABSOLUTE PATH IS ANSWERED. `Path.resolve()` resolves a relative one
    against the PROCESS's cwd, so `under("", root)`, `under("relative", root)`
    and herdr's own `"?"` placeholder all came back True whenever this ran from
    inside the base -- which is where it always runs. Three unrelated sessions
    counted as this campaign's for no better reason than the shell they were
    read from."""
    if not path or not str(path).startswith("/"):
        return False
    try:
        c, t = Path(path).resolve().parts, Path(root).resolve().parts
    except (TypeError, OSError, ValueError):
        return False
    return c[:len(t)] == t


def merged_pr_of(repo, branch):
    """The merged pull request number whose head was this branch, or None, or
    `?` when the question was not answered. Three outcomes and not two: a
    listing that failed is not an absence of a merge."""
    r = run("gh", "pr", "list", "-R", repo, "--head", branch, "--state",
            "merged", "--json", "number")
    if r.returncode != 0:
        return "?"
    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return "?"
    return prs[0].get("number") if prs else None


def cmd_live(args):
    root, _ = base_root()
    mine, scope_note = scope_for(args.campaign_issue)
    print(scope_note)
    # `live` reads a whole campaign rather than one sub-issue, so it has no
    # `## Lands in` section to consult; the base is where it starts and the clones
    # on disk widen it. `--repo` here is a starting point, not an assertion
    # about one sub-issue's home.
    repos, repo_note = claim_repos(args.repo or DEFAULT_REPO, root, mine,
                                   args.campaign_issue)
    found, unread1 = all_refs(repos, args.campaign_issue)
    branches = sorted(found)
    why1 = "; ".join(unread1) if unread1 else None
    print(f"reading 1  refs under campaign-{args.campaign_issue}/ in "
          f"{', '.join(repos)} -- "
          f"{'FAILED: ' + why1 if why1 else str(len(branches)) + ' claim(s)'}")
    print(f"           {repo_note}")
    sessions, why2 = herdr_sessions()
    print(f"reading 2  herdr agent list -- "
          f"{'FAILED: ' + why2 if why2 else str(len(sessions)) + ' session(s) on this machine'}")
    roots, unread, why3 = sweep_roots(sessions or {}, mine)
    if why3:
        where = {}
    else:
        where, more = checkouts(roots)
        unread = unread + more
    print(f"reading 3  git worktree list -- "
          f"{'FAILED: ' + why3 if why3 else f'{len(roots)} repo(s) swept, {len(unread)} unread'}")
    # NOT `root`: this loop used to rebind the base root that `classify` is
    # given below, so the cwd rule the peer set turns on was compared against
    # the last repository swept. The unit case passed throughout, because it
    # calls `classify` with the right root directly -- a fixture standing in for
    # the deployed path.
    for swept in (roots or []):
        print(f"           {swept}")
    for note in unread:
        print(f"           !! {note}")
    if why1 or why2 or why3:
        print("\nOne of the three readings did not happen, so no count below "
              "is safe to act on.", file=sys.stderr)
        return 1

    # THE CALLER IS EXCLUDED, and it says so. A close runs from a session of
    # the campaign it is closing, so a gate refusing on any live session of the
    # campaign would refuse on the closer itself. Printed because a row silently
    # missing from a count is the shape nobody questions -- and because with
    # `$CLAUDE_CODE_SESSION_ID` unset there is no exclusion at all, and then the
    # closer's own row makes the close unpassable with no cause shown.
    caller = os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    print(f"           this session is "
          f"{caller or '<$CLAUDE_CODE_SESSION_ID unset: not excluded below>'}")
    occupied, vacant, ours = classify(
        branches, where, sessions, args.campaign_issue, root=root,
        caller=caller)

    print(f"\nclaims checked out on this machine ({len(occupied)}) -- joined "
          f"on the branch name, which a restart and a rename both leave alone")
    for b, paths in occupied:
        for path in paths:
            print(f"  {b:<34} {path}")

    print(f"\nclaims checked out nowhere on this machine ({len(vacant)})")
    # WITH ITS MERGED PULL REQUEST, because without that the group is
    # unactionable: a branch whose work landed months ago sits here forever --
    # `delete_branch_on_merge` is off on this tracker -- and a close gate told
    # to refuse on the whole group can never pass. `landed` is a finished claim
    # nobody is standing in; `open` is one to ask about.
    for b, _ in vacant:
        pr = merged_pr_of(found[b], b)
        mark = ("landed as #%s" % pr if isinstance(pr, int)
                else "MERGE UNREADABLE" if pr == "?" else "never merged")
        print(f"  {b:<40} {mark}")
    if vacant:
        print("  `landed` is finished work whose ref outlived it, and blocks "
              "nothing. The rest are\n  one of: a delegate that exited, or a "
              "checkout on another machine. Ask before\n  treating either as "
              "free.")

    print(f"\nlive sessions of campaign-{args.campaign_issue} ({len(ours)})")
    for sid, row in ours:
        print(f"  {row['name']:<24} {row['status']:<8} {row['pane']:<10} "
              f"{row['cwd']}")
    if ours:
        print("  WHICH of these holds which claim above is not derivable: "
              "herdr reports where a\n  session started, not the worktree it "
              "is working in. Ask them; the four messages\n  are the address, "
              "and this list is who to ask.")

    # ON STDOUT, and only one of the two ever prints. AGENTS.md tells a caller
    # to read the word and never the exit status, so a completed-verdict line
    # printed beside a failed reading is the exact shape that gets acted on: a
    # branch checked out in an unswept repository reads as vacant, and the
    # denial goes to a stream nobody was told to read.
    if unread:
        print(f"\nNOT all readings were made: {len(unread)} repositor(y/ies) "
              f"could not be swept, so\nthe counts above are of what was "
              f"readable and not of what is here. A claim may be\nstanding in "
              f"a workspace this did not look at.")
        for note in unread:
            print(f"  !! {note}")
        return 1

    print(f"\nall three readings were made. {len(occupied)} occupied, "
          f"{len(vacant)} vacant, {len(ours)} live session(s) of this campaign.")
    print("No verdict: a close reads these counts, it does not get one from "
          "here.")
    return 0


# --------------------------------------------------------------------- release


def compare_path(repo, branch):
    """Where to ask how far a branch is ahead of main."""
    return f"repos/{repo}/compare/main...{branch}"


def delete_path(repo, branch):
    """Where the ref is deleted. Same repo argument as compare_path, and that
    is the whole point: a claim branch has the same name in every member
    repository, so asking local git instead of the named remote could delete a
    different repository's ref holding a delegate's commits."""
    return f"repos/{repo}/git/refs/heads/{branch}"


def which_branch(branches, campaign_issue, issue, branch_arg):
    """(branch, refusal) -- which ref this release is about. Pure.

    `--branch` wins, because it is the caller naming one directly for the case
    the naming rule was broken. Otherwise the remote's own refs answer, and TWO
    matching one sub-issue is a refusal: nothing here can tell which of them
    holds the work, and deleting the wrong one costs a branch."""
    if branch_arg:
        return branch_arg, None
    found = refs_for_issue(branches, campaign_issue, issue)
    if not found:
        return None, (f"no ref under campaign-{campaign_issue}/ names sub-issue "
                      f"#{issue}, so there is no claim here to release. Pass "
                      f"--branch if the branch was named some other way.")
    if len(found) > 1:
        return None, (f"{len(found)} refs name sub-issue #{issue} "
                      f"({', '.join(found)}). Nothing here can tell which holds "
                      f"the work; pass --branch to name one.")
    return found[0], None


def occupants(where, branch):
    """The workspaces this branch is checked out in. Pure -- the reading the
    record could not make: it said who CLAIMED a sub-issue, never whether
    anything is standing in it right now."""
    return where.get(branch, [])


def ahead_count(returncode, out):
    """The comparison's ahead_by as an int, or None when the question was not
    answered. Split out so a known N is distinguishable from a comparison that
    did not happen; only the first is safe to act on."""
    ahead = (out or "").strip()
    if returncode != 0 or not ahead.isdigit():
        return None
    return int(ahead)


def ahead_verdict(n, out, err, repo, branch):
    """Read the comparison, already reduced to `n` by ahead_count so the caller
    parses it once and passes it through. Returns (ok, refusal)."""
    if n is None:
        ahead = (out or "").strip()
        return False, (f"could not ask {repo} how far {branch} is ahead of "
                       f"main; got {ahead!r}; {(err or '').strip()[:200]}. "
                       f"A comparison that did not happen is not an empty "
                       f"branch.")
    if n != 0:
        return False, (f"{repo} says {branch} is {n} commit(s) ahead of main. "
                       f"A ref holding commits is reported, never deleted.")
    return True, None


def ref_gone(returncode, err):
    """Did the comparison answer 404, meaning the ref is not there? Every other
    non-zero is a question that was not answered, and stays one."""
    return returncode != 0 and "HTTP 404" in (err or "")


def ref_probe(returncode, err):
    """What `git/ref/heads/<branch>` said: `present`, `gone`, or `unanswered`.
    Asked only after the comparison answered 404, because that 404 is the same
    bytes for a gone ref, a missing base, and an unreachable repository; only
    the ref's own endpoint separates the first from the other two."""
    if returncode == 0:
        return "present"
    if "HTTP 404" in (err or ""):
        return "gone"
    return "unanswered"


def merged_head_verdict(returncode, out, repo, branch):
    """Read `gh pr list --head <branch> --state merged`. Returns (ok, text):
    the merged pull request's number when ok, the refusal otherwise."""
    if returncode != 0:
        return False, (f"could not ask {repo} for a merged pull request whose "
                       f"head was {branch}. A question that did not get "
                       f"answered is not an absence.")
    try:
        prs = json.loads(out or "[]")
    except json.JSONDecodeError:
        return False, (f"{repo} answered the pull request question with "
                       f"something that is not JSON: {(out or '')[:120]!r}")
    if not prs:
        return False, (f"{repo} has no ref {branch} and no merged pull request "
                       f"whose head was it. A branch that vanished without "
                       f"merging is reported, never released.")
    return True, f"merged as #{prs[0].get('number', '?')}"


def cmd_release(args):
    root, _ = base_root()
    mine, scope_note = scope_for(args.campaign_issue)
    print(scope_note)
    # WHERE, from the sub-issue and not the caller -- the same reading `take`
    # makes. The spec says "`take` and `release` read the sub-issue's own
    # `## Lands in` section"; before this, only `take` did, and `release` still
    # picked a repository out of the clones on disk. A delete aimed by the
    # wrong reader takes a ref that is not this sub-issue's.
    subject, _named, note = issue_repo(args.issue, DEFAULT_REPO)
    if subject is None:
        print(f"refusing: {note}\n  Where a claim lives is a fact about the "
              f"sub-issue, and this deletes a ref.", file=sys.stderr)
        return 1
    print(note)
    if repo_named(args) and args.repo != subject:
        print(f"refusing: --repo says {args.repo}, #{args.issue} says "
              f"{subject}.\n  The sub-issue decides.", file=sys.stderr)
        return 1
    repos, repo_note = claim_repos(subject, root, mine,
                                   args.campaign_issue)
    found, unread1 = all_refs(repos, args.campaign_issue)
    if unread1 and not args.branch:
        print(f"refusing: {'; '.join(unread1)}\n  A ref listing that did not "
              f"happen is not an absence of claims.", file=sys.stderr)
        return 1
    branch, refusal = which_branch(sorted(found), args.campaign_issue,
                                   args.issue, args.branch)
    if refusal:
        print(f"refusing: {refusal}", file=sys.stderr)
        return 1
    # The repository the ref was FOUND on, never the default: the same branch
    # name exists in every member repository and a delete aimed at the wrong one
    # takes somebody else's commits. A `--branch` this did not find is exactly
    # that danger -- falling back to the base aimed every later question, the
    # DELETE included, at a repository that may carry the same name -- so an
    # unfound branch refuses rather than guessing which remote it is on.
    if branch not in found:
        print(f"refusing: nothing this read holds {branch}, so which repository "
              f"it is on is unknown.\n  Read: {', '.join(repos)}"
              + (f"\n  Unread: {'; '.join(unread1)}" if unread1 else "")
              + f"\n  Pass --repo to name the remote directly. Guessing the "
                f"base would aim the delete at a\n  repository that may carry "
                f"the same branch name.", file=sys.stderr)
        return 1
    repo = found[branch]
    print(f"releasing {branch} on {repo} ({repo_note})")

    # What is standing in it, read before anything is deleted. A sweep that
    # failed refuses: not knowing whether a workspace holds the branch is not
    # the same as knowing none does.
    sessions, why2 = herdr_sessions()
    if why2:
        print(f"refusing: {why2}\n  The repositories to sweep are derived from "
              f"the live sessions, so an unread\n  listing leaves an occupant "
              f"unread too.", file=sys.stderr)
        return 1
    roots, unread, why3 = sweep_roots(sessions, mine)
    if why3:
        print(f"refusing: {why3}", file=sys.stderr)
        return 1
    where, more = checkouts(roots)
    unread = unread + more
    if unread:
        print(f"refusing: {len(unread)} repositor(y/ies) could not be swept, "
              f"so whether a workspace\n  holds {branch} is unknown:",
              file=sys.stderr)
        for note in unread:
            print(f"  {note}", file=sys.stderr)
        return 1
    here = occupants(where, branch)
    if here:
        print(f"refusing: {branch} is checked out in {len(here)} workspace(s):",
              file=sys.stderr)
        for path in here:
            print(f"  {path}", file=sys.stderr)
        print("  Deleting the ref under a workspace strands its work. Remove "
              "the worktree first.", file=sys.stderr)
        return 1
    print(f"{branch} is checked out in no workspace on this machine "
          f"({len(roots)} repo(s) swept)")

    r = run("gh", "api", compare_path(repo, branch), "--jq", ".ahead_by")
    if ref_gone(r.returncode, r.stderr):
        q = run("gh", "api", f"repos/{repo}/git/ref/heads/{branch}")
        state = ref_probe(q.returncode, q.stderr)
        if state != "gone":
            print(f"refusing: the comparison against main answered 404 but the "
                  f"ref {branch} is {state} on {repo}"
                  f"{'' if state == 'present' else ': ' + q.stderr.strip()[:120]}. "
                  f"A comparison that did not happen is not an empty branch.",
                  file=sys.stderr)
            return 1
        p = run("gh", "pr", "list", "-R", repo, "--head", branch,
                "--state", "merged", "--json", "number")
        ok, text = merged_head_verdict(p.returncode, p.stdout, repo, branch)
        if not ok:
            print(f"refusing: {text}", file=sys.stderr)
            return 1
        print(f"{repo} has no ref {branch}, and it was {text}: nothing "
              f"beyond main, and no ref to delete")
        release_line(compact_own_pane(sessions,
                                      os.environ.get(SESSION_ID_VAR)), branch)
        return 0
    n = ahead_count(r.returncode, r.stdout)
    ok, refusal = ahead_verdict(n, r.stdout, r.stderr, repo, branch)
    if not ok:
        # A BRANCH WITH COMMITS IS NEVER DELETED HERE, and that is not a
        # shortcut -- but it used to leave no exit at all. When the record was
        # the claim, a confirmed absence retired the record and KEPT the ref;
        # now the ref IS the claim, so the same situation -- a sub-issue closed
        # `not planned` after its worker pushed -- left a ref standing that
        # `take`'s sibling sweep then refused forever, and the sub-issue could
        # never be re-taken. Deleting it silently is the one thing worse. So
        # this says what the two ways out are and makes the destructive one a
        # person's own command, run after they have looked at what is on the
        # branch.
        print(f"refusing: {refusal}", file=sys.stderr)
        if n:
            print(f"  The claim cannot be retired without the branch, because "
                  f"the branch IS the claim.\n"
                  f"  Either land those {n} commit(s) through a pull request, "
                  f"or -- having read them --\n"
                  f"  delete the ref by hand and re-take:\n"
                  f"    gh api -X DELETE {delete_path(repo, branch)}",
                  file=sys.stderr)
        return 1
    print(f"{repo} says {branch} holds nothing beyond main")

    # AN EMPTY BRANCH IS EITHER FINISHED WORK OR A CLAIM NOBODY HAS STARTED,
    # and the two look identical: both are 0 ahead of main and in no workspace.
    # A claim is cut BEFORE its delegate is launched (AGENTS.md § The binding),
    # so between the create-ref and the delegate's first checkout every claim on
    # this campaign is in exactly that state -- and deleting one there lets a
    # second `take` succeed and puts two workers on one sub-issue. A merged
    # pull request whose head was this branch is what tells the two apart; with
    # none, a person has to say the holder is gone, which is what
    # `--confirmed-absent` is. This is the proof the record's `session` field
    # used to carry and this restores, in the one place its absence destroyed
    # work rather than merely losing an address.
    p = run("gh", "pr", "list", "-R", repo, "--head", branch,
            "--state", "merged", "--json", "number")
    merged, text = merged_head_verdict(p.returncode, p.stdout, repo, branch)
    if merged:
        print(f"{branch} was {text}, so it is finished work and not a fresh "
              f"claim")
    elif p.returncode != 0:
        print(f"refusing: could not ask {repo} whether {branch} was ever "
              f"merged, so whether this is finished work or an unstarted claim "
              f"is unknown.", file=sys.stderr)
        return 1
    else:
        # THE SUB-ISSUE'S OWN STATE ANSWERS THIS, and it used to take a person
        # (#187 question 2). 0 ahead and never merged cannot tell finished work
        # from a claim cut for a holder who has not started -- but GitHub
        # already carries the missing bit: a CLOSED sub-issue says the work is
        # over, as completed or as not planned, and neither is a claim anybody
        # is standing in. That is `settled[Now.issue]` in
        # spec/campaign/orchestration/scenarios.als's `releaseNeedsAWorker`,
        # widened from `complete` by this question, with R7e as its control.
        #
        # This is what makes `R4_RepolessCampaign` true of the code: a sub-issue
        # whose work lands no commit closes with no pull request, so its ref is
        # 0 ahead for ever and only its `stateReason` can say the work is done.
        # `--confirmed-absent` survives for the sub-issue that is still OPEN,
        # which is the one case where nothing on GitHub says the holder is gone.
        settled, state_note = issue_settled(args.issue)
        if settled is None:
            print(f"refusing: {branch} holds nothing beyond main and was never "
                  f"merged, and {state_note}.\n  Whether its work is over is "
                  f"unknown, and an unknown is not a release.", file=sys.stderr)
            return 1
        if settled:
            print(f"{state_note}, so its work is over and the ref is residue")
        elif not args.confirmed_absent:
            print(f"refusing: {branch} holds nothing beyond main, was never "
                  f"merged, and {state_note},\n  so it is indistinguishable "
                  f"from a claim cut for a holder that has not checked it out "
                  f"yet.\n  Close the sub-issue if its work is done, or ask "
                  f"whose the claim is\n  (`{sys.argv[0]} live "
                  f"{args.campaign_issue}`, then the peers) and pass\n  "
                  f"--confirmed-absent WHO. Deleting it lets a second `take` "
                  f"succeed on the same sub-issue.", file=sys.stderr)
            return 1
        else:
            print(f"never merged and empty, but absence confirmed by: "
                  f"{args.confirmed_absent}")

    r = run("gh", "api", "-X", "DELETE", delete_path(repo, branch))
    if r.returncode != 0:
        print(f"refusing: could not delete the ref.\n  {r.stderr.strip()}",
              file=sys.stderr)
        return 1
    print(f"deleted {branch}")
    # LAST, and after the delete rather than before it: the release is what
    # this command is for, and compaction is a cost rule that must not be able
    # to stop one. Last also because the prompt fires when the turn ends, so
    # anything printed after it is printed by a session about to be compacted.
    release_line(compact_own_pane(sessions, os.environ.get(SESSION_ID_VAR)),
                 branch)
    return 0


# ------------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(add_help=True,
                                 description=__doc__.splitlines()[0])
    against = argparse.ArgumentParser(add_help=False)
    # SENTINEL, not the default value. Comparing `args.repo != DEFAULT_REPO`
    # cannot tell `--repo kalaluthien/campaign-base` typed by hand from no flag
    # at all, so an explicit base `--repo` on a member-repository sub-issue was
    # the one case "`--repo` may only confirm" silently did not cover.
    against.add_argument("--repo", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # One shape for the campaign issue everywhere: `#1` and `1` are the same
    # campaign in the branch and in `bound`.
    def number(s):
        return s.lstrip("#")

    t = sub.add_parser("take", parents=[against],
                       help="cut the claim branch on the remote")
    t.add_argument("campaign_issue", type=number)
    t.add_argument("issue")
    t.add_argument("topic")
    t.set_defaults(fn=cmd_take)

    r = sub.add_parser("release", parents=[against],
                       help="delete a claim branch holding nothing beyond main")
    r.add_argument("campaign_issue", type=number)
    r.add_argument("issue")
    r.add_argument("--branch", help="name the ref directly, for a branch the "
                                    "naming rule does not describe")
    r.add_argument("--confirmed-absent", metavar="WHO",
                   help="who established the holder is gone. Needed only for a "
                        "branch that is empty AND was never merged, which is "
                        "what a claim cut for a holder that never started "
                        "looks like.")
    r.set_defaults(fn=cmd_release)

    v = sub.add_parser("live", parents=[against],
                       help="which claims exist, and who is standing in them")
    v.add_argument("campaign_issue", type=number)
    v.set_defaults(fn=cmd_live)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
