# Engineering journey

gnognote0 is being built as an evolving experiment rather than a one-shot model demo. The work has explored durable task records, interrupted-work recovery, policy-bounded action, offline packaging, evidence capture, and evaluation that can distinguish a local pass from a stronger acceptance claim.

Several design lessons are shaping the project:

- **Make the boundary visible.** Separate what the system may consider from what it may execute.
- **Keep evidence close to the claim.** A result should point to the exact candidate and checks behind it.
- **Make recovery boring.** Restart behavior should be deterministic and duplicate-safe.
- **Preserve history honestly.** New versions should carry forward known gaps rather than rewriting predecessor evidence.
- **Treat local success as local.** Browser or unit-test evidence does not substitute for independent assessment, elapsed-time operation, or release approval.
- **Choose useful work over activity.** The strongest milestone is a real task with inspectable value, not another pile of test output.

Development uses AI-assisted coding tools, including Codex, directed by a human product owner. That collaboration is part of the engineering process; it should not be confused with an independently operating deployed product.
