# Daily update workflow

The updater is prepared for a local macOS schedule at **8:00 PM America/Chicago**. It is not installed or enabled. The LaunchAgent template is marked `Disabled` and contains placeholders rather than machine-specific paths.

## What the updater does

- Reads a private local policy file that is kept outside this repository. That policy points to the source project, the newest numbered baseline candidate, the source verifier, and a short list of curator-approved public update entries.
- Verifies the newest candidate using the configured local verifier. If the newest baseline fails or its authority locks change, it stops; it never falls back to an older candidate.
- Checks that each approved entry refers to an exact evidence file and hash bound by the verified baseline. It does not copy or summarize the evidence itself.
- Publishes only already-approved text, after a deterministic privacy check. It writes only the development log and the marked status summary. No new disclosure category can be added by generated prose.
- Uses an event marker and one-run-per-local-day audit guard to avoid duplicate entries. `RunAtLoad` and the calendar trigger support catch-up after a missed run or wake; the per-day guard makes a repeated trigger harmless. The host-level schedule still requires installation and verification before it can be called operational.
- Keeps a local, append-only, mode-restricted audit of checks and outcomes. The audit contains no source text, credentials, or private paths.

The policy example in `config/` is intentionally incomplete. It contains placeholders, no source path, and no approved entries. The active source policy and audit are local-only files and are ignored by Git.

## Publishing controls

Publishing defaults to off. Before unattended publishing is enabled, the owner must review the initial showcase and approve the exact automation scope. Once separately approved and configured, the script accepts only the expected showcase remote, the `main` branch, a clean or exactly generated worktree, and the two output paths in its code allowlist. It uses the machine's existing Git credential helper; credentials never enter arguments, environment variables, tracked files, or logs.

A failed baseline, unsafe generated text, unexpected file change, remote mismatch, or non-fast-forward push stops the run. Recovery is idempotent: a locally committed update that was interrupted before push can be pushed on the next run without creating a second entry.

## Local verification

Run the deterministic test suite with:

```text
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/daily_update.py tests/test_daily_update.py
```

The tests cover meaningful progress, no-change days, injected private content, interrupted publication recovery, duplicate prevention, and disabled publishing. They use temporary fixtures and a local bare Git repository; they do not contact GitHub or inspect the private source project.

## Activation remains pending

No LaunchAgent has been installed, no schedule has been loaded, and no unattended push has been enabled. Public repository visibility also remains private pending owner review.
