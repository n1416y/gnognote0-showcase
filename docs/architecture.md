# Architecture at a glance

The diagram shows the development model being explored. It is a conceptual overview, not a deployed system diagram.

```mermaid
flowchart LR
  Sources[Curated public-interest source material] --> Package[Offline knowledge package]
  Package --> Search[Search and review experience]
  Search --> Person[Reader inspects information and provenance]

  subgraph Agent[Bounded autonomous-work experiment]
    Discovery[Identify candidate work] --> Governor[Policy and resource check]
    Governor -->|eligible| Sandbox[Isolated local execution]
    Governor -->|defer or reject| Record[Durable decision record]
    Sandbox --> Evaluation[Independent checks and outcome evidence]
    Evaluation --> Record
    Record --> Discovery
  end

  Evidence[Verified local baseline] --> Discovery
  Suggestions[Untrusted future audience suggestions] -. never privileged .-> Governor
  Codex[AI-assisted development tools] -. help build and test .-> Package
  Codex -. distinct from runtime .-> Agent
```

## Boundaries

- The knowledge experience can be built as a self-contained offline package; a package candidate is not the same as a formally accepted public product.
- Work discovery and policy checks are separate from execution. A request or suggestion cannot grant capabilities.
- Execution experiments are local and bounded. External providers, public interaction, and production operations are outside the claims made here.
- Evidence records distinguish a successful local check from independent evaluation or formal acceptance.
