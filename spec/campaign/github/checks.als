/*
 * What GitHub records about a campaign, told as traces and checked: the
 * witnesses that show a story about it, what must hold of github/system, and
 * the floor that says its events are reachable at all. github/system.als is
 * spec/'s entry point and carries the orientation.
 */
module github/checks

open github/system

/* ---------------- witnesses ---------------- */

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

/* The tracker's third kind: an issue on the base that no campaign ever
   holds. SAT, since no fact closes the base's tracker to campaign issues. */
pred S18_PlainBaseIssue {
  some i: Issue | i.repo = Base and always (i not in Campaign.campaignIssue + Campaign.memberIssues)
}

/* S20. THE BASE IS NEVER IN `## Repos`. The premise `claimWithinScope`'s
   `Base` disjunct rests on.

   EXPECT 0 WITH THE FACT. Dropping `always Base not in Campaign.reposInBody`
   from `WellFormed` makes it SAT, which is what tells the fact from a comment
   about the fact. That the fact bounds the relation rather than empties it
   is R14c_ScopeAdmitsTheListedMember's: a NON-base repository in the list
   stays reachable there.

   Not R14d's job, and R14d cannot be given it: that command ASSUMES
   `Base not in c.reposInBody` inside its own witness, so it is satisfied by a
   world the fact forbids and by a world it permits alike. */
pred S20_TheBaseIsNeverListed { eventually Base in Campaign.reposInBody }

/* THE PERSON'S HOLD, and the close event it refuses. S21 asks for the trace
   `closeDiscipline` must not have: the campaign issue closed at a moment when
   the campaign is `Standing`. It reddens -- goes SAT -- the instant
   `c not in Standing` leaves `closable`, which is what tells the conjunct from
   a comment about the conjunct.

   `expect 0` alone is satisfied by a `closable` that admits nothing at all;
   the ORDINARY close with the hold off is S1_HappyPath's, under the same
   `closeDiscipline`. */
pred S21_StandingBlocksTheClose {
  one c: Campaign |
    closeDiscipline[c] and eventually (Now.event = CloseIssue
      and Now.issue = c.campaignIssue and c in Standing)
}

/* THE PERSON'S HOLD ON A SUB-ISSUE, and the claim it refuses. S22 asks for the
   trace `backlogDiscipline` must not have: a claim cut on a sub-issue in
   `Backlog`; it goes SAT the instant the discipline stops reading the label.
   S22a is the control: the same claim with the hold off is still
   reachable, so the UNSAT is the discipline's and not the model's. */
pred S22_BacklogBlocksTheClaim {
  backlogDiscipline and eventually (Now.event = Claim and Now.issue in Backlog)
}
pred S22a_ControlTheClaimHappensWithTheHoldOff {
  backlogDiscipline and eventually (Now.event = Claim and Now.issue not in Backlog)
}

/* JV1. A JUDGMENT ADVISES ONLY WHEN IT REPLIED, WAS CONFIDENT AND FIT
   (system.als's `advised`), and only then: JV1b is UNSAT because a failed call,
   an answer under its threshold and the no-match option each come back
   `unknown`, and dropping any one of `advised`'s three conditions makes it
   SAT. */
pred JV1_ARepliedConfidentFittingJudgmentAdvises { some j: Judgment | advised[j] }
pred JV1b_AFailedLowOrNoMatchAnswerNeverAdvises {
  some j: Judgment | advised[j] and (j not in Replied or j not in Confident or j not in Fits)
}

/* ---------------- commands ---------------- */

-- a judgment advises only when it replied, was confident and fit
run JV1_ARepliedConfidentFittingJudgmentAdvises for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 1
run JV1b_AFailedLowOrNoMatchAnswerNeverAdvises    for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 0

run S1_HappyPath             for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S2_SubIssueDropped           for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S5_FollowUpAfterSettled     for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 2 Repo, 14 steps expect 1
run S6_RepoJoinsMidFlight       for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 14 steps expect 1
run S8_CloseWithOpenSubIssue     for exactly 3 Issue, 2 PullRequest, exactly 1 Campaign, exactly 3 Repo, 12 steps expect 1
run S11_MergedButIssueLeftOpen  for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 1
-- the tracker's third kind exists
run S18_PlainBaseIssue              for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 1 Repo, 6 steps expect 1
-- the base is never in `## Repos`, and the list is not thereby empty
run S20_TheBaseIsNeverListed          for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 6 steps expect 0

run S21_StandingBlocksTheClose        for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 0
run S22a_ControlTheClaimHappensWithTheHoldOff for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 1
run S22_BacklogBlocksTheClaim         for exactly 2 Issue, 1 PullRequest, exactly 1 Campaign, exactly 2 Repo, 8 steps expect 0

/* ---------------- properties ---------------- */

/* Neither missing a member nor holding a stale one. Dropping `addMember`'s
   sub-issue write reddens it, and so does any index that is a second write. */
assert IndexExact { always all c: Campaign | c.memberIssues = indexOf[c] }

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

/* The repair: read settlement both ways and the same traces terminate.
   Dropping `weakFairness` reddens it. */
assert TerminationUnderSettlement {
  (hasWork
   and (eventually always Now.event != AddMember)
   and weakFairness)
  implies (eventually all c: Campaign, i: c.memberIssues | settled[i])
}

/* ---------------- reachability floor ----------------
   Every event the checks above name fires in some trace, so none holds by
   vacuity; alloy-check.py reads these as the witnesses. RemoveMember is named
   by no check here and fires for its own sake. */
pred Cov_AddMember    { eventually Now.event = AddMember }
pred Cov_OpenPullRequest       { eventually Now.event = OpenPullRequest }
pred Cov_MergePullRequest      { eventually Now.event = MergePullRequest }
pred Cov_CloseIssue   { eventually Now.event = CloseIssue }
pred Cov_RemoveMember { eventually Now.event = RemoveMember }

/* ---------------- commands ---------------- */

-- the index is exactly the membership
check IndexExact                 for 4 Issue, 3 PullRequest, 2 Campaign, 3 Repo, 6 steps expect 0
-- the reading AGENTS.md adopted
check TerminationUnderSettlement   for 3 Issue, 2 PullRequest, 1 Campaign, 2 Repo, 10 steps expect 0

run Cov_AddMember    for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_OpenPullRequest       for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_MergePullRequest      for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_CloseIssue   for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
run Cov_RemoveMember for 4 Issue, 2 PullRequest, 2 Campaign, 3 Repo, 8 steps expect 1
