# Daily update workflow

A Codex scheduled follow-up is active for **8:00 PM America/Chicago**. It reviews the newest verified local baseline and publishes only when it finds new, meaningful, evidence-backed progress. The initial manual check found no new approved progress, so it skipped publication.

## What the updater does

- Reads the private local development source and its newest numbered baseline candidate.
- Verifies that candidate with the configured local verifier. If the newest baseline fails or its authority locks change, it stops; it never falls back to an older candidate.
- Compares new evidence with the public log and status. Any proposed entry must be supported by an exact evidence file and hash bound by the verified baseline.
- Uses a narrow public vocabulary for offline-knowledge improvements, bounded local engineering outcomes, and directly relevant local evaluation. It distinguishes local and synthetic checks from formal acceptance, independent evaluation, deployment, and elapsed-time reliability evidence.
- Runs deterministic privacy checks and updates only the development log and the marked status summary. It never publishes raw manifests, checkpoint reports, source code, private ledgers, operational configuration, credentials, personal paths, or protected narrative material.
- Uses event markers and a one-run-per-local-day audit guard to prevent duplicate entries. If there is no meaningful new progress, it publishes nothing.
- Keeps a local, append-only, mode-restricted audit. The audit contains no source text, credentials, or private paths.

The policy example in `config/` is intentionally incomplete. The active policy and audit remain local-only files and are ignored by Git.

## Publishing controls

The owner approved public visibility and the daily publishing scope. The scheduled follow-up uses the connected GitHub app to update only approved files on the showcase's `main` branch, with the current file SHA as a write guard. It does not send Git credentials through command-line arguments, environment variables, tracked files, or logs.

A new update must be genuinely meaningful, tied to exact evidence in the verified baseline, and pass the local privacy checks before publication. The schedule does not manufacture daily filler. LinkedIn remains a draft-only channel.

A failed baseline, unsafe text, unexpected repository state, or stale write guard stops publication and preserves the last known-good public state.

## Local verification

Run the deterministic test suite with:

```text
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/daily_update.py tests/test_daily_update.py
```

The seven tests cover meaningful progress, no-change days, injected private content, interrupted publication recovery, duplicate prevention, and disabled publishing. They use temporary fixtures and a local bare Git repository; they do not publish to GitHub.

## Operational status

The scheduled follow-up is active at the time above. A direct no-change check verified the current source baseline and found no new approved entry, so no public update was created. The native macOS LaunchAgent fallback remains disabled; the scheduled follow-up handles publication through the connected GitHub app. No LinkedIn post has been published. The workflow is limited to this public showcase and cannot modify production systems or other public channels.
