<!-- Greenbar dogfoods itself — a PR here should pass its own gates. -->

## What & why
<!-- one or two lines -->

## Contract
- [ ] This change has a contract in `contracts/` (or updates one) and `greenbar lint` passes
- Tier: <!-- trivial / scoped / critical — or run `greenbar classify` -->

## Gates
- [ ] `greenbar gate <tier> --contract contracts/<id>.md` is green locally
- [ ] Tests added/updated (a failing test first, then the code)
- [ ] For a `critical` change: a `greenbar review` record is attached / the `review` gate passes

## Notes
<!-- deferrals, follow-ups, anything a reviewer should trace against the real code -->
