# Result-library deployed-source synchronization

## Scope

This branch is based only on upstream `de9ff0d0fc5399dffabbb4d7d2a48d263c942d14`.
It carries the already-reviewed/deployed result library and its required approved
major-village title/member-access prerequisites. It does not merge the live
server's unrelated unpublished history or copy its unrelated dirty overlays.

The protected `index.html` retains the exact deployed/browser-tested SHA-256:
`94be5592d0bb97f7c0646f943e1e7902351d4f7c0b0a63793e18e4b5c932539d`.
Question/scorer/artwork pins remain those of the original independent review.
The review ledger is retained byte-for-byte so tests do not require an
unpublished `f95a7c7` Git object. No immutable expected digest was regenerated.

## Shared shell/config integration

Only the previously approved exploration menu/title/member entry, parent-result
link and layer include are applied to upstream `templates/base.html`.
Other live NEWS, reading-label and branding overlays are deliberately not
introduced without their own source/dependency reconciliation. `config.py`
changes only the scoped member-interest gate/default and its already-approved
production value; it is not copied from the dirty live server.

The two live-shell HTML fixtures preserve reduced-shell regression coverage of
the exact earlier deployed shell overlay. They are fixtures, not the upstream
runtime base template.

## Prevent a destructive ordinary deployment

The workflow now runs `scripts/verify_reset_deploy.py` before staged dependency
installation and again immediately before `git reset --hard`. It rejects:

- unpublished or divergent live commits;
- existing staged changes;
- dirty live source that differs from the exact target Git blob;
- conflicting new-file paths, including ignored files that the target tracks.

Exact already-installed target bytes may be adopted without rewriting their
content. The guard is read-only, does not boot Flask or inspect operational DBs,
and does not mutate refs/index/files. It is a fail-closed source/history check,
not a replacement for full writer-drain or database-preservation release gates.

## Publication and live state

Publish this synchronization commit with `[skip ci]`: this request synchronizes
source, not another service restart, migration or content release. Verify the
remote SHA and the absence of a deployment workflow for that exact SHA.

The earlier deployed source overlay remains active. Other independently deployed
live features still have their own unsynchronized commits/dirty files; this
sync does **not** establish that a whole-tree reset-based release is safe. The
new guard intentionally blocks such a reset until those changes are reconciled.
Do not bypass the guard, reset the live tree or include unrelated source to
make it pass. No production account, student record, preference or notice is
changed by this synchronization.

See `source-provenance.json` for original reviewed/deployed bindings. Test logs,
JUnit and the final remote/server readback are recorded in the local task report
folder and are not substitutes for an Actions deployment (which is skipped).
