#!/usr/bin/env python3
# witnesses: Cov_CreateDir, S15_NoLocalDirectory
"""Answer which directory on this machine is a campaign's, read from its marker.

A campaign directory is named `campaign-<slug>-<date>` and the bare `<slug>/` is
the accepted older form, so no name shape separates one from `scripts/` and no
caller can compose the path from the slug. What identifies it is the `.campaign`
marker, whose two fields are the campaign's issue number and its slug -- and
`check-campaign-claim.py` owns that reading. This is the one-word reader the
skills call: it imports the guard's `campaign_dirs_at` and filters, so the walk
stays in one file.

THE ANSWER IS THE WORD, alone on stdout so `$( )` can take it, with the
sentence beside it on stderr; the status says whether the reading was made.

    <absolute path>  exit 0   exactly one directory here names that campaign
    none             exit 1   a base was read, and no directory in it names the
                              campaign
    unknown          exit 2   there was nowhere to look, the reading failed, or
                              two directories name it

Two directories naming one campaign is refused rather than tie-broken, for
`campaign_number`'s reason: sorted order is not a tiebreak, and a close that
picked one would `rm -rf` a directory nobody named.

The token is the campaign's issue number or its slug -- the marker's two fields
-- because the callers hold different halves: a close holds the number, and a
session's own name holds the slug.

Usage: scripts/campaign-directory.py <campaign issue number or slug> [start]

`start` is where the base root is resolved from, defaulting to the working
directory; a caller already holding `$BASE` passes it.
"""
import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "check-campaign-claim.py"


def load_guard():
    """(module, None) or (None, why). The guard is imported for one function and
    never run: it is a PreToolUse hook and reads a payload on stdin."""
    try:
        spec = importlib.util.spec_from_loader(
            "guard", importlib.machinery.SourceFileLoader("guard", str(GUARD)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:                      # noqa: BLE001 -- any of them
        return None, f"{GUARD}: {e.__class__.__name__}: {e}"
    return module, None


def resolve(token, start):
    """(the word, the sentence beside it)."""
    guard, why = load_guard()
    if guard is None:
        return "unknown", f"the marker reader would not load ({why})"
    try:
        # NO BASE ROOT AT ALL IS NOT AN EMPTY SET, which is `known_slugs`'s
        # distinction in the guard beside this one. With no base above `start`
        # -- a path outside every base, or a checkout git will not name -- there
        # was nowhere to look, and answering `none` there sends `opening-campaign`
        # on to scaffold a second directory for a campaign that already has one.
        roots = guard.base_roots_for(Path(start))
        if not roots:
            return "unknown", (f"no base root above {start}, so there was "
                               f"nowhere to look for a campaign directory")
        found = sorted({d.resolve() for d, fields
                        in guard.campaign_dirs_at(start)
                        if token in (fields[0], fields[1])})
    except OSError as e:
        return "unknown", (f"the base roots above {start} would not be read "
                           f"({e.__class__.__name__})")
    if not found:
        return "none", (f"no directory above {start} carries a .campaign "
                        f"marker naming {token}")
    if len(found) > 1:
        return "unknown", ("two directories name that campaign, so which one is "
                           "meant is not a reading: "
                           + ", ".join(str(p) for p in found))
    return str(found[0]), f"read from {found[0]}/.campaign"


def main(argv) -> int:
    if not (1 <= len(argv) <= 2):
        print("unknown")
        print("usage: campaign-directory.py <campaign issue number or slug> "
              "[start]", file=sys.stderr)
        return 2
    start = Path(argv[1]) if len(argv) == 2 else Path(os.getcwd())
    word, note = resolve(argv[0], start)
    # THE WORD ALONE ON STDOUT, and the sentence beside it on stderr whatever
    # the answer: every caller here is `CAMPAIGN_DIR=$(campaign-directory.py
    # ...)`, and a note on stdout would land inside the path.
    print(word)
    print(f"campaign-directory: {note}", file=sys.stderr)
    return {"none": 1, "unknown": 2}.get(word, 0)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:                      # noqa: BLE001 -- answered, not raised
        print("unknown")
        print(f"campaign-directory: the reader raised "
              f"{e.__class__.__name__}: {e}", file=sys.stderr)
        sys.exit(2)
