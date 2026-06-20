# Kreator TODO

## Phase 5 complete (2026-06-14)

All five build phases are done. See CLAUDE.md for the full phase checklist.

## Next priorities (JobHunterApp-driven)

- [ ] **GitHub Actions CI for Kreator itself.** Tests + lint on push/PR. Currently only runs locally.
- [ ] **Verify Express and Go backends end-to-end.** FastAPI is battle-tested via JobHunterApp dogfooding. Express and Go templates exist but haven't been through a full `kreator dev` cycle.
- [ ] **OAuth template support.** Snowfall (social bookmarking) needs OAuth for Twitter/Instagram/etc. Add an optional OAuth module to the backend templates.
- [ ] **AWS provider.** Civo works. AWS would demonstrate broader cloud knowledge. The Crossplane abstraction makes this a Composition swap.
- [ ] **Live demo deployment.** Deploy JobHunterApp to Civo via `kreator deploy` and link it in the README. A running app is worth more than any README.
- [ ] **PyPI publishing.** `pip install kreator` instead of `pip install -e .`. Version bump automation.
