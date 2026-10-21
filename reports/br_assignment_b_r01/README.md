# B-R01 / F7 isolated rehearsal checkpoint

**Status: B_R01_PARTIAL_NOT_FULL_ACCEPTANCE. This is not a production rollout or full acceptance.**

This change tracks the independent sidecar schema at `app/services/p3_assignment_schema.py` and preserves byte-exact snapshots of the five external rehearsal files, their source/gate/library manifests, approval-history documents, and selected raw evidence. It does not wire application routes, enable a feature flag, register the schema on application metadata, create a migration, or change existing business logic.

## Verified live run

- Final checkpoint: `br_assignment/evidence/d33c55cd19214d4ea7fb8b00c1e37e20_checkpoint.json`.
- Final raw log: `br_assignment/evidence/95_final_frozen_regression.log`.
- Verified summary: `br_assignment/evidence/97_final_verified_checkpoint_summary.json`.
- 39 scoped tests passed, execution exit 0; 38 NEW owners; 386 measured DBAPI connections; unexpected audit denials empty.
- 110 enumerated constraint-negative cases, independent expectations for 14 trigger SQL definitions, and an actual Windows junction create/reject/cleanup probe passed.
- The final same-live-run child returned READBACK_PASS: all 23 tables' schema and rows matched, FK check empty, integrity ok, DB bytes unchanged.
- F7 uses the parent runner's direct stdin pipe, a parent in-memory one-use registry, child challenge/PID binding, exact source/schema/identity/DB hashes, sanitized environment, and closed writers. The child rejects checkpoint CLI input, reused/stale capabilities, mismatches, writes, DDL, other DB connections, and other processes.
- New behavior RED/GREEN logs are preserved. Added existing-behavior matrices are regression evidence, not retrospective RED claims.

## Remaining acceptance criteria

- Setup reference REPLACE evidence is layered: 4 trigger refusals and 12 CASCADE-authorizer refusals, not 16 unmasked trigger proofs.
- Complete independent per-edge FK/RESTRICT proof is still partial: lineage/immutable triggers mask some constraints. Independent FK12 and notification RESTRICT1 are proven; guards were not weakened to manufacture other proofs.
- Three frozen execution orders and B-R02 through B-R10 are not completed.
- Full independent runtime acceptance review and overall closeout remain outstanding. A commit review is not that acceptance review.
- Historical C2A strict-TDD PARTIAL and symlink SKIP remain unchanged. The junction result does not supersede the symlink SKIP.

## Archive, not a relocated executable distribution

The archived runner/loader/test/readback files retain their original absolute paths, original external evidence-root assumptions, approved exact-source allowlists, and original hashes. They are evidence snapshots, **not portable entrypoints for this repository or this branch**. Do not execute them from this archive or loosen their guards to make them run. Relocation, a new source manifest, or a portable test runner requires its own reviewed scope. The verified run was performed against the original approved local source tree, not against this archival branch's older remote base.

No SQLite DB, owner sentinel/token, credentials, real user data, uploads, or production artifacts are included. Rows represented in checkpoint JSON are synthetic fixtures only. No normal application/bootstrap, provider, Push, browser, server, production DB, migration, or legacy reset/delete execution is claimed.

## Evidence history

All copied evidence retains its original result, including failed attempts. In particular, old checkpoint-based readback evidence is NOT F7-compliant; log91 is the second-notification selection regression; log94 is an environment-preflight failure; log95 is the final successful frozen run. The final setup probe selects fixed known fixture IDs with `.one()`, never `.first()`.

`archive_manifest.json` records original SHA256 values. The local `.gitattributes` disables text conversion only within this archive so evidence remains byte-exact. This branch is based on remote master and intentionally excludes unrelated local commits, tracked changes, and untracked files.
