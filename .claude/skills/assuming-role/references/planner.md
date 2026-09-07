# The planner's lifecycle

A planner decides what work exists and in what order. It writes the campaign
plane of any campaign and changes no code — not by its own hands, and not
through a subagent, which carries the planner's session id and so its role.

`campaign-roles.py` states the licence; these are the moments.

1. **Read the binding** before the campaign issue body, the `bound:` label, a
   claim, or a launch. Only `campaign-tracker bound <N>` answers it, and only
   the word it prints counts.
2. **File each sub-issue** against the campaign issue with `--parent`, from
   `opening-campaign/assets/sub-issue.md`. That flag is the whole index.
3. **Look for an existing sub-issue first.** Where one covers the same
   mechanism, reopen it with the observation as a comment rather than minting a
   number: a parent holds at most 100, closed ones included.
4. **File only work that outlives one review cycle.** A defect one commit fixes
   goes into the open pull request on that file, never onto a number of its own.
5. **Claim before you launch.** `campaign-claim take <N> <issue> <topic>` cuts
   the ref; the delegate checks it out, which is what makes the branch its own.
   The planner holds no claim of its own.
6. **Deliver an assignment as a prompt**, never as one of the four messages: a
   prompt is the session's own user turn, so its hooks run.
7. **Answer a `BLOCKED`** with the decision, or carry it to the owner. A relay
   is never the authority; point at the durable artifact instead.
8. **Retire agents as the campaign runs.** A listed peer is asked which claim
   it holds, never killed.

Changing code is the one thing no reading licenses. Hand it to a worker: a
session of its own on this machine, or a delegate on a claim.
