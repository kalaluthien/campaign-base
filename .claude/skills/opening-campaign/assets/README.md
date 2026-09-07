<!-- The campaign issue. Title: a verb-first mission carrying the words a
     search would use. No `Campaign:` prefix -- the `campaign` label says which
     kind this is, and structure is what every reader classifies by.

     Body: bullets or tables, no prose paragraphs. Both ceilings are numbers in
     `scripts/campaign-tracker.py` and are not repeated here;
     `campaign-tracker.py check <N>` prints each one beside what it measured,
     and `campaign-tracker bind` prints that reading and never gates on it.
     Design over the body ceiling is a file in `spec/` or `docs/`, linked from
     here. -->

## Intent

- <what is wrong or wanted now, and what says so>

## Scope

In:

- <what this campaign covers>

Out:

- <what it deliberately does not cover, and where that work goes instead>

## Done when

- <a condition the finished work must satisfy, checkable rather than admirable,
  and readable off the closed campaign issue>

## Repos

<!-- The MEMBER repositories this campaign clones. `- none`, alone, is the whole
     list for a campaign with no member repository; adding the first one
     replaces it, and the two never sit together. The base is never listed --
     it reaches its campaign directory by its own route, and
     `scripts/campaign-repos.py` refuses an entry naming it.

     A repository INSTALLED on this machine -- checked out where it is used,
     `~/.claude` for dotclaude -- carries one bracket saying where, and what
     the install runs once a merge is carried into it:
       - owner/repo (installed: <path>, apply: <command>)
     `apply:` is optional; `installed:` is absolute or `~`-rooted. The entry
     is still cloned like any other; `scripts/campaign-installed.py` is what
     reads the install and reaches it after a merge. -->

- <owner/repo>
- <owner/repo>
