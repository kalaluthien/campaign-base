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

## The planner's clock

A planner that has handed work out waits on a cron it sets itself
(§ Watching and retiring in `AGENTS.md`). Three horizons decide the cadence,
each a different cost:

| horizon | length | crossing it costs | the cron that answers it |
| --- | --- | --- | --- |
| prompt cache | 1 hour of silence | the next wake-up re-bills the whole context | recurring, under the hour, while workers run |
| usage window | 5 hours (status line's reset time) | the window's limit stops a planner that looks like one still thinking | one-shot, 1 minute after the reset, when a limit menu is read |
| weekly limit | 1 week (`/usage`'s "Current week" reset) | stops everything until its own reset | stop, and a one-shot at the weekly reset |

Two harness facts, from `CronCreate`'s own description:

- A cron is session-only: it lives only in this session and is gone when the
  session ends, so it is re-set after every restart.
- A recurring cron auto-expires after 7 days, firing once more first — a
  campaign running longer than a week re-arms the recurring cron then, or the
  cache heartbeat lapses silently.
