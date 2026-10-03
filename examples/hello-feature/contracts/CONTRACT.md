---
id: hello-feature
goal: "Add a /health endpoint · measurable: GET /health returns 200 {status:ok} · constraint: no auth, <5ms."
tier: scoped
non_goals:
  - "readiness/liveness split (just a basic health check)"
acceptance:
  - { id: A1, must: "GET /health returns HTTP 200" }
  - { id: A2, must: "the body is exactly {\"status\":\"ok\"}" }
quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1 and A2 pass" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "endpoint never 500s, even under a malformed request" }
hitl: ["merge to main"]
---
# Hello feature

The smallest possible real contract — copy it, change the frontmatter, and run
`greenbar lint contracts/CONTRACT.md` then `greenbar gate scoped --contract contracts/CONTRACT.md`.
