---
name: close
description: Closes one piece of a campaign in the campaign-base repository, or the whole of it, through scripts/campaign-close.py, which reads the scope off the one target -- a campaign issue number, a sub-issue number, a session name, owner/repo, or nothing for this directory -- and prints which it read. Use when a person types /close, with or without a target.
disable-model-invocation: true
---

# Close

```sh
BASE=$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && pwd -P)
"$BASE/scripts/campaign-close.py" $ARGUMENTS
```

Its first line says which scope it read off the target and from where; its
`--help` holds every step and each `Holds when`. Read the last line it prints.

| it ends | then |
| --- | --- |
| `REFUSE <gate>:` | the line names the gate and why; clear that, run again |
| `HALT:` listing open sub-issues | each needs the person's disposition: finish it, `/close <sub-issue> --not-planned "<why>"`, or reparent it; run again |
| `HALT: … re-run with <flag>` | ask the person; on their yes, run again with that flag |
