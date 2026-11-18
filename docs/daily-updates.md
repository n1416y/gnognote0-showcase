# Daily update workflow

A scheduled check runs daily at **8:00 PM America/Chicago**. It verifies the newest local development baseline and compares its newly bound evidence with the showcase.

A public update is published only when there is genuinely new, material, evidence-backed progress. On a quiet day, the workflow publishes nothing and records the skipped check privately. It never adds a no-change entry just to fill the feed. A failed baseline or privacy check also publishes nothing; the workflow never falls back to an older baseline.

## What the updater does

- Reads the private local development source and its newest numbered baseline candidate.
- Requires the configured verifier to report `PASS_LOCAL_MANIFEST`, readiness `STOP`, and execution authority `NOT_GRANTED`.
- Compares new evidence with the public log and status. A progress claim must be supported by the exact evidence file bound by the verified baseline.
- Uses a narrow public vocabulary for offline-knowledge improvements, bounded local engineering outcomes, and directly relevant local evaluation. It distinguishes local and synthetic checks from formal acceptance, independent evaluation, deployment, and elapsed-time reliability evidence.
- Runs deterministic privacy checks and updates only the development log and, when materially warranted, the marked status summary.
- Never publishes raw manifests, checkpoint reports, source code, private ledgers, operational configuration, credentials, personal paths, protected narrative material, or private hashes.
- Prevents duplicate publication and keeps a private, append-only audit of published, skipped, rejected, and failed runs without source text or public disclosure of private paths.

The policy example in `config/` is intentionally incomplete. The active policy and audit remain local-only files and are ignored by Git.

## Publishing controls

The owner approved public visibility and the daily publishing scope. The scheduled workflow uses the connected GitHub app to update only approved files on the showcase's `main` branch, with the current file SHA as a write guard. It does not place Git credentials in command-line arguments, environment variables, tracked files, or logs.

A progress update must be tied to exact evidence in the verified baseline and pass local privacy checks before publication. The workflow cannot add a new disclosure category without owner review. LinkedIn remains a draft-only channel.

A failed baseline, unsafe text, unexpected repository state, or stale write guard stops publication and preserves the last known-good public state. The workflow cannot modify the private development repository, production, cloud resources, Twitch, protected secrets, constitutional state, or Formal Genesis authority.

## Local verification

Run the deterministic test suite with:

```text
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/daily_update.py tests/test_daily_update.py
```

The seven tests cover meaningful progress, no-change days, injected private content, interrupted publication recovery, duplicate prevention, stale evidence, and disabled local publishing. They use temporary fixtures and a local bare Git repository; they do not publish to GitHub.

## Operational status

The daily scheduled check is active for the public showcase. It publishes only qualifying material progress and skips public updates otherwise. It does not publish to LinkedIn. The native macOS LaunchAgent fallback remains disabled; the scheduled check publishes through the connected GitHub app. No public update is produced when a run has nothing new to report.
