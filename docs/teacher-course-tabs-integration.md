# Teacher course status tabs — scoped upstream integration

This synchronizes only the already-deployed teacher course-tabs feature onto upstream `3eabee1560d11d9a5560ee2fb1fdae8b5a2a822a`. It does not copy the live shared routes file wholesale or synchronize other unmerged overlays.

Runtime scope: `app/teacher/routes.py` (only `courses()` status normalization) and `templates/teacher/courses.html`. Carry the isolated real-blueprint/ORM/browser tests and runner under `tests/teacher_course_tabs/`.

## Verification

- Upstream worktree focused runner: 52 passed, 0 failures/errors/skips; 1545 inherited datetime.utcnow deprecation warnings. Real blueprint/ORM and Chromium 156.0.8078.4, synthetic persistence, reduced base shell.
- Authenticated production walkthrough through administrator-supported teacher impersonation: default active, active/completed/cancelled tab clicks, no-match search, reset within completed, weekday sort on a populated list, completed reload, blank/invalid status normalization. 390px mobile DOM measurement: scroll width 390, all three tabs present. No course/attendance/enrollment mutation was submitted. Login/account switching may create ordinary session/audit activity.
- Live UI evidence JSON is stored outside Git under deployment/resume-20261124/live-browser. Initial browser checks were corrected to await navigation and sort only populated lists; production code was not changed. A later screenshot attempt was blank and is not visual acceptance evidence; the attempted admin-return route led to login, then the validation tab was parked at about:blank. No teacher impersonation tab was left active.
- Source-only commit uses `[skip ci]` because normal master deployment performs migration and a service restart, which are not part of this integration. Verify remote exact SHA and zero workflow runs independently after push; skipped CI is not a passing CI run.

## Existing deployed receipt

`/home/chsh82/momoai-release-backups/exploration-member-17fj0vys/receipt.json`
SHA-256: `0e0b68a8b7c225801dde076be81480d9c968fd84087330f823e4b25fb1dfba76`

Installed raw SHA-256:
- routes: `ab418ecd727d3e9a0f53a30ae9d34904106a9196f822f9e47c4acae68a86647b`
- template: `605dc29a225211f27cb818c1d16d01ac3199da562086cf0ca47259cec1e0ee9c`

The upstream shared routes file intentionally differs from the full live file: unrelated live overlays remain out of scope. Its courses function and course template must match the deployed feature semantically. The live Git HEAD remains its existing commit; do not reset or restart production to align metadata. Whole-tree automatic deployment is not certified by this scoped synchronization.
