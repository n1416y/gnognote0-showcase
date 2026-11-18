# G0 case study: offline preparedness knowledge

G0 is the project's concrete public-benefit thread: a searchable, portable knowledge package focused on hurricane preparedness and resilience. Its engineering priorities include offline access, understandable source context, and visible limits around what stored metadata can and cannot establish.

## A useful local improvement

In a recent bounded development demonstration, the local work loop identified that readers could not filter the package by its saved source-review marker. It selected and completed a narrow change: add a filter for recorded review states, while labeling that state as information from the package rather than a live source check.

The resulting candidate was checked for package integrity, local links, browser behavior, syntax, and focused regressions. The checks were performed locally against the candidate package. The source review labels do not guarantee that an underlying public source is current, complete, or authoritative today.

## Why the boundary matters

Preparedness information can be time-sensitive. An offline copy can improve access during connectivity interruptions, but it can also become stale. Readers need provenance and recency context, and the tool must not imply that a saved review date is a current verification.

The candidate is engineering evidence, not formal G0 acceptance, an independent usefulness evaluation, or a deployed service. Continued rights review, independent evaluation, and release readiness remain separate work.
