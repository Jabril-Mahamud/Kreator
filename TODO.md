# Kreator TODO

## Phase 5 complete (2026-06-14)

All five build phases are done. See CLAUDE.md for the full phase checklist.

## Next priorities (JobHunterApp-driven)

- [x] **GitHub Actions CI for Kreator itself.** Tests + lint on push/PR via `.github/workflows/ci.yml`, with a 3.12/3.13 test matrix and a separate lint job.
- [x] **Verify Express and Go backends end-to-end.** Both went through `kreator init`, a Docker build, and a runtime check against a real Postgres (2026-06-20): `/healthz` returns 200 and register/login round-trips work. See the Phase 4 note in CLAUDE.md.
- [ ] **OAuth template support.** Snowfall (social bookmarking) needs OAuth for Twitter/Instagram/etc. Add an optional OAuth module to the backend templates.
- [ ] **AWS provider.** In progress (2026-07-18). Done: `provider: aws` in kreator.yaml/init, `kreator deploy` provider dispatch with `--aws-credentials-file`, upbound provider-family-aws + provider-aws-s3 install, `xbuckets.kreator.dev` XRD, aws bucket composition and claim, unit tests. Left: RDS composition (swap the database claim onto AWS), VPC, EKS (until then aws deploy provisions infra only, no app deploy), region shorthand naming, local bucket composition for `kreator dev`.
- [ ] **Live demo deployment.** Deploy JobHunterApp to Civo via `kreator deploy` and link it in the README. A running app is worth more than any README.
- [ ] **PyPI publishing.** `pip install kreator` instead of `pip install -e .`. Version bump automation.
