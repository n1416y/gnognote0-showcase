# Daily update workflow

The local macOS LaunchAgent is installed and active for **8:00 PM America/Chicago**. Its initial run verified the current local baseline and skipped publication because there was no new approved progress to post.

## What the updater does

- Reads a private local policy file kept outside this repository. That policy points to the source project, the newest numbered baseline candidate, the source verifier, and curator-approved public update entries.
- Verifies the newest candidate using the configured local verifier. If the newest baseline fails or its authority locks change, it stops; it never falls back to an older candidate.
- Checks that each approved entry refers to an exact evidence file and hash bound by the verified baseline. It does not copy or summarize the evidence itself.
- Publishes only text in the policy allowlist, after a deterministic privacy check. It writes only the development log and the marked status summary. No new disclosure category can be added by generated prose.
- Uses an event marker and one-run-per-local-day audit guard to avoid duplicate entries. The calendar trigger and run-at-load behavior support a catch-up attempt after a missed run or wake; the per-day guard makes repeated triggers harmless.
- Keeps a local, append-only, mode-restricted audit of checks and outcomes. The audit contains no source text, credentials, or private paths.

The policy example in `config/` is intentionally incomplete. The active policy and audit remain local-only files and are ignored by Git.

## Publishing controls

The owner approved public visibility and this daily publishing scope. The workflow accepts only the expected showcase remote, the `main` branch, a clean or exactly generated worktree, and the two output paths in its code allowlist. It uses the machine's existing Git credential helper; credentials never enter arguments, environment variables, tracked files, or logs.

The current policy contains only the already-published, evidence-bound offline-filter update, so the next run will publish nothing unless a new meaningful update is added. No-change days create no public post. The updater does not draft new prose from arbitrary private records: new entries must be curated from exact, verified evidence and added to the local allowlist. This keeps public copy bounded, though it means content discovery and curation are not yet fully unattended.

A failed baseline, unsafe generated text, unexpected file change, remote mismatch, or non-fast-forward push stops the run. Recovery is idempotent: a locally committed update interrupted before push can be pushed on the next run without creating a second entry.

## Local verification

Run the deterministic test suite with:

```text
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/daily_update.py tests/test_daily_update.py
```

The tests cover meaningful progress, no-change days, injected private content, interrupted publication recovery, duplicate prevention, and disabled publishing. They use temporary fixtures and a local bare Git repository; they do not inspect the private source project or publish to GitHub.

## Operational status

The local publisher is enabled on this host at the schedule above. The no-change path has been exercised and recorded in the private audit. No LinkedIn post has been published. The workflow publishes to this public showcase only; it cannot modify the private product source, production systems, or other public channels.
