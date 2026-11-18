# Autonomy and governance

The design goal is purposeful, bounded autonomy: a system should sometimes act without a person spelling out every step, while still making its authority, evidence, and failure behavior inspectable.

## A governed loop

1. **Notice a gap.** Use an approved source of work and a verified baseline.
2. **Form a small task.** State the expected result, constraints, dependencies, and resource ceiling.
3. **Decide independently.** A policy governor can approve only predefined, low-risk local capabilities. Unclear or out-of-scope work is deferred or rejected.
4. **Execute in a boundary.** Work is isolated, reversible where possible, and does not gain authority from user or audience text.
5. **Evaluate and record.** Preserve a durable account of the choice, work performed, checks, and outcome.
6. **Continue or stop.** Recovery must not repeat work or bypass a failed check.

## What this does not mean

A synthetic exercise is not proof of real-world autonomy. A task runner is not evidence that every candidate task is useful. Passing tests does not imply product acceptance. External actions, public interaction, and consequential changes require their own authorization and verification.

Codex is used as an AI-assisted engineering tool under human direction. That is different from gnognote0's intended autonomous runtime, which remains an experimental system under development.
