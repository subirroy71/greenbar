# Greenbar rules (Cursor / Windsurf / Cline)

Paste into your rules file (`.cursorrules`, `.windsurfrules`, or a Cline custom mode).

- For any non-trivial change, first write `contracts/<id>.md` with full Greenbar frontmatter
  (goal, tier, non_goals, binary acceptance, quality_axes with behavioral must_have KPIs).
- Run `greenbar lint contracts/<id>.md` and fix all errors **before** writing code.
- Implement tests-first against the acceptance criteria.
- Before proposing the change as done, run `greenbar gate <tier> --contract contracts/<id>.md`
  and fold every failure. Do not present a change as complete if a required gate is red.
- Never mark an `hitl:` item (merge/release/spend/external comms) done yourself — surface it.
- An asserted quality axis without a behavioral KPI is not allowed — defer it or add the KPI.
