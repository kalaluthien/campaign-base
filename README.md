# campaign-base

A base for running **campaigns** — units of work across the repositories
they need — on repositories that live elsewhere.

A campaign is one assignment a person is responsible for, worked across the
repositories it needs, which may be none. It is bigger than a ticket and has no
size ceiling. It gets a directory on the machine that holds it — the
repositories it needs are assembled inside it, and its sub-issues are handed to
agents — and that directory is one machine's cache of a campaign that lives on
GitHub. When it is over the directory is deleted and nothing is lost, because
everything durable was already somewhere else.

## Shape

```
campaign-base/
  AGENTS.md CLAUDE.md README.md .gitignore    tracked here
  .claude/skills/opening-campaign
  .claude/skills/closing-campaign
  spec/  scripts/
  auth-refactor/                 a campaign, named for its slug, git-ignored
    .campaign                    the campaign issue number and the slug; what
                                 makes this directory a campaign's
    AGENTS.md CLAUDE.md          engineering principles for this campaign
    README.md                    the campaign issue body, section for section
    runtime/                     data, state and artifacts of this campaign
    scripts/                     scripts built for this campaign; scratch,
                                 listed at the close and deleted with the directory
    repos/api/  repos/web/       member repositories, each its own git repo
```

`.gitignore` is an allowlist: it ignores `/*` and re-admits only the base's
own files. Campaign directories and everything cloned into them stay untracked,
so a campaign can never be committed into the wrong repository by accident.

## Where things live

| what | lives in |
| --- | --- |
| how campaigns are run | this repository |
| the code being changed | each member repository's own remote |
| what a campaign is and how far along it is | GitHub issues |

A campaign has two names: its **campaign issue number**, which every `gh` call
is given, and its **slug**, which every name a person reads is built from — the
session names, the claim branches, the directory. The slug lives on the campaign
issue as a `campaign:<slug>` label, so one reader finds it and no two campaigns
can share one.

A campaign's identity is its **campaign issue** in this repository. Sub-issues are
issues in this repository too, whichever repository their code lives in — each
filed as a sub-issue of that campaign issue, and the link the creating command
makes is the whole index; a member repository receives only branches and pull
requests. That makes
GitHub the single record: a campaign can move from one machine to another, and a
phone can read it, without anything local having to agree. It runs on one
machine at a time, and one `bound:<machine>` label on the campaign issue says which.

## Setup

Git hooks do not clone, so run the installer once per clone:

```sh
scripts/install-hooks.sh
```

It installs the `pre-commit` that chains the machine-wide no-commits-on-`main`
guard with this repository's own guards (the `# runs:` line the installer
writes is the one list), the `post-commit` that pushes a campaign branch on
its first commit, and the harness claim guard in `~/.claude/settings.json`. It
refuses rather than overwrites a hook it did not write, with one exception it
announces: the shim `acquire-repo.sh` leaves in a clone, in either of its two
shapes, which it adopts because the hook it writes runs the same guard and the
same claim gate.

A delegate clone gets its hooks from `acquire-repo.sh`. Where the repository
ships this installer, that means running it with `--git-only`; where it ships
none -- which is every member repository -- `acquire-repo.sh` writes the shim
itself, and since #190 that shim carries the claim gate by its absolute path in
the base, because the clone has no `scripts/` of its own to reach it through.

The harness claim guard is registered from one checkout for every session on
the machine, so a clone must not repoint it at itself; `--git-only` is how a
second checkout installs the git hooks alone.

Requires `git`, `gh` (authenticated), `herdr`, `uv`, and Python 3.

## Reading order

`AGENTS.md` for the rules. `spec/campaign/github/system.als` for why they are
those rules, what was rejected, and which risks are still open — it is the entry
point to `spec/`, which is Alloy models with an HTML diagram allowed beside one;
each model's comments carry the part of the spec it checks. `spec/campaign/` is
one module in five entities, each `open`ing the one below — `github`,
`directory`, `synchronization`, `session`, `orchestration` — so the top one is
the whole composed model. Each entity is three files: `system.als` is the
signatures, events and trace, `scenarios.als` the witnesses, `checks.als` the
assertions. `spec/campaign/diagram.html` for the shape of all of it, and
`spec/campaign/orchestration/system.als` for how a campaign session and its
agents talk.
