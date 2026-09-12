/*
 * What GitHub records about a campaign, told as traces and checked: the
 * witnesses that show a story about it, what must hold of github/system, and
 * the floor that says its events are reachable at all. github/system.als is
 * spec/'s entry point and carries the orientation.
 */
module github/checks

open github/system

/* ---------------- witnesses ---------------- */

/* Settlement is strictly weaker than completion at these bounds, so that
   assertion is an answer rather than a synonym. */
pred SettledWithoutMerge { eventually (some i: Campaign.memberIssues | settled[i] and no i.pullRequest) }

/* The plain path. */
pred S1_HappyPath {
  one c: Campaign {
    #c.memberIssues = 2
    #(c.memberIssues.repo) = 2
    always Now.event not in AddMember + RemoveMember
    mergeClosed[c.memberIssues]
    eventually (all i: c.memberIssues | complete[i])
    closeDiscipline[c]
    eventually (closable[c] and campaignClosed[c])
  }
}

/* Closed as not planned, no pull request ever, and closable is still
   reached. */
pred S2_SubIssueDropped {
  one c: Campaign {
    #c.memberIssues = 2
    always Now.event not in AddMember + RemoveMember
    some disj i1, i2: c.memberIssues {
      mergeClosed[i1]
      eventually complete[i1]
      always no i2.pullRequest
      eventually dropped[i2]
    }
    closeDiscipline[c]
    eventually (closable[c] and campaignClosed[c])
  }
}

/* The campaign re-opens work instead of closing. */
pred S5_FollowUpAfterSettled {
  one c: Campaign {
    #c.memberIssues = 1
    mergeClosed[Issue - c.campaignIssue]
    always Now.event != RemoveMember          -- no emptying the campaign to fake "all settled"
    some i1: c.memberIssues, i2: Issue - c.memberIssues - c.campaignIssue {
      eventually (complete[i1] and c.campaignIssue in Open
                  and Now.event = AddMember and Now.issue = i2)
      eventually (i2 in c.memberIssues and not settled[i2])
      eventually complete[i2]
    }
    closeDiscipline[c]
    eventually (closable[c] and campaignClosed[c])
  }
}

/* The added sub-issue's work lands in a repository no existing member's does. */
pred S6_RepoJoinsMidFlight {
  one c: Campaign {
    #c.memberIssues = 1
    #(c.memberIssues.repo) = 1
    mergeClosed[Issue - c.campaignIssue]
    always Now.event != RemoveMember
    eventually (Now.event = AddMember
                and Now.issue not in c.memberIssues
                and Now.issue.repo not in c.memberIssues.repo)
    eventually (#c.memberIssues = 2 and #(c.memberIssues.repo) = 2
                and (all i: c.memberIssues | complete[i]))
  }
}

/* Nothing guards the campaign issue's close, so a real run must report it. */
pred S8_CloseWithOpenSubIssue {
  one c: Campaign {
    #c.memberIssues = 2
    always Now.event not in AddMember + RemoveMember
    mergeClosed[c.memberIssues]
    some disj i1, i2: c.memberIssues |
      eventually (Now.event = CloseIssue and Now.issue = c.campaignIssue
                  and complete[i1] and i2 in Open)
    eventually (campaignClosed[c] and (some i: c.memberIssues | i in Open))
  }
}

/* The index prunes with it, which is what the sub-issue link buys over a
   back-reference: a mention cannot be un-said. */
pred S10_SubIssueMovedOut {
  one c: Campaign {
    #c.memberIssues = 2
    mergeClosed[c.memberIssues]
    always Now.event != AddMember
    some disj i1, i2: c.memberIssues {
      always (Now.event = RemoveMember implies Now.issue = i2)
      eventually (Now.event = RemoveMember and Now.issue = i2)
      eventually complete[i1]
      eventually c.memberIssues = i1
    }
    always (all d: Campaign | d.memberIssues = indexOf[d])
    closeDiscipline[c]
    eventually (closable[c] and campaignClosed[c])
  }
}

/* A missing "Closes #N": the campaign never becomes closable and nothing
   says why. */
pred S11_MergedButIssueLeftOpen {
  one c: Campaign {
    #c.memberIssues = 1
    always Now.event not in AddMember + RemoveMember
    some i: c.memberIssues {
      eventually (some i.pullRequest and i.pullRequest in Merged and i in Open)
      eventually always (i in Open)
      always not complete[i]
    }
    always not closable[c]
  }
}

/* What a per-campaign branch prefix buys. */
pred S12_TwoCampaignsOneRepo {
  #Campaign = 2
  all c: Campaign | #c.memberIssues = 1
  one r: Repo - Base | Campaign.memberIssues.repo = r
  mergeClosed[Campaign.memberIssues]
  always Now.event not in AddMember + RemoveMember
  all c: Campaign | closeDiscipline[c]
  eventually (all c: Campaign, i: c.memberIssues | complete[i])
  eventually (all c: Campaign | campaignClosed[c])
}

/* Reopened after it read complete. UNSAT, and S13a-S13c pin why rather than
   leaving it to the bounds. NOT VERIFIED AGAINST GITHUB -- `gh issue reopen`
   documents no such restriction, so if it holds it is the model, not the
   design, that needs a reopen event. */
pred S13_ReopenAfterMerge {
  one c: Campaign | some i: c.memberIssues {
    eventually complete[i]
    eventually (complete[i] and after (i in Open))
  }
}

/* S13a: completion is reachable at these bounds. S13b: a closed issue can
   reopen, via the re-add. S13c: one that ever had a pull request cannot --
   `addMember` guards on `no i.pullRequest` and `WellFormed` never undoes a pr link,
   which is the actual blocker. */
pred S13a_ControlCompletes { some i: Campaign.memberIssues | eventually complete[i] }
pred S13b_ReopenAnyClosed  {
  some i: Issue | eventually (i not in Open and Now.event = AddMember and Now.issue = i
                              and after (i in Open))
}
pred S13c_ReopenWithPR     { some i: Issue | eventually (some i.pullRequest and i not in Open and after (i in Open)) }

/* Nothing in the design guards a closed campaign issue against later sub-issues. */
pred S14_FollowUpAfterClose {
  one c: Campaign {
    #c.memberIssues = 1
    mergeClosed[Issue - c.campaignIssue]
    always Now.event != RemoveMember
    closeDiscipline[c]
    some i2: Issue - c.memberIssues - c.campaignIssue {
      eventually (campaignClosed[c] and Now.event = AddMember and Now.issue = i2)
      eventually (campaignClosed[c] and i2 in c.memberIssues and i2 in Open and not settled[i2])
    }
  }
}

/* Under the narrow reading the base cannot be a member of its own
   campaign at all: the model forbade what was about to happen for real. */
pred S16a_BaseMemberUnderNarrowReading {
  baseIsCampaignIssueOnly
  some c: Campaign, i: c.memberIssues | i.repo = Base
}

/* The tracker's third kind. It was UNSAT at any bound while
   `baseIssuesAreCampaignIssues` was a fact, and no verdict said so. */
pred S18_PlainBaseIssue {
  some i: Issue | i.repo = Base and always (i not in Campaign.campaignIssue + Campaign.memberIssues)
}

/* Why the clause is kept rather than deleted: as a predicate it still says
   exactly what it said as a fact. */
pred S18a_PlainBaseIssueUnderClosedWorld {
  baseIssuesAreCampaignIssues and S18_PlainBaseIssue
}

/* S20. THE BASE IS NEVER IN `## Repos` (kalaluthien/campaign-base#205). The
   premise `claimWithinScope`'s `Base` disjunct rests on, and until #205 it was
   prose in three files: `campaign-repos.py` accepted `- kalaluthien/campaign-base`
   and exited 0, and this model let a trace put `Base` in `reposInBody`. Both
   have a reader now, and this is the model's.

   EXPECT 0 WITH THE FACT. Dropping `always Base not in Campaign.reposInBody`
   from `WellFormed` makes it SAT, which is what tells the fact from a comment
   about the fact. S20a beside it is the control: a NON-base repository in the
   list is ordinary and must stay SAT, or the fact has emptied the relation
   rather than bounded it -- which a single `expect 0` cannot tell apart.

   Not R14d's job, and R14d cannot be given it: that command ASSUMES
   `Base not in c.reposInBody` inside its own witness, so it is satisfied by a
   world the fact forbids and by a world it permits alike. */
pred S20_TheBaseIsNeverListed { eventually Base in Campaign.reposInBody }
pred S20a_ControlANonBaseRepoIsListed {
  some r: Repo | r != Base and eventually r in Campaign.reposInBody
}

/* THE PERSON'S HOLD, and the close event it refuses. S21 asks for the trace
   `closeDiscipline` must not have: the campaign issue closed at a moment when
   the campaign is `Standing`. It reddens -- goes SAT -- the instant
   `c not in Standing` leaves `closable`, which is what tells the conjunct from
   a comment about the conjunct.

   S21a beside it is the control, and it is not optional: `expect 0` alone is
   satisfied by a `closable` that admits nothing at all, so a second command
   must show that the ORDINARY close -- the same event with the hold off -- is
   still reachable. Same shape as S20/S20a. */
pred S21_StandingBlocksTheClose {
  one c: Campaign |
    closeDiscipline[c] and eventually (Now.event = CloseIssue
      and Now.issue = c.campaignIssue and c in Standing)
}
pred S21a_ControlTheCloseHappensWithTheHoldOff {
  one c: Campaign |
    closeDiscipline[c] and eventually (Now.event = CloseIssue
      and Now.issue = c.campaignIssue and c not in Standing)
}

/* ---------------- commands ---------------- */

-- control: settlement is weaker
run SettledWithoutMerge  for 4 Issue, 3 PullRequest, 2 Campaign, 3 Repo, 6 steps expect 1

run S1_HappyPath                for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S2_SubIssueDropped           for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S5_FollowUpAfterSettled     for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 2 Repo, 14 steps expect 1
run S6_RepoJoinsMidFlight       for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 14 steps expect 1
run S8_CloseWithOpenSubIssue     for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S10_SubIssueMovedOut         for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S11_MergedButIssueLeftOpen  for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 1
run S12_TwoCampaignsOneRepo     for exactly 4 Issue, 2 PullRequest, exactly 2 Campaign, exactly 2 Repo, 14 steps expect 1
-- the finding: no reopen after a pull request
run S13_ReopenAfterMerge        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 10 steps expect 0
run S13a_ControlCompletes       for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 10 steps expect 1
run S13b_ReopenAnyClosed        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 10 steps expect 1
-- the actual blocker
run S13c_ReopenWithPR           for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 10 steps expect 0
run S14_FollowUpAfterClose      for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 2 Repo, 14 steps expect 1
-- the narrow reading forbade it
run S16a_BaseMemberUnderNarrowReading for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 0
-- the tracker's third kind exists
run S18_PlainBaseIssue              for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Repo, 6 steps expect 1
-- control: the clause bites
run S18a_PlainBaseIssueUnderClosedWorld for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Repo, 6 steps expect 0
-- #205: the base is never in `## Repos`, and the list is not thereby empty
run S20_TheBaseIsNeverListed          for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 0
run S20a_ControlANonBaseRepoIsListed  for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 1

run S21_StandingBlocksTheClose        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 0
run S21a_ControlTheCloseHappensWithTheHoldOff for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 1


/* ---------------- properties ---------------- */

// X. The cheaper reading -- "the issue is closed" -- is not completion.
assert ClosedImpliesComplete {
  always all c: Campaign, i: c.memberIssues | i not in Open implies complete[i]
}

/* Neither missing a member nor holding a stale one. Dropping `addMember`'s
   sub-issue write reddens it, and so does any index that is a second write. */
assert IndexExact { always all c: Campaign | c.memberIssues = indexOf[c] }

/* From the campaign issue alone, member repositories and open sub-issues are
   recoverable. */
assert Reconstitution {
  always all c: Campaign |
    c.memberIssues.repo = indexOf[c].repo and (c.memberIssues & Open) = (indexOf[c] & Open)
}

/* Weak fairness: whenever some progress event is enabled on a member issue,
   one eventually fires. It says nothing when nothing is enabled. */
pred progressEnabled {
  some i: Campaign.memberIssues |
    (i in Open and no i.pullRequest)
    or (some i.pullRequest and i.pullRequest not in Merged)
    or i in Open
}
pred weakFairness { always (progressEnabled implies eventually Now.event in OpenPullRequest + MergePullRequest + CloseIssue) }

/* `githubInit` also admits the empty world a campaign issue is filed from, where the
   conclusion is vacuously true at time zero. */
pred hasWork { some Campaign.memberIssues }

/* This counterexample changed the design: a member closed without a merged
   pull request never reads complete, so the campaign never becomes closable. */
assert TerminationUnderFairness {
  (hasWork
   and (eventually always Now.event != AddMember)
   and weakFairness)
  implies (eventually all c: Campaign, i: c.memberIssues | complete[i])
}

// PASS. Under fairness AND an issue closed only by a merged pull request.
assert TerminationDisciplined {
  (hasWork
   and (eventually always Now.event != AddMember)
   and (always (Now.event = CloseIssue implies (some Now.issue.pullRequest and Now.issue.pullRequest in Merged)))
   and (always Now.event != RemoveMember)
   and weakFairness)
  implies (eventually all c: Campaign, i: c.memberIssues | complete[i])
}

/* The repair: read settlement both ways and the same traces terminate.
   Dropping `weakFairness` reddens it. */
assert TerminationUnderSettlement {
  (hasWork
   and (eventually always Now.event != AddMember)
   and weakFairness)
  implies (eventually all c: Campaign, i: c.memberIssues | settled[i])
}

/* ---------------- reachability floor ----------------
 * An event no trace can reach silently removes a whole question from the
 * commands above, and an over-tight frame is the cheapest way to cause it
 * without any command turning red.
 */
pred Cov_FileCampaignIssue   { eventually Now.event = FileCampaignIssue }
pred Cov_AddMember    { eventually Now.event = AddMember }
pred Cov_RemoveMember { eventually Now.event = RemoveMember }
pred Cov_OpenPullRequest       { eventually Now.event = OpenPullRequest }
pred Cov_MergePullRequest      { eventually Now.event = MergePullRequest }
pred Cov_CloseIssue   { eventually Now.event = CloseIssue }
pred Cov_WriteBody    { eventually Now.event = WriteBody }
pred Cov_Claim        { eventually Now.event = Claim }
pred Cov_Release      { eventually Now.event = Release }

/* ---------------- commands ---------------- */

-- closed is not completed
check ClosedImpliesComplete      for 4 Issue, 3 PullRequest, 2 Campaign, 3 Repo, 6 steps expect 1
-- the index is exactly the membership
check IndexExact                 for 4 Issue, 3 PullRequest, 2 Campaign, 3 Repo, 6 steps expect 0
-- the campaign issue alone recovers the campaign
check Reconstitution             for 4 Issue, 3 PullRequest, 2 Campaign, 3 Repo, 6 steps expect 0
-- closed-and-merged cannot say "dropped"
check TerminationUnderFairness     for 3 Issue, 2 PullRequest, 1 Campaign, 2 Repo, 10 steps expect 1
check TerminationDisciplined       for 3 Issue, 2 PullRequest, 1 Campaign, 2 Repo, 10 steps expect 0
-- the reading AGENTS.md adopted
check TerminationUnderSettlement   for 3 Issue, 2 PullRequest, 1 Campaign, 2 Repo, 10 steps expect 0

-- every own event fires in some trace
run Cov_FileCampaignIssue   for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_AddMember    for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_RemoveMember for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_OpenPullRequest       for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_MergePullRequest      for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_CloseIssue   for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_WriteBody    for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_Claim         for 3 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_Release       for 3 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
