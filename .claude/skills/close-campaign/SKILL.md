---
name: close-campaign
description: Closes a campaign in the campaign-base repository through scripts/campaign-close.py, which refuses on the binding, the standing label, a live claim or session, work only on this machine, an install behind, or an open sub-issue, and writes only on the person's word. Use when a person types /close-campaign with a campaign number. Not for dropping one sub-issue, retiring one worker, dropping a repository or letting a directory go, which are the same script's other scopes.
disable-model-invocation: true
---

# Close a campaign

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
"$BASE/scripts/campaign-close.py" campaign $ARGUMENTS
```

Its `--help` holds every step and each `Holds when`; read the last line it
prints.

| it ends | then |
| --- | --- |
| `REFUSE <gate>:` | the line names the gate and why; clear that, run again |
| `HALT:` listing open sub-issues | each needs the person's disposition: finish it, drop it with the script's `sub-issue` scope, or reparent it; run again |
| `HALT: … --close` or `… --delete` | ask the person; on their yes, run again with that flag |
