#!/usr/bin/env python3
"""The role table: what a planner and a worker may write, stated once.

    .claude/skills/assuming-role/scripts/campaign-roles.py [--brief]

The `assuming-role` skill owns the role machinery, and this is its schema half
-- what a role IS and what it may write -- kept apart from the instruction half
in the skill's `references/`, which says how a role acts. The split is by what
would make each wrong: a value here is wrong when the guard's behaviour differs
from it, which a suite can decide; a sentence there is wrong when the work goes
badly, which it cannot.

WHY A TABLE AND NOT PROSE. Before #227 these values were four constants in
check-campaign-claim.py and a paragraph of its docstring, and the paragraph was
restated in AGENTS.md and again in each skill that briefed a session. A rule
stated in four places is a rule with one reader and three copies; this file is
the one spelling, and `check-rule-readers.py` cannot catch a re-statement in
prose that names no shape. What keeps it honest instead is that every reader
IMPORTS it: check-campaign-claim.py decides by it, campaign-name-session.py
builds its name pattern from its keys, campaign-primitives.py prints it, and
campaign-role-brief.py briefs from it. A value nothing imports would be
documentation, and belongs in the skill's references instead.

WHAT IS NOT HERE, and why each is somewhere else:

  * THE CLAIM. A worker's licence over code is conditional on a claim, and the
    claim is derived per call from the target's checkout and the session's
    worktrees -- two clauses that read git, not a fact about the role. Putting
    a `claim: True` here would read as though the table decided it. The
    conjunct stays in check-campaign-claim.py, where the reading happens.

  * THE NAME PATTERN. campaign-name-session.py owns it and imports the role
    words from here, not the other way round: the shape of a name is that
    script's rule, the set of roles is this one's.

  * THE COMMENT KINDS AND CEILINGS. Campaign-wide, not per-role: every session
    posts under the same five kinds. They stay in campaign-tracker.py and the
    guard.

  * THE ROLE OF A GIVEN SESSION. Read from herdr by session id at the moment of
    the call. This file says what a role may do, never who holds one.

THE ROLE IS NOT A SECURITY BOUNDARY. A session can rename itself, so it can
name itself a planner; every session here also shares one `gh` account, so one
that renames itself already holds the power the name would grant. What the role
buys is that it is EXPLICIT and that the mistake is LOUD. #194 is the sub-issue
for tying the name to something the named session did not choose.

EXIT. 0 always for `--brief` and the default listing; this file decides
nothing on its own and refuses nothing. Its readers do.
"""
import sys

# THE TWO ROLES, and the keys are the role words themselves: every other
# reader takes its vocabulary from here, so adding a third role is an edit to
# this dict and to whatever new behaviour it needs, never a sweep for the words
# `planner` and `worker` across the tree. #169 renamed `executor` to `worker`
# by exactly such a sweep, and campaign-name-session-test.py still carries the
# case that keeps the retired word out.
#
# `campaign_plane` is WHOSE campaign plane the role writes, and the two values
# are the whole difference #185 drew: a planner keeps the campaign plane of ANY
# campaign -- a comment, a sub-issue, a close, a claim cut for a delegate --
# because deciding what work exists is what a planner is for, while a worker
# writes the campaign it is named for and no other.
#
# `code_plane` is whether the role may change code AT ALL. False for a planner
# is #185's rule, "a planner changes no code", and the guard enforces it over a
# file tool's writes; True for a worker is a licence its claim then bounds,
# never a blanket one -- see WHAT IS NOT HERE above.
ROLES = {
    "planner": {
        "campaign_plane": "any",
        "code_plane": False,
        # WHICH gh WRITES ARE THE CAMPAIGN PLANE. The planner licence is
        # bounded by this and not by the guard's WRITES set, which holds both
        # planes: `gh pr create` is OpenPullRequest and `gh pr merge` is
        # MergePullRequest, and `codePlaneEvents` in
        # spec/campaign/orchestration/system.als puts the first on the code
        # plane while the three merge conditions -- not a role -- hold the
        # second. A planner allowed every write row could open and merge pull
        # requests and delete another worker's claim ref through `gh api`,
        # which is the opposite of "a planner changes no code".
        #
        # Keyed on the SUBCOMMAND alone, because that is what the plane is a
        # property of. Anything absent is not a planner's by this rule and
        # falls through to the claim reading, which refuses it without a claim
        # exactly as before.
        "gh": frozenset({"issue", "label"}),
        # THE ONE `gh issue` VERB THE LICENCE DOES NOT COVER
        # (kalaluthien/campaign-base#213). `gh issue develop` cuts a branch in
        # the sub-issue's own repository, and with
        # `--name <slug>/<issue>-<topic>` that branch IS a claim -- the
        # same object `campaign-claim take` cuts. Bare, it names the branch
        # `<issue>-<slug>`, which no reader here treats as a claim; the flag is
        # one word away and the guard reads no flags, so the verb is judged by
        # what it CAN cut and not by what a given spelling does cut.
        #
        # The tempting argument, that `develop` belongs beside `gh pr create`
        # on the code plane, is WRONG and was checked rather than assumed:
        # `Claim` sits in `campaignPlaneEvents` and not in `codePlaneEvents`
        # (spec/campaign/orchestration/system.als), and a planner cutting a
        # claim for a delegate it is about to launch is precisely what the
        # licence exists to buy. What is wrong is the ROUTE, not the plane:
        # `campaign-claim take` reads the binding, the sub-issue's real parent,
        # and the campaign issue's `## Repos` -- `claimWithinScope` in
        # spec/campaign/orchestration/scenarios.als -- and `gh issue develop`
        # reads none of the three and cuts the ref anyway. Refusing it leaves
        # ONE route to a claim, which is the only condition under which that
        # model rule has a reader at all.
        "gh_except": frozenset({("issue", "develop")}),
        "own_campaign_gh": {"campaign issue": frozenset(),
                            "sub-issue": frozenset()},
    },
    "worker": {
        "campaign_plane": "own",
        "code_plane": True,
        # A worker reaches a `gh` write through the CLAIM reading, not through
        # a licence, so it holds no subcommand outright. Empty is a value here
        # and not an omission: it is what makes `gh pr merge` from a worker a
        # question about its claim rather than about its role.
        "gh": frozenset(),
        "gh_except": frozenset(),
        # WHAT A WORKER MAY DO TO ITS OWN CAMPAIGN'S ISSUE WITHOUT A CLAIM
        # (#207). No claim can ever cover the campaign issue -- it is nobody's
        # sub-issue -- so this is carved out. Keyed on the VERB and not on the
        # issue number, which is the conjunct the first cut was missing:
        # `edit` is the charter body, which only `closing-campaign` step 4
        # writes; `close` closes the CAMPAIGN, a person's decision; `delete`
        # and `transfer` are irreversible. A claim on some other sub-issue
        # makes none of them safer, so the claim was never the missing test.
        #
        # ANY SUB-ISSUE OF THAT CAMPAIGN, TOO, for the two verbs that append
        # to its record (#354). AGENTS.md § Sub-issues has a discovery appended
        # to the sub-issue that covers it and that sub-issue reopened; without
        # this a worker could do neither on a number it held no claim on, and
        # its findings drifted onto new numbers under the 100-sub-issue cap.
        # `reopen` is the SUB-ISSUE's and not the campaign issue's: reopening
        # the campaign undoes a close, which is a person's decision.
        "own_campaign_gh": {
            "campaign issue": frozenset({("issue", "comment")}),
            "sub-issue": frozenset({("issue", "comment"),
                                    ("issue", "reopen")}),
        },
    },
}

# The role words, in the order the table states them, for a reader building a
# pattern or a listing. campaign-name-session.py's NAME alternation is built
# from this, so a role that exists here is nameable and one that does not is
# refused at the rename -- one fact, not two.
ROLE_WORDS = tuple(ROLES)

# What a name that the pattern does not admit resolves to, as distinct from a
# role that could not be read at all. The two license different things and the
# guard keeps them apart; the word lives here because it is a value OF the role
# reading, not of any one reader.
NO_ROLE = "no-role"


def role(word):
    """The row for one role word, or None. Callers that must distinguish an
    unknown word from a role with an empty licence use this rather than
    `ROLES.get(word, {})`, which makes the two read alike."""
    return ROLES.get(word)


def main():
    brief = "--brief" in sys.argv
    if brief:
        print("campaign-roles: the role table -- plane and writes per role")
        return 0
    print(f"{len(ROLES)} role(s), and every reader imports them from here.")
    for name, r in ROLES.items():
        print(f"\n  {name}")
        print(f"    campaign plane   {r['campaign_plane']}")
        print(f"    changes code     {'yes' if r['code_plane'] else 'no'}"
              + ("" if not r["code_plane"]
                 else "  (bounded by its claim, read per call)"))
        gh = ", ".join(sorted(r["gh"])) or "none outright"
        print(f"    gh subcommands   {gh}")
        if r["gh_except"]:
            print("    except           "
                  + ", ".join(sorted(f"{s} {v}" for s, v in r["gh_except"])))
        for target, pairs in r["own_campaign_gh"].items():
            if pairs:
                print(f"    own {target}: "
                      + ", ".join(sorted(f"{s} {v}" for s, v in pairs)))
    print("\nWhat this file does not decide: the claim (per call, in "
          "check-campaign-claim.py), the name shape (campaign-name-session.py), "
          "and who holds a role (herdr, by session id).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
